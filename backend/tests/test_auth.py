"""认证流程测试。"""

from httpx import AsyncClient


async def test_register_returns_token_and_me_works(client: AsyncClient) -> None:
    r = await client.post("/auth/register", json={"email": "a@b.com", "password": "password123"})
    assert r.status_code == 201
    token = r.json()["access_token"]

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "a@b.com"


async def test_register_duplicate_email_conflict(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "d@b.com", "password": "password123"})
    r = await client.post("/auth/register", json={"email": "d@b.com", "password": "password123"})
    assert r.status_code == 409


async def test_login_success_and_wrong_password(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": "l@b.com", "password": "password123"})
    ok = await client.post("/auth/login", json={"email": "l@b.com", "password": "password123"})
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    bad = await client.post("/auth/login", json={"email": "l@b.com", "password": "wrongpass1"})
    assert bad.status_code == 401


async def test_me_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/auth/me")).status_code == 401
    assert (
        await client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
    ).status_code == 401


async def test_password_too_short_rejected(client: AsyncClient) -> None:
    r = await client.post("/auth/register", json={"email": "x@b.com", "password": "short"})
    assert r.status_code == 422
