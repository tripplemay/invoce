/** Telegram 绑定 API 客户端。 */
import { api } from './auth';

export interface TelegramAccount {
  id: string;
  chat_id: number;
  username: string | null;
  enabled: boolean;
}

export interface TelegramLink {
  code: string;
  deep_link: string; // https://t.me/<bot>?start=<code>
  expires_in: number;
}

export function getTelegramAccount(): Promise<TelegramAccount | null> {
  return api.get<TelegramAccount | null>('/telegram/account');
}

export function createTelegramLink(): Promise<TelegramLink> {
  return api.post<TelegramLink>('/telegram/link-code');
}

export function unlinkTelegram(): Promise<null> {
  return api.delete<null>('/telegram/account');
}
