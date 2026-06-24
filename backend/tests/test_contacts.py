"""通讯录（下游处理人联系人）CRUD 测试。"""

import uuid

from httpx import AsyncClient


async def test_create_and_list_contacts(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/contacts", json={"name": "财务张三", "email": "zhang@corp.com", "note": "审批"}
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "财务张三"
    assert body["email"] == "zhang@corp.com"
    assert body["note"] == "审批"
    assert "id" in body

    await auth_client.post("/contacts", json={"name": "李四", "email": "li@corp.com"})
    lst = (await auth_client.get("/contacts")).json()
    assert {c["email"] for c in lst} == {"zhang@corp.com", "li@corp.com"}


async def test_create_duplicate_email_409(auth_client: AsyncClient) -> None:
    await auth_client.post("/contacts", json={"name": "张三", "email": "dup@corp.com"})
    r = await auth_client.post("/contacts", json={"name": "张三B", "email": "dup@corp.com"})
    assert r.status_code == 409


async def test_create_invalid_email_422(auth_client: AsyncClient) -> None:
    r = await auth_client.post("/contacts", json={"name": "X", "email": "not-an-email"})
    assert r.status_code == 422


async def test_update_contact(auth_client: AsyncClient) -> None:
    c = (await auth_client.post("/contacts", json={"name": "旧名", "email": "old@corp.com"})).json()
    r = await auth_client.patch(f"/contacts/{c['id']}", json={"name": "新名", "note": "财务负责人"})
    assert r.status_code == 200
    assert r.json()["name"] == "新名"
    assert r.json()["note"] == "财务负责人"
    assert r.json()["email"] == "old@corp.com"  # 未传不变


async def test_delete_contact(auth_client: AsyncClient) -> None:
    c = (await auth_client.post("/contacts", json={"name": "待删", "email": "del@corp.com"})).json()
    r = await auth_client.delete(f"/contacts/{c['id']}")
    assert r.status_code == 204
    assert (await auth_client.get("/contacts")).json() == []


async def test_cannot_touch_other_users_contact(
    auth_client: AsyncClient, client: AsyncClient
) -> None:
    c = (await auth_client.post("/contacts", json={"name": "A", "email": "a@corp.com"})).json()
    reg = await client.post(
        "/auth/register", json={"email": "other@test.com", "password": "password123"}
    )
    other = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    assert (
        await client.patch(f"/contacts/{c['id']}", json={"name": "X"}, headers=other)
    ).status_code == 404
    assert (await client.delete(f"/contacts/{c['id']}", headers=other)).status_code == 404


async def test_update_missing_contact_404(auth_client: AsyncClient) -> None:
    r = await auth_client.patch(f"/contacts/{uuid.uuid4()}", json={"name": "X"})
    assert r.status_code == 404
