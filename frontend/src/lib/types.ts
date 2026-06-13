/** 与后端对齐的发票类型。 */

export type ReimbursementStatus = 'unreimbursed' | 'submitted' | 'reimbursed';
export type InvoiceStatus = 'processing' | 'pending' | 'verified' | 'failed';
export type InvoiceSource = 'manual' | 'email_auto';

export interface Invoice {
  id: string;
  invoice_code: string | null;
  invoice_number: string | null;
  issue_date: string | null;
  invoice_type: string | null;
  seller_name: string | null;
  buyer_name: string | null;
  total_amount: string | null;
  category: string | null;
  tags: string[] | null;
  reimbursement_status: ReimbursementStatus;
  source: InvoiceSource;
  status: InvoiceStatus;
  ai_confidence?: number | null;
}

export const REIMBURSEMENT_LABELS: Record<ReimbursementStatus, string> = {
  unreimbursed: '待报销',
  submitted: '报销中',
  reimbursed: '已到账',
};

export const SOURCE_LABELS: Record<InvoiceSource, string> = {
  manual: '手动上传',
  email_auto: 'QQ邮箱',
};

export const STATUS_LABELS: Record<InvoiceStatus, string> = {
  processing: '识别中',
  pending: '待校对',
  verified: '已校对',
  failed: '抽取失败',
};
