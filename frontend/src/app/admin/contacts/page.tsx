'use client';

import Button from 'components/button';
import Card from 'components/card';
import { useEffect, useState } from 'react';
import { MdDelete, MdPersonAdd } from 'react-icons/md';
import {
  Contact,
  createContact,
  deleteContact,
  listContacts,
} from 'lib/contacts';

const inputCls =
  'h-11 w-full rounded-xl border border-gray-200 bg-white/0 px-3 text-sm outline-none focus:border-brand-400 dark:border-white/10 dark:text-white';

export default function ContactsPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setContacts(await listContacts());
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function add() {
    if (!name.trim() || !email.trim()) {
      setError('请填写姓名与邮箱');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createContact({
        name: name.trim(),
        email: email.trim(),
        note: note.trim() || null,
      });
      setName('');
      setEmail('');
      setNote('');
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : '添加失败');
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: string) {
    try {
      await deleteContact(id);
      await refresh();
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="mt-3">
      <Card extra="w-full px-6 pb-6">
        <div className="pt-5">
          <h2 className="text-lg font-bold text-navy-700 dark:text-white">
            通讯录
          </h2>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            维护下游处理人（财务 / 审批）的收件邮箱，发送报销单时可直接勾选。
          </p>
        </div>

        {/* 新增表单 */}
        <div className="mt-5 flex flex-col gap-3 rounded-xl border border-gray-100 p-4 dark:border-white/10 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label className="ml-1 text-xs font-medium text-gray-500">
              姓名
            </label>
            <input
              className={`mt-1 ${inputCls}`}
              placeholder="如：财务张三"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="flex-1">
            <label className="ml-1 text-xs font-medium text-gray-500">
              邮箱
            </label>
            <input
              className={`mt-1 ${inputCls}`}
              placeholder="finance@corp.com"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="flex-1">
            <label className="ml-1 text-xs font-medium text-gray-500">
              备注（可选）
            </label>
            <input
              className={`mt-1 ${inputCls}`}
              placeholder="如：月度报销审批"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
          <Button
            onClick={add}
            disabled={saving}
            className="flex items-center gap-1 whitespace-nowrap"
          >
            <MdPersonAdd className="h-4 w-4" />
            {saving ? '添加中…' : '添加'}
          </Button>
        </div>
        {error && <p className="mt-2 text-sm text-red-500">{error}</p>}

        {/* 列表 */}
        {loading ? (
          <p className="mt-6 text-sm text-gray-400">加载中…</p>
        ) : contacts.length === 0 ? (
          <p className="mt-6 text-sm text-gray-400">
            还没有联系人。在上方添加下游处理人后即可在发送报销单时选用。
          </p>
        ) : (
          <div className="mt-4 flex flex-col gap-2">
            {contacts.map((c) => (
              <div
                key={c.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-gray-100 px-4 py-3 dark:border-white/10"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-navy-700 dark:text-white">
                      {c.name}
                    </span>
                    {c.note && (
                      <span className="truncate text-xs text-gray-400">
                        {c.note}
                      </span>
                    )}
                  </div>
                  <span className="text-xs text-gray-500">{c.email}</span>
                </div>
                <button
                  type="button"
                  onClick={() => remove(c.id)}
                  className="flex items-center gap-1 rounded-lg px-3 py-2 text-sm text-red-500 transition hover:bg-red-50 dark:hover:bg-red-500/10"
                >
                  <MdDelete className="h-4 w-4" />
                  删除
                </button>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
