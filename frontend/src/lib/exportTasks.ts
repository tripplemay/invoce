/** 异步导出任务 API 客户端。 */
import { api } from './auth';

export type ExportTaskStatus =
  | 'pending'
  | 'processing'
  | 'completed'
  | 'failed';

export interface ExportTask {
  id: string;
  status: ExportTaskStatus;
  invoice_count: number;
  mark_submitted: boolean;
  result_filename: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export const EXPORT_STATUS_LABELS: Record<ExportTaskStatus, string> = {
  pending: '排队中',
  processing: '生成中',
  completed: '已完成',
  failed: '失败',
};

export function createExportTask(
  ids: string[],
  markSubmitted: boolean,
): Promise<ExportTask> {
  return api.post<ExportTask>('/export-tasks', {
    invoice_ids: ids,
    mark_submitted: markSubmitted,
  });
}

export function listExportTasks(): Promise<ExportTask[]> {
  return api.get<ExportTask[]>('/export-tasks');
}

export function getExportDownloadUrl(
  id: string,
): Promise<{ url: string; expires_in: number }> {
  return api.get<{ url: string; expires_in: number }>(
    `/export-tasks/${id}/download`,
  );
}

export type ExportSendStatus = 'pending' | 'sending' | 'sent' | 'failed';
export type DeliveryMode = 'attachment' | 'link';

export interface ExportSend {
  id: string;
  export_task_id: string;
  to_addresses: string[];
  subject: string | null;
  note: string | null;
  delivery_mode: DeliveryMode | null;
  status: ExportSendStatus;
  error_message: string | null;
  sent_at: string | null;
  created_at: string;
}

export const SEND_STATUS_LABELS: Record<ExportSendStatus, string> = {
  pending: '排队中',
  sending: '发送中',
  sent: '已发送',
  failed: '发送失败',
};

export interface SendExportPayload {
  contact_ids?: string[];
  emails?: string[];
  note?: string;
}

export function sendExportTask(
  taskId: string,
  payload: SendExportPayload,
): Promise<ExportSend> {
  return api.post<ExportSend>(`/export-tasks/${taskId}/send`, payload);
}

export function listExportSends(taskId: string): Promise<ExportSend[]> {
  return api.get<ExportSend[]>(`/export-tasks/${taskId}/sends`);
}
