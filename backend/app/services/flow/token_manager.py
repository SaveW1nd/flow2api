"""ST -> AT(access token)管理器。

Google Labs FX 的鉴权用一个 `__Secure-next-auth.session-token`(ST,长期有效)cookie,
通过 HTTP GET `labs.google/fx/api/auth/session` 即可换出 `ya29` access token(AT,约 1h)
以及账号邮箱、过期时间。本模块负责:

- 纯 HTTP 用 ST 换 AT(curl_cffi 模拟 Chrome TLS 指纹,降低风控);
- 进程内缓存 AT,临近过期(默认提前 120s)自动刷新;
- 暴露同步入口,供 Celery worker 调用。

相比"浏览器抓 bearer",这套更稳、更快、可水平扩展(无需登录态浏览器即可刷新 AT)。
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from app.services.flow import protocol as P

try:  # Chrome TLS 指纹
    from curl_cffi import requests as _curl_requests  # type: ignore
except Exception:  # noqa: BLE001
    _curl_requests = None

import httpx

_REFRESH_MARGIN = 120  # 提前刷新秒数
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class TokenError(Exception):
    def __init__(self, message: str, *, kind: str = "auth"):
        super().__init__(message)
        self.kind = kind


@dataclass
class AccessToken:
    token: str
    expires_at: float  # epoch seconds
    email: str | None = None

    @property
    def valid(self) -> bool:
        return bool(self.token) and (self.expires_at - _REFRESH_MARGIN) > time.time()


_cache: dict[str, AccessToken] = {}
_lock = threading.Lock()


def _parse_expires(expires: str | None) -> float:
    if not expires:
        return time.time() + 1800
    try:
        iso = expires.replace("Z", "+00:00")
        return datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp()
    except Exception:  # noqa: BLE001
        return time.time() + 1800


def _fetch_once(session_token: str, impersonate: str, proxy: str | None) -> tuple[dict, int]:
    """单次 GET 拉 session,不做语义判断。返回 (parsed_data, http_status)。"""
    from app.services.flow.proxy import curl_proxies

    headers = {
        "Cookie": f"{P.SESSION_COOKIE_NAME}={session_token}",
        "Content-Type": "application/json",
        "User-Agent": _UA,
    }
    proxies = curl_proxies(proxy)
    try:
        if _curl_requests is not None:
            s = _curl_requests.Session()
            kwargs = {"headers": headers, "timeout": 30, "impersonate": impersonate}
            if proxies:
                kwargs["proxies"] = proxies
            r = s.get(P.AUTH_SESSION_URL, **kwargs)
            text, status = r.text, r.status_code
        else:
            with httpx.Client(timeout=30, follow_redirects=True, proxy=(proxy or None)) as client:
                r = client.get(P.AUTH_SESSION_URL, headers=headers)
                text, status = r.text, r.status_code
    except Exception as exc:  # noqa: BLE001
        raise TokenError(f"ST 换 AT 网络错误: {exc}", kind="transient") from exc

    if status != 200:
        raise TokenError(f"ST 换 AT 失败 HTTP {status}", kind="auth")
    try:
        return (json.loads(text) if text else {}), status
    except json.JSONDecodeError as exc:
        raise TokenError("ST 换 AT 响应解析失败", kind="auth") from exc


def _fetch(session_token: str, impersonate: str = "chrome124", proxy: str | None = None) -> AccessToken:
    """ST 换 AT。NextAuth 的 /api/auth/session 在 AT 过期时会先返回一个已过期的 AT
    + error="ACCESS_TOKEN_REFRESH_NEEDED"(Google 那侧异步刷新),下一次同请求才返回新 AT。
    所以遇到 stale 响应时自动重试,避免上游拿过期 token 触发 401。
    """
    for attempt in range(3):
        data, _ = _fetch_once(session_token, impersonate, proxy)
        at = data.get("access_token")
        if not at:
            raise TokenError("ST 已失效或无 access_token(请更新账号 session_token)", kind="auth")

        exp = _parse_expires(data.get("expires"))
        err = data.get("error")
        stale = (err == "ACCESS_TOKEN_REFRESH_NEEDED") or (exp - _REFRESH_MARGIN <= time.time())
        if not stale:
            return AccessToken(token=at, expires_at=exp, email=(data.get("user") or {}).get("email"))

        # 给 Google 一点时间完成后台 refresh;最后一次仍 stale 才报错
        if attempt < 2:
            time.sleep(1.2)

    raise TokenError(
        f"ST 换 AT 反复返回过期 token(error={err!r}),需要重新登录该账号",
        kind="auth",
    )


def get_access_token(
    session_token: str,
    *,
    force: bool = False,
    impersonate: str = "chrome124",
    proxy: str | None = None,
) -> AccessToken:
    """返回有效 AT(命中缓存则直接返回,否则刷新)。线程安全。"""
    if not session_token:
        raise TokenError("账号缺少 session_token(ST)", kind="auth")
    key = session_token[-32:]
    if not force:
        cached = _cache.get(key)
        if cached and cached.valid:
            return cached
    with _lock:
        if not force:
            cached = _cache.get(key)
            if cached and cached.valid:
                return cached
        tok = _fetch(session_token, impersonate=impersonate, proxy=proxy)
        _cache[key] = tok
        return tok


def invalidate(session_token: str) -> None:
    _cache.pop(session_token[-32:], None)
