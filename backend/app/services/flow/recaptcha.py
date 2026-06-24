"""reCAPTCHA Enterprise token Oracle(纯 HTTP 协议版)。

完整生成链路要求三个凭证:
- labs.google session token(ST):后台账号保存;
- aisandbox access token(AT/ya29):token_manager 用 ST 纯 HTTP 刷新;
- recaptcha token:本模块用 Google reCAPTCHA Enterprise anchor/reload 协议纯 HTTP 获取。

这里不启动浏览器、不使用 Chrome profile。reCAPTCHA 服务端最终评分仍由 Google 决定;
如果纯 HTTP token 被判低分,上游会返回 PUBLIC_ERROR_UNUSUAL_ACTIVITY,由 worker 重试处理。
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import socket
import string
import subprocess
import time
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from urllib.parse import urlencode
import urllib.request

from app.core.config import settings
from app.services.flow import protocol as P
from app.services.flow.proxy import browser_args, curl_proxies

try:
    from curl_cffi import requests as _curl_requests  # type: ignore
except Exception:  # noqa: BLE001
    _curl_requests = None

try:
    import websockets  # type: ignore
except Exception:  # noqa: BLE001
    websockets = None

RECAPTCHA_ORIGIN = "https://labs.google"
RECAPTCHA_CO = "aHR0cHM6Ly9sYWJzLmdvb2dsZTo0NDM."
RECAPTCHA_BASE = "https://www.google.com/recaptcha/enterprise"
RECAPTCHA_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
CHROME_CANDIDATES = [
    settings.FLOW_CHROME_PATH,
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]


@dataclass
class OracleResult:
    recaptcha_token: str
    browser_headers: dict[str, str] = field(default_factory=dict)
    bearer: str | None = None  # 兼容旧调用方;nodriver 路径不再抓 bearer


class RecaptchaError(Exception):
    pass


def _token_looks_good(tok: str | None) -> bool:
    return bool(tok and len(tok) > 500)


def _rand_cb(n: int = 12) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))


def _common_headers(*, referer: str | None = None, origin: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": RECAPTCHA_UA,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    if origin:
        headers["Origin"] = origin
    return headers


def _request(session, method: str, url: str, *, proxy: str | None = None, **kwargs):
    request_kwargs = dict(kwargs)
    request_kwargs["timeout"] = request_kwargs.get("timeout") or 30
    proxies = curl_proxies(proxy)
    if proxies:
        request_kwargs["proxies"] = proxies
    return session.request(method, url, **request_kwargs)


def _extract_version(text: str) -> str:
    match = re.search(r"/recaptcha/releases/([^/]+)/recaptcha__", text)
    if not match:
        raise RecaptchaError("无法解析 reCAPTCHA release version")
    return match.group(1)


def _parse_anchor_token(html: str) -> str:
    patterns = [
        r'id="recaptcha-token"\s+value="([^"]+)"',
        r'value="([^"]+)"\s+id="recaptcha-token"',
        r'"recaptcha-token"\s*,\s*"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return unescape(match.group(1))
    raise RecaptchaError("无法从 anchor 响应解析 recaptcha-token")


def _parse_reload_response(text: str) -> str:
    raw = re.sub(r"^\)\]\}'\s*", "", text.strip())
    try:
        arr = json.loads(raw)
        if isinstance(arr, list):
            for i, value in enumerate(arr):
                if value == "rresp" and i + 1 < len(arr) and isinstance(arr[i + 1], str):
                    return arr[i + 1]
            if len(arr) > 1 and isinstance(arr[1], str):
                return arr[1]
    except json.JSONDecodeError:
        pass
    match = re.search(r'\["rresp","([^"]+)"', raw)
    if match:
        return match.group(1)
    raise RecaptchaError("无法从 reload 响应解析 rresp token")


def _labs_cookie(session_token: str | None) -> str | None:
    if not session_token:
        return None
    return f"{P.SESSION_COOKIE_NAME}={session_token}"


def _google_cookie_header(google_cookies: str | None) -> str:
    text = (google_cookies or "").strip()
    if not text:
        return ""
    if "=" in text and not text.startswith(("[", "{")):
        return text
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text

    items: list[dict] = []
    if isinstance(data, list):
        items = [x for x in data if isinstance(x, dict)]
    elif isinstance(data, dict):
        cookies = data.get("cookies")
        if isinstance(cookies, list):
            items = [x for x in cookies if isinstance(x, dict)]
        else:
            return "; ".join(f"{k}={v}" for k, v in data.items() if isinstance(v, str) and v)

    pairs = []
    for item in items:
        name = item.get("name")
        value = item.get("value")
        domain = item.get("domain", "")
        # Browser requests to www.google.com/recaptcha only carry .google.com/www.google.com cookies.
        # Do not leak labs.google/accounts.google.com host cookies across domains; that is not browser-like.
        if name and value and domain in (".google.com", "www.google.com", ".www.google.com", ""):
            pairs.append(f"{name}={value}")
    return "; ".join(pairs)


def _merge_cookie_headers(*values: str | None) -> str:
    return "; ".join(v.strip().strip(";") for v in values if v and v.strip())


def _resolve_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        if candidate and Path(candidate).exists():
            return candidate
    raise RecaptchaError("未找到 Chrome,请设置 FLOW_CHROME_PATH")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_json(url: str, timeout: int = 25):
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.5)
    raise RecaptchaError(f"Chrome DevTools 未就绪: {last_error}")


def _pick_page_ws(port: int) -> str:
    pages = _wait_json(f"http://127.0.0.1:{port}/json", timeout=20)
    for page in pages:
        if page.get("type") == "page" and page.get("webSocketDebuggerUrl"):
            return page["webSocketDebuggerUrl"]
    raise RecaptchaError("未找到 Chrome page 调试目标")


async def _cdp_call(ws, msg_id: int, method: str, params: dict | None = None):
    await ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(await ws.recv())
        if msg.get("id") == msg_id:
            if "error" in msg:
                raise RecaptchaError(f"CDP {method} 失败: {msg['error']}")
            return msg.get("result", {})


async def _browser_execute_token(port: int, project_id: str | None, action: str, cookies: list | None = None) -> str:
    if websockets is None:
        raise RecaptchaError("缺少 websockets,无法使用官方 JS reCAPTCHA broker")
    ws_url = _pick_page_ws(port)
    async with websockets.connect(ws_url, max_size=16 * 1024 * 1024) as ws:
        await _cdp_call(ws, 1, "Page.enable")
        await _cdp_call(ws, 2, "Runtime.enable")
        if cookies:
            try:
                await _cdp_call(ws, 50, "Network.enable")
            except Exception:
                pass
            _cid = 51
            for _c in cookies:
                try:
                    await _cdp_call(ws, _cid, "Network.setCookie", _c)
                except Exception:
                    pass
                _cid += 1
        url = (
            f"https://labs.google/fx/tools/flow/project/{project_id}"
            if project_id
            else "https://labs.google/fx/tools/flow"
        )
        await _cdp_call(ws, 3, "Page.navigate", {"url": url})
        # Let Labs and reCAPTCHA scripts collect normal page signals before execute().
        await asyncio.sleep(8)
        expr = f"""
        (async () => {{
          const siteKey = {json.dumps(P.RECAPTCHA_SITE_KEY)};
          const action = {json.dumps(action)};
          if (!window.grecaptcha || !window.grecaptcha.enterprise) {{
            await new Promise((resolve, reject) => {{
              const s = document.createElement('script');
              s.src = 'https://www.google.com/recaptcha/enterprise.js?render=' + encodeURIComponent(siteKey);
              s.onload = resolve;
              s.onerror = reject;
              document.head.appendChild(s);
            }});
          }}
          await new Promise(resolve => window.grecaptcha.enterprise.ready(resolve));
          return await window.grecaptcha.enterprise.execute(siteKey, {{action}});
        }})()
        """
        result = await _cdp_call(
            ws,
            4,
            "Runtime.evaluate",
            {"expression": expr, "awaitPromise": True, "returnByValue": True},
        )
        token = ((result.get("result") or {}).get("value") or "").strip()
        if not _token_looks_good(token):
            raise RecaptchaError("官方 JS reCAPTCHA token 为空或长度异常")
        return token


def _cookies_for_cdp(session_token, google_cookies):
    out = []
    text = (google_cookies or "").strip()
    if text:
        try:
            data = json.loads(text)
            items = data if isinstance(data, list) else (data.get("cookies", []) if isinstance(data, dict) else [])
            for it in items:
                if isinstance(it, dict) and it.get("name") and it.get("value"):
                    out.append({"name": it["name"], "value": it["value"], "domain": it.get("domain") or ".google.com", "path": "/", "secure": True})
        except Exception:
            pass
    if session_token:
        out.append({"name": P.SESSION_COOKIE_NAME, "value": session_token, "domain": "labs.google", "path": "/", "secure": True, "httpOnly": True})
    return out


def _get_recaptcha_token_browser(
    *,
    profile_dir: str,
    project_id: str | None,
    action: str,
    proxy: str | None,
    session_token: str | None = None,
    google_cookies: str | None = None,
) -> OracleResult:
    chrome = _resolve_chrome()
    port = _free_port()
    profile = Path(profile_dir).resolve()
    profile.mkdir(parents=True, exist_ok=True)
    proxy_args, proxy_ext = browser_args(proxy)
    headless_args = ["--headless=new", "--disable-gpu"] if settings.FLOW_HEADLESS else []
    cmd = [
        chrome,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--remote-allow-origins=*",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        *headless_args,
        *proxy_args,
        "about:blank",
    ]
    proc = subprocess.Popen(cmd)
    try:
        _wait_json(f"http://127.0.0.1:{port}/json/version", timeout=25)
        token = asyncio.run(_browser_execute_token(port, project_id, action, _cookies_for_cdp(session_token, google_cookies)))
        return OracleResult(
            recaptcha_token=token,
            browser_headers={
                "user-agent": RECAPTCHA_UA,
                "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
    except RecaptchaError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RecaptchaError(f"官方 JS reCAPTCHA broker 获取失败: {exc}") from exc
    finally:
        _ = proxy_ext
        try:
            proc.terminate()
        except Exception:  # noqa: BLE001
            pass


def _get_recaptcha_token_http(
    *,
    session_token: str | None,
    google_cookies: str | None,
    action: str,
    proxy: str | None,
) -> OracleResult:
    if _curl_requests is None:
        raise RecaptchaError("缺少 curl_cffi,无法使用纯 HTTP reCAPTCHA 协议")

    session = _curl_requests.Session(impersonate=settings.FLOW_IMPERSONATE)
    try:
        js = _request(
            session,
            "GET",
            P.RECAPTCHA_ENTERPRISE_JS,
            proxy=proxy,
            headers=_common_headers(referer=RECAPTCHA_ORIGIN + "/"),
        )
        js.raise_for_status()
        version = _extract_version(js.text)

        anchor_qs = {
            "ar": "1",
            "k": P.RECAPTCHA_SITE_KEY,
            "co": RECAPTCHA_CO,
            "hl": "zh-CN",
            "v": version,
            "size": "invisible",
            "anchor-ms": "20000",
            "execute-ms": "30000",
            "cb": _rand_cb(),
        }
        anchor_url = f"{RECAPTCHA_BASE}/anchor?{urlencode(anchor_qs)}"
        anchor_headers = {
            **_common_headers(referer=RECAPTCHA_ORIGIN + "/"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Sec-Fetch-Dest": "iframe",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
        }
        cookie = _merge_cookie_headers(_labs_cookie(session_token), _google_cookie_header(google_cookies))
        if cookie:
            anchor_headers["Cookie"] = cookie
        anchor = _request(session, "GET", anchor_url, proxy=proxy, headers=anchor_headers)
        anchor.raise_for_status()
        challenge = _parse_anchor_token(anchor.text)

        reload_body = {
            "v": version,
            "reason": "q",
            "c": challenge,
            "k": P.RECAPTCHA_SITE_KEY,
            "co": RECAPTCHA_CO,
            "hl": "zh-CN",
            "size": "invisible",
            "sa": action,
        }
        reload_headers = {
            **_common_headers(referer=anchor_url, origin="https://www.google.com"),
            "Accept": "*/*",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        if cookie:
            reload_headers["Cookie"] = cookie
        reload_url = f"{RECAPTCHA_BASE}/reload?k={P.RECAPTCHA_SITE_KEY}"
        reload = _request(
            session,
            "POST",
            reload_url,
            proxy=proxy,
            headers=reload_headers,
            data=reload_body,
        )
        reload.raise_for_status()
        token = _parse_reload_response(reload.text)
    except RecaptchaError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RecaptchaError(f"纯 HTTP reCAPTCHA 获取失败: {exc}") from exc

    if not _token_looks_good(token):
        raise RecaptchaError("纯 HTTP reCAPTCHA token 为空或长度异常")
    return OracleResult(
        recaptcha_token=token,
        browser_headers={
            "user-agent": RECAPTCHA_UA,
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )


def get_recaptcha_token(
    profile_dir: str,
    *,
    session_token: str | None = None,
    google_cookies: str | None = None,
    project_id: str | None = None,
    proxy: str | None = None,
    action: str = P.ACTION_IMAGE,
) -> OracleResult:
    """同步入口(供 Celery worker 调用)。

    优先使用官方 JS `grecaptcha.enterprise.execute()` 获取高分 token;
    若 Chrome/CDP 不可用,回退到纯 HTTP anchor/reload(成功率较低)。
    """
    try:
        return _get_recaptcha_token_browser(
            profile_dir=profile_dir,
            project_id=project_id,
            action=action,
            proxy=proxy,
            session_token=session_token,
            google_cookies=google_cookies,
        )
    except RecaptchaError:
        return _get_recaptcha_token_http(
            session_token=session_token,
            google_cookies=google_cookies,
            action=action,
            proxy=proxy,
        )


# 兼容旧调用名
def get_token_and_bearer(profile_dir: str, action: str = P.ACTION_VIDEO) -> OracleResult:
    return get_recaptcha_token(profile_dir, action=action)
