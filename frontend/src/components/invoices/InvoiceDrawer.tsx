'use client';

import { useEffect, useState } from 'react';
import { MdClose } from 'react-icons/md';
import { Invoice } from 'lib/types';

interface Props {
  invoice: Invoice | null;
  open: boolean;
  onClose: () => void;
}

const FIELDS: { key: keyof Invoice; label: string }[] = [
  { key: 'issue_date', label: '开票日期' },
  { key: 'invoice_type', label: '发票类型' },
  { key: 'invoice_code', label: '发票代码' },
  { key: 'invoice_number', label: '发票号码' },
  { key: 'seller_name', label: '开票方' },
  { key: 'buyer_name', label: '购买方抬头' },
  { key: 'total_amount', label: '价税合计' },
  { key: 'category', label: '归属分类' },
];

export default function InvoiceDrawer({ invoice, open, onClose }: Props) {
  const [form, setForm] = useState<Record<string, string>>({});

  useEffect(() => {
    if (invoice) {
      const next: Record<string, string> = {};
      for (const f of FIELDS) {
        const v = invoice[f.key];
        next[f.key] = v == null ? '' : String(v);
      }
      setForm(next);
    }
  }, [invoice]);

  return (
    <>
      {/* 遮罩 */}
      <div
        className={`fixed inset-0 z-40 bg-black/40 transition-opacity duration-300 ${
          open ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
        onClick={onClose}
      />
      {/* 右侧抽屉，占屏 50% */}
      <aside
        className={`fixed right-0 top-0 z-50 h-full w-full transform bg-white shadow-2xl transition-transform duration-300 dark:bg-navy-800 md:w-1/2 ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-white/10">
          <h3 className="text-lg font-bold text-navy-700 dark:text-white">发票校对</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1 text-gray-500 hover:bg-gray-100 dark:hover:bg-navy-700"
          >
            <MdClose size={22} />
          </button>
        </div>

        <div className="grid h-[calc(100%-64px)] grid-cols-1 gap-0 overflow-y-auto md:grid-cols-2">
          {/* 左：原件预览区（占位） */}
          <div className="flex min-h-[300px] items-center justify-center border-b border-gray-200 bg-gray-50 p-6 dark:border-white/10 dark:bg-navy-900 md:border-b-0 md:border-r">
            <div className="text-center text-sm text-gray-400">
              <div className="mb-2 text-5xl">🧾</div>
              发票原件预览区
              <div className="mt-1 text-xs">（阶段3 接入 PDF/图片渲染 + 缩放）</div>
            </div>
          </div>

          {/* 右：结构化可编辑表单 */}
          <div className="p-6">
            <div className="grid grid-cols-1 gap-4">
              {FIELDS.map((f) => (
                <div key={f.key}>
                  <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-300">
                    {f.label}
                  </label>
                  <input
                    value={form[f.key] ?? ''}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, [f.key]: e.target.value }))
                    }
                    placeholder={invoice?.status === 'processing' ? '识别中…' : ''}
                    className="w-full rounded-xl border border-gray-200 bg-white/0 p-2.5 text-sm outline-none focus:border-brand-500 dark:border-white/10 dark:text-white"
                  />
                </div>
              ))}
            </div>
            <button
              type="button"
              className="linear mt-6 w-full rounded-xl bg-brand-500 py-3 text-sm font-medium text-white hover:bg-brand-600 dark:bg-brand-400"
            >
              确认入库
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
