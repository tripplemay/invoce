# 部署与 CI/CD 指南

## 总览
- **CI**（`.github/workflows/ci.yml`）：PR / push 触发。后端 lint(ruff)+格式(black)+类型(mypy)+迁移(alembic)+测试(pytest≥80%)；前端 lint+build；安全 gitleaks(密钥)+trivy(依赖/文件)。
- **CD**（`.github/workflows/deploy.yml`）：合并到 `main` 后，构建 `api`/`frontend` 镜像推送 GHCR → 经 `production` 环境**人工 approve** → SSH 到 VPS `docker compose -f docker-compose.prod.yml pull` → 独立步骤 `alembic upgrade head`（先迁移）→ `up -d`（后重启）。

## 一、GitHub 仓库设置
1. 新建私有仓库，推送本项目。
2. **Settings → Environments → New environment** 建 `production`，勾选 **Required reviewers**（加你自己）。这样每次部署会卡在等你点 approve。
3. **Settings → Secrets and variables → Actions** 添加以下 secrets：

| Secret | 用途 |
| :--- | :--- |
| `VPS_HOST` | 服务器 IP 或域名 |
| `VPS_USER` | SSH 登录用户名 |
| `VPS_SSH_KEY` | SSH 私钥（PEM 全文） |
| `VPS_APP_DIR` | 服务器上放 `docker-compose.prod.yml` 与 `.env` 的目录 |
| `GHCR_TOKEN` | GHCR 拉取用 PAT（classic，勾 `read:packages`）；供 VPS 上 `docker login ghcr.io` |

> 镜像推送用内置 `GITHUB_TOKEN`（`packages: write` 权限已在 workflow 声明），无需额外配置。

## 二、VPS 准备
1. 安装 Docker + Docker Compose v2。
2. 在 `VPS_APP_DIR` 放置：
   - `docker-compose.prod.yml`（本仓库根目录同名文件）
   - `.env`（由 `.env.example` 派生，**填真实密钥**，权限 600，绝不进仓库）
3. `.env` 必须包含（除业务密钥外）：
   ```
   GH_REPO=<owner/repo 小写>
   IMAGE_TAG=latest
   POSTGRES_USER=... POSTGRES_PASSWORD=... POSTGRES_DB=...
   NEXT_PUBLIC_API_BASE_URL=https://<你的域名>
   # 以及 JWT_SECRET / FERNET_KEY / S3_* / AIGC_* 等全部生产密钥
   ```
4. 前置反代（nginx/caddy）将外部 80/443 转发到本机 `127.0.0.1:3000`（前端）与 `127.0.0.1:8000`（API）。

## 三、密钥分层（安全红线）
- 业务密钥（QQ 授权码、S3、AIGC Key、JWT、Fernet）**只在 VPS 的 `.env`**，永不进仓库、不进 CI。
- CI 只持有 SSH + GHCR 凭证（GitHub Secrets）。
- `FERNET_KEY` 生产生成：`python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"`

## 四、首次部署
1. 服务器登录 GHCR：`echo <PAT> | docker login ghcr.io -u <user> --password-stdin`
2. push `main` → CI 绿 → 在 Actions 里对 `production` 点 **Approve** → 自动部署。
3. 验证：`curl https://<域名>/api/health` 应返回 `{"status":"ok"}`。
