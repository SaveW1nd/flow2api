#!/usr/bin/env python3
"""
flow2api 账号 cookie 自动刷新脚本。

从本机 Chrome 读 labs.google + .google.com 关键 cookie，写入 flow2api 账号。
依赖：browser_cookie3（装在 flow2api/backend/.venv）。

用法：
  /Users/savewind/Documents/chat/server209/flow2api/backend/.venv/bin/python \
    /Users/savewind/Documents/chat/server209/flow2api/scripts/refresh_cookies.py

适合 launchd / cron 周期跑（建议每 6 小时）。
保活前提：浏览器里至少每 6~12 小时打开一次 https://labs.google/fx/tools/flow（让 Labs 续期 cookie）。
"""
import json
import sys
import urllib.request

import browser_cookie3

API_BASE = "http://127.0.0.1:18000/api/v1"
ADMIN_EMAIL = "admin@flow2api.com"
ADMIN_PASS = "12345678"
ACCOUNT_ID = 1

CORE_GOOGLE = [
    "__Secure-1PSID", "__Secure-3PSID", "SAPISID",
    "__Secure-1PAPISID", "__Secure-3PAPISID",
    "SID", "HSID", "SSID", "APISID", "NID",
    "__Secure-1PSIDTS", "__Secure-3PSIDTS",
    "__Secure-1PSIDCC", "__Secure-3PSIDCC", "AEC",
]


def _post(path, body, token=None):
    req = urllib.request.Request(
        f"{API_BASE}{path}", method="POST" if path.endswith("login") else "PATCH",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def read_chrome_cookies():
    session_token = None
    for c in browser_cookie3.chrome(domain_name="labs.google"):
        if "session-token" in c.name:
            session_token = c.value
            break
    if not session_token:
        raise SystemExit("✗ Chrome 里没找到 labs.google 的 session-token——请在浏览器登录 https://labs.google/fx/tools/flow")

    seen, gc = set(), []
    for c in browser_cookie3.chrome(domain_name=".google.com"):
        if c.name in CORE_GOOGLE and c.name not in seen:
            seen.add(c.name)
            gc.append({"name": c.name, "value": c.value, "domain": c.domain})
    return session_token, gc


def main():
    st, gc = read_chrome_cookies()
    print(f"✓ ST: {len(st)} 字符 | google_cookies: {len(gc)} 条")

    # 登录 + 写入 + 清冷却
    tok_resp = _post("/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    token = tok_resp["access_token"]
    req = urllib.request.Request(
        f"{API_BASE}/admin/accounts/{ACCOUNT_ID}", method="PATCH",
        data=json.dumps({"session_token": st, "google_cookies": json.dumps(gc), "status": "active"}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        out = json.loads(r.read())
    print(f"✓ flow2api 账号 #{ACCOUNT_ID} 已刷新 (status={out.get('status')})")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"✗ 刷新失败: {exc}", file=sys.stderr)
        sys.exit(1)
