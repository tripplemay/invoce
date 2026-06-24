# 部署与 CI/CD 指南

> 生产环境：`https://invoce.vpanel.cc`（**GCP「kolmatrix」`34.180.93.185`**，应用目录 `/opt/apps/invoce`，登录用户 `tripplezhou`，本地 `ssh -i ~/.ssh/kolmatrix_deploy tripplezhou@34.180.93.185`）。
>
> **迁移记录**：原在腾讯云 VPS `38.175.193.100`（与 nextpanel 同机），因该机在服务商层面封了出站 `993/25`，QQ 邮箱 IMAP 连不通，于 **2026-06-14 迁至 GCP kolmatrix**（迁移保留 `FERNET_KEY`/`JWT_SECRET`，用户登录态与邮箱授权码不失效）。旧机上的 invoce 已完全下线，现仅跑 nextpanel/worldcup，**勿动**。

## 架构
```
互联网 :443 ──► [nginx(系统级)] ──┬─ /api/*  ──► 127.0.0.1:8000  (api 容器)
   (certbot 自动签发/续期)        └─ 其余    ──► 127.0.0.1:3100  (frontend 容器)
                                  [postgres][redis][worker]  仅 docker 内网
```
- 反代复用服务器**现有 nginx**（站点见 `deploy/nginx/invoce.conf`），与同机其它项目并存。
- TLS 由 **certbot** 签发并**自动续期**（systemd 定时任务，无需人工）。
- invoce 全栈跑在 **Docker**（postgres/redis/api/worker/frontend），镜像来自 **GHCR**。

## CI / CD
- **CI**（`ci.yml`，PR/push 触发）：后端 ruff/black/mypy/pytest≥80% + alembic；前端 lint/build；安全 gitleaks/trivy。
- **CD**（`deploy.yml`，push main 触发；`paths-ignore` 含 `**.md`/`docs/**`，纯文档改动不触发）：构建 `api`/`frontend` 镜像推 GHCR → SSH 到 kolmatrix `git pull` + `docker compose -f docker-compose.prod.yml pull` → `alembic upgrade head`（先迁移）→ `up -d`（后重启）。
  - 前端镜像构建期注入 `NEXT_PUBLIC_API_BASE_URL=https://invoce.vpanel.cc/api`。
  - 服务器用本次运行的 `GITHUB_TOKEN` 临时登录 GHCR 拉镜像（**无需常驻 PAT**）。

## GitHub Secrets（当前指向 kolmatrix）
| Secret | 值/用途 |
| :--- | :--- |
| `VPS_HOST` | `34.180.93.185`（GCP kolmatrix） |
| `VPS_PORT` | SSH 端口（22） |
| `VPS_USER` | `tripplezhou`（非 root，在 docker 组、免密 sudo） |
| `VPS_APP_DIR` | `/opt/apps/invoce` |
| `VPS_SSH_KEY` | 专用部署私钥（本地 `~/.ssh/kolmatrix_deploy`，公钥在服务器 `tripplezhou` 的 `~/.ssh/authorized_keys`） |

> 镜像推送用内置 `GITHUB_TOKEN`（workflow 已声明 `packages: write`），无需额外 PAT。

## 出站发件 SMTP（报销单一键发送，2026-06-25 上线）
- 走**阿里云邮件推送 DirectMail**（杭州地域），发信地址 `noreply@mail.invoce.vpanel.cc`。
- 用**专用子域 `mail.invoce.vpanel.cc`**：SPF / DKIM（selector `aliyun-cn-hangzhou`）/ DMARC / MX 四条记录在 **Cloudflare zone `vpanel.cc`**，**与根域的 Cloudflare Email Routing 收票 MX 互不干扰**（根域 MX 留给入站收票）。
- kolmatrix `.env` 键：`SMTP_HOST=smtpdm.aliyun.com`、`SMTP_PORT=465`、`SMTP_USE_SSL=true`、`SMTP_USER=noreply@mail.invoce.vpanel.cc`、`SMTP_PASSWORD=***`、`OUTBOUND_FROM_ADDRESS=noreply@mail.invoce.vpanel.cc`、`OUTBOUND_FROM_NAME=发票助手`。**留空 `SMTP_HOST` 则发送端点返回 503**（休眠开关）。
- 改 SMTP 密码：阿里云「发信地址 → 设置 SMTP 密码」→ 改服务器 `.env` → `docker compose -f docker-compose.prod.yml up -d --force-recreate api worker`。

## 服务器一次性初始化（记录备查）
1. 装 Docker：`curl -fsSL https://get.docker.com | sh`，并把部署用户加入 `docker` 组。
2. `git clone https://github.com/tripplemay/invoce.git /opt/apps/invoce`（归属部署用户 `tripplezhou`）。
3. 建 `.env`（`chmod 600`，密钥服务器端 `openssl`/`python` 生成）：`POSTGRES_PASSWORD`/`JWT_SECRET`/`FERNET_KEY`、`GH_REPO=tripplemay/invoce`、`IMAGE_TAG=latest`、`NEXT_PUBLIC_API_BASE_URL=https://invoce.vpanel.cc/api`，以及 `S3_*`/`AIGC_*`/`SMTP_*` 等运行凭证。
4. nginx 站点（见 `deploy/nginx/invoce.conf`）→ 软链 sites-enabled → `nginx -t` → `reload`。
5. `certbot --nginx -d invoce.vpanel.cc --non-interactive --agree-tos --redirect`。
6. 生成部署密钥并把公钥加入部署用户的 `authorized_keys`。

## 密钥分层（安全红线）
- 业务密钥（QQ 授权码、`S3_*`、`AIGC_*`、`SMTP_PASSWORD`、`JWT_SECRET`、`FERNET_KEY`）**只在服务器的 `.env`**；CI 只持有 SSH + 自动 `GITHUB_TOKEN`。
- `FERNET_KEY` 生成：`python3 -c "import os,base64;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`
