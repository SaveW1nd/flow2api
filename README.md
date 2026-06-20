# Flow2API

Flow2API 是一个 Python + Web 的多用户 Google Flow / Labs FX 协议生成平台。它把 Flow 出图、出视频、账号池、额度、任务队列、文件存储和后台管理封装成一套可部署的 Web 系统，适合做内部 AIGC 平台、API 中转和多账号调度。

当前版本已实测支持协议出图和协议出视频，支持 OMNI 视频模型，支持无头 Chrome broker 获取 reCAPTCHA Enterprise token，无需人工打码平台。

## 功能说明

- 多用户 Web 工作台：用户可提交文生图、文生视频任务，查看任务进度和历史结果。
- 管理员后台：支持用户管理、账号池配置、代理配置、并发控制、额度配置和运行状态查看。
- Flow 协议出图：对接 `aisandbox-pa.googleapis.com` 的 `flowMedia:batchGenerateImages`，支持 Nano Banana / Banana Pro / Imagen 等模型映射。
- Flow 协议出视频：对接 `video:batchAsyncGenerateVideoText` 和状态轮询接口，默认支持 OMNI / `omni_flash`，并可配置其他 Flow 视频模型。
- 1080P 下载优先：视频生成完成后优先通过 Labs media redirect 获取 `_upsampled` 版本，失败时自动回退普通媒体下载。
- reCAPTCHA 无头 broker：worker 通过本机 Chrome DevTools Protocol 在无头模式执行官方 `grecaptcha.enterprise.execute()`，获取高分 token，无需接入打码平台。
- 纯 HTTP 兜底：无头 broker 不可用时，保留 Enterprise anchor / reload 协议 token 获取逻辑作为兜底。
- Google 登录态管理：支持保存 `__Secure-next-auth.session-token`，也支持导入 Google / Labs cookies 后通过协议刷新 Labs session。
- 代理一致性：支持全局代理和单账号代理，reCAPTCHA、ST/AT 刷新、Flow API 请求和媒体下载可走同一出口 IP。
- 高并发任务架构：FastAPI 负责 API，Celery + Redis 负责异步出图/出视频，图片和视频分队列运行。
- 媒体存储：默认使用 MinIO / S3，写入失败时自动 fallback 到本地 `backend/media` 并由 FastAPI 静态服务输出。
- 企业风格前端：Next.js + Tailwind 实现蓝色企业风 UI，包含统一按钮、提示框、确认框和自适应布局。

## 技术架构

- 后端：FastAPI、SQLAlchemy 2.0、Alembic、Pydantic。
- 任务队列：Celery、Redis，图片和视频独立队列。
- 数据库：PostgreSQL。
- 存储：MinIO / S3，本地媒体 fallback。
- 前端：Next.js App Router、TypeScript、Tailwind CSS。
- 协议请求：`curl_cffi` 模拟 Chrome TLS 指纹，普通请求 fallback 到 HTTP 客户端。
- reCAPTCHA broker：系统 Chrome / Chromium + CDP WebSocket，无头执行官方 reCAPTCHA Enterprise JS。

```text
Browser / Next.js
        |
        v
FastAPI API  ---- PostgreSQL
        |
        +---- Redis queue / lock / rate limit
                  |
                  +---- Celery image worker
                  +---- Celery video worker
                              |
                              +---- Flow protocol client
                              +---- Headless reCAPTCHA broker
                              +---- MinIO / local media storage
```

## 目录结构

```text
flow2api/
├── backend/
│   ├── app/
│   │   ├── api/          API 路由
│   │   ├── core/         配置、数据库、Redis、安全
│   │   ├── models/       SQLAlchemy 模型
│   │   ├── schemas/      Pydantic schema
│   │   ├── services/     Flow 协议、账号池、存储、额度
│   │   └── workers/      Celery 任务
│   ├── export_google_cookies.py
│   └── capture_download_urls.py
├── frontend/
│   └── src/
├── docker-compose.yml
├── run_workers.ps1
└── setup_workers.ps1
```

## 部署说明

### 1. 准备环境

本地开发推荐 Windows 10/11 + Docker Desktop + Python 3.11 + Node.js 20。worker 原生运行在宿主机，方便调用本机 Chrome 作为无头 reCAPTCHA broker。

需要提前安装 Chrome 或 Chromium，并确保当前 Google 账号可正常访问 `https://labs.google/fx/tools/flow`。

### 2. 配置环境变量

```powershell
Copy-Item .env.example .env
```

重点配置项：

- `SECRET_KEY`：生产环境必须改成随机长字符串。
- `FLOW_PROXY`：全局默认代理，格式如 `http://user:pass@host:port` 或 `socks5://user:pass@host:port`。
- `FLOW_HEADLESS=true`：启用无头 broker，生产建议开启。
- `FLOW_CHROME_PATH`：Chrome 不在默认路径时填写。
- `MEDIA_PUBLIC_ENDPOINT=http://localhost:18000/media`：本地媒体 fallback 的公开地址。
- `NEXT_PUBLIC_API_BASE=http://localhost:18000`：前端访问后端 API 的地址。
- `NEXT_PUBLIC_WS_BASE=ws://localhost:18000`：前端 WebSocket 地址。

### 3. 启动基础服务

```powershell
docker compose up -d --build postgres redis minio backend frontend
```

默认访问地址：

- 前端：`http://localhost:3000`
- 后端 API 文档：`http://localhost:18000/docs`
- MinIO 控制台：`http://localhost:9001`

### 4. 初始化数据库

```powershell
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed
```

默认管理员账号来自 `.env`：

- 邮箱：`admin@flow2api.com`
- 密码：`admin12345`

生产环境请立即修改默认密码。

### 5. 安装并启动 worker

首次运行：

```powershell
.\setup_workers.ps1
```

启动图片和视频 worker：

```powershell
.\run_workers.ps1
```

`run_workers.ps1` 会打开图片队列和视频队列 worker。Windows 下使用 Celery `solo` pool 更稳定。生产部署时也可以拆成多台 worker，但要保证每台 worker 可访问相同的 PostgreSQL、Redis 和媒体存储。

### 6. 导入 Flow 账号

管理员后台新增 Flow 账号时至少需要：

- `session_token`：Labs 的 `__Secure-next-auth.session-token`。
- `project_id`：Flow 项目 ID。
- `proxy`：建议每个账号绑定固定代理，保证登录态、reCAPTCHA 和 API 请求出口一致。
- `google_cookies`：建议导入 Google / Labs 相关 cookies，用于协议刷新 session 和提升 reCAPTCHA 评分。

可以使用脚本辅助导出 cookies：

```powershell
cd backend
.\.venv\Scripts\python.exe export_google_cookies.py --account-id 1 --proxy "http://user:pass@host:port"
```

脚本会打开 Chrome，登录完成后读取 cookies 并保存到账号。导出的 `google_cookies_export*.json` 属于敏感文件，不要提交到 Git。

## Flow 协议说明

协议适配层位于 `backend/app/services/flow/`。

- `protocol.py`：维护 Flow / Labs FX 端点、API key、模型映射、比例映射和请求体构造。
- `client.py`：负责 ST/AT 鉴权、提交出图/出视频、轮询视频状态、下载媒体、错误分类和重试。
- `recaptcha.py`：优先启动无头 Chrome broker，通过 CDP 执行官方 reCAPTCHA Enterprise JS 获取 token；失败时回退到纯 HTTP anchor/reload。
- `token_manager.py`：用 Labs session token 换取访问 token。
- `session_login.py`：用 Google cookies 通过协议刷新 Labs session token。
- `pool.py`：账号选择、代理解析、并发控制、冷却和凭证构造。
- `proxy.py`：代理解析和 Chrome 代理参数支持。

出图流程：

```text
选择账号 -> 刷新 Labs access token -> 获取 IMAGE_GENERATION reCAPTCHA token
-> batchGenerateImages -> 下载图片 -> 写入 MinIO 或本地媒体目录
```

出视频流程：

```text
选择账号 -> 刷新 Labs access token -> 获取 VIDEO_GENERATION reCAPTCHA token
-> batchAsyncGenerateVideoText -> batchCheckAsyncVideoGenerationStatus 轮询
-> 优先下载 _upsampled 1080P 媒体 -> 写入 MinIO 或本地媒体目录
```

## OMNI 支持

默认视频模型为 `omni_flash`，协议层映射到 Flow 视频模型 key：

```text
omni_flash -> abra_t2v_10s
```

接口请求可以通过 `model` 或 `extra` 扩展传入其他模型 key。当前协议层也预留了 `veo_3_1_fast`、`veo_3_1_lite`、`veo_3_1_quality` 等映射，实际可用性取决于账号权限和 Google Flow 当前灰度状态。

## reCAPTCHA 说明

Flow 每次生成都需要新鲜的 reCAPTCHA Enterprise token。项目不使用打码平台，默认策略是：

1. worker 启动本机 Chrome / Chromium。
2. 使用 CDP 打开 Labs 页面上下文。
3. 注入并执行官方 `grecaptcha.enterprise.execute(siteKey, { action })`。
4. 拿到 token 后立即提交 Flow 协议请求。
5. 如果无头 broker 不可用，再尝试纯 HTTP Enterprise anchor/reload 兜底。

实测无头 broker 可完成出图和出视频。为了提升通过率，请保持以下一致：

- cookies 登录出口 IP、reCAPTCHA 获取出口 IP、Flow API 请求出口 IP 尽量一致。
- 同一账号使用固定代理。
- 不要频繁并发压同一个账号。
- `FLOW_USE_CURL=true`，并使用本机 `curl_cffi` 支持的 `FLOW_IMPERSONATE` 版本。

## 常用接口

- `POST /api/v1/auth/login`：登录获取 JWT。
- `POST /api/v1/generate/image`：提交出图任务。
- `POST /api/v1/generate/video`：提交出视频任务。
- `GET /api/v1/generate/tasks/{public_id}`：查询任务状态。
- `WS /api/v1/ws/tasks/{public_id}`：订阅任务进度。
- `/api/v1/admin/*`：管理员用户、账号池和系统管理。

## 生产建议

- 使用 HTTPS 和反向代理，不要直接暴露后端管理接口。
- 修改默认管理员密码和 `SECRET_KEY`。
- PostgreSQL、Redis、MinIO 使用持久化存储和访问控制。
- 每个 Flow 账号绑定独立代理，按账号权限设置合理并发。
- 定期清理本地 `backend/media` 或改用正式 S3。
- 不要提交 `.env`、cookies 导出文件、Chrome profile、生成媒体和日志。

## 开源说明

本项目用于学习、研究和自建自动化平台。使用者需要自行准备合法可用的 Google / Labs 账号，并遵守目标服务条款、当地法律法规和账号使用限制。

项目不内置任何账号、cookie、代理或第三方打码服务。仓库中的协议代码仅用于说明客户端如何组织请求、任务队列和工程化部署；请勿用于垃圾请求、滥用配额或绕过平台风控规则。

## License

请根据你的开源计划补充许可证文件，例如 MIT、Apache-2.0 或其他许可证。
