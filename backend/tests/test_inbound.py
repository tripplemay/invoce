"""专属收票邮箱测试：token 派生/去重、地址解析、注册分配、/inbox 查询、入站 webhook。"""

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.user import User
from app.services import inbox

DOMAIN = "invoce.vpanel.cc"


class FakePool:
    def __init__(self) -> None:
        self.jobs: list[tuple] = []

    async def enqueue_job(self, name, *args):
        self.jobs.append((name, args))

    async def aclose(self):
        pass


@pytest.fixture
def fake_pool(monkeypatch):
    pool = FakePool()

    async def _get_pool():
        return pool

    monkeypatch.setattr("app.api.inbound.get_pool", _get_pool)
    return pool


@pytest.fixture
def inbound_on(monkeypatch):
    """启用收票域 + 设置 webhook 密钥。"""
    monkeypatch.setattr(settings, "inbound_email_domain", DOMAIN)
    monkeypatch.setattr(settings, "inbound_webhook_secret", "s3cr3t")


# ---- 纯函数 ----


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("Becky.Cervantes1992@aol.com", "becky.cervantes1992"),
        ("a b!#c@x.com", "a-b-c"),
        ("..--__@x.com", "user"),
        ("@x.com", "user"),
        ("张三@x.com", "user"),
        ("UPPER@x.com", "upper"),
    ],
)
def test_base_from_email(email: str, expected: str) -> None:
    assert inbox.base_from_email(email) == expected


def test_prod_requires_strong_inbound_secret() -> None:
    from app.core.config import Settings

    base = dict(environment="production", jwt_secret="x" * 40, fernet_key="y" * 44)
    # 启用收票域但密钥过短 → 启动期即报错，避免端点静默 401
    with pytest.raises(ValueError):
        Settings(**base, inbound_email_domain=DOMAIN, inbound_webhook_secret="short")
    # 足够强 → 放行
    ok = Settings(**base, inbound_email_domain=DOMAIN, inbound_webhook_secret="z" * 32)
    assert ok.inbound_enabled is True
    # 未启用收票域 → 不校验密钥
    assert Settings(**base).inbound_enabled is False


def test_token_from_recipient(monkeypatch) -> None:
    monkeypatch.setattr(settings, "inbound_email_domain", DOMAIN)
    assert inbox.token_from_recipient(f"becky@{DOMAIN}") == "becky"
    # 子地址 +detail 去掉
    assert inbox.token_from_recipient(f"becky+jd@{DOMAIN}") == "becky"
    # 大小写归一
    assert inbox.token_from_recipient(f"Becky@{DOMAIN.upper()}") == "becky"
    # 非本域拒绝
    assert inbox.token_from_recipient("becky@evil.com") is None
    # 畸形
    assert inbox.token_from_recipient("not-an-email") is None
    assert inbox.token_from_recipient("") is None


# ---- 注册分配 / 去重 ----


@pytest.mark.asyncio
async def test_register_assigns_inbox_token(auth_client, db_session) -> None:
    user = await db_session.scalar(select(User).where(User.email == "user@test.com"))
    assert user is not None
    assert user.inbox_token == "user"


@pytest.mark.asyncio
async def test_generate_inbox_token_unique(client, db_session) -> None:
    # 两个相同 localpart 不同域的用户 → 第二个 token 必须不同
    await client.post("/auth/register", json={"email": "sam@a.com", "password": "password123"})
    await client.post("/auth/register", json={"email": "sam@b.com", "password": "password123"})
    tokens = (await db_session.scalars(select(User.inbox_token))).all()
    assert "sam" in tokens
    assert len(set(tokens)) == 2  # 无重复


# ---- GET /inbox ----


@pytest.mark.asyncio
async def test_get_inbox_returns_address(auth_client, inbound_on) -> None:
    r = await auth_client.get("/inbox")
    assert r.status_code == 200
    body = r.json()
    assert body == {"token": "user", "address": f"user@{DOMAIN}", "enabled": True}


@pytest.mark.asyncio
async def test_get_inbox_disabled_without_domain(auth_client) -> None:
    r = await auth_client.get("/inbox")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    assert body["address"] is None


@pytest.mark.asyncio
async def test_get_inbox_lazy_generates_token(auth_client, db_session, inbound_on) -> None:
    user = await db_session.scalar(select(User).where(User.email == "user@test.com"))
    user.inbox_token = None
    await db_session.commit()
    r = await auth_client.get("/inbox")
    assert r.status_code == 200
    assert r.json()["token"]  # 惰性补发非空


# ---- POST /inbound/email webhook ----


@pytest.mark.asyncio
async def test_inbound_rejects_when_disabled(client, fake_pool) -> None:
    r = await client.post("/inbound/email", content=b"raw")
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_inbound_rejects_wrong_secret(client, fake_pool, inbound_on) -> None:
    r = await client.post(
        "/inbound/email",
        content=b"raw",
        headers={"X-Inbound-Secret": "wrong", "X-Original-To": f"user@{DOMAIN}"},
    )
    assert r.status_code == 401
    assert fake_pool.jobs == []


@pytest.mark.asyncio
async def test_inbound_rejects_unknown_recipient(auth_client, fake_pool, inbound_on) -> None:
    r = await auth_client.post(
        "/inbound/email",
        content=b"raw",
        headers={"X-Inbound-Secret": "s3cr3t", "X-Original-To": f"nobody@{DOMAIN}"},
    )
    assert r.status_code == 404
    assert fake_pool.jobs == []


@pytest.mark.asyncio
async def test_inbound_rejects_empty_body(auth_client, fake_pool, inbound_on) -> None:
    r = await auth_client.post(
        "/inbound/email",
        headers={"X-Inbound-Secret": "s3cr3t", "X-Original-To": f"user@{DOMAIN}"},
    )
    assert r.status_code == 400
    assert fake_pool.jobs == []


@pytest.mark.asyncio
async def test_inbound_enqueues_for_known_recipient(
    auth_client, db_session, fake_pool, inbound_on
) -> None:
    user = await db_session.scalar(select(User).where(User.email == "user@test.com"))
    r = await auth_client.post(
        "/inbound/email",
        content=b"raw-mime-bytes",
        headers={"X-Inbound-Secret": "s3cr3t", "X-Original-To": f"user@{DOMAIN}"},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert len(fake_pool.jobs) == 1
    name, args = fake_pool.jobs[0]
    assert name == "process_inbound_email"
    assert args == (str(user.id), b"raw-mime-bytes")
