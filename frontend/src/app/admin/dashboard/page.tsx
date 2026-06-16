'use client';
import Card from 'components/card';
import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { MdCloudUpload } from 'react-icons/md';
import EmailAccounts from 'components/invoices/EmailAccounts';
import TelegramBinding from 'components/invoices/TelegramBinding';
import { uploadInvoices } from 'lib/invoices';

interface UploadItem {
  id: string;
  name: string;
  status: 'processing' | 'done' | 'failed';
}

export default function DashboardPage() {
  const [items, setItems] = useState<UploadItem[]>([]);
  const [error, setError] = useState('');

  const onDrop = useCallback(async (files: File[]) => {
    if (files.length === 0) return;
    setError('');
    const pending: UploadItem[] = files.map((f, idx) => ({
      id: `tmp-${Date.now()}-${idx}`,
      name: f.name,
      status: 'processing',
    }));
    const ids = new Set(pending.map((p) => p.id));
    setItems((prev) => [...pending, ...prev]);
    try {
      await uploadInvoices(files);
      setItems((prev) =>
        prev.map((p) => (ids.has(p.id) ? { ...p, status: 'done' } : p)),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : '上传失败');
      setItems((prev) =>
        prev.map((p) => (ids.has(p.id) ? { ...p, status: 'failed' } : p)),
      );
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/png': ['.png'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'application/zip': ['.zip'],
      'application/x-zip-compressed': ['.zip'],
    },
  });

  return (
    <div className="mt-3 grid grid-cols-1 gap-5">
      <Card extra="w-full p-6">
        <h1 className="text-2xl font-bold text-navy-700 dark:text-white">
          工作台
        </h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
          拖拽或点击上传发票，自动进入识别队列
        </p>
        <div
          {...getRootProps()}
          className={`mt-5 flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed py-14 transition ${
            isDragActive
              ? 'dark:bg-brand-500/10 border-brand-500 bg-brand-50'
              : 'border-gray-300 hover:border-brand-400 dark:border-white/20'
          }`}
        >
          <input {...getInputProps()} />
          <MdCloudUpload className="text-5xl text-brand-500" />
          <p className="mt-3 text-base font-medium text-navy-700 dark:text-white">
            {isDragActive ? '松手即可上传' : '拖拽发票到此，或点击选择'}
          </p>
          <p className="mt-1 text-xs text-gray-500">
            支持 PDF / PNG / JPG / ZIP（如京东批量发票包，自动解出每张），可批量
          </p>
        </div>
        {error && <p className="mt-3 text-sm text-red-500">{error}</p>}
      </Card>

      <Card extra="w-full p-6">
        <h2 className="text-lg font-bold text-navy-700 dark:text-white">
          上传队列
        </h2>
        {items.length === 0 ? (
          <p className="mt-4 text-sm text-gray-400">暂无上传记录</p>
        ) : (
          <div className="mt-4 flex flex-col gap-2">
            {items.map((it) => (
              <div
                key={it.id}
                className="flex items-center justify-between rounded-xl border border-gray-100 px-4 py-3 dark:border-white/10"
              >
                <span className="truncate text-sm font-medium text-navy-700 dark:text-white">
                  {it.name}
                </span>
                {it.status === 'processing' ? (
                  <span className="inline-flex animate-pulse items-center rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
                    上传中…
                  </span>
                ) : it.status === 'done' ? (
                  <span className="inline-flex items-center rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-600 dark:bg-green-500/10 dark:text-green-400">
                    已入库
                  </span>
                ) : (
                  <span className="inline-flex items-center rounded-full bg-red-50 px-3 py-1 text-xs font-medium text-red-600 dark:bg-red-500/10 dark:text-red-400">
                    失败
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <EmailAccounts />
      <TelegramBinding />
    </div>
  );
}
