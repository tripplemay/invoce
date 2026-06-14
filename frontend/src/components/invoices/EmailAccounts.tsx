'use client';

import Button from 'components/button';
import Card from 'components/card';
import InputField from 'components/fields/InputField';
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
      <h2 className="text-lg font-bold text-navy-700 dark:text-white">
        QQ 邮箱自动归集
      </h2>
      <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
        添加邮箱后，系统每 30 分钟自动拉取未读发票邮件（需在 QQ
        邮箱「设置-账户」生成 16 位授权码）
      </p>

      <form onSubmit={add} className="mt-4 flex flex-col gap-3">
        <div className="flex flex-col gap-3 md:flex-row">
          <InputField
            id="imap_user"
            label="QQ 邮箱号"
            extra="flex-1"
            placeholder="xxx@qq.com"
            value={imapUser}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setImapUser(e.target.value)
            }
          />
          <InputField
            id="auth_code"
            label="16 位授权码"
            type="password"
            extra="flex-1"
            placeholder="在 QQ 邮箱设置中生成"
            value={authCode}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setAuthCode(e.target.value)
            }
          />
        </div>
        <Button
          type="submit"
          className="self-start"
          disabled={busy || !imapUser || !authCode}
        >
          {busy ? '添加中…' : '添加'}
        </Button>
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
                <span className="ml-2 text-xs text-gray-400">
                  {a.imap_host}
                </span>
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
