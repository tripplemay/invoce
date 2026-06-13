'use client';
import Card from 'components/card';
import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { MdCloudUpload } from 'react-icons/md';

interface UploadItem {
  id: string;
  name: string;
  status: 'processing' | 'done';
}

export default function DashboardPage() {
  const [items, setItems] = useState<UploadItem[]>([]);

  const onDrop = useCallback((files: File[]) => {
    const next: UploadItem[] = files.map((f, idx) => ({
      id: `${Date.now()}-${idx}`,
      name: f.name,
      status: 'processing',
    }));
    setItems((prev) => [...next, ...prev]);
    // Mock：模拟异步识别完成
    next.forEach((it) =>
      setTimeout(
        () =>
          setItems((prev) =>
            prev.map((p) => (p.id === it.id ? { ...p, status: 'done' } : p)),
          ),
        2500,
      ),
    );
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/png': ['.png'],
      'image/jpeg': ['.jpg', '.jpeg'],
    },
  });

  return (
    <div className="mt-3 grid grid-cols-1 gap-5">
      <Card extra="w-full p-6">
        <h1 className="text-2xl font-bold text-navy-700 dark:text-white">工作台</h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
          拖拽或点击上传发票，自动进入识别队列
        </p>
        <div
          {...getRootProps()}
          className={`mt-5 flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed py-14 transition ${
            isDragActive
              ? 'border-brand-500 bg-brand-50 dark:bg-brand-500/10'
              : 'border-gray-300 hover:border-brand-400 dark:border-white/20'
          }`}
        >
          <input {...getInputProps()} />
          <MdCloudUpload className="text-5xl text-brand-500" />
          <p className="mt-3 text-base font-medium text-navy-700 dark:text-white">
            {isDragActive ? '松手即可上传' : '拖拽发票到此，或点击选择'}
          </p>
          <p className="mt-1 text-xs text-gray-500">支持 PDF / PNG / JPG，可批量</p>
        </div>
      </Card>

      <Card extra="w-full p-6">
        <h2 className="text-lg font-bold text-navy-700 dark:text-white">上传队列</h2>
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
                    识别中…
                  </span>
                ) : (
                  <span className="inline-flex items-center rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-600 dark:bg-green-500/10 dark:text-green-400">
                    已入库
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
