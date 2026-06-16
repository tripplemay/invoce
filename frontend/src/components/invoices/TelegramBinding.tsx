'use client';

import Button from 'components/button';
import Card from 'components/card';
import { useEffect, useState } from 'react';
import { MdDelete } from 'react-icons/md';
import {
  TelegramAccount,
  TelegramLink,
  createTelegramLink,
  getTelegramAccount,
  unlinkTelegram,
} from 'lib/telegram';

export default function TelegramBinding() {
  const [account, setAccount] = useState<TelegramAccount | null>(null);
  const [link, setLink] = useState<TelegramLink | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setAccount(await getTelegramAccount());
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function generate() {
    setError('');
    setBusy(true);
    try {
      setLink(await createTelegramLink());
    } catch (e) {
      setError(
        e instanceof Error ? e.message : 'Telegram 功能未配置或生成失败',
      );
    } finally {
      setBusy(false);
    }
  }

  async function unlink() {
    try {
      await unlinkTelegram();
      setAccount(null);
      setLink(null);
      await refresh();
    } catch {
      /* ignore */
    }
  }

  return (
    <Card extra="w-full p-6">
      <h2 className="text-lg font-bold text-navy-700 dark:text-white">
        Telegram Bot 自动入库
      </h2>
      <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
        绑定后，把发票文件（PDF / 图片 / ZIP）发给 bot 即自动入库。要保留原始
        PDF 请用「文件」方式发送（「照片」会被 Telegram 压缩）。
      </p>

      {account ? (
        <div className="mt-4 flex items-center justify-between rounded-xl border border-green-100 bg-green-50 px-4 py-3 dark:border-green-500/20 dark:bg-green-500/10">
          <span className="text-sm font-medium text-green-700 dark:text-green-300">
            ✅ 已绑定{' '}
            {account.username
              ? `@${account.username}`
              : `chat ${account.chat_id}`}
          </span>
          <button
            type="button"
            onClick={unlink}
            aria-label="解绑"
            className="rounded-lg p-1.5 text-red-500 hover:bg-red-100 dark:hover:bg-red-500/10"
          >
            <MdDelete size={18} />
          </button>
        </div>
      ) : link ? (
        <div className="mt-4 rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-white/10 dark:bg-navy-900">
          <p className="text-sm font-medium text-navy-700 dark:text-white">
            在装有 Telegram 的设备上点开下方按钮，会自动发送绑定指令完成绑定：
          </p>
          <a
            href={link.deep_link}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-600 dark:bg-brand-400"
          >
            在 Telegram 中打开并绑定
          </a>
          <p className="mt-3 break-all rounded-lg bg-white px-3 py-2 font-mono text-xs text-navy-700 dark:bg-navy-800 dark:text-gray-200">
            {link.deep_link}
          </p>
          <div className="mt-3 flex items-center justify-between gap-3">
            <span className="text-xs text-gray-600 dark:text-gray-300">
              链接 {Math.round(link.expires_in / 60)} 分钟内有效
            </span>
            <button
              type="button"
              onClick={refresh}
              className="text-xs font-medium text-brand-600 hover:underline dark:text-brand-400"
            >
              我已绑定，刷新状态
            </button>
          </div>
        </div>
      ) : (
        <Button className="mt-4 self-start" onClick={generate} disabled={busy}>
          {busy ? '生成中…' : '生成绑定链接'}
        </Button>
      )}
      {error && <p className="mt-2 text-sm text-red-500">{error}</p>}
    </Card>
  );
}
