'use client';
import Button from 'components/button';
import InvoiceDrawer from 'components/invoices/InvoiceDrawer';
import InvoiceTable from 'components/invoices/InvoiceTable';
import { useCallback, useEffect, useState } from 'react';
import {
  changeReimbursementStatus,
  exportInvoices,
  listInvoices,
} from 'lib/invoices';
import { Invoice, ReimbursementStatus } from 'lib/types';

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Invoice | null>(null);
  const [open, setOpen] = useState(false);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [showModal, setShowModal] = useState(false);
  const [exporting, setExporting] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setInvoices(await listInvoices());
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const toggleSelect = useCallback((id: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleAll = useCallback((ids: string[], on: boolean) => {
    setChecked((prev) => {
      const next = new Set(prev);
      ids.forEach((id) => (on ? next.add(id) : next.delete(id)));
      return next;
    });
  }, []);

  const handleSelect = useCallback((invoice: Invoice) => {
    setSelected(invoice);
    setOpen(true);
  }, []);

  const handleAdvance = useCallback(
    async (invoice: Invoice) => {
      const next: ReimbursementStatus =
        invoice.reimbursement_status === 'unreimbursed'
          ? 'submitted'
          : 'reimbursed';
      try {
        await changeReimbursementStatus(invoice.id, next);
        await refresh();
      } catch {
        /* ignore */
      }
    },
    [refresh],
  );

  async function doExport(markSubmitted: boolean) {
    setExporting(true);
    try {
      await exportInvoices([...checked], markSubmitted);
      setChecked(new Set());
      setShowModal(false);
      await refresh();
    } catch {
      /* ignore */
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="mt-3">
      {checked.size > 0 && (
        <div className="dark:bg-brand-500/10 mb-3 flex items-center justify-between rounded-xl bg-brand-50 px-4 py-3">
          <span className="text-sm font-medium text-brand-700 dark:text-brand-300">
            已选 {checked.size} 张发票
          </span>
          <Button onClick={() => setShowModal(true)}>导出报销单</Button>
        </div>
      )}

      {loading ? (
        <p className="p-6 text-sm text-gray-400">加载中…</p>
      ) : (
        <InvoiceTable
          data={invoices}
          onSelect={handleSelect}
          onAdvanceStatus={handleAdvance}
          selectedIds={checked}
          onToggleSelect={toggleSelect}
          onToggleAll={toggleAll}
        />
      )}

      <InvoiceDrawer
        invoice={selected}
        open={open}
        onClose={() => setOpen(false)}
        onSaved={refresh}
      />

      {showModal && (
        <div className="bg-black/40 fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-[440px] rounded-2xl bg-white p-6 shadow-2xl dark:bg-navy-800">
            <h3 className="text-lg font-bold text-navy-700 dark:text-white">
              导出报销单
            </h3>
            <p className="mt-3 text-sm text-gray-600 dark:text-gray-300">
              报销单 Excel 与原件将打包为 ZIP 下载。是否同步将选中的{' '}
              {checked.size} 张发票状态变更为「报销中」？
            </p>
            <div className="mt-6 flex flex-col gap-2">
              <Button
                className="w-full"
                disabled={exporting}
                onClick={() => doExport(true)}
              >
                {exporting ? '导出中…' : '导出并标记为「报销中」'}
              </Button>
              <Button
                variant="secondary"
                className="w-full"
                disabled={exporting}
                onClick={() => doExport(false)}
              >
                仅导出，不改状态
              </Button>
              <Button
                variant="ghost"
                className="w-full"
                disabled={exporting}
                onClick={() => setShowModal(false)}
              >
                取消
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
