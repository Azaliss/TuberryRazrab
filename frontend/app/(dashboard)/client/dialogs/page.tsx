'use client';

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/base-badge';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { apiFetch } from '@/lib/api';
import type { Dialog, DialogDetail, DialogMessage } from '../types';
import { Loader2, RefreshCcw, SendHorizontal } from 'lucide-react';

const REFRESH_INTERVAL_MS = 10_000;

function formatDate(value?: string) {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(parsed);
}

function formatDateTime(value?: string) {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '';
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(parsed);
}

function sortDialogsByRecent(dialogs: Dialog[]): Dialog[] {
  const getTimestamp = (dialog: Dialog) => {
    const candidates: (string | undefined)[] = [dialog.last_message_at, dialog.created_at];
    for (const value of candidates) {
      if (!value) continue;
      const time = new Date(value).getTime();
      if (!Number.isNaN(time)) {
        return time;
      }
    }
    return 0;
  };

  return [...dialogs].sort((a, b) => getTimestamp(b) - getTimestamp(a));
}

function sortMessages(messages: DialogMessage[]): DialogMessage[] {
  return [...messages].sort((a, b) => {
    const aTime = a.created_at ? new Date(a.created_at).getTime() : 0;
    const bTime = b.created_at ? new Date(b.created_at).getTime() : 0;
    return aTime - bTime;
  });
}

export default function DialogsPage() {
  const [dialogs, setDialogs] = useState<Dialog[]>([]);
  const [selectedDialogId, setSelectedDialogId] = useState<number | null>(null);
  const [detail, setDetail] = useState<DialogDetail | null>(null);
  const [loadingDialogs, setLoadingDialogs] = useState<boolean>(false);
  const [loadingMessages, setLoadingMessages] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [messageDraft, setMessageDraft] = useState<string>('');
  const [sending, setSending] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const loadDialogs = useCallback(async () => {
    setLoadingDialogs(true);
    setError(null);
    try {
      const data = (await apiFetch('/api/dialogs/')) as Dialog[];
      const sortedList = sortDialogsByRecent(data);
      setDialogs(sortedList);
      if (sortedList.length > 0 && !sortedList.some((dialog) => dialog.id === selectedDialogId)) {
        setSelectedDialogId(sortedList[0].id);
      } else if (data.length === 0) {
        setSelectedDialogId(null);
        setDetail(null);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoadingDialogs(false);
    }
  }, [selectedDialogId]);

  const loadDialogMessages = useCallback(
    async (dialogId: number, withLoader = true) => {
      if (withLoader) {
        setLoadingMessages(true);
      }
      setError(null);
      try {
        const data = await apiFetch(`/api/dialogs/${dialogId}`);
        setDetail(data);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        if (withLoader) {
          setLoadingMessages(false);
        }
      }
    },
    [],
  );

  useEffect(() => {
    void loadDialogs();
  }, [loadDialogs]);

  useEffect(() => {
    if (selectedDialogId == null) return;
    void loadDialogMessages(selectedDialogId);
  }, [selectedDialogId, loadDialogMessages]);

  useEffect(() => {
    if (selectedDialogId == null) return undefined;
    const interval = setInterval(() => {
      void loadDialogMessages(selectedDialogId, false);
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [selectedDialogId, loadDialogMessages]);

  const sortedMessages = useMemo(() => {
    if (!detail) return [];
    return sortMessages(detail.messages);
  }, [detail]);

  useEffect(() => {
    if (!sortedMessages.length) return;
    if (!messagesEndRef.current) return;
    messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [sortedMessages, selectedDialogId]);

  const handleSend = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!selectedDialogId) return;
      const trimmed = messageDraft.trim();
      if (!trimmed) return;
      if (detail?.dialog.source === 'telegram') {
        setSendError('Ответы отправляются в рабочем Telegram-чате. В портале отправка недоступна для этого источника.');
        return;
      }
      setSending(true);
      setSendError(null);
      try {
        await apiFetch(`/api/dialogs/${selectedDialogId}/messages`, {
          method: 'POST',
          body: JSON.stringify({ text: trimmed }),
        });
        setMessageDraft('');
        await loadDialogMessages(selectedDialogId);
      } catch (err) {
        setSendError((err as Error).message);
      } finally {
        setSending(false);
      }
    },
    [messageDraft, selectedDialogId, loadDialogMessages, detail],
  );

  const currentDialog = detail?.dialog;

  return (
    <div className="grid gap-6 xl:grid-cols-[280px_1fr_320px]">
      <aside className="glass-panel flex h-[720px] flex-col rounded-[28px] border border-[var(--app-border)] p-5 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.45)] backdrop-blur-2xl">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Диалоги</h2>
            <p className="text-xs text-muted-foreground">Список активных обращений</p>
          </div>
          <Button variant="ghost" size="icon" onClick={() => loadDialogs()} disabled={loadingDialogs}>
            {loadingDialogs ? <Loader2 className="size-4 animate-spin" /> : <RefreshCcw className="size-4" />}
          </Button>
        </div>

        <div className="mt-4 flex-1 space-y-2 overflow-y-auto pr-2">
          {loadingDialogs && dialogs.length === 0 ? (
            <div className="rounded-2xl bg-white/70 p-4 text-sm text-muted-foreground">Загружаем диалоги…</div>
          ) : dialogs.length === 0 ? (
            <div className="rounded-2xl bg-white/70 p-4 text-sm text-muted-foreground">
              Диалогов пока нет. Ответы появятся после первых сообщений клиентов.
            </div>
          ) : (
            dialogs.map((dialog) => {
              const isActive = dialog.id === selectedDialogId;
              const primaryLabel =
                dialog.source === 'telegram'
                  ? `Telegram • ${dialog.external_display_name || dialog.external_username || dialog.avito_dialog_id}`
                  : `Avito #${dialog.avito_dialog_id}`;
              const secondaryLabel =
                dialog.source === 'telegram'
                  ? dialog.external_username
                    ? `@${dialog.external_username}`
                    : dialog.external_reference
                    ? `ID: ${dialog.external_reference}`
                    : `Диалог #${dialog.id}`
                  : `Диалог #${dialog.id}`;
              return (
                <button
                  key={dialog.id}
                  type="button"
                  onClick={() => setSelectedDialogId(dialog.id)}
                  className={cn(
                    'w-full rounded-2xl border border-transparent p-4 text-left transition-colors',
                    'bg-white/70 hover:border-blue-200 hover:bg-white shadow-sm shadow-blue-100',
                    isActive && 'border-blue-300 bg-blue-50/70 shadow-[0_12px_40px_-30px_rgba(30,64,175,0.75)]',
                  )}
                >
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{primaryLabel}</span>
                    {dialog.last_message_at ? <span>{formatDate(dialog.last_message_at)}</span> : null}
                  </div>
                  <div className="mt-2 text-sm font-medium text-foreground">{secondaryLabel}</div>
                  {dialog.telegram_topic_id ? (
                    <p className="mt-1 text-xs text-muted-foreground">ID топика: {dialog.telegram_topic_id}</p>
                  ) : null}
                </button>
              );
            })
          )}
        </div>
      </aside>

      <section className="glass-panel flex h-[720px] flex-col rounded-[28px] border border-[var(--app-border)] p-6 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.45)] backdrop-blur-2xl">
        {error && (
          <Alert variant="destructive" className="mb-4">
            <AlertTitle>Не удалось загрузить данные</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {!currentDialog ? (
          <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
            Выберите диалог слева, чтобы продолжить переписку.
          </div>
        ) : (
          <>
            <header className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-white/80 px-4 py-3 shadow-inner shadow-blue-100">
              <div>
                <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                  {currentDialog.source === 'telegram' ? 'Диалог из Telegram' : 'Диалог из Avito'}
                </p>
                <h2 className="text-lg font-semibold text-foreground">
                  {currentDialog.source === 'telegram'
                    ? `Telegram • ${currentDialog.external_display_name || currentDialog.external_username || currentDialog.avito_dialog_id}`
                    : `Avito #${currentDialog.avito_dialog_id}`}
                </h2>
                <p className="text-xs text-muted-foreground">
                  {currentDialog.source === 'telegram'
                    ? [
                        currentDialog.external_username ? `@${currentDialog.external_username}` : null,
                        currentDialog.external_reference ? `ID: ${currentDialog.external_reference}` : null,
                        currentDialog.telegram_topic_id ? `Топик: ${currentDialog.telegram_topic_id}` : null,
                      ]
                        .filter(Boolean)
                        .join(' • ') || 'Источник Telegram'
                    : currentDialog.telegram_topic_id
                    ? `Топик Telegram: ${currentDialog.telegram_topic_id}`
                    : 'Топик ещё не создан'}
                </p>
              </div>
              <Badge appearance="light" variant="secondary" size="sm">
                {currentDialog.state ?? 'active'}
              </Badge>
            </header>

            <div className="mt-4 flex-1 overflow-y-auto pr-2">
              {loadingMessages && sortedMessages.length === 0 ? (
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                  <Loader2 className="mr-2 size-4 animate-spin" /> Загружаем переписку…
                </div>
              ) : sortedMessages.length === 0 ? (
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                  Пока нет сообщений. Напишите клиенту первыми.
                </div>
              ) : (
                <div className="space-y-3">
                  {sortedMessages.map((message) => {
                    const isOutgoing =
                      message.direction === 'telegram' || message.direction === 'telegram_source_out';
                    const timestamp = formatDateTime(message.created_at);
                    const metaColor = isOutgoing ? 'text-primary-foreground/70' : 'text-slate-500';
                    const statusLabel = message.status?.toUpperCase();

                    return (
                      <div key={message.id} className={cn('flex', isOutgoing ? 'justify-end' : 'justify-start')}>
                        <div
                          className={cn(
                            'max-w-[75%] rounded-2xl px-4 py-3 text-sm shadow-sm transition-colors',
                            isOutgoing
                              ? 'bg-primary text-primary-foreground shadow-blue-200/50'
                              : 'bg-white/80 text-foreground shadow-blue-100',
                          )}
                        >
                          <div className={cn('flex items-center justify-between gap-3 text-[11px] leading-[1.1]', metaColor)}>
                            <time dateTime={message.created_at} className="font-medium whitespace-nowrap normal-case">
                              {timestamp}
                            </time>
                            {statusLabel ? (
                              <span className="uppercase tracking-[0.18em] text-[10px]">{statusLabel}</span>
                            ) : null}
                          </div>
                          {message.body ? (
                            <p className="mt-2 whitespace-pre-line break-words text-sm leading-relaxed">{message.body}</p>
                          ) : null}
                          {message.attachments ? (
                            <div className="mt-2 text-xs text-primary-foreground/80">
                              Вложение: {Array.isArray(message.attachments) ? message.attachments.length : 1}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            <form onSubmit={handleSend} className="mt-4 space-y-3">
              {sendError && (
                <Alert variant="destructive">
                  <AlertTitle>Не удалось отправить сообщение</AlertTitle>
                  <AlertDescription>{sendError}</AlertDescription>
                </Alert>
              )}
              {currentDialog.source === 'telegram' ? (
                <Alert appearance="light" className="border-blue-200/70 bg-blue-50/70 text-blue-900">
                  <AlertDescription>
                    Ответы для этого источника отправляются напрямую из рабочего чата Telegram. Используйте соответствующий топик, чтобы продолжить переписку.
                  </AlertDescription>
                </Alert>
              ) : null}
              <div className="flex items-end gap-3">
                <Textarea
                  value={messageDraft}
                  onChange={(event) => setMessageDraft(event.target.value)}
                  placeholder={currentDialog.source === 'telegram' ? 'Отправка доступна только из Telegram-чата' : 'Напишите ответ клиенту...'}
                  rows={3}
                  disabled={sending || currentDialog.source === 'telegram'}
                  className="flex-1 resize-none"
                />
                <Button
                  type="submit"
                  disabled={
                    sending || !messageDraft.trim() || currentDialog.source === 'telegram'
                  }
                  variant="primary"
                  className="flex h-12 w-12 items-center justify-center rounded-full p-0 shadow-[0_18px_40px_-18px_rgba(59,130,246,0.7)] transition-transform hover:scale-105"
                  aria-label="Отправить сообщение"
                >
                  {sending ? <Loader2 className="size-5 animate-spin" /> : <SendHorizontal className="size-5" />}
                </Button>
              </div>
            </form>
          </>
        )}
      </section>

      <aside className="glass-panel h-[720px] rounded-[28px] border border-[var(--app-border)] p-6 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.45)] backdrop-blur-2xl">
        <h2 className="text-lg font-semibold text-foreground">Информация о диалоге</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Здесь появится аналитика: скорость ответов, статус воронки, KPI менеджеров. Пока это тематическая заглушка.
        </p>
        <div className="mt-4 space-y-3 rounded-2xl bg-white/80 p-4 text-sm shadow-inner shadow-blue-100">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Источник</span>
            <span className="font-medium text-foreground">
              {currentDialog?.source === 'telegram' ? 'Telegram бот' : 'Avito аккаунт'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Создан</span>
            <span className="font-medium text-foreground">{formatDate(currentDialog?.created_at)}</span>
          </div>
          {currentDialog?.source === 'telegram' ? (
            <>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Пользователь</span>
                <span className="font-medium text-foreground">
                  {currentDialog.external_display_name || currentDialog.external_username || '—'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Username</span>
                <span className="font-medium text-foreground">
                  {currentDialog.external_username ? `@${currentDialog.external_username}` : '—'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Chat ID</span>
                <span className="font-medium text-foreground">{currentDialog.external_reference ?? '—'}</span>
              </div>
            </>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Avito ID</span>
                <span className="font-medium text-foreground">{currentDialog?.avito_dialog_id ?? '—'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Telegram чат</span>
                <span className="font-medium text-foreground">{currentDialog?.telegram_chat_id ?? '—'}</span>
              </div>
            </>
          )}
        </div>
        <div className="mt-6 space-y-3 rounded-2xl bg-gradient-to-br from-blue-500/10 via-indigo-400/5 to-white/60 p-4 text-sm text-muted-foreground shadow-inner shadow-blue-100">
          <p>
            📊 В будущем здесь появятся показатели по диалогу: время ответа, вовлечённость клиента, количество сообщений и
            статус выполнения.
          </p>
          <p>💡 Наша команда уже готовит визуализации и рекомендации — следите за обновлениями!</p>
        </div>
      </aside>
    </div>
  );
}
