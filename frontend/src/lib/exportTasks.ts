/** 异步导出任务 API 客户端。 */
import { api } from './auth';

export type ExportTaskStatus = 'pending' | 'processing' | 'completed' | 'failed';

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
