'use client';

import Card from 'components/card';
import { useEffect, useState } from 'react';
import { MdDownload, MdRefresh, MdSend } from 'react-icons/md';
import {
  EXPORT_STATUS_LABELS,
  ExportSend,
  ExportSendStatus,
  ExportTask,
  ExportTaskStatus,
  SEND_STATUS_LABELS,
  getExportDownloadUrl,
  listExportSends,
  listExportTasks,
} from 'lib/exportTasks';
import SendModal from './SendModal';

const fmtTime = (iso: string): string => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(
    d.getHours(),
  )}:${p(d.getMinutes())}`;
};

const BADGE: Record<ExportTaskStatus, string> = {
  pending: 'bg-gray-100 text-gray-600 dark:bg-navy-700 dark:text-gray-300',
  processing:
    'animate-pulse bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400',
  completed:
    'bg-green-50 text-green-600 dark:bg-green-500/10 dark:text-green-400',
  failed: 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400',
};

const SEND_BADGE: Record<ExportSendStatus, string> = {
  pending: 'bg-gray-100 text-gray-600 dark:bg-navy-700 dark:text-gray-300',
  sending:
    'animate-pulse bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400',
  sent: 'bg-green-50 text-green-600 dark:bg-green-500/10 dark:text-green-400',
  failed: 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400',
};

export default function ExportTasksPage() {
  const [tasks, setTasks] = useState<ExportTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [sendFor, setSendFor] = useState<string | null>(null);
  const [sends, setSends] = useState<Record<string, ExportSend[]>>({});

  useEffect(() => {
    let active = true;
    const tick = async () => {
      try {
        const t = await listExportTasks();
        if (!active) return;
        setTasks(t);
        // 拉取已完成任务的发送记录：关掉发送弹窗后，这里仍能看到发往谁 / 成功失败
        const completed = t.filter((x) => x.status === 'completed');
        const entries = await Promise.all(
          completed.map(async (x) => {
            try {
              return [x.id, await listExportSends(x.id)] as const;
            } catch {
              return [x.id, [] as ExportSend[]] as const;
            }
          }),
        );
        if (active) setSends(Object.fromEntries(entries));
      } catch {
        /* ignore */
      } finally {
        if (active) setLoading(false);
      }
    };
    tick();
    // 轮询进度：有任务在生成时实时刷新状态
    const id = setInterval(tick, 4000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  async function download(id: string) {
    setBusy(id);
    try {
      const { url } = await getExportDownloadUrl(id);
      const a = document.createElement('a');
      a.href = url;
      a.click();
    } catch {
      /* ignore */
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mt-3">
      <Card extra="w-full px-6 pb-6">
        <div className="flex items-center justify-between pt-5">
          <div>
            <h2 className="text-lg font-bold text-navy-700 dark:text-white">
              导出任务
            </h2>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
              报销单在后台异步打包，完成后可在此下载（含对账 Excel + 原件）。
            </p>
          </div>
          <span className="flex items-center gap-1 text-xs text-gray-400">
            <MdRefresh className="h-4 w-4" /> 自动刷新
          </span>
        </div>

        {loading ? (
          <p className="mt-6 text-sm text-gray-400">加载中…</p>
        ) : tasks.length === 0 ? (
          <p className="mt-6 text-sm text-gray-400">
            还没有导出任务。在「发票管理」选中发票后点「导出报销单」即可创建。
          </p>
        ) : (
          <div className="mt-4 flex flex-col gap-3">
            {tasks.map((t) => {
              const taskSends = sends[t.id] ?? [];
              return (
                <div
                  key={t.id}
                  className="rounded-xl border border-gray-100 px-4 py-3 dark:border-white/10"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={`rounded-full px-3 py-1 text-xs font-medium ${
                            BADGE[t.status]
                          }`}
                        >
                          {EXPORT_STATUS_LABELS[t.status]}
                        </span>
                        <span className="text-sm font-medium text-navy-700 dark:text-white">
                          {t.invoice_count} 张发票
                        </span>
                        {t.mark_submitted && (
                          <span className="text-xs text-gray-400">
                            已标记报销中
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-gray-400">
                        创建于 {fmtTime(t.created_at)}
                        {t.status === 'failed' && t.error_message
                          ? ` · 失败：${t.error_message}`
                          : ''}
                      </span>
                    </div>
                    {t.status === 'completed' ? (
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => setSendFor(t.id)}
                          className="flex items-center gap-1 rounded-lg bg-gray-50 px-4 py-2 text-sm font-medium text-navy-700 transition hover:bg-gray-100 dark:bg-navy-700 dark:text-white dark:hover:bg-navy-600"
                        >
                          <MdSend className="h-4 w-4" />
                          发送
                        </button>
                        <button
                          type="button"
                          disabled={busy === t.id}
                          onClick={() => download(t.id)}
                          className="dark:bg-brand-500/10 flex items-center gap-1 rounded-lg bg-brand-50 px-4 py-2 text-sm font-medium text-brand-600 transition hover:bg-brand-100 disabled:opacity-50 dark:text-brand-400"
                        >
                          <MdDownload className="h-4 w-4" />
                          {busy === t.id ? '准备中…' : '下载报销单'}
                        </button>
                      </div>
                    ) : t.status === 'failed' ? (
                      <span className="text-xs text-red-400">生成失败</span>
                    ) : (
                      <span className="text-xs text-gray-400">生成中…</span>
                    )}
                  </div>

                  {/* 发送状态/历史：关掉弹窗后仍可见每次发往谁、成功还是失败 */}
                  {t.status === 'completed' && taskSends.length > 0 && (
                    <div className="mt-2 flex flex-col gap-1 border-t border-gray-100 pt-2 dark:border-white/10">
                      {taskSends.map((s) => (
                        <div
                          key={s.id}
                          className="flex flex-wrap items-center gap-2 text-xs"
                        >
                          <span
                            className={`rounded-full px-2 py-0.5 font-medium ${
                              SEND_BADGE[s.status]
                            }`}
                          >
                            {SEND_STATUS_LABELS[s.status]}
                          </span>
                          <span className="text-gray-500 dark:text-gray-400">
                            → {s.to_addresses.join('、')}
                          </span>
                          {s.status === 'sent' &&
                            s.delivery_mode === 'link' && (
                              <span className="text-gray-400">
                                （下载链接）
                              </span>
                            )}
                          {s.status === 'failed' && s.error_message && (
                            <span className="text-red-400">
                              · {s.error_message}
                            </span>
                          )}
                          <span className="text-gray-400">
                            · {fmtTime(s.created_at)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {sendFor && (
        <SendModal taskId={sendFor} onClose={() => setSendFor(null)} />
      )}
    </div>
  );
}
