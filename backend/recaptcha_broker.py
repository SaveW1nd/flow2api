"""极小 reCAPTCHA token broker：只暴露一个取 token 端点，复用 app.services.flow.recaptcha 的浏览器路径。

KleinAI Go 通过 HTTP 调它。不依赖 DB/Celery/Redis/MinIO。
浏览器优先（Chrome CDP 跑 grecaptcha.enterprise.execute 拿高分 token），HTTP 兜底。

本地运行（mac 有 Chrome）::

    uvicorn recaptcha_broker:app --host 127.0.0.1 --port 8900

Go 调用::

    POST /recaptcha/token
    {"action":"image","session_token":"...","google_cookies":"...","project_id":"...","proxy":"..."}
    -> 200 {"token":"<recaptcha_token>","browser_headers":{...}}
    -> 502 {"detail":"recaptcha failed: ..."}   # 取 token 失败（账号低分/被 flag 等）
    -> 500 {"detail":"broker error: ..."}        # broker 内部异常
"""

import shutil
import tempfile

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.services.flow import protocol as P
from app.services.flow import recaptcha as R

app = FastAPI(title="Flow reCAPTCHA Broker")


class TokenRequest(BaseModel):
    action: str = "IMAGE_GENERATION"  # 或 VIDEO_GENERATION / image / video
    session_token: str | None = None
    google_cookies: str | None = None
    project_id: str | None = None
    proxy: str | None = None


class TokenResponse(BaseModel):
    token: str
    browser_headers: dict | None = None


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/recaptcha/token", response_model=TokenResponse)
def get_token(req: TokenRequest):
    # action 归一：接受 IMAGE_GENERATION/VIDEO_GENERATION 或 image/video
    action = req.action
    if action.lower() in ("image", "image_generation"):
        action = P.ACTION_IMAGE
    elif action.lower() in ("video", "video_generation"):
        action = P.ACTION_VIDEO

    profile = tempfile.mkdtemp(prefix="flow_recap_broker_")
    try:
        res = R.get_recaptcha_token(
            profile,
            session_token=req.session_token,
            google_cookies=req.google_cookies,
            project_id=req.project_id,
            proxy=req.proxy,
            action=action,
        )
        return TokenResponse(token=res.recaptcha_token, browser_headers=res.browser_headers)
    except R.RecaptchaError as e:
        raise HTTPException(status_code=502, detail=f"recaptcha failed: {e}")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"broker error: {type(e).__name__}: {e}")
    finally:
        shutil.rmtree(profile, ignore_errors=True)
