# Invoce · 个人发票与消费分析助手

发票「收集 → AI 抽取 → 人工校对 → 防重 → 分类分析 → 打包导出报销」一体化的个人系统。

## 技术栈
- **前端**：Next.js（Horizon UI PRO 模板）+ TailwindCSS + Tremor
- **后端**：FastAPI（全异步）+ PostgreSQL + ARQ（Redis 队列）
- **存储**：S3 兼容私有桶（R2/S3），60 秒预签名 URL
- **AI**：AIGC 网关（默认 `qwen3.5-plus`，抽象客户端可换）
- **部署**：Docker / docker-compose；CI/CD 走 GitHub Actions + GHCR → 自托管 VPS

## 目录结构
```
.
├── backend/            # FastAPI + SQLAlchemy + Alembic + ARQ worker
│   ├── app/
│   │   ├── core/       # 配置 / 数据库 / 加密 / 安全
│   │   ├── models/     # 5 张表：users / email_accounts / invoices / seller_category_rules / email_sync_logs
│   │   ├── api/        # 路由
│   │   └── worker/     # ARQ 配置
│   └── alembic/        # 数据库迁移
├── frontend/           # Next.js 前端（由 Horizon PRO 模板瘦身而来）
└── docker-compose.yml  # postgres / redis / api / worker / frontend
```

## 本地启动
```bash
cp .env.example .env          # 按需填写 S3 / AIGC 网关 等凭证
docker compose up -d --build  # 起全套服务
# 前端 http://localhost:3000 ，API http://localhost:8000/health
```

数据库迁移由 api 容器启动时自动执行（`alembic upgrade head`）。

## 开发约定
- 后端：`ruff` + `black` + `mypy` + `pytest`（目标 80% 覆盖）
- 密钥只走 VPS 的 `.env`，绝不进仓库或前端

## 实施进度
按阶段推进：0 骨架 → 0.5 CI/CD → 1 认证 → 2 前端三页 → 3 上传/存储/预览/防重 → 4 AI 抽取 → 5 IMAP 归集 → 6 导出闭环 → 7 收尾。
