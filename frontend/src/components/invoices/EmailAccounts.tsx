'use client';

import Card from 'components/card';
import { useEffect, useState } from 'react';
import { MdDelete } from 'react-icons/md';
import {
  createEmailAccount,
  deleteEmailAccount,
  EmailAccount,
  listEmailAccounts,
} from 'lib/emailAccounts';

export default function EmailAccounts() {
  const [accounts, setAccounts] = useState<EmailAccount[]>([]);
  const [imapUser, setImapUser] = useState('');
  const [authCode, setAuthCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setAccounts(await listEmailAccounts());
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await createEmailAccount({ imap_user: imapUser, auth_code: authCode });
      setImapUser('');
      setAuthCode('');
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : '添加失败');
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    try {
      await deleteEmailAccount(id);
      await refresh();
    } catch {
      /* ignore */
    }
  }

  return (
    <Card extra="w-full p-6">
      <h2 className="text-lg font-bold text-navy-700 dark:text-white">QQ 邮箱自动归集</h2>
      <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
        添加邮箱后，系统每 30 分钟自动拉取未读发票邮件（需在 QQ 邮箱「设置-账户」生成 16 位授权码）
      </p>

      <form onSubmit={add} className="mt-4 flex flex-col gap-3 md:flex-row">
        <input
          value={imapUser}
          onChange={(e) => setImapUser(e.target.value)}
          placeholder="QQ 邮箱号 (xxx@qq.com)"
          className="flex-1 rounded-xl border border-gray-200 bg-white/0 p-2.5 text-sm outline-none focus:border-brand-500 dark:border-white/10 dark:text-white"
        />
        <input
          value={authCode}
          onChange={(e) => setAuthCode(e.target.value)}
          type="password"
          placeholder="16 位授权码"
          className="flex-1 rounded-xl border border-gray-200 bg-white/0 p-2.5 text-sm outline-none focus:border-brand-500 dark:border-white/10 dark:text-white"
        />
        <button
          type="submit"
          disabled={busy || !imapUser || !authCode}
          className="linear rounded-xl bg-brand-500 px-6 py-2.5 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50 dark:bg-brand-400"
        >
          {busy ? '添加中…' : '添加'}
        </button>
      </form>
      {error && <p className="mt-2 text-sm text-red-500">{error}</p>}

      <div className="mt-4 flex flex-col gap-2">
        {accounts.length === 0 ? (
          <p className="text-sm text-gray-400">尚未添加邮箱</p>
        ) : (
          accounts.map((a) => (
            <div
              key={a.id}
              className="flex items-center justify-between rounded-xl border border-gray-100 px-4 py-3 dark:border-white/10"
            >
              <span className="text-sm font-medium text-navy-700 dark:text-white">
                {a.imap_user}
                <span className="ml-2 text-xs text-gray-400">{a.imap_host}</span>
              </span>
              <button
                type="button"
                onClick={() => remove(a.id)}
                className="rounded-lg p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10"
              >
                <MdDelete size={18} />
              </button>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
