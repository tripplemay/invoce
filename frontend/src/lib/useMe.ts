'use client';
import { useEffect, useState } from 'react';
import { getMe, CurrentUser } from 'lib/auth';

// 模块级 Promise 缓存：sidebar + navbar 共用，避免重复请求 /auth/me。
let cache: Promise<CurrentUser> | null = null;

export function useMe(): CurrentUser | null {
  const [u, setU] = useState<CurrentUser | null>(null);
  useEffect(() => {
    if (!cache) cache = getMe();
    cache
      .then(setU)
      .catch(() => {
        // 失败时清空缓存，下次挂载可重试。
        cache = null;
      });
  }, []);
  return u;
}
