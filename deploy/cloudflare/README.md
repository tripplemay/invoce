# 专属收票邮箱 · Cloudflare 接入指南

每个用户注册即获得一个专属地址 `<token>@invoce.vpanel.cc`，发到该地址的邮件里的发票自动入库。
入站链路：**发件人 → Cloudflare Email Routing（catch-all）→ Email Worker → 后端 `POST /api/inbound/email` → ARQ `process_inbound_email` → 复用 IMAP 同款解析/入库管线**。

> 功能默认休眠：后端未配置 `INBOUND_EMAIL_DOMAIN` 时 `/inbound/email` 返回 503、`/inbox` 显示未启用。配置好下面两项即激活。

## 一、后端环境变量（写入生产 `.env`，勿入库 git）

```
INBOUND_EMAIL_DOMAIN=invoce.vpanel.cc
INBOUND_WEBHOOK_SECRET=<openssl rand -hex 32 生成的随机串>
```

改完重启 `api` 与 `worker` 容器。数据库迁移随发布执行（`alembic upgrade head` 到 `0005`，新增 `users.inbox_token`）。

## 二、Cloudflare 配置

前提：`invoce.vpanel.cc`（或 `vpanel.cc`）的 DNS 托管在 Cloudflare（使用 Cloudflare 名称服务器，full setup）。

1. **Email Routing**：进入该 zone → Email → Email Routing → 启用，按提示添加 Cloudflare 给出的 MX / SPF 记录。
2. **Email Worker**（这是「Worker 代码」，**不是** Pages 静态站；千万别用 Workers & Pages 里「上传并部署 / 拖放静态文件」那个入口——它是给静态网站的，拖 `.js` 进去会报「至少找到了一个 JavaScript 文件，请改用 wrangler」）。两种正确方式二选一：

   **方式 A · 控制台在线编辑器（推荐，无需命令行）**
   - Workers & Pages → **Create（创建）** → 选 **Workers** 这一栏里的 **“Hello World” / 从代码开始**（不要选 “Import a repository”“Upload assets/Pages”）→ 命名如 `invoce-email-inbound` → Deploy 出一个默认 worker。
   - 进该 Worker → **Edit code（编辑代码）**→ 全选删掉默认内容，粘贴本目录 `email-worker.js` 全文 → **Deploy**。
   - 该 Worker → **Settings → Variables and Secrets**：
     - 加变量 `WEBHOOK_URL` = `https://invoce.vpanel.cc/api/inbound/email`（明文）
     - 加 **Secret** `WEBHOOK_SECRET` = 与后端 `INBOUND_WEBHOOK_SECRET` 完全一致。

   **方式 B · wrangler CLI（即报错提示的方式）**
   - 见本目录 `wrangler.toml` 顶部注释：`npx wrangler login` → `npx wrangler secret put WEBHOOK_SECRET` → `npx wrangler deploy`。`WEBHOOK_URL` 已写在 `wrangler.toml` 的 `[vars]`。
3. **Catch-all 路由**：Email Routing → Routing rules → Catch-all address → Action 选 **Send to a Worker** → 选上面的 Worker。
   - 这样任意 `*@invoce.vpanel.cc` 都进同一个 Worker，无需为每个用户单独建规则。

## 三、验证

- 给某个已注册用户的地址（登录后在仪表盘“专属收票邮箱”处复制）发一封带 PDF 发票的邮件。
- 后端日志应出现 `process_inbound_email` 任务；发票出现在列表，来源标记为「收票邮箱」。
- 发到不存在的 token（如 `nobody@invoce.vpanel.cc`）→ 发件人收到“查无此人”退信，不入库。

## 备注

- Cloudflare Email Workers 单封上限 25 MiB；后端兜底 26 MB（超限返回 413，Worker 退信告知过大）。
- 观察期反滥用：暂不按 SPF/DKIM/DMARC 拦截（接受所有发件人），后续可在后端加开关收紧。
- 备选方案（若 DNS 不能托管到 Cloudflare）：Mailgun Routes（约 $15/mo），webhook 协议一致，仅需改投递源。
