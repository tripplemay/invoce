/** 发票 API 客户端。 */
import { API_BASE_URL } from './api';
import { api, getToken } from './auth';
import { Invoice, ReimbursementStatus } from './types';

export function listInvoices(reimbursementStatus?: string): Promise<Invoice[]> {
  const q = reimbursementStatus
    ? `?reimbursement_status=${reimbursementStatus}`
    : '';
  return api.get<Invoice[]>(`/invoices${q}`);
}

export function getInvoice(id: string): Promise<Invoice> {
  return api.get<Invoice>(`/invoices/${id}`);
}

export function updateInvoice(
  id: string,
  data: Partial<Invoice>,
): Promise<Invoice> {
  return api.patch<Invoice>(`/invoices/${id}`, data);
}

export function deleteInvoice(id: string): Promise<null> {
  return api.delete<null>(`/invoices/${id}`);
}

export function changeReimbursementStatus(
  id: string,
  reimbursementStatus: ReimbursementStatus,
): Promise<Invoice> {
  return api.patch<Invoice>(`/invoices/${id}/reimbursement-status`, {
    reimbursement_status: reimbursementStatus,
  });
}

/** 批量改报销状态：把选中发票一次性改为目标状态（任意方向）。 */
export function bulkChangeStatus(
  ids: string[],
  reimbursementStatus: ReimbursementStatus,
): Promise<{ count: number }> {
  return api.post<{ count: number }>('/invoices/bulk/reimbursement-status', {
    invoice_ids: ids,
    reimbursement_status: reimbursementStatus,
  });
}

/** 批量删除选中发票（连同原件）。 */
export function bulkDeleteInvoices(ids: string[]): Promise<{ count: number }> {
  return api.post<{ count: number }>('/invoices/bulk-delete', {
    invoice_ids: ids,
  });
}

export interface DuplicateCheck {
  duplicate: boolean;
  existing_id: string | null;
  existing_date: string | null;
}

export function checkDuplicate(
  invoiceNumber: string,
  invoiceCode: string | null,
  excludeId?: string,
): Promise<DuplicateCheck> {
  return api.post<DuplicateCheck>('/invoices/check-duplicate', {
    invoice_number: invoiceNumber,
    invoice_code: invoiceCode,
    exclude_id: excludeId,
  });
}

export async function uploadInvoices(files: File[]): Promise<Invoice[]> {
  const form = new FormData();
  files.forEach((f) => form.append('files', f));
  const token = getToken();
  const res = await fetch(`${API_BASE_URL}/invoices/upload`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) {
    let detail = '上传失败';
    try {
      const b = await res.json();
      if (typeof b?.detail === 'string') detail = b.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

export interface PreviewResp {
  url: string;
  expires_in: number;
}

export function getPreview(id: string): Promise<PreviewResp> {
  return api.get<PreviewResp>(`/invoices/${id}/preview`);
}

export async function exportInvoices(
  ids: string[],
  markSubmitted: boolean,
): Promise<void> {
  const token = getToken();
  const res = await fetch(`${API_BASE_URL}/invoices/export`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ invoice_ids: ids, mark_submitted: markSubmitted }),
  });
  if (!res.ok) throw new Error('导出失败');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'reimbursement.zip';
  a.click();
  URL.revokeObjectURL(url);
}
