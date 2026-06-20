"""FLOW 适配层(逆向网页接口 / Token 模拟请求)。

这一层把「逆向得到的 FLOW 请求」封装为统一的 `submit_image` / `submit_video`
接口。上层(Celery 任务)只依赖这里暴露的抽象,因此当你拿到真实的 FLOW 网页
接口后,只需要在标注 `# >>> 逆向接入点` 的地方填入真实 URL / 载荷 / 解析逻辑,
无需改动业务代码。

设计要点:
- 每个 FlowAccount 携带 auth_token / cookie / extra_headers,逆向时直接复用。
- 出图通常一次请求即可拿到结果;出视频通常需要「提交 -> 轮询任务状态」。
- 所有网络异常都抛出 FlowError,由上层做账号冷却 / 重试 / 故障转移。
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings


class FlowError(Exception):
    """FLOW 上游调用失败。retryable 表示是否值得换账号/重试。"""

    def __init__(self, message: str, *, retryable: bool = True, status_code: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


@dataclass
class FlowCredential:
    account_id: int
    label: str
    auth_token: str
    cookie: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)

    def headers(self) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Flow2API)",
        }
        if self.cookie:
            h["Cookie"] = self.cookie
        h.update(self.extra_headers or {})
        return h


@dataclass
class FlowResult:
    """统一的生成结果:outputs 为远端可下载的资源 URL 列表。"""

    outputs: list[dict[str, Any]]  # [{"url": ..., "type": "image"|"video"}]
    raw: dict[str, Any] = field(default_factory=dict)


# >>> 逆向接入点:把抓包得到的 FLOW base URL 与端点填到这里
FLOW_BASE_URL = "https://flow.example.com"
FLOW_IMAGE_ENDPOINT = "/api/generate/image"
FLOW_VIDEO_SUBMIT_ENDPOINT = "/api/generate/video"
FLOW_VIDEO_STATUS_ENDPOINT = "/api/tasks/{task_id}"


class FlowClient:
    def __init__(self, credential: FlowCredential):
        self.cred = credential

    async def submit_image(self, prompt: str, params: dict[str, Any]) -> FlowResult:
        """出图:提交并直接返回结果。"""
        payload = {
            "prompt": prompt,
            "negative_prompt": params.get("negative_prompt"),
            "aspect_ratio": params.get("aspect_ratio", "1:1"),
            "num_outputs": params.get("num_outputs", 1),
            "seed": params.get("seed"),
            **params.get("extra", {}),
        }
        async with httpx.AsyncClient(timeout=settings.FLOW_REQUEST_TIMEOUT) as client:
            data = await self._post(client, FLOW_IMAGE_ENDPOINT, payload)
        # >>> 逆向接入点:根据真实响应结构解析出图片 URL 列表
        outputs = self._parse_outputs(data, default_type="image")
        return FlowResult(outputs=outputs, raw=data)

    async def submit_video(
        self,
        prompt: str,
        params: dict[str, Any],
        progress_cb=None,
    ) -> FlowResult:
        """出视频:提交 -> 轮询任务状态 -> 返回结果。"""
        payload = {
            "prompt": prompt,
            "duration": params.get("duration", 5),
            "aspect_ratio": params.get("aspect_ratio", "16:9"),
            "image_url": params.get("image_url"),
            "seed": params.get("seed"),
            **params.get("extra", {}),
        }
        async with httpx.AsyncClient(timeout=settings.FLOW_REQUEST_TIMEOUT) as client:
            submit = await self._post(client, FLOW_VIDEO_SUBMIT_ENDPOINT, payload)
            # >>> 逆向接入点:从提交响应里取出上游任务 id
            remote_task_id = submit.get("task_id") or submit.get("id")
            if not remote_task_id:
                raise FlowError("提交出视频任务失败:未返回 task_id", retryable=True)

            waited = 0
            interval = 3
            while waited < settings.FLOW_VIDEO_MAX_WAIT:
                status = await self._get(
                    client, FLOW_VIDEO_STATUS_ENDPOINT.format(task_id=remote_task_id)
                )
                # >>> 逆向接入点:根据真实状态字段判断完成/失败/进度
                state = (status.get("status") or status.get("state") or "").lower()
                pct = int(status.get("progress", 0) or 0)
                if progress_cb:
                    progress_cb(min(95, max(5, pct)))
                if state in ("succeeded", "success", "completed", "done"):
                    outputs = self._parse_outputs(status, default_type="video")
                    return FlowResult(outputs=outputs, raw=status)
                if state in ("failed", "error"):
                    raise FlowError(
                        f"FLOW 出视频失败: {status.get('error') or state}", retryable=True
                    )
                await asyncio.sleep(interval)
                waited += interval

        raise FlowError("FLOW 出视频超时", retryable=True)

    # ------------------------------------------------------------------ #
    async def _post(self, client: httpx.AsyncClient, path: str, payload: dict) -> dict:
        return await self._request(client, "POST", path, json=payload)

    async def _get(self, client: httpx.AsyncClient, path: str) -> dict:
        return await self._request(client, "GET", path)

    async def _request(self, client: httpx.AsyncClient, method: str, path: str, **kw) -> dict:
        url = f"{FLOW_BASE_URL}{path}"
        try:
            resp = await client.request(method, url, headers=self.cred.headers(), **kw)
        except httpx.HTTPError as exc:
            raise FlowError(f"网络错误: {exc}", retryable=True) from exc

        if resp.status_code in (401, 403):
            raise FlowError("账号鉴权失效", retryable=True, status_code=resp.status_code)
        if resp.status_code == 429:
            raise FlowError("账号被限流", retryable=True, status_code=429)
        if resp.status_code >= 500:
            raise FlowError(f"上游 {resp.status_code}", retryable=True, status_code=resp.status_code)
        if resp.status_code >= 400:
            raise FlowError(
                f"请求被拒绝 {resp.status_code}: {resp.text[:200]}",
                retryable=False,
                status_code=resp.status_code,
            )
        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            raise FlowError("无法解析上游响应", retryable=True) from exc

    @staticmethod
    def _parse_outputs(data: dict, default_type: str) -> list[dict[str, Any]]:
        """从多种可能的响应结构里尽量提取资源 URL。逆向后按真实结构精简。"""
        urls: list[str] = []
        for key in ("outputs", "images", "videos", "results", "data", "assets"):
            val = data.get(key)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        urls.append(item)
                    elif isinstance(item, dict):
                        u = item.get("url") or item.get("image_url") or item.get("video_url")
                        if u:
                            urls.append(u)
        for key in ("url", "image_url", "video_url", "output_url"):
            if isinstance(data.get(key), str):
                urls.append(data[key])
        # 去重保持顺序
        seen: set[str] = set()
        outputs = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                outputs.append({"url": u, "type": default_type})
        if not outputs:
            raise FlowError("上游未返回可用资源 URL", retryable=True)
        return outputs
