'use client';

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/base-badge';
import { Input } from '@/components/ui/base-input';
import { Label } from '@/components/ui/base-label';
import { Button } from '@/components/ui/button';
import { apiFetch } from '@/lib/api';
import { Loader2, LogOut, RefreshCcw, ShieldCheck, Sparkles } from 'lucide-react';

const decodeRole = (token: string): string | undefined => {
  try {
    const [, payload] = token.split('.');
    if (!payload) {
      return undefined;
    }
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), '=');
    const parsed = JSON.parse(atob(padded));
    return typeof parsed.role === 'string' ? parsed.role : undefined;
  } catch {
    return undefined;
  }
};

const SUMMARY_LABELS: Record<string, string> = {
  clients: 'Клиенты',
  owners: 'Владельцы',
  managers: 'Менеджеры',
  bots: 'Telegram-боты',
  avito_accounts: 'Аккаунты Avito',
  dialogs: 'Диалоги',
  pending_messages: 'Сообщения в очереди',
  active_integrations: 'Активные интеграции',
};

const formatSummaryKey = (key: string): string => {
  if (SUMMARY_LABELS[key]) {
    return SUMMARY_LABELS[key];
  }
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
};

export default function AdminDashboard() {
  const router = useRouter();
  const [summary, setSummary] = useState<Record<string, number> | null>(null);
  const [settingsForm, setSettingsForm] = useState({ master_bot_token: '', master_bot_name: '' });
  const [error, setError] = useState<string | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [settingsSubmitting, setSettingsSubmitting] = useState<boolean>(false);
  const [loadingSummary, setLoadingSummary] = useState<boolean>(false);
  const [authState, setAuthState] = useState<'checking' | 'authorized' | 'unauthorized'>('checking');

  const load = useCallback(async () => {
    try {
      setLoadingSummary(true);
      setError(null);
      setSettingsError(null);
      setFlash(null);
      const [summaryData, settingsData] = await Promise.all([
        apiFetch('/api/admin/summary'),
        apiFetch('/api/admin/settings'),
      ]);
      setSummary(summaryData);
      setSettingsForm({
        master_bot_token: settingsData.master_bot_token ?? '',
        master_bot_name: settingsData.master_bot_name ?? '',
      });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoadingSummary(false);
    }
  }, []);

  useEffect(() => {
    const token = typeof window !== 'undefined' ? window.localStorage.getItem('tuberry_token') : null;
    if (!token) {
      setAuthState('unauthorized');
      router.replace('/admin/login');
      return;
    }
    const role = decodeRole(token);
    if (role !== 'admin') {
      setAuthState('unauthorized');
      router.replace('/login');
      return;
    }
    setAuthState('authorized');
    void load();
  }, [load, router]);

  useEffect(() => {
    if (authState !== 'authorized') {
      return;
    }
    const previousTitle = document.title;
    document.title = 'Админ-панель | Tuberry';
    return () => {
      document.title = previousTitle;
    };
  }, [authState]);

  const handleLogout = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem('tuberry_token');
    }
    window.location.href = 'https://tuberry.ru/admin/login';
  }, []);

  const handleSettingsSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSettingsSubmitting(true);
    setSettingsError(null);
    setFlash(null);
    try {
      const updated = await apiFetch('/api/admin/settings', {
        method: 'PUT',
        body: JSON.stringify(settingsForm),
      });
      setSettingsForm({
        master_bot_token: updated.master_bot_token ?? '',
        master_bot_name: updated.master_bot_name ?? '',
      });
      setFlash('Настройки мастер-бота обновлены.');
    } catch (err) {
      setSettingsError((err as Error).message);
    } finally {
      setSettingsSubmitting(false);
    }
  };

  const summaryEntries = useMemo(() => (summary ? Object.entries(summary) : []), [summary]);

  if (authState === 'checking') {
    return (
      <div className="relative min-h-screen bg-[var(--app-gradient)]">
        <div className="absolute inset-0 -z-10 bg-gradient-to-br from-white/60 via-white/35 to-transparent backdrop-blur-xl" />
        <div className="flex min-h-screen items-center justify-center px-6">
          <div className="glass-panel flex items-center gap-3 rounded-[28px] px-6 py-4 text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            <span>Проверяем права доступа…</span>
          </div>
        </div>
      </div>
    );
  }

  if (authState !== 'authorized') {
    return null;
  }

  return (
    <div className="relative min-h-screen bg-[var(--app-gradient)]">
      <div className="absolute inset-0 -z-10 bg-gradient-to-br from-white/60 via-white/40 to-transparent backdrop-blur-xl" />
      <div className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 px-4 py-10 lg:px-8">
        <header className="glass-panel flex flex-col gap-4 rounded-[30px] border border-[var(--app-border)] p-8 shadow-[0_32px_120px_-60px_rgba(30,64,175,0.45)]">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-2">
              <Badge variant="info" appearance="light" size="xs" className="uppercase tracking-[0.3em] text-[10px]">
                Control center
              </Badge>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-500/15 text-blue-600 shadow-inner">
                  <ShieldCheck className="size-5" />
                </div>
                <div>
                  <h1 className="text-2xl font-semibold">Админ-панель Tuberry</h1>
                  <p className="text-sm text-muted-foreground">
                    Следите за ключевыми метриками, настраивайте мастер-бота и поддерживайте стабильность сервиса.
                  </p>
                </div>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="button"
                variant="outline"
                size="md"
                onClick={() => void load()}
                disabled={loadingSummary}
                className="w-full max-w-[200px] sm:w-auto"
              >
                {loadingSummary ? <Loader2 className="mr-2 size-4 animate-spin" /> : <RefreshCcw className="mr-2 size-4" />}
                {loadingSummary ? 'Обновляем данные…' : 'Обновить данные'}
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="md"
                onClick={handleLogout}
                className="w-full max-w-[200px] sm:w-auto"
              >
                <LogOut className="mr-2 size-4" />Выйти
              </Button>
            </div>
          </div>

          {error && (
            <Alert variant="destructive" appearance="light" className="glass-panel border border-red-200/70">
              <AlertTitle>Не удалось загрузить данные</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </header>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {summaryEntries.length > 0 ? (
            summaryEntries.map(([key, value]) => (
              <div
                key={key}
                className="glass-panel rounded-[26px] border border-[var(--app-border)] p-6 shadow-[0_20px_80px_-50px_rgba(30,64,175,0.35)]"
              >
                <div className="flex items-start justify-between">
                  <Badge variant="secondary" appearance="light" size="sm" className="uppercase tracking-[0.15em]">
                    {formatSummaryKey(key)}
                  </Badge>
                  <Sparkles className="size-4 text-blue-500/70" />
                </div>
                <p className="mt-6 text-3xl font-semibold">{value}</p>
              </div>
            ))
          ) : (
            <div className="glass-panel col-span-full flex flex-col items-center justify-center gap-3 rounded-[26px] border border-dashed border-[var(--app-border)]/70 p-10 text-muted-foreground">
              {loadingSummary ? (
                <>
                  <Loader2 className="size-5 animate-spin" />
                  <span>Собираем статистику…</span>
                </>
              ) : (
                <span>Метрики появятся, как только будут доступны данные.</span>
              )}
            </div>
          )}
        </section>

        <section className="glass-panel w-full max-w-2xl rounded-[30px] border border-[var(--app-border)] p-8 shadow-[0_32px_120px_-60px_rgba(30,64,175,0.4)]">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-1">
              <h2 className="text-xl font-semibold">Настройки мастер-бота</h2>
              <p className="text-sm text-muted-foreground">
                Эти параметры используются для генерации ссылок и верификации Telegram Login во время онбординга.
              </p>
            </div>
          </div>

          <form onSubmit={handleSettingsSubmit} className="mt-6 space-y-6">
            <div className="grid gap-5">
              <div className="space-y-2">
                <Label htmlFor="master_bot_token">MASTER_BOT_TOKEN</Label>
                <Input
                  id="master_bot_token"
                  type="password"
                  placeholder="Введите токен мастер-бота"
                  value={settingsForm.master_bot_token}
                  onChange={(event) =>
                    setSettingsForm((prev) => ({ ...prev, master_bot_token: event.target.value }))
                  }
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="master_bot_name">Отображаемое имя</Label>
                <Input
                  id="master_bot_name"
                  placeholder="Например, @company_helper_bot"
                  value={settingsForm.master_bot_name}
                  onChange={(event) =>
                    setSettingsForm((prev) => ({ ...prev, master_bot_name: event.target.value }))
                  }
                />
                <p className="text-xs text-muted-foreground">
                  Имя отображается администраторам и клиентам на этапах подключения и авторизации.
                </p>
              </div>
            </div>

            {settingsError && (
              <Alert variant="destructive" appearance="light" className="glass-panel border border-red-200/70">
                <AlertTitle>Не удалось сохранить</AlertTitle>
                <AlertDescription>{settingsError}</AlertDescription>
              </Alert>
            )}

            {flash && (
              <Alert variant="success" appearance="light" className="glass-panel border border-emerald-200/70">
                <AlertTitle>Сохранено</AlertTitle>
                <AlertDescription>{flash}</AlertDescription>
              </Alert>
            )}

            <div className="flex items-center justify-end gap-3">
              <Button type="submit" disabled={settingsSubmitting}>
                {settingsSubmitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
                {settingsSubmitting ? 'Сохраняем…' : 'Сохранить настройки'}
              </Button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}
