'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { getToken } from 'lib/auth';

/**
 * 路由守卫：无 token 则跳转登录；有则渲染子内容。
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace('/auth/sign-in/default');
    } else {
      setAuthed(true);
    }
  }, [router]);

  if (!authed) return null;
  return <>{children}</>;
}
