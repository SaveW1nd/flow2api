"""Open Chrome, let the user login, then export Google cookies for protocol reCAPTCHA.

Usage from repo backend directory:
    .\.venv\Scripts\python.exe export_google_cookies.py --account-id 3

The script opens a dedicated Chrome profile so it does not disturb your normal browser.
After you finish Google login in the opened browser, press Enter in the terminal. The
script exports .google.com/accounts.google.com/labs.google cookies, saves them to
google_cookies_export.json, and writes them to flow_accounts.google_cookies.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

os.environ.setdefault("POSTGRES_HOST", "127.0.0.1")
os.environ.setdefault("POSTGRES_PORT", "15432")
os.environ.setdefault("REDIS_HOST", "127.0.0.1")

from sqlalchemy import select

from app.core.db_sync import SyncSessionLocal
from app.models.flow_account import FlowAccount
from app.services.flow.proxy import browser_args

try:
    import websockets
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency 'websockets'. Run: .\\.venv\\Scripts\\pip.exe install websockets"
    ) from exc


CHROME_CANDIDATES = [
    os.environ.get("FLOW_CHROME_PATH", ""),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]

TARGET_DOMAINS = (
    ".google.com",
    "accounts.google.com",
    ".accounts.google.com",
    "www.google.com",
    ".labs.google",
    "labs.google",
)

IMPORTANT_NAMES = {
    "SID",
    "HSID",
    "SSID",
    "APISID",
    "SAPISID",
    "__Secure-1PSID",
    "__Secure-3PSID",
    "__Secure-1PAPISID",
    "__Secure-3PAPISID",
    "__Secure-1PSIDTS",
    "__Secure-3PSIDTS",
    "__Secure-next-auth.session-token",
    "_GRECAPTCHA",
}


def resolve_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit("Chrome not found. Set FLOW_CHROME_PATH to chrome.exe.")


def wait_json(url: str, timeout: int = 20) -> Any:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"Chrome DevTools not ready: {last_error}")


def pick_page_ws(port: int) -> str:
    pages = wait_json(f"http://127.0.0.1:{port}/json")
    for page in pages:
        if page.get("type") == "page" and page.get("webSocketDebuggerUrl"):
            return page["webSocketDebuggerUrl"]
    raise RuntimeError("No Chrome page target with webSocketDebuggerUrl found.")


async def cdp_call(ws, msg_id: int, method: str, params: dict | None = None) -> Any:
    await ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(await ws.recv())
        if msg.get("id") == msg_id:
            if "error" in msg:
                raise RuntimeError(f"CDP {method} failed: {msg['error']}")
            return msg.get("result")


async def read_cookies(port: int) -> list[dict[str, Any]]:
    ws_url = pick_page_ws(port)
    async with websockets.connect(ws_url, max_size=16 * 1024 * 1024) as ws:
        await cdp_call(ws, 1, "Network.enable")
        result = await cdp_call(ws, 2, "Network.getAllCookies")
        return result.get("cookies", [])


def wanted_cookie(cookie: dict[str, Any]) -> bool:
    domain = cookie.get("domain", "")
    return any(d in domain for d in TARGET_DOMAINS)


def sanitize_cookie(cookie: dict[str, Any]) -> dict[str, Any]:
    keys = ["name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"]
    return {k: cookie[k] for k in keys if k in cookie}


def _session_token_from_cookies(cookies_json: str) -> str | None:
    try:
        cookies = json.loads(cookies_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(cookies, list):
        return None
    for cookie in cookies:
        if not isinstance(cookie, dict):
            continue
        if cookie.get("name") == "__Secure-next-auth.session-token" and "labs.google" in cookie.get("domain", ""):
            value = cookie.get("value")
            return value if isinstance(value, str) and value else None
    return None


def save_to_account(account_id: int, cookies_json: str) -> None:
    db = SyncSessionLocal()
    try:
        account = db.execute(select(FlowAccount).where(FlowAccount.id == account_id)).scalar_one()
        account.google_cookies = cookies_json
        session_token = _session_token_from_cookies(cookies_json)
        if session_token:
            account.session_token = session_token
        db.commit()
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", type=int, default=3, help="flow_accounts.id to update")
    parser.add_argument("--port", type=int, default=9223)
    parser.add_argument("--profile-dir", default=str(Path.cwd().parent / "flow_cookie_profile"))
    parser.add_argument("--out", default="google_cookies_export.json")
    parser.add_argument("--import-file", default="", help="import existing cookies JSON file into database")
    parser.add_argument("--proxy", default="", help="Chrome proxy, e.g. http://user:pass@host:port")
    parser.add_argument("--no-db", action="store_true", help="only write JSON file, do not update database")
    args = parser.parse_args()

    if args.import_file:
        cookies_json = Path(args.import_file).read_text(encoding="utf-8")
        save_to_account(args.account_id, cookies_json)
        print(f"Imported cookies from {args.import_file} to account id={args.account_id}")
        return

    chrome = resolve_chrome()
    profile_dir = Path(args.profile_dir).resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)
    proxy_args, proxy_ext = browser_args(args.proxy)

    url = "https://labs.google/fx/tools/flow"
    cmd = [
        chrome,
        f"--remote-debugging-port={args.port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--remote-allow-origins=*",
        *proxy_args,
        url,
    ]
    print(f"[1/4] Starting Chrome profile: {profile_dir}")
    if args.proxy:
        print("[1/4] Chrome proxy enabled for cookie export.")
    proc = subprocess.Popen(cmd)

    try:
        wait_json(f"http://127.0.0.1:{args.port}/json/version", timeout=20)
        print("[2/4] Chrome opened. Login to Google/Labs in that browser window.")
        print("      Make sure Flow page can open normally, then return here.")
        input("Press Enter after login is complete...")

        print("[3/4] Reading cookies through Chrome DevTools...")
        all_cookies = asyncio.run(read_cookies(args.port))
        selected = [sanitize_cookie(c) for c in all_cookies if wanted_cookie(c)]
        selected.sort(key=lambda c: (c.get("domain", ""), c.get("name", "")))

        out_path = Path(args.out).resolve()
        cookies_json = json.dumps(selected, ensure_ascii=False, indent=2)
        out_path.write_text(cookies_json, encoding="utf-8")
        names = [(c.get("domain"), c.get("name")) for c in selected]
        print(f"[4/4] Exported {len(selected)} cookies to {out_path}")
        print("      Cookie names:", names)

        if not args.no_db:
            save_to_account(args.account_id, cookies_json)
            print(f"      Updated flow_accounts.google_cookies for account id={args.account_id}")

        required = {"SID", "HSID", "SSID", "APISID", "SAPISID"}
        found = {c.get("name") for c in selected}
        missing = sorted(required - found)
        if missing:
            print("[WARN] Missing classic Google cookies:", missing)
            print("       If generation still fails, export cookies from a fully logged-in Google browser.")
    finally:
        print("Chrome is left open so you can inspect it. Close it manually when done.")
        # Do not terminate proc; leaving it open lets the user verify the login state.
        _ = (proc, proxy_ext)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
