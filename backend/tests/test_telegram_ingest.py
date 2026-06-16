"""Telegram 消息处理测试（telegram 客户端 + storage 已 mock，用 FakeRedis 代替 ARQ/Redis）。"""

import io
import zipfile

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password
from app.models.invoice import Invoice
from app.models.telegram_account import TelegramAccount
from app.models.user import User
from app.services import telegram_ingest


class FakeRedis:
    """够用即可：get/set/delete（绑定码）+ enqueue_job（AI 抽取）。"""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.jobs: list[tuple] = []

    async def get(self, k):
        return self.store.get(k)

    async def set(self, k, v, ex=None):
        self.store[k] = v.encode() if isinstance(v, str) else v

    async def delete(self, k):
        self.store.pop(k, None)

    async def enqueue_job(self, name, *args):
        self.jobs.append((name, args))


@pytest.fixture
def tg_mocks(monkeypatch):
    """mock Telegram 回复 + R2 上传；返回收集到的回复列表。"""
    sent: list[tuple[int, str]] = []

    async def _send(chat_id, text):
        sent.append((chat_id, text))

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr("app.core.telegram.send_message", _send)
    monkeypatch.setattr("app.core.storage.upload_bytes", _noop)
    return sent


async def _make_user(db_session) -> User:
    u = User(email="tg@b.com", password_hash=hash_password("password123"))
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


async def _bind_account(db_session, user, chat_id) -> None:
    db_session.add(TelegramAccount(user_id=user.id, chat_id=chat_id))
    await db_session.commit()


def _mock_download(monkeypatch, data: bytes | None, *, expect_file_id: str | None = None):
    async def _path(file_id):
        if expect_file_id is not None:
            assert file_id == expect_file_id
        return "files/doc.bin"

    async def _dl(path, **k):
        return data

    monkeypatch.setattr("app.core.telegram.get_file_path", _path)
    monkeypatch.setattr("app.core.telegram.download_file", _dl)


async def test_bind_valid_code(db_session, tg_mocks) -> None:
    user = await _make_user(db_session)
    redis = FakeRedis()
    redis.store["tg:link:CODE123"] = str(user.id).encode()
    update = {
        "message": {"chat": {"id": 555}, "from": {"username": "alice"}, "text": "/start CODE123"}
    }
    await telegram_ingest.process_update(db_session, redis, update)

    acc = await db_session.scalar(select(TelegramAccount))
    assert acc is not None
    assert acc.user_id == user.id and acc.chat_id == 555 and acc.username == "alice"
    assert "tg:link:CODE123" not in redis.store  # 码已一次性消费
    assert any("绑定成功" in t for _, t in tg_mocks)


async def test_bind_invalid_code(db_session, tg_mocks) -> None:
    update = {"message": {"chat": {"id": 1}, "text": "/start NOPE"}}
    await telegram_ingest.process_update(db_session, FakeRedis(), update)
    assert await db_session.scalar(select(func.count()).select_from(TelegramAccount)) == 0
    assert any("无效或已过期" in t for _, t in tg_mocks)


async def test_rebind_replaces_old(db_session, tg_mocks) -> None:
    """同用户重新绑定到新 chat：旧绑定被替换，不撞唯一约束。"""
    user = await _make_user(db_session)
    await _bind_account(db_session, user, 100)
    redis = FakeRedis()
    redis.store["tg:link:NEW"] = str(user.id).encode()
    update = {"message": {"chat": {"id": 200}, "from": {"username": "a"}, "text": "/start NEW"}}
    await telegram_ingest.process_update(db_session, redis, update)
    accs = (await db_session.scalars(select(TelegramAccount))).all()
    assert len(accs) == 1 and accs[0].chat_id == 200


async def test_file_ingest_when_bound(db_session, tg_mocks, monkeypatch) -> None:
    user = await _make_user(db_session)
    await _bind_account(db_session, user, 777)
    _mock_download(monkeypatch, b"%PDF-1.4 tg invoice")
    redis = FakeRedis()
    update = {
        "message": {"chat": {"id": 777}, "document": {"file_id": "F1", "file_name": "inv.pdf"}}
    }
    await telegram_ingest.process_update(db_session, redis, update)

    inv = await db_session.scalar(select(Invoice))
    assert inv is not None and inv.source == "telegram" and inv.status == "processing"
    assert redis.jobs and redis.jobs[0][0] == "extract_invoice"
    assert any("已入库 1 张" in t for _, t in tg_mocks)


async def test_zip_ingest(db_session, tg_mocks, monkeypatch) -> None:
    user = await _make_user(db_session)
    await _bind_account(db_session, user, 888)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.pdf", b"%PDF-A")
        z.writestr("b.pdf", b"%PDF-B")
    _mock_download(monkeypatch, buf.getvalue())
    update = {"message": {"chat": {"id": 888}, "document": {"file_id": "Z"}}}
    await telegram_ingest.process_update(db_session, FakeRedis(), update)
    assert await db_session.scalar(select(func.count()).select_from(Invoice)) == 2
    assert any("已入库 2 张" in t for _, t in tg_mocks)


async def test_photo_takes_largest(db_session, tg_mocks, monkeypatch) -> None:
    user = await _make_user(db_session)
    await _bind_account(db_session, user, 222)
    _mock_download(monkeypatch, b"\xff\xd8\xff fake jpeg", expect_file_id="BIG")
    update = {"message": {"chat": {"id": 222}, "photo": [{"file_id": "SMALL"}, {"file_id": "BIG"}]}}
    await telegram_ingest.process_update(db_session, FakeRedis(), update)
    inv = await db_session.scalar(select(Invoice))
    assert inv is not None and inv.source == "telegram"


async def test_file_when_not_bound(db_session, tg_mocks) -> None:
    update = {"message": {"chat": {"id": 999}, "document": {"file_id": "F"}}}
    await telegram_ingest.process_update(db_session, FakeRedis(), update)
    assert await db_session.scalar(select(func.count()).select_from(Invoice)) == 0
    assert any("还没绑定" in t for _, t in tg_mocks)


async def test_download_failure_graceful(db_session, tg_mocks, monkeypatch) -> None:
    user = await _make_user(db_session)
    await _bind_account(db_session, user, 333)
    _mock_download(monkeypatch, None)  # 下载失败/超 20MB
    update = {"message": {"chat": {"id": 333}, "document": {"file_id": "F"}}}
    await telegram_ingest.process_update(db_session, FakeRedis(), update)
    assert await db_session.scalar(select(func.count()).select_from(Invoice)) == 0
    assert any("下载失败" in t for _, t in tg_mocks)


async def test_plain_text_gets_help(db_session, tg_mocks) -> None:
    update = {"message": {"chat": {"id": 5}, "text": "你好"}}
    await telegram_ingest.process_update(db_session, FakeRedis(), update)
    assert any("自动入库" in t for _, t in tg_mocks)


async def test_non_message_update_ignored(db_session, tg_mocks) -> None:
    await telegram_ingest.process_update(db_session, FakeRedis(), {"edited_message": {}})
    assert tg_mocks == []  # 无回复、不崩
