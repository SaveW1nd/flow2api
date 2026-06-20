"""代理工具:统一给「nodriver 浏览器」与「curl_cffi HTTP」配置同一个代理。

关键约束:reCAPTCHA token 与出图/出视频请求必须从「同一出口 IP」发出,否则 Google 判
PUBLIC_ERROR_UNUSUAL_ACTIVITY。因此浏览器与 HTTP 两侧务必使用同一个代理。

带认证的代理在 Chrome 命令行 `--proxy-server=` 里无法写 user:pass,这里用一个极简的
临时扩展通过 webRequest.onAuthRequired 喂凭证(路由仍由 --proxy-server 负责,避免 MV3
设置代理的启动竞态)。
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass

_PROXY_RE = re.compile(
    r"^(?P<protocol>https?|socks5h?|socks4)://"
    r"(?:(?P<username>[^:@/]+):(?P<password>[^@/]+)@)?"
    r"(?P<host>[^:@/]+):(?P<port>\d+)/?$"
)


@dataclass
class ProxyInfo:
    protocol: str
    host: str
    port: str
    username: str | None
    password: str | None

    @property
    def url(self) -> str:
        auth = f"{self.username}:{self.password}@" if self.username else ""
        return f"{self.protocol}://{auth}{self.host}:{self.port}"

    @property
    def server_arg(self) -> str:
        scheme = "socks5" if self.protocol.startswith("socks5") else self.protocol
        return f"--proxy-server={scheme}://{self.host}:{self.port}"


def parse_proxy(proxy: str | None) -> ProxyInfo | None:
    if not proxy or not proxy.strip():
        return None
    m = _PROXY_RE.match(proxy.strip())
    if not m:
        return None
    d = m.groupdict()
    proto = d["protocol"]
    if proto == "socks5h":
        proto = "socks5"
    return ProxyInfo(
        protocol=proto,
        host=d["host"],
        port=d["port"],
        username=d.get("username"),
        password=d.get("password"),
    )


def curl_proxies(proxy: str | None) -> dict[str, str] | None:
    """返回 curl_cffi 的 proxies 字典(http/https 同一代理)。"""
    info = parse_proxy(proxy)
    if not info:
        return None
    return {"http": info.url, "https": info.url}


def make_auth_extension(info: ProxyInfo) -> str | None:
    """为带认证的代理生成临时 Chrome 扩展(仅处理 onAuthRequired)。无认证返回 None。"""
    if not info.username:
        return None
    ext_dir = tempfile.mkdtemp(prefix="flow_proxy_auth_")
    manifest = {
        "version": "1.0.0",
        "manifest_version": 3,
        "name": "Proxy Auth Helper",
        "permissions": ["webRequest", "webRequestAuthProvider"],
        "host_permissions": ["<all_urls>"],
        "background": {"service_worker": "background.js"},
        "minimum_chrome_version": "108.0.0.0",
    }
    background_js = (
        "chrome.webRequest.onAuthRequired.addListener(\n"
        "  (details, callback) => {\n"
        "    if (!details.isProxy) { callback({}); return; }\n"
        "    callback({ authCredentials: {\n"
        f"      username: {json.dumps(info.username)},\n"
        f"      password: {json.dumps(info.password or '')}\n"
        "    }});\n"
        "  },\n"
        '  {urls: ["<all_urls>"]},\n'
        "  ['asyncBlocking']\n"
        ");\n"
    )
    with open(os.path.join(ext_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    with open(os.path.join(ext_dir, "background.js"), "w", encoding="utf-8") as f:
        f.write(background_js)
    return ext_dir


def browser_args(proxy: str | None) -> tuple[list[str], str | None]:
    """返回 (chrome 启动参数列表, 临时扩展目录或 None)。"""
    info = parse_proxy(proxy)
    if not info:
        return [], None
    args = [info.server_arg]
    ext = make_auth_extension(info)
    if ext:
        args.append(f"--load-extension={ext}")
    return args, ext
