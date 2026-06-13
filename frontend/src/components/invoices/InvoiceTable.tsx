'use client';

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  SortingState,
  useReactTable,
} from '@tanstack/react-table';
import Card from 'components/card';
import { useState } from 'react';
import {
  Invoice,
  ReimbursementStatus,
  SOURCE_LABELS,
  STATUS_LABELS,
} from 'lib/types';
import StatusBadge from './StatusBadge';

const NEXT_STATUS: Record<ReimbursementStatus, ReimbursementStatus | null> = {
  unreimbursed: 'submitted',
  submitted: 'reimbursed',
  reimbursed: null,
};
const NEXT_LABEL: Record<ReimbursementStatus, string> = {
  unreimbursed: '标记报销中',
  submitted: '标记已到账',
  reimbursed: '',
};

const TABS: { key: string; label: string; match: (i: Invoice) => boolean }[] = [
  { key: 'all', label: '全部', match: () => true },
  {
    key: 'unreimbursed',
    label: '待报销',
    match: (i) => i.reimbursement_status === 'unreimbursed',
  },
  {
    key: 'submitted',
    label: '报销中',
    match: (i) => i.reimbursement_status === 'submitted',
  },
  {
    key: 'reimbursed',
    label: '已完成',
    match: (i) => i.reimbursement_status === 'reimbursed',
  },
];

const columnHelper = createColumnHelper<Invoice>();
const HEAD = 'text-xs font-bold uppercase text-gray-500 dark:text-gray-400';
const CELL = 'text-sm font-medium text-navy-700 dark:text-white';
const dash = (v: string | null) => (v == null || v === '' ? '—' : v);

interface Props {
  data: Invoice[];
  onSelect: (i: Invoice) => void;
  onAdvanceStatus: (i: Invoice) => void;
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onToggleAll: (ids: string[], checked: boolean) => void;
}

export default function InvoiceTable({
  data,
  onSelect,
  onAdvanceStatus,
  selectedIds,
  onToggleSelect,
  onToggleAll,
}: Props) {
  const [tab, setTab] = useState('all');
  const [sorting, setSorting] = useState<SortingState>([]);
  const filtered = data.filter(TABS.find((t) => t.key === tab)!.match);

  const columns = [
    columnHelper.display({
      id: 'select',
      header: () => (
        <input
          type="checkbox"
          className="h-4 w-4 cursor-pointer accent-brand-500"
          checked={
            filtered.length > 0 && filtered.every((i) => selectedIds.has(i.id))
          }
          onChange={(e) =>
            onToggleAll(
              filtered.map((i) => i.id),
              e.target.checked,
            )
          }
        />
      ),
      cell: (info) => (
        <input
          type="checkbox"
          className="h-4 w-4 cursor-pointer accent-brand-500"
          checked={selectedIds.has(info.row.original.id)}
          onClick={(e) => e.stopPropagation()}
          onChange={() => onToggleSelect(info.row.original.id)}
        />
      ),
    }),
    columnHelper.accessor('issue_date', {
      header: () => <p className={HEAD}>开票日期</p>,
      cell: (info) => <p className={CELL}>{dash(info.getValue())}</p>,
    }),
    columnHelper.accessor('invoice_type', {
      header: () => <p className={HEAD}>类型</p>,
      cell: (info) => <p className={CELL}>{dash(info.getValue())}</p>,
    }),
    columnHelper.accessor('seller_name', {
      header: () => <p className={HEAD}>开票方</p>,
      cell: (info) => (
        <p className="max-w-[200px] truncate text-sm font-medium text-navy-700 dark:text-white">
          {dash(info.getValue())}
        </p>
      ),
    }),
    columnHelper.accessor('total_amount', {
      header: () => <p className={HEAD}>价税合计</p>,
      cell: (info) => (
        <p className={CELL}>
          {info.getValue() == null ? '—' : `¥${info.getValue()}`}
        </p>
      ),
    }),
    columnHelper.accessor('category', {
      header: () => <p className={HEAD}>归属分类</p>,
      cell: (info) => <p className={CELL}>{dash(info.getValue())}</p>,
    }),
    columnHelper.accessor('source', {
      header: () => <p className={HEAD}>来源</p>,
      cell: (info) => (
        <span className="rounded-md bg-gray-100 px-2 py-1 text-xs text-gray-600 dark:bg-navy-700 dark:text-gray-300">
          {SOURCE_LABELS[info.getValue()]}
        </span>
      ),
    }),
    columnHelper.accessor('reimbursement_status', {
      header: () => <p className={HEAD}>报销状态</p>,
      cell: (info) =>
        info.row.original.status === 'processing' ? (
          <span className="inline-flex animate-pulse items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
            {STATUS_LABELS.processing}…
          </span>
        ) : (
          <StatusBadge status={info.getValue()} />
        ),
    }),
    columnHelper.display({
      id: 'actions',
      header: () => <p className={HEAD}>操作</p>,
      cell: (info) => {
        const row = info.row.original;
        const next = NEXT_STATUS[row.reimbursement_status];
        if (row.status === 'processing' || !next) {
          return <span className="text-xs text-gray-300">—</span>;
        }
        return (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onAdvanceStatus(row);
            }}
            className="dark:bg-brand-500/10 rounded-lg bg-brand-50 px-3 py-1 text-xs font-medium text-brand-600 hover:bg-brand-100 dark:text-brand-400"
          >
            {NEXT_LABEL[row.reimbursement_status]}
          </button>
        );
      },
    }),
  ];

  const table = useReactTable({
    data: filtered,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <Card extra="w-full h-full px-6 pb-6 sm:overflow-x-auto">
      <div className="flex flex-wrap items-center gap-2 pt-5">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
              tab === t.key
                ? 'bg-brand-500 text-white dark:bg-brand-400'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-navy-700 dark:text-gray-300'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="!border-px !border-gray-400">
                {hg.headers.map((header) => (
                  <th
                    key={header.id}
                    onClick={header.column.getToggleSortingHandler()}
                    className="cursor-pointer border-b border-gray-200 pb-2 pr-4 pt-4 text-start dark:border-white/30"
                  >
                    {flexRender(
                      header.column.columnDef.header,
                      header.getContext(),
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                onClick={() => onSelect(row.original)}
                className="cursor-pointer transition hover:bg-gray-50 dark:hover:bg-navy-900"
              >
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className="min-w-[120px] border-white/0 py-3 pr-4"
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
            {table.getRowModel().rows.length === 0 && (
              <tr>
                <td
                  colSpan={columns.length}
                  className="py-10 text-center text-sm text-gray-400"
                >
                  暂无发票
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
