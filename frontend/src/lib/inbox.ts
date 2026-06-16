/** 专属收票邮箱 API 客户端。 */
import { api } from './auth';

export interface Inbox {
  token: string;
  address: string | null; // <token>@<收票域>；未配置收票域时为 null
  enabled: boolean;
}

export function getInbox(): Promise<Inbox> {
  return api.get<Inbox>('/inbox');
}
