/**
 * 认证与 API 客户端：token 存 localStorage，请求自动带 Bearer。
 */
import { API_BASE_URL } from './api';

const TOKEN_KEY = 'invoce_token';

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) ?? {}),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = '请求失败';
    try {
      const body = await res.json();
      if (typeof body?.detail === 'string') detail = body.detail;
    } catch {
      /* ignore */
    }
    if (res.status === 401) clearToken();
    throw new Error(detail);
  }
  return (res.status === 204 ? null : await res.json()) as T;
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: 'PATCH', body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(p: string) => request<T>(p, { method: 'DELETE' }),
};

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface CurrentUser {
  id: string;
  email: string;
  created_at: string;
}

export async function login(email: string, password: string): Promise<void> {
  const data = await api.post<TokenResponse>('/auth/login', { email, password });
  setToken(data.access_token);
}

export async function register(email: string, password: string): Promise<void> {
  const data = await api.post<TokenResponse>('/auth/register', { email, password });
  setToken(data.access_token);
}

export function getMe(): Promise<CurrentUser> {
  return api.get<CurrentUser>('/auth/me');
}

export function logout(): void {
  clearToken();
}
