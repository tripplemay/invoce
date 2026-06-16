"""Telegram API 测试：webhook secret 校验/入队 + 绑定码/状态/解绑（get_pool 已 mock）。"""

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.telegram_account import TelegramAccount
from app.models.user import User


class FakePool:
    def __init__(self) -> None:
        self.jobs: list[tuple] = []
        self.kv: dict[str, tuple] = {}

    async def enqueue_job(self, name, *args):
        self.jobs.append((name, args))

    async def set(self, k, v, ex=None):
        self.kv[k] = (v, ex)

    async def aclose(self):
        pass


@pytest.fixture
def fake_pool(monkeypatch):
    pool = FakePool()

    async def _get_pool():
        return pool

    monkeypatch.setattr("app.api.telegram.get_pool", _get_pool)
    return pool


async def test_webhook_rejects_wrong_secret(client, fake_pool, monkeypatch) -> None:
    monkeypatch.setattr(settings, "telegram_webhook_secret", "right")
    r = await client.post(
        "/telegram/webhook",
        json={"message": {}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert r.status_code == 403
    assert fake_pool.jobs == []


async def test_webhook_rejects_when_secret_unset(client, fake_pool) -> None:
    # 服务端未配置 secret（默认空）→ 一律拒绝，不可被无 secret 调用
    r = await client.post("/telegram/webhook", json={"message": {}})
    assert r.status_code == 403


async def test_webhook_enqueues_on_valid_secret(client, fake_pool, monkeypatch) -> None:
    monkeypatch.setattr(settings, "telegram_webhook_secret", "right")
    upd = {"message": {"chat": {"id": 1}, "text": "hi"}}
    r = await client.post(
        "/telegram/webhook", json=upd, headers={"X-Telegram-Bot-Api-Secret-Token": "right"}
    )
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert fake_pool.jobs and fake_pool.jobs[0][0] == "process_telegram_update"
    assert fake_pool.jobs[0][1][0] == upd


async def test_link_code_returns_deep_link(auth_client, fake_pool, monkeypatch) -> None:
    monkeypatch.setattr(settings, "telegram_bot_token", "TOKEN")
    monkeypatch.setattr(settings, "telegram_bot_username", "invoce_bot")
    r = await auth_client.post("/telegram/link-code")
    assert r.status_code == 200
    body = r.json()
    assert body["deep_link"].startswith("https://t.me/invoce_bot?start=")
    assert body["expires_in"] == 600
    assert any(k.startswith("tg:link:") for k in fake_pool.kv)  # 码已写入(TTL)


async def test_link_code_disabled_without_config(auth_client) -> None:
    r = await auth_client.post("/telegram/link-code")  # 默认无 token
    assert r.status_code == 503


async def test_webhook_requires_no_auth_but_link_code_does(client) -> None:
    # link-code 需登录
    assert (await client.post("/telegram/link-code")).status_code == 401


async def test_account_status_and_unlink(auth_client, db_session) -> None:
    assert (await auth_client.get("/telegram/account")).json() is None  # 初始未绑定
    user = await db_session.scalar(select(User).where(User.email == "user@test.com"))
    db_session.add(TelegramAccount(user_id=user.id, chat_id=42, username="bob"))
    await db_session.commit()
    got = (await auth_client.get("/telegram/account")).json()
    assert got["chat_id"] == 42 and got["username"] == "bob"
    assert (await auth_client.delete("/telegram/account")).status_code == 204
    assert (await auth_client.get("/telegram/account")).json() is None
