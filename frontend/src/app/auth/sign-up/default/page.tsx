'use client';
import Default from 'components/auth/variants/DefaultAuthLayout';
import InputField from 'components/fields/InputField';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { register } from 'lib/auth';

function SignUpDefault() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (password.length < 8) {
      setError('密码至少 8 位');
      return;
    }
    setLoading(true);
    try {
      await register(email, password);
      router.replace('/admin/dashboard');
    } catch (err) {
      setError(err instanceof Error ? err.message : '注册失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Default
      maincard={
        <div className="mb-16 mt-16 flex h-full w-full items-center justify-center px-2 md:mx-0 md:px-0 lg:mb-10 lg:items-center lg:justify-start">
          <form
            onSubmit={handleSubmit}
            className="mt-[10vh] w-full max-w-full flex-col items-center md:pl-4 lg:pl-0 xl:max-w-[420px]"
          >
            <h3 className="mb-2.5 text-4xl font-bold text-navy-700 dark:text-white">注册</h3>
            <p className="mb-9 ml-1 text-base text-gray-600">创建你的 invoce 账号</p>

            {error && (
              <div className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600 dark:bg-red-500/10 dark:text-red-400">
                {error}
              </div>
            )}

            <InputField
              variant="auth"
              extra="mb-3"
              label="邮箱*"
              placeholder="mail@example.com"
              id="email"
              type="email"
              value={email}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
            />
            <InputField
              variant="auth"
              extra="mb-3"
              label="密码*"
              placeholder="至少 8 位"
              id="password"
              type="password"
              value={password}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
            />

            <button
              type="submit"
              disabled={loading}
              className="linear mt-2 w-full rounded-xl bg-brand-500 py-3 text-base font-medium text-white transition duration-200 hover:bg-brand-600 active:bg-brand-700 disabled:opacity-60 dark:bg-brand-400 dark:text-white dark:hover:bg-brand-300 dark:active:bg-brand-200"
            >
              {loading ? '注册中…' : '注册'}
            </button>

            <div className="mt-4">
              <span className="text-sm font-medium text-navy-700 dark:text-gray-500">
                已有账号？
              </span>
              <a
                href="/auth/sign-in/default"
                className="ml-1 text-sm font-medium text-brand-500 hover:text-brand-600 dark:text-white"
              >
                去登录
              </a>
            </div>
          </form>
        </div>
      }
    />
  );
}

export default SignUpDefault;
