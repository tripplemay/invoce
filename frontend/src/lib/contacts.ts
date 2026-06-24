/** 通讯录（下游处理人联系人）API 客户端。 */
import { api } from './auth';

export interface Contact {
  id: string;
  name: string;
  email: string;
  note: string | null;
  created_at: string;
}

export function listContacts(): Promise<Contact[]> {
  return api.get<Contact[]>('/contacts');
}

export function createContact(data: {
  name: string;
  email: string;
  note?: string | null;
}): Promise<Contact> {
  return api.post<Contact>('/contacts', data);
}

export function updateContact(
  id: string,
  data: { name?: string; email?: string; note?: string | null },
): Promise<Contact> {
  return api.patch<Contact>(`/contacts/${id}`, data);
}

export function deleteContact(id: string): Promise<null> {
  return api.delete<null>(`/contacts/${id}`);
}
