# Flow2API — 多用户 AIGC 出图 / 出视频平台

一个面向商用的多用户 AIGC 平台:前台用户用 **FLOW** 出图 / 出视频,后台管理员配置账号池、额度与监控。架构按 **高并发 / 水平扩展** 设计。

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI (异步) |
| 任务队列 | Celery + Redis(出图 / 出视频分队列) |
| 实时进度 | WebSocket |
| 数据库 | PostgreSQL + SQLAlchemy 2.0 (async) + Alembic |
| 缓存 / 限流 / 锁 / 队列 | Redis |
| 对象存储 | MinIO (S3 兼容) |
| 前端 | Next.js (App Router) + TypeScript + Tailwind + Framer Motion |
| 部署 | Docker Compose(本地)/ K8s(生产) |

## 架构概览

```
浏览器(Next.js)
   │ HTTPS / WSS
Nginx 负载均衡
   │
FastAPI 集群 ──→ PostgreSQL
   │   │
   │   └──→ Redis(队列 / 缓存 / 分布式锁 / 限流)
   │             │
   │        Celery Workers(出图队列 / 出视频队列)
   │             │
   │        FLOW 适配层(账号池 + 并发闸门)──→ FLOW
   │             │
   └──进度 WS──┘ 生成结果 ──→ MinIO / S3
```

## 高并发设计要点

1. **请求/执行解耦**:HTTP 仅入队并返回 `task_id`,真正生成在 Worker 执行。
2. **账号池 + 并发闸门**:Redis 信号量限制对 FLOW 的最大并发,多账号轮询 + 故障转移。
3. **用户级限流与额度**:Redis 计数器实现按用户/按天的额度与频控。
4. **分队列**:出图(快)与出视频(慢)分队列、分 worker,互不阻塞。
5. **无状态横向扩展**:API 与 Worker 均无状态,可任意扩容。

## 本地启动

```bash
cp .env.example .env
docker compose up -d --build
# 前端:   http://localhost:3000
# 后端文档: http://localhost:8000/docs
# MinIO:   http://localhost:9001  (minioadmin / minioadmin)
```

首次启动后初始化数据库与管理员账号:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed
```

## 目录结构

```
flow2api/
├── backend/        FastAPI + Celery
│   └── app/
│       ├── core/       配置 / DB / Redis / 安全
│       ├── models/     SQLAlchemy 模型
│       ├── schemas/    Pydantic schema
│       ├── api/        路由(auth / generation / admin / ws)
│       ├── services/   FLOW 适配层 / 账号池 / 额度
│       ├── workers/    Celery 任务
│       └── scripts/    seed 等脚本
├── frontend/       Next.js 前台 + 管理员后台
└── docker-compose.yml
```

## FLOW 接入说明

FLOW 采用「逆向网页接口 / Token 模拟请求」方式接入。适配层位于
`backend/app/services/flow/`,把逆向得到的请求填入 `FlowClient`(已留好抽象与
账号池调度),无需改动上层业务即可切换接入方式。
