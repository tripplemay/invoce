'use client';
import Button from 'components/button';
import Dropdown from 'components/dropdown';
import InvoiceDrawer from 'components/invoices/InvoiceDrawer';
import InvoiceTable from 'components/invoices/InvoiceTable';
import { useCallback, useEffect, useState } from 'react';
import {
  bulkChangeStatus,
  bulkDeleteInvoices,
  changeReimbursementStatus,
  exportInvoices,
  listInvoices,
} from 'lib/invoices';
import { Invoice, REIMBURSEMENT_LABELS, ReimbursementStatus } from 'lib/types';

const BULK_STATUSES: ReimbursementStatus[] = [
  'unreimbursed',
  'submitted',
  'reimbursed',
];

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Invoice | null>(null);
  const [open, setOpen] = useState(false);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [showModal, setShowModal] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

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

  async function handleBulkStatus(status: ReimbursementStatus) {
    try {
      await bulkChangeStatus([...checked], status);
      setChecked(new Set());
      await refresh();
    } catch {
      /* ignore */
    }
  }

  async function handleBulkDelete() {
    setDeleting(true);
    try {
      await bulkDeleteInvoices([...checked]);
      setChecked(new Set());
      setShowDelete(false);
      await refresh();
    } catch {
      /* ignore */
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="mt-3">
      {checked.size > 0 && (
        <div className="dark:bg-brand-500/10 mb-3 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-brand-50 px-4 py-3">
          <span className="text-sm font-medium text-brand-700 dark:text-brand-300">
            已选 {checked.size} 张发票
          </span>
          <div className="flex flex-wrap items-center gap-2">
            <Dropdown
              button={<Button variant="secondary">改状态 ▾</Button>}
              classNames="top-11 right-0 w-40"
            >
              <div className="flex flex-col rounded-xl bg-white p-1.5 shadow-xl dark:bg-navy-700">
                {BULK_STATUSES.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => handleBulkStatus(s)}
                    className="rounded-lg px-3 py-2 text-left text-sm text-navy-700 transition hover:bg-gray-100 dark:text-white dark:hover:bg-navy-800"
                  >
                    {REIMBURSEMENT_LABELS[s]}
                  </button>
                ))}
              </div>
            </Dropdown>
            <button
              type="button"
              onClick={() => setShowDelete(true)}
              className="rounded-xl border border-red-200 px-5 py-2.5 text-sm font-medium text-red-600 transition hover:bg-red-50 dark:border-red-500/30 dark:text-red-400 dark:hover:bg-red-500/10"
            >
              删除
            </button>
            <Button onClick={() => setShowModal(true)}>导出报销单</Button>
          </div>
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

      {showDelete && (
        <div className="bg-black/40 fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-[440px] rounded-2xl bg-white p-6 shadow-2xl dark:bg-navy-800">
            <h3 className="text-lg font-bold text-navy-700 dark:text-white">
              删除发票
            </h3>
            <p className="mt-3 text-sm text-gray-600 dark:text-gray-300">
              确定删除选中的 {checked.size}{' '}
              张发票吗？此操作不可撤销，原件也会一并移除。
            </p>
            <div className="mt-6 flex flex-col gap-2">
              <button
                type="button"
                disabled={deleting}
                onClick={handleBulkDelete}
                className="w-full rounded-xl bg-red-500 px-6 py-3 text-sm font-medium text-white transition hover:bg-red-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {deleting ? '删除中…' : `确认删除 ${checked.size} 张`}
              </button>
              <Button
                variant="ghost"
                className="w-full"
                disabled={deleting}
                onClick={() => setShowDelete(false)}
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
