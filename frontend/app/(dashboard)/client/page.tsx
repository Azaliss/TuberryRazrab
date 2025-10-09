'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/base-badge';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { apiFetch } from '@/lib/api';
import type { AvitoAccount, Bot, Dialog } from './types';
import { ArrowRight, Loader2, MessageCircle, RefreshCcw, Settings2, Sparkles } from 'lucide-react';
import Link from 'next/link';

interface ClientSnapshot {
  filter_keywords?: string;
  require_reply_for_avito?: boolean;
  hide_system_messages?: boolean;
}

function formatDate(value?: string) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '—';
  }
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export default function ClientDashboardPage() {
  const [bots, setBots] = useState<Bot[]>([]);
  const [accounts, setAccounts] = useState<AvitoAccount[]>([]);
  const [dialogs, setDialogs] = useState<Dialog[]>([]);
  const [profile, setProfile] = useState<ClientSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [clientResp, botsResp, accountsResp, dialogsResp] = await Promise.all([
        apiFetch('/api/clients/me'),
        apiFetch('/api/bots/'),
        apiFetch('/api/avito/accounts'),
        apiFetch('/api/dialogs/'),
      ]);
      setProfile(clientResp);
      setBots(botsResp);
      setAccounts(accountsResp);
      setDialogs(dialogsResp);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const previousTitle = document.title;
    document.title = 'Личный кабинет | Tuberry';
    return () => {
      document.title = previousTitle;
    };
  }, []);

  const activeBots = useMemo(() => bots.filter((bot) => bot.status === 'active'), [bots]);
  const activeAccounts = useMemo(() => accounts.filter((account) => account.status === 'active'), [accounts]);
  const monitoringDisabled = useMemo(
    () => accounts.filter((account) => !account.monitoring_enabled).length,
    [accounts],
  );
  const latestDialogs = useMemo(
    () =>
      [...dialogs]
        .filter((dialog) => dialog.last_message_at)
        .sort((a, b) => (a.last_message_at && b.last_message_at ? b.last_message_at.localeCompare(a.last_message_at) : 0))
        .slice(0, 5),
    [dialogs],
  );

  return (
    <div className="space-y-8 pb-12">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">Кабинет клиента</h1>
          <p className="text-muted-foreground">
            Отслеживайте состояние интеграций и диалогов. Управление настройками вынесено в отдельный раздел.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button asChild variant="secondary" size="sm" className="shadow-xs">
            <Link href="/client/settings">
              <Settings2 className="mr-2 size-4" />Настройки
            </Link>
          </Button>
          <Button variant="outline" size="sm" onClick={() => load()} disabled={loading}>
            {loading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <RefreshCcw className="mr-2 size-4" />}
            Обновить данные
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive" appearance="light" className="glass-panel border border-red-200/70">
          <AlertTitle>Не удалось получить данные</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="glass-panel rounded-3xl border border-[var(--app-border)] p-5 shadow-lg shadow-blue-100">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Telegram</p>
              <h2 className="mt-2 text-3xl font-semibold">{activeBots.length}</h2>
            </div>
            <Badge variant={activeBots.length ? 'success' : 'warning'} appearance="light" size="sm">
              {activeBots.length ? 'Активны' : 'Нет активных'}
            </Badge>
          </div>
          <p className="mt-3 text-sm text-muted-foreground">
            Всего подключено {bots.length} бота. Статус обновляется каждые 60 секунд.
          </p>
        </div>

        <div className="glass-panel rounded-3xl border border-[var(--app-border)] p-5 shadow-lg shadow-blue-100">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Avito</p>
              <h2 className="mt-2 text-3xl font-semibold">{activeAccounts.length}</h2>
            </div>
            <Badge variant={activeAccounts.length ? 'primary' : 'warning'} appearance="light" size="sm">
              {activeAccounts.length ? 'Подключено' : 'Нет подключений'}
            </Badge>
          </div>
          <p className="mt-3 text-sm text-muted-foreground">
            Мониторинг отключён у {monitoringDisabled} аккаунтов.
          </p>
        </div>

        <div className="glass-panel rounded-3xl border border-[var(--app-border)] p-5 shadow-lg shadow-blue-100">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Диалоги</p>
              <h2 className="mt-2 text-3xl font-semibold">{dialogs.length}</h2>
            </div>
            <Badge variant="info" appearance="light" size="sm">
              {dialogs.length ? 'В работе' : 'Нет активных'}
            </Badge>
          </div>
          <p className="mt-3 text-sm text-muted-foreground">
            Список последних обращений обновляется автоматически.
          </p>
        </div>

        <div className="glass-panel rounded-3xl border border-[var(--app-border)] p-5 shadow-lg shadow-blue-100">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Фильтр</p>
              <h2 className="mt-2 text-3xl font-semibold">{profile?.filter_keywords ? 'Включён' : 'Не настроен'}</h2>
            </div>
            <Badge variant={profile?.require_reply_for_avito ? 'warning' : 'secondary'} appearance="light" size="sm">
              {profile?.require_reply_for_avito ? 'Нужно цитирование' : 'Свободный ответ'}
            </Badge>
          </div>
          <p className="mt-3 text-sm text-muted-foreground line-clamp-2">
            {profile?.filter_keywords ? profile.filter_keywords.replace(/\n/g, ', ') : 'Добавьте стоп-слова в настройках.'}
          </p>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="glass-panel flex h-full flex-col justify-between rounded-3xl border border-[var(--app-border)] p-6 shadow-lg shadow-blue-100">
          <div className="space-y-3">
            <Badge variant="info" appearance="light" size="xs" className="uppercase tracking-[0.2em] text-[10px]">
              Рекомендация
            </Badge>
            <h2 className="text-2xl font-semibold">Центр управления интеграциями</h2>
            <p className="text-sm text-muted-foreground">
              Сводка подключений и быстрые действия для поддержки команды. Следите за статусами каналов и управляйте
              фильтрами в один клик.
            </p>
          </div>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button asChild>
              <Link href="/client/settings">
                Перейти к настройкам
                <ArrowRight className="ml-2 size-4" />
              </Link>
            </Button>
            <Badge variant="secondary" appearance="light" size="sm" className="flex items-center gap-1">
              <MessageCircle className="size-3.5" /> {dialogs.length} диалогов
            </Badge>
            <Badge variant="primary" appearance="light" size="sm" className="flex items-center gap-1">
              <Sparkles className="size-3.5" /> Скоро: автоответы
            </Badge>
          </div>
        </div>

        <div className="glass-panel rounded-3xl border border-[var(--app-border)] p-6 shadow-lg shadow-blue-100">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Ближайшие обновления</h2>
              <p className="text-sm text-muted-foreground">Планы команды разработки на ближайшие релизы.</p>
            </div>
            <Badge variant="secondary" appearance="light" size="sm">
              Скорая дорожная карта
            </Badge>
          </div>
          <ul className="mt-5 space-y-3 text-sm">
            <li className="flex items-start gap-3 rounded-2xl bg-white/60 p-3 shadow-sm shadow-blue-100 ring-1 ring-white/60">
              <Badge variant="info" appearance="light" size="xs" className="mt-0.5">
                Скоро
              </Badge>
              <div>
                <p className="font-medium">Отчёты по менеджерам</p>
                <p className="text-muted-foreground">
                  Ежедневная статистика по времени ответов и количеству диалогов в export-friendly формате.
                </p>
              </div>
            </li>
            <li className="flex items-start gap-3 rounded-2xl bg-white/60 p-3 shadow-sm shadow-blue-100 ring-1 ring-white/60">
              <Badge variant="primary" appearance="light" size="xs" className="mt-0.5">
                В разработке
              </Badge>
              <div>
                <p className="font-medium">Автоматические автоответы</p>
                <p className="text-muted-foreground">
                  Настройка шаблонов, которые будут отправляться клиентам при первом обращении.
                </p>
              </div>
            </li>
            <li className="flex items-start gap-3 rounded-2xl bg-white/60 p-3 shadow-sm shadow-blue-100 ring-1 ring-white/60">
              <Badge variant="secondary" appearance="light" size="xs" className="mt-0.5">
                Идея
              </Badge>
              <div>
                <p className="font-medium">Webhook на входящие заявки</p>
                <p className="text-muted-foreground">
                  Позволит подключить CRM к Tuberry и синхронизировать статусы автоматически.
                </p>
              </div>
            </li>
          </ul>
        </div>
      </section>

      <section className="glass-panel rounded-3xl border border-[var(--app-border)] p-6 shadow-lg shadow-blue-100">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Последние диалоги</h2>
            <p className="text-sm text-muted-foreground">Пять последних активностей с указанием топика Telegram.</p>
          </div>
          <Badge variant="secondary" appearance="light" size="sm">
            {dialogs.length} всего
          </Badge>
        </div>
        <div className="mt-4 overflow-hidden rounded-xl border border-border/60">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Avito ID</TableHead>
                <TableHead>Topic</TableHead>
                <TableHead>Последнее сообщение</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={3} className="py-6 text-center text-sm text-muted-foreground">
                    Загружаем диалоги…
                  </TableCell>
                </TableRow>
              ) : latestDialogs.length > 0 ? (
                latestDialogs.map((dialog) => (
                  <TableRow key={dialog.id}>
                    <TableCell className="font-medium">{dialog.avito_dialog_id}</TableCell>
                    <TableCell className="font-mono text-sm text-muted-foreground">
                      {dialog.telegram_topic_id ?? '—'}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{formatDate(dialog.last_message_at)}</TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={3} className="py-6 text-center text-sm text-muted-foreground">
                    Активных диалогов пока нет
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </section>
    </div>
  );
}
