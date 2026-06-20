"""Pure HTTP Labs session login from Google cookies.

This mirrors the NextAuth + Google OAuth flow used by labs.google:
Google cookies -> OAuth redirect chain -> labs session cookie (ST).
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

from app.core.config import settings
from app.services.flow import protocol as P
from app.services.flow.proxy import curl_proxies

try:
    from curl_cffi import requests as _curl_requests  # type: ignore
except Exception:  # noqa: BLE001
    _curl_requests = None


class SessionLoginError(Exception):
    pass


def _parse_cookie_text(raw: str | None) -> dict[str, str]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        result: dict[str, str] = {}
        for part in text.split(";"):
            name, sep, value = part.strip().partition("=")
            if sep and name and value:
                result[name] = value
        return result

    result: dict[str, str] = {}
    items: list[Any]
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and isinstance(data.get("cookies"), list):
        items = data["cookies"]
    elif isinstance(data, dict):
        return {k: v for k, v in data.items() if isinstance(v, str) and v}
    else:
        return {}
    for item in items:
        if isinstance(item, dict):
            name = item.get("name")
            value = item.get("value")
            if isinstance(name, str) and isinstance(value, str) and name and value:
                result[name] = value
    return result


def _cookie_header(cookies: dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items() if v)


def _merge_set_cookies(cookies: dict[str, str], headers) -> None:
    values = []
    if hasattr(headers, "getlist"):
        values = headers.getlist("set-cookie") or []
    elif hasattr(headers, "get_list"):
        values = headers.get_list("set-cookie") or []
    else:
        value = headers.get("set-cookie")
        if value:
            values = [value]
    for value in values:
        pair = value.split(";", 1)[0]
        name, sep, cookie_value = pair.partition("=")
        if sep and name:
            cookies[name.strip()] = cookie_value.strip()


def _extract_session_token(headers) -> str | None:
    values = []
    if hasattr(headers, "getlist"):
        values = headers.getlist("set-cookie") or []
    elif hasattr(headers, "get_list"):
        values = headers.get_list("set-cookie") or []
    else:
        value = headers.get("set-cookie")
        if value:
            values = [value]
    prefix = P.SESSION_COOKIE_NAME + "="
    for value in values:
        if value.startswith(prefix):
            return value[len(prefix) :].split(";", 1)[0].strip()
    return None


def _extract_redirect_from_html(text: str) -> str | None:
    patterns = [
        r'content\s*=\s*["\']?\d+\s*;\s*url\s*=\s*([^"\'>\s]+)',
        r'location\.(?:href|replace)\s*\(\s*["\']([^"\']+)["\']',
        r'location\s*=\s*["\']([^"\']+)["\']',
        r'<form[^>]*action\s*=\s*["\']([^"\']+)["\']',
        r'(https://labs\.google/fx/api/auth/callback/google[^"\'<>\s]*)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    match = re.search(r"[&?]continue=([^\"'<>\s&]+)", text)
    if match:
        from urllib.parse import unquote

        return unquote(match.group(1))
    return None


def protocol_login_from_google_cookies(
    google_cookies_raw: str,
    *,
    proxy: str | None = None,
    email: str | None = None,
    impersonate: str | None = None,
) -> str:
    if _curl_requests is None:
        raise SessionLoginError("缺少 curl_cffi,无法纯协议刷新 labs session token")

    google_cookies = _parse_cookie_text(google_cookies_raw)
    if not any(name in google_cookies for name in ("SID", "HSID", "SSID", "APISID", "SAPISID")):
        raise SessionLoginError("Google cookies 不完整,至少需要 SID/HSID/SSID/APISID/SAPISID 之一")

    proxies = curl_proxies(proxy)
    session = _curl_requests.Session(impersonate=impersonate or settings.FLOW_IMPERSONATE)
    try:
        req_kwargs: dict[str, Any] = {}
        if proxies:
            req_kwargs["proxies"] = proxies

        labs_cookies: dict[str, str] = {}
        csrf = session.get(f"{P.FLOW_URL.replace('/tools/flow', '')}/api/auth/csrf", timeout=30, **req_kwargs)
        csrf.raise_for_status()
        csrf_token = csrf.json().get("csrfToken")
        if not csrf_token:
            raise SessionLoginError("CSRF 响应中没有 csrfToken")
        _merge_set_cookies(labs_cookies, csrf.headers)

        signin = session.post(
            f"{P.FLOW_URL.replace('/tools/flow', '')}/api/auth/signin/google",
            data={"csrfToken": csrf_token, "callbackUrl": "https://labs.google/fx", "json": "true"},
            headers={
                "Referer": "https://labs.google/fx",
                "Origin": "https://labs.google",
                "Cookie": _cookie_header(labs_cookies),
            },
            allow_redirects=False,
            timeout=30,
            **req_kwargs,
        )
        signin.raise_for_status()
        _merge_set_cookies(labs_cookies, signin.headers)
        redirect_url = signin.json().get("redirect") or signin.json().get("url")
        if not redirect_url:
            raise SessionLoginError("signin/google 未返回 OAuth URL")

        if email:
            parsed = urlparse(redirect_url)
            qs = parse_qs(parsed.query)
            qs["login_hint"] = [email]
            redirect_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{urlencode(qs, doseq=True)}"

        callback_url = None
        current_url = redirect_url
        google_cookie_header = _cookie_header(google_cookies)
        for i in range(12):
            resp = session.get(
                current_url,
                headers={
                    "Cookie": google_cookie_header,
                    "Referer": "https://labs.google/" if i == 0 else "https://accounts.google.com/",
                },
                allow_redirects=False,
                timeout=30,
                **req_kwargs,
            )
            location = resp.headers.get("location")
            if location and "labs.google/fx/api/auth/callback/google" in location:
                callback_url = location
                break
            if location:
                current_url = location
                continue
            if resp.status_code == 200:
                body = resp.text or ""
                if "signin/rejected" in body:
                    raise SessionLoginError("Google 拒绝协议登录,cookies 可能过期或风险过高")
                extracted = _extract_redirect_from_html(body)
                if extracted:
                    current_url = urljoin(current_url, extracted)
                    if "labs.google/fx/api/auth/callback/google" in current_url:
                        callback_url = current_url
                        break
                    continue
            raise SessionLoginError(f"Google OAuth 未返回可用跳转: HTTP {resp.status_code}")

        if not callback_url:
            raise SessionLoginError("Google OAuth 流程未获得 labs callback URL")

        callback = session.get(
            callback_url,
            headers={"Cookie": _cookie_header(labs_cookies), "Referer": "https://accounts.google.com/"},
            allow_redirects=False,
            timeout=30,
            **req_kwargs,
        )
        token = _extract_session_token(callback.headers)
        for _ in range(5):
            if token:
                return token
            location = callback.headers.get("location")
            if not location:
                break
            _merge_set_cookies(labs_cookies, callback.headers)
            callback = session.get(
                location,
                headers={"Cookie": _cookie_header(labs_cookies)},
                allow_redirects=False,
                timeout=30,
                **req_kwargs,
            )
            token = _extract_session_token(callback.headers)
    except SessionLoginError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise SessionLoginError(f"纯协议刷新 labs session token 失败: {exc}") from exc

    raise SessionLoginError("callback 未返回 labs session token")
