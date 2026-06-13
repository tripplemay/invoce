/** 邮箱账户 API 客户端。 */
import { api } from './auth';

export interface EmailAccount {
  id: string;
  imap_user: string;
  imap_host: string;
  imap_port: number;
  enabled: boolean;
  last_sync_uid: number | null;
  created_at: string;
}

export function listEmailAccounts(): Promise<EmailAccount[]> {
  return api.get<EmailAccount[]>('/email-accounts');
}

export function createEmailAccount(data: {
  imap_user: string;
  auth_code: string;
}): Promise<EmailAccount> {
  return api.post<EmailAccount>('/email-accounts', data);
}

export function deleteEmailAccount(id: string): Promise<null> {
  return api.delete<null>(`/email-accounts/${id}`);
}
