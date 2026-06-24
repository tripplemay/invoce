'use client';

import Button from 'components/button';
import { useEffect, useState } from 'react';
import { Contact, listContacts } from 'lib/contacts';
import {
  ExportSend,
  SEND_STATUS_LABELS,
  listExportSends,
  sendExportTask,
} from 'lib/exportTasks';

interface Props {
  taskId: string;
  onClose: () => void;
}

function splitEmails(raw: string): string[] {
  return raw
    .split(/[,\s;]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function SendModal({ taskId, onClose }: Props) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [extra, setExtra] = useState('');
  const [note, setNote] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ExportSend | null>(null);

  useEffect(() => {
    listContacts()
      .then(setContacts)
      .catch(() => {
        /* ignore */
      });
  }, []);

  // 提交后轮询发送状态，直至 sent/失败
  useEffect(() => {
    if (!result || result.status === 'sent' || result.status === 'failed') {
      return;
    }
    const id = setInterval(async () => {
      try {
        const sends = await listExportSends(taskId);
        const mine = sends.find((s) => s.id === result.id);
        if (mine) setResult(mine);
      } catch {
        /* ignore */
      }
    }, 3000);
    return () => clearInterval(id);
  }, [result, taskId]);

  const extraEmails = splitEmails(extra);
  const canSend = picked.size > 0 || extraEmails.length > 0;

  function toggle(id: string) {
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function submit() {
    setSending(true);
    setError(null);
    try {
      const rec = await sendExportTask(taskId, {
        contact_ids: [...picked],
        emails: extraEmails,
        note: note.trim() || undefined,
      });
      setResult(rec);
    } catch (e) {
      setError(e instanceof Error ? e.message : '发送失败');
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="bg-black/40 fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="flex max-h-[85vh] w-full max-w-[480px] flex-col rounded-2xl bg-white p-6 shadow-2xl dark:bg-navy-800">
        <h3 className="text-lg font-bold text-navy-700 dark:text-white">
          发送报销单
        </h3>

        {result ? (
          // 发送结果视图
          <div className="mt-4">
            <p className="text-sm text-gray-600 dark:text-gray-300">
              已提交发送给：{result.to_addresses.join('、')}
            </p>
            <div className="mt-3 flex items-center gap-2">
              <span className="text-sm font-medium text-navy-700 dark:text-white">
                状态：{SEND_STATUS_LABELS[result.status]}
              </span>
              {(result.status === 'pending' ||
                result.status === 'sending') && (
                <span className="text-xs text-gray-400">处理中…</span>
              )}
            </div>
            {result.status === 'sent' && result.delivery_mode === 'link' && (
              <p className="mt-2 text-xs text-gray-400">
                文件较大，已以下载链接形式发送。
              </p>
            )}
            {result.status === 'failed' && (
              <p className="mt-2 text-sm text-red-500">
                {result.error_message || '发送失败，请稍后重试'}
              </p>
            )}
            <Button className="mt-6 w-full" onClick={onClose}>
              关闭
            </Button>
          </div>
        ) : (
          // 发送表单视图
          <>
            <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
              选择下游处理人，把报销单（对账 Excel + 发票原件）发到其邮箱。
            </p>

            <div className="mt-4 flex-1 overflow-y-auto">
              {contacts.length === 0 ? (
                <p className="text-sm text-gray-400">
                  通讯录为空，可在下方临时填写收件邮箱，或先到「通讯录」添加联系人。
                </p>
              ) : (
                <div className="flex flex-col gap-1">
                  {contacts.map((c) => (
                    <label
                      key={c.id}
                      className="flex cursor-pointer items-center gap-3 rounded-lg px-2 py-2 hover:bg-gray-50 dark:hover:bg-navy-700"
                    >
                      <input
                        type="checkbox"
                        checked={picked.has(c.id)}
                        onChange={() => toggle(c.id)}
                        className="h-4 w-4 accent-brand-500"
                      />
                      <span className="text-sm text-navy-700 dark:text-white">
                        {c.name}
                      </span>
                      <span className="text-xs text-gray-400">{c.email}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-4">
              <label className="ml-1 text-xs font-medium text-gray-500">
                临时邮箱（可选，多个用逗号分隔）
              </label>
              <input
                className="mt-1 h-11 w-full rounded-xl border border-gray-200 bg-white/0 px-3 text-sm outline-none focus:border-brand-400 dark:border-white/10 dark:text-white"
                placeholder="someone@corp.com"
                value={extra}
                onChange={(e) => setExtra(e.target.value)}
              />
            </div>

            <div className="mt-3">
              <label className="ml-1 text-xs font-medium text-gray-500">
                备注（可选，附在邮件正文）
              </label>
              <input
                className="mt-1 h-11 w-full rounded-xl border border-gray-200 bg-white/0 px-3 text-sm outline-none focus:border-brand-400 dark:border-white/10 dark:text-white"
                placeholder="如：本月差旅报销，请审批"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </div>

            {error && <p className="mt-3 text-sm text-red-500">{error}</p>}

            <div className="mt-6 flex flex-col gap-2">
              <Button
                className="w-full"
                disabled={sending || !canSend}
                onClick={submit}
              >
                {sending ? '提交中…' : '发送'}
              </Button>
              <Button
                variant="ghost"
                className="w-full"
                disabled={sending}
                onClick={onClose}
              >
                取消
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
