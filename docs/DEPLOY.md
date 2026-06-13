# 部署与 CI/CD 指南

> 生产环境：`https://invoce.vpanel.cc`（VPS `38.175.193.100`，与 nextpanel 同机）。

## 架构
```
互联网 :443 ──► [nginx(系统级)] ──┬─ /api/*  ──► 127.0.0.1:8000  (api 容器)
   (certbot 自动签发/续期)        └─ 其余    ──► 127.0.0.1:3100  (frontend 容器)
                                  [postgres][redis][worker]  仅 docker 内网
```
- 反代复用服务器**现有 nginx**（站点 `/etc/nginx/sites-available/invoce`），与 aidash/nextpanel/sync 并存。
- TLS 由 **certbot** 签发并**自动续期**（systemd 定时任务，无需人工）。
- invoce 全栈跑在 **Docker**（postgres/redis/api/worker/frontend），镜像来自 **GHCR**。

## CI / CD
- **CI**（`ci.yml`，PR/push 触发）：后端 ruff/black/mypy/pytest≥80% + alembic；前端 lint/build；安全 gitleaks/trivy。
- **CD**（`deploy.yml`，push main 触发）：构建 `api`/`frontend` 镜像推 GHCR → SSH 到 VPS `git pull` + `docker compose -f docker-compose.prod.yml pull` → `alembic upgrade head`（先迁移）→ `up -d`（后重启）。
  - 前端镜像构建期注入 `NEXT_PUBLIC_API_BASE_URL=https://invoce.vpanel.cc/api`。
  - VPS 用本次运行的 `GITHUB_TOKEN` 临时登录 GHCR 拉镜像（**无需常驻 PAT**）。

## GitHub Secrets（已配置）
| Secret | 值/用途 |
| :--- | :--- |
| `VPS_HOST` | `38.175.193.100` |
| `VPS_PORT` | SSH 端口 |
| `VPS_USER` | `root` |
| `VPS_APP_DIR` | `/opt/apps/invoce` |
| `VPS_SSH_KEY` | 专用部署私钥（VPS 上 `/root/.ssh/invoce_deploy`，公钥已加入 authorized_keys） |

> 镜像推送用内置 `GITHUB_TOKEN`（workflow 已声明 `packages: write`），无需额外 PAT。

## VPS 一次性初始化（已完成，记录备查）
1. 装 Docker：`curl -fsSL https://get.docker.com | sh`
2. `git clone https://github.com/tripplemay/invoce.git /opt/apps/invoce`
3. 建 `.env`（`chmod 600`，密钥服务器端 `openssl` 生成）：`POSTGRES_PASSWORD`/`JWT_SECRET`/`FERNET_KEY` 等；`GH_REPO=tripplemay/invoce`、`IMAGE_TAG=latest`、`NEXT_PUBLIC_API_BASE_URL=https://invoce.vpanel.cc/api`。
4. nginx 站点 `/etc/nginx/sites-available/invoce`（见 `deploy/nginx/invoce.conf`）→ 软链 sites-enabled → `nginx -t` → `reload`。
5. `certbot --nginx -d invoce.vpanel.cc --non-interactive --agree-tos --redirect`。
6. 生成部署密钥并加入 `authorized_keys`。

## 待补（后续阶段）
- `.env` 里 `S3_*` / `AIGC_*` 目前留空，阶段3/4 接入对象存储与 AI 网关时填真实凭证（仅在 VPS 的 `.env`，不进仓库/CI）。

## 密钥分层（安全红线）
- 业务密钥（QQ 授权码、S3、AIGC Key、JWT、Fernet）**只在 VPS 的 `.env`**；CI 只持有 SSH + 自动 `GITHUB_TOKEN`。
- `FERNET_KEY` 生成：`python3 -c "import os,base64;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`
