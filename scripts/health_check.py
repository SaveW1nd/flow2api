#!/usr/bin/env python3
"""flow2api 账号健康巡检。

对所有 status=active 的账号调 /admin/accounts/{id}/test（用 ST 换 AT 验证凭证），
- 成功：记录 email + AT 过期时间。
- 失败：写入失败原因；可选 macOS 系统通知。

每次结果落 /tmp/flow2api_health.json + 追加到 /tmp/flow2api_health.log。

用法：
  /Users/savewind/Documents/chat/server209/flow2api/backend/.venv/bin/python \
    /Users/savewind/Documents/chat/server209/flow2api/scripts/health_check.py [--notify]

适合 launchd 每 30 分钟跑（建议 1800 秒），不要太频繁避免触发 Google 风控。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

API_BASE = os.environ.get("FLOW2API_BASE", "http://127.0.0.1:18000/api/v1")
ADMIN_EMAIL = os.environ.get("FLOW2API_ADMIN_EMAIL", "admin@flow2api.com")
ADMIN_PASS = os.environ.get("FLOW2API_ADMIN_PASS", "12345678")

RESULT_JSON = "/tmp/flow2api_health.json"
LOG_PATH = "/tmp/flow2api_health.log"


def _http(method: str, path: str, *, token: str | None = None, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{API_BASE}{path}", method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read() or b"{}")
        except Exception:
            payload = {}
        raise RuntimeError(f"HTTP {e.code}: {payload.get('detail') or payload}") from None


def login() -> str:
    return _http("POST", "/auth/login", body={"email": ADMIN_EMAIL, "password": ADMIN_PASS})["access_token"]


def list_accounts(token: str) -> list[dict]:
    return _http("GET", "/admin/accounts", token=token)


def test_account(token: str, account_id: int) -> dict:
    return _http("POST", f"/admin/accounts/{account_id}/test", token=token)


def macos_notify(title: str, message: str) -> None:
    """非阻塞 macOS 系统通知；非 mac 自动跳过。"""
    try:
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], check=False, timeout=5)
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--notify", action="store_true", help="失败时发 macOS 系统通知")
    parser.add_argument("--only-active", action="store_true", default=True, help="只巡检 status=active（默认）")
    parser.add_argument("--all", dest="only_active", action="store_false", help="巡检所有账号")
    args = parser.parse_args()

    started = time.time()
    now = datetime.now(timezone.utc).isoformat()

    try:
        token = login()
        accounts = list_accounts(token)
    except Exception as e:
        msg = f"[health] login/list 失败：{e}"
        print(msg, file=sys.stderr)
        if args.notify:
            macos_notify("flow2api health 异常", "无法登录 admin API")
        return 2

    targets = [a for a in accounts if (not args.only_active) or a.get("status") == "active"]
    results: list[dict] = []
    ok_count = fail_count = 0
    for a in targets:
        aid = a["id"]
        label = a.get("label") or f"#{aid}"
        try:
            t0 = time.time()
            r = test_account(token, aid)
            dt = round(time.time() - t0, 2)
            results.append({
                "id": aid, "label": label, "email": r.get("email"),
                "ok": True, "expires_at": r.get("expires_at"), "latency_s": dt,
            })
            ok_count += 1
            print(f"✓ {label} ({r.get('email')}) AT 至 {r.get('expires_at')} [{dt}s]")
        except Exception as e:
            err = str(e)[:300]
            results.append({"id": aid, "label": label, "ok": False, "error": err})
            fail_count += 1
            print(f"✗ {label}: {err}", file=sys.stderr)

    summary = {
        "checked_at": now,
        "duration_s": round(time.time() - started, 2),
        "total": len(targets),
        "ok": ok_count,
        "fail": fail_count,
        "results": results,
    }

    try:
        with open(RESULT_JSON, "w") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        with open(LOG_PATH, "a") as f:
            f.write(f"{now} total={summary['total']} ok={ok_count} fail={fail_count}\n")
            for r in results:
                if not r["ok"]:
                    f.write(f"  ✗ #{r['id']} {r['label']}: {r.get('error')}\n")
    except Exception as e:
        print(f"[health] 写结果失败：{e}", file=sys.stderr)

    if fail_count and args.notify:
        macos_notify(
            "flow2api 账号异常",
            f"{fail_count}/{summary['total']} 失败：" + ", ".join(
                str(r["id"]) for r in results if not r["ok"]
            ),
        )

    print(f"\n汇总：{ok_count}/{summary['total']} OK，{fail_count} 失败，{summary['duration_s']}s。结果 → {RESULT_JSON}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
