import { REIMBURSEMENT_LABELS, ReimbursementStatus } from 'lib/types';

const STYLE: Record<ReimbursementStatus, string> = {
  unreimbursed: 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400',
  submitted: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400',
  reimbursed: 'bg-green-50 text-green-600 dark:bg-green-500/10 dark:text-green-400',
};

const DOT: Record<ReimbursementStatus, string> = {
  unreimbursed: 'bg-red-500',
  submitted: 'bg-amber-500',
  reimbursed: 'bg-green-500',
};

export default function StatusBadge({ status }: { status: ReimbursementStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${STYLE[status]}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${DOT[status]}`} />
      {REIMBURSEMENT_LABELS[status]}
    </span>
  );
}
