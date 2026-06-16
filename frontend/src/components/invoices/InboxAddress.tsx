'use client';

import Card from 'components/card';
import { useEffect, useState } from 'react';
import { MdContentCopy, MdCheck } from 'react-icons/md';
import { Inbox, getInbox } from 'lib/inbox';

export default function InboxAddress() {
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    getInbox()
      .then(setInbox)
      .catch(() => {
        /* ignore */
      });
  }, []);

  async function copy() {
    if (!inbox?.address) return;
    try {
      await navigator.clipboard.writeText(inbox.address);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* 剪贴板不可用时忽略 */
    }
  }

  return (
    <Card extra="w-full p-6">
      <h2 className="text-lg font-bold text-navy-700 dark:text-white">
        专属收票邮箱
      </h2>
      <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
        把这个地址填到电商/商家开票时的「收票邮箱」，或直接转发发票邮件到这里，发票会自动入库。
      </p>

      {inbox?.enabled && inbox.address ? (
        <div className="mt-4 flex items-center justify-between gap-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 dark:border-white/10 dark:bg-navy-900">
          <span className="break-all font-mono text-sm text-navy-700 dark:text-gray-200">
            {inbox.address}
          </span>
          <button
            type="button"
            onClick={copy}
            aria-label="复制地址"
            className="flex shrink-0 items-center gap-1 rounded-lg px-2.5 py-1.5 text-sm font-medium text-brand-600 hover:bg-brand-50 dark:text-brand-400 dark:hover:bg-brand-400/10"
          >
            {copied ? <MdCheck size={18} /> : <MdContentCopy size={18} />}
            {copied ? '已复制' : '复制'}
          </button>
        </div>
      ) : (
        <div className="mt-4 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:border-white/10 dark:bg-navy-900 dark:text-gray-300">
          收票邮箱功能尚未开启，请联系管理员配置收票域名。
        </div>
      )}
    </Card>
  );
}
