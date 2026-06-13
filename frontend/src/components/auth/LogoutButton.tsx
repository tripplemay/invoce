'use client';

import { useRouter } from 'next/navigation';
import { logout } from 'lib/auth';

export default function LogoutButton({ className }: { className?: string }) {
  const router = useRouter();
  function handleLogout() {
    logout();
    router.replace('/auth/sign-in/default');
  }
  return (
    <button type="button" onClick={handleLogout} className={className}>
      退出登录
    </button>
  );
}
