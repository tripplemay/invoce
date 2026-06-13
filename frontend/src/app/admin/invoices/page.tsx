'use client';
import { useState } from 'react';
import InvoiceDrawer from 'components/invoices/InvoiceDrawer';
import InvoiceTable from 'components/invoices/InvoiceTable';
import { MOCK_INVOICES } from 'lib/mock';
import { Invoice } from 'lib/types';

export default function InvoicesPage() {
  const [selected, setSelected] = useState<Invoice | null>(null);
  const [open, setOpen] = useState(false);

  function handleSelect(invoice: Invoice) {
    setSelected(invoice);
    setOpen(true);
  }

  return (
    <div className="mt-3">
      <InvoiceTable data={MOCK_INVOICES} onSelect={handleSelect} />
      <InvoiceDrawer invoice={selected} open={open} onClose={() => setOpen(false)} />
    </div>
  );
}
