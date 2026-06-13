'use client';

import { useEffect, useState } from 'react';
import { MdClose } from 'react-icons/md';
import { checkDuplicate, getPreview, updateInvoice } from 'lib/invoices';
import { Invoice } from 'lib/types';

interface Props {
  invoice: Invoice | null;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
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

export default function InvoiceDrawer({ invoice, open, onClose, onSaved }: Props) {
  const [form, setForm] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState('');
  const [dupWarn, setDupWarn] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!invoice) return;
    const next: Record<string, string> = {};
    for (const f of FIELDS) {
      const v = invoice[f.key];
      next[f.key] = v == null ? '' : String(v);
    }
    setForm(next);
    setDupWarn('');
    setError('');
  }, [invoice]);

  // 预览：拉取 60s 预签名 URL，并在过期前自动续签
  useEffect(() => {
    if (!open || !invoice) return;
    let active = true;
    const load = async () => {
      try {
        const p = await getPreview(invoice.id);
        if (active) setPreview(p.url);
      } catch {
        /* 预览不可用时忽略 */
      }
    };
    load();
    const timer = setInterval(load, 50000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [open, invoice]);

  async function handleNumberBlur() {
    if (!invoice || !form.invoice_number) {
      setDupWarn('');
      return;
    }
    try {
      const r = await checkDuplicate(form.invoice_number, form.invoice_code || null, invoice.id);
      setDupWarn(
        r.duplicate ? `该发票已于 ${r.existing_date} 录入系统，存在重复报销风险！` : '',
      );
    } catch {
      /* ignore */
    }
  }

  async function handleSave() {
    if (!invoice || dupWarn) return;
    setSaving(true);
    setError('');
    try {
      await updateInvoice(invoice.id, {
        invoice_code: form.invoice_code || null,
        invoice_number: form.invoice_number || null,
        issue_date: form.issue_date || null,
        invoice_type: form.invoice_type || null,
        seller_name: form.seller_name || null,
        buyer_name: form.buyer_name || null,
        total_amount: form.total_amount || null,
        category: form.category || null,
      });
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败');
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div
        className={`fixed inset-0 z-40 bg-black/40 transition-opacity duration-300 ${
          open ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
        onClick={onClose}
      />
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

        <div className="grid h-[calc(100%-64px)] grid-cols-1 overflow-y-auto md:grid-cols-2">
          {/* 左：原件预览（60s 预签名，自动续签） */}
          <div className="min-h-[300px] border-b border-gray-200 bg-gray-50 dark:border-white/10 dark:bg-navy-900 md:border-b-0 md:border-r">
            {preview ? (
              <iframe title="发票原件" src={preview} className="h-full min-h-[400px] w-full" />
            ) : (
              <div className="flex h-full min-h-[300px] items-center justify-center text-center text-sm text-gray-400">
                <div>
                  <div className="mb-2 text-5xl">🧾</div>
                  原件加载中 / 暂不可用
                </div>
              </div>
            )}
          </div>

          {/* 右：结构化可编辑表单 */}
          <div className="p-6">
            {dupWarn && (
              <div className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm font-medium text-red-600 dark:bg-red-500/10 dark:text-red-400">
                ⚠️ {dupWarn}
              </div>
            )}
            {error && (
              <div className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600 dark:bg-red-500/10 dark:text-red-400">
                {error}
              </div>
            )}
            <div className="grid grid-cols-1 gap-4">
              {FIELDS.map((f) => {
                const isNumber = f.key === 'invoice_number';
                return (
                  <div key={f.key}>
                    <label className="mb-1 block text-xs font-medium text-gray-600 dark:text-gray-300">
                      {f.label}
                    </label>
                    <input
                      value={form[f.key] ?? ''}
                      onChange={(e) =>
                        setForm((prev) => ({ ...prev, [f.key]: e.target.value }))
                      }
                      onBlur={isNumber ? handleNumberBlur : undefined}
                      className={`w-full rounded-xl border bg-white/0 p-2.5 text-sm outline-none dark:text-white ${
                        isNumber && dupWarn
                          ? 'border-red-500 text-red-600'
                          : 'border-gray-200 focus:border-brand-500 dark:border-white/10'
                      }`}
                    />
                  </div>
                );
              })}
            </div>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || Boolean(dupWarn)}
              className="linear mt-6 w-full rounded-xl bg-brand-500 py-3 text-sm font-medium text-white hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-brand-400"
            >
              {saving ? '保存中…' : '确认入库'}
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
