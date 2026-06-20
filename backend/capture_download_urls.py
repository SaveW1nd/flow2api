"""Open Flow in the logged-in Chrome profile and capture download-related URLs.

Use this to click the 1080P download option manually, then press Enter in the
terminal. The script prints URLs observed via Chrome DevTools Protocol.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

import websockets

from app.services.flow.proxy import browser_args

CHROME_CANDIDATES = [
    os.environ.get("FLOW_CHROME_PATH", ""),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]


def resolve_chrome() -> str:
    for candidate in CHROME_CANDIDATES:
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit("Chrome not found. Set FLOW_CHROME_PATH to chrome.exe.")


def wait_json(url: str, timeout: int = 20):
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


async def cdp_call(ws, msg_id: int, method: str, params: dict | None = None):
    await ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(await ws.recv())
        if msg.get("id") == msg_id:
            if "error" in msg:
                raise RuntimeError(f"CDP {method} failed: {msg['error']}")
            return msg.get("result", {})


async def capture(port: int, out_path: Path):
    urls: list[dict] = []
    ws_url = pick_page_ws(port)
    async with websockets.connect(ws_url, max_size=16 * 1024 * 1024) as ws:
        await cdp_call(ws, 1, "Network.enable")
        print("Capture is active. Click the 1080P download option in Chrome.")
        print("Press Enter here after the download menu/request has fired...")

        async def reader():
            while True:
                msg = json.loads(await ws.recv())
                method = msg.get("method")
                params = msg.get("params") or {}
                if method in ("Network.requestWillBeSent", "Network.responseReceived"):
                    req = params.get("request") or {}
                    resp = params.get("response") or {}
                    url = req.get("url") or resp.get("url") or ""
                    if any(s in url.lower() for s in ["download", "media", "video", "flow-content", "bigstore"]):
                        item = {
                            "kind": method,
                            "url": url,
                            "status": resp.get("status"),
                            "headers": resp.get("headers") if resp else req.get("headers"),
                        }
                        urls.append(item)
                        print(item["kind"], item.get("status"), item["url"][:240])

        task = asyncio.create_task(reader())
        await asyncio.to_thread(input)
        task.cancel()
    out_path.write_text(json.dumps(urls, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(urls)} captured events to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--proxy", default="")
    parser.add_argument("--port", type=int, default=9444)
    parser.add_argument(
        "--profile-dir",
        default=r"C:\Users\Administrator\Desktop\flow2api\flow_cookie_profile_167_full",
    )
    parser.add_argument("--out", default="download_capture.json")
    args = parser.parse_args()

    chrome = resolve_chrome()
    profile_dir = Path(args.profile_dir).resolve()
    proxy_args, proxy_ext = browser_args(args.proxy)
    url = f"https://labs.google/fx/tools/flow/project/{args.project_id}"
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
    proc = subprocess.Popen(cmd)
    _ = (proc, proxy_ext)
    wait_json(f"http://127.0.0.1:{args.port}/json/version")
    asyncio.run(capture(args.port, Path(args.out).resolve()))


if __name__ == "__main__":
    main()
