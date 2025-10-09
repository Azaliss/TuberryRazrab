'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/base-badge';
import { Input } from '@/components/ui/base-input';
import { Label } from '@/components/ui/base-label';
import { Button } from '@/components/ui/button';
import { apiFetch } from '@/lib/api';
import { Loader2, LogIn, ShieldCheck } from 'lucide-react';

export default function AdminLoginPage() {
  const router = useRouter();
  const [form, setForm] = useState({ username: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setStatus(null);

    try {
      const response = await apiFetch('/api/auth/admin/login', {
        method: 'POST',
        body: JSON.stringify(form),
      });
      const token: string | undefined = response?.access_token;
      if (!token) {
        throw new Error('Не удалось получить токен.');
      }

      if (typeof window !== 'undefined') {
        window.localStorage.setItem('tuberry_token', token);
      }

      setStatus('Готовим админ-панель…');
      router.replace('/admin');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen bg-[var(--app-gradient)] py-16">
      <div className="absolute inset-0 -z-10 bg-gradient-to-br from-white/60 via-white/35 to-transparent backdrop-blur-xl" />
      <div className="mx-auto flex w-full max-w-md flex-col gap-6 rounded-[30px] border border-[var(--app-border)] bg-white/75 p-8 shadow-[0_30px_120px_-50px_rgba(30,64,175,0.35)] backdrop-blur-2xl">
        <header className="space-y-3 text-start">
          <Badge variant="info" appearance="light" size="xs" className="uppercase tracking-[0.3em] text-[10px]">
            Admin access
          </Badge>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-500/15 text-blue-600 shadow-inner">
              <ShieldCheck className="size-5" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold">Вход в админ-панель</h1>
              <p className="text-sm text-muted-foreground">
                Используйте служебные учётные данные, чтобы управлять сервисом и онбордингом клиентов.
              </p>
            </div>
          </div>
        </header>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <Label htmlFor="username">Логин</Label>
            <Input
              id="username"
              placeholder="admin"
              value={form.username}
              onChange={(event) => setForm((prev) => ({ ...prev, username: event.target.value }))}
              autoComplete="username"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Пароль</Label>
            <Input
              id="password"
              type="password"
              placeholder="Введите пароль"
              value={form.password}
              onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
              autoComplete="current-password"
              required
            />
          </div>

          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <LogIn className="mr-2 size-4" />}
            {loading ? 'Проверяем доступ…' : 'Войти'}
          </Button>
        </form>

        {status && (
          <Alert variant="success" appearance="light" className="glass-panel border border-emerald-200/70">
            <AlertTitle>Успешно</AlertTitle>
            <AlertDescription>{status}</AlertDescription>
          </Alert>
        )}

        {error && (
          <Alert variant="destructive" appearance="light" className="glass-panel border border-red-200/70">
            <AlertTitle>Ошибка входа</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <footer className="rounded-2xl bg-white/60 p-4 text-center text-xs text-muted-foreground">
          После входа вы будете перенаправлены на защищённую админ-панель.
        </footer>
      </div>
    </div>
  );
}
