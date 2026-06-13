"""邮箱账户 CRUD / 加密 / 隔离测试。"""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt
from app.models.email_account import EmailAccount


async def test_email_account_crud(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/email-accounts", json={"imap_user": "123@qq.com", "auth_code": "abcd1234efgh5678"}
    )
    assert r.status_code == 201
    data = r.json()
    assert data["imap_user"] == "123@qq.com"
    assert data["imap_host"] == "imap.qq.com"
    assert data["imap_port"] == 993
    assert "auth_code" not in data and "auth_code_enc" not in data  # 永不回传
    acct_id = data["id"]

    lst = await auth_client.get("/email-accounts")
    assert lst.status_code == 200 and len(lst.json()) == 1

    up = await auth_client.patch(f"/email-accounts/{acct_id}", json={"enabled": False})
    assert up.status_code == 200 and up.json()["enabled"] is False

    d = await auth_client.delete(f"/email-accounts/{acct_id}")
    assert d.status_code == 204
    assert len((await auth_client.get("/email-accounts")).json()) == 0


async def test_email_accounts_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/email-accounts")).status_code == 401


async def test_email_account_isolation_between_users(client: AsyncClient) -> None:
    ra = await client.post("/auth/register", json={"email": "a2@b.com", "password": "password123"})
    ta = ra.json()["access_token"]
    acc = await client.post(
        "/email-accounts",
        json={"imap_user": "a@qq.com", "auth_code": "code1234"},
        headers={"Authorization": f"Bearer {ta}"},
    )
    aid = acc.json()["id"]

    rb = await client.post("/auth/register", json={"email": "b2@b.com", "password": "password123"})
    tb = rb.json()["access_token"]
    bheaders = {"Authorization": f"Bearer {tb}"}
    assert (await client.get("/email-accounts", headers=bheaders)).json() == []
    assert (await client.delete(f"/email-accounts/{aid}", headers=bheaders)).status_code == 404


async def test_auth_code_stored_encrypted(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    r = await auth_client.post(
        "/email-accounts", json={"imap_user": "e@qq.com", "auth_code": "secret-code-1234"}
    )
    assert r.status_code == 201
    acct = (await db_session.scalars(select(EmailAccount))).first()
    assert acct is not None
    assert acct.auth_code_enc != b"secret-code-1234"
    assert decrypt(acct.auth_code_enc) == "secret-code-1234"
