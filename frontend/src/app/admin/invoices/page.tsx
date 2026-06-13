'use client';
import InvoiceDrawer from 'components/invoices/InvoiceDrawer';
import InvoiceTable from 'components/invoices/InvoiceTable';
import { useCallback, useEffect, useState } from 'react';
import { changeReimbursementStatus, listInvoices } from 'lib/invoices';
import { Invoice, ReimbursementStatus } from 'lib/types';

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Invoice | null>(null);
  const [open, setOpen] = useState(false);

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

  function handleSelect(invoice: Invoice) {
    setSelected(invoice);
    setOpen(true);
  }

  async function handleAdvance(invoice: Invoice) {
    const next: ReimbursementStatus =
      invoice.reimbursement_status === 'unreimbursed' ? 'submitted' : 'reimbursed';
    try {
      await changeReimbursementStatus(invoice.id, next);
      await refresh();
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="mt-3">
      {loading ? (
        <p className="p-6 text-sm text-gray-400">加载中…</p>
      ) : (
        <InvoiceTable data={invoices} onSelect={handleSelect} onAdvanceStatus={handleAdvance} />
      )}
      <InvoiceDrawer
        invoice={selected}
        open={open}
        onClose={() => setOpen(false)}
        onSaved={refresh}
      />
    </div>
  );
}
