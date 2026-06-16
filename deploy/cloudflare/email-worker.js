/**
 * Cloudflare Email Worker —— 专属收票邮箱入站转发。
 *
 * 绑定到 invoce.vpanel.cc 的 catch-all 路由：收到任意 <token>@invoce.vpanel.cc 的邮件后，
 * 把原始 MIME 原样 POST 到后端 webhook，由后端按 token 定位用户并入库。
 *
 * 需要在 Worker 上配置两个变量（Settings → Variables）：
 *   WEBHOOK_URL    例如 https://api.invoce.example.com/inbound/email
 *   WEBHOOK_SECRET 与后端 INBOUND_WEBHOOK_SECRET 完全一致（机密变量）
 *
 * 拒信策略：
 *   - 404（无此收件人）→ setReject，发件人收到“查无此人”退信（正确语义）。
 *   - 413（邮件过大）  → setReject，告知过大。
 *   - 其他非 2xx / 网络异常 → throw，让 Cloudflare 重试（给后端/配置恢复的机会，不丢信）。
 */
export default {
  async email(message, env, ctx) {
    const raw = await new Response(message.raw).arrayBuffer();

    let resp;
    try {
      resp = await fetch(env.WEBHOOK_URL, {
        method: "POST",
        headers: {
          "Content-Type": "message/rfc822",
          "X-Inbound-Secret": env.WEBHOOK_SECRET,
          "X-Original-To": message.to,
        },
        body: raw,
      });
    } catch (err) {
      // 网络层失败：抛出让 Cloudflare 重试，避免误退信。
      throw new Error(`inbound webhook unreachable: ${err}`);
    }

    if (resp.status === 404) {
      message.setReject("No such recipient");
      return;
    }
    if (resp.status === 413) {
      message.setReject("Message too large");
      return;
    }
    if (!resp.ok) {
      // 401/5xx 等：当作可恢复错误抛出重试，不要把邮件退掉。
      throw new Error(`inbound webhook returned ${resp.status}`);
    }
  },
};
