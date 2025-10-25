'use client';

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/base-badge';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogClose,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/base-alert-dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/base-input';
import { Label } from '@/components/ui/base-label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/base-select';
import { Switch } from '@/components/ui/base-switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';
import { apiFetch } from '@/lib/api';
import type { AvitoAccount, Bot, Project, TelegramSource } from '../../types';
import { ArrowLeft, Loader2, RefreshCcw, ShieldCheck, Sparkles, Trash2 } from 'lucide-react';

const TIME_OPTIONS = [
  '06:00',
  '07:00',
  '08:00',
  '09:00',
  '10:00',
  '11:00',
  '12:00',
  '13:00',
  '14:00',
  '15:00',
  '16:00',
  '17:00',
  '18:00',
  '19:00',
  '20:00',
  '21:00',
];

type AutoReplyFormState = {
  autoReplyEnabled: boolean;
  autoReplyText: string;
  autoReplyTimezone: string;
  autoReplyAlways: boolean;
  autoReplyStartTime: string;
  autoReplyEndTime: string;
  requireReply: boolean;
  hideSystemMessages: boolean;
};

type AvitoFormState = {
  name: string;
  apiClientId: string;
  apiClientSecret: string;
  monitoringEnabled: boolean;
};

type TelegramSourceFormState = {
  token: string;
  displayName: string;
  description: string;
};

const initialAutoReplyState: AutoReplyFormState = {
  autoReplyEnabled: false,
  autoReplyText: '',
  autoReplyTimezone: 'Europe/Moscow',
  autoReplyAlways: true,
  autoReplyStartTime: '09:00',
  autoReplyEndTime: '18:00',
  requireReply: false,
  hideSystemMessages: true,
};

const initialAvitoForm: AvitoFormState = {
  name: '',
  apiClientId: '',
  apiClientSecret: '',
  monitoringEnabled: true,
};

const initialTelegramSourceForm: TelegramSourceFormState = {
  token: '',
  displayName: '',
  description: '',
};

const TIMEZONE_OPTIONS = [
  { value: 'Europe/Kaliningrad', label: 'Калининград (UTC+2)' },
  { value: 'Europe/Moscow', label: 'Москва (UTC+3)' },
  { value: 'Europe/Samara', label: 'Самара (UTC+4)' },
  { value: 'Asia/Yekaterinburg', label: 'Екатеринбург (UTC+5)' },
  { value: 'Asia/Omsk', label: 'Омск (UTC+6)' },
  { value: 'Asia/Novosibirsk', label: 'Новосибирск (UTC+7)' },
  { value: 'Asia/Krasnoyarsk', label: 'Красноярск (UTC+7)' },
  { value: 'Asia/Irkutsk', label: 'Иркутск (UTC+8)' },
  { value: 'Asia/Yakutsk', label: 'Якутск (UTC+9)' },
  { value: 'Asia/Vladivostok', label: 'Владивосток (UTC+10)' },
  { value: 'Asia/Sakhalin', label: 'Сахалин (UTC+11)' },
  { value: 'Asia/Magadan', label: 'Магадан (UTC+11)' },
  { value: 'Asia/Kamchatka', label: 'Камчатка (UTC+12)' },
  { value: 'Asia/Anadyr', label: 'Анадырь (UTC+12)' },
];

function formatTimeForInput(value?: string | null) {
  if (!value) return '09:00';
  return value.slice(0, 5);
}

export default function ProjectDetailPage() {
  const params = useParams<{ projectId: string }>();
  const router = useRouter();
  const projectId = Number(params.projectId);

  const [project, setProject] = useState<Project | null>(null);
  const [bot, setBot] = useState<Bot | null>(null);
  const [accounts, setAccounts] = useState<AvitoAccount[]>([]);
  const [sources, setSources] = useState<TelegramSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [autoReplyForm, setAutoReplyForm] = useState<AutoReplyFormState>(initialAutoReplyState);
  const [autoReplyError, setAutoReplyError] = useState<string | null>(null);
  const [autoReplySubmitting, setAutoReplySubmitting] = useState(false);

  const [avitoForm, setAvitoForm] = useState<AvitoFormState>(initialAvitoForm);
  const [avitoError, setAvitoError] = useState<string | null>(null);
  const [avitoSubmitting, setAvitoSubmitting] = useState(false);

  const [telegramForm, setTelegramForm] = useState<TelegramSourceFormState>(initialTelegramSourceForm);
  const [telegramError, setTelegramError] = useState<string | null>(null);
  const [telegramSubmitting, setTelegramSubmitting] = useState(false);

  const [deletingAvitoId, setDeletingAvitoId] = useState<number | null>(null);
  const [deletingSourceId, setDeletingSourceId] = useState<number | null>(null);
  const [deletingProject, setDeletingProject] = useState(false);
  const [avitoDeleteError, setAvitoDeleteError] = useState<string | null>(null);
  const [telegramDeleteError, setTelegramDeleteError] = useState<string | null>(null);
  const [projectDeleteError, setProjectDeleteError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!Number.isFinite(projectId)) {
      setError('Некорректный идентификатор проекта.');
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const [projectResp, botsResp, accountsResp, sourcesResp] = await Promise.all([
        apiFetch(`/api/projects/${projectId}`),
        apiFetch('/api/bots/'),
        apiFetch(`/api/avito/accounts?project_id=${projectId}`),
        apiFetch(`/api/telegram-sources?project_id=${projectId}`),
      ]);

      setProject(projectResp);
      setBot(projectResp?.bot_id ? botsResp.find((candidate: Bot) => candidate.id === projectResp.bot_id) ?? null : null);
      setAccounts(accountsResp);
      setSources(sourcesResp);
      setError(null);

      setAutoReplyForm({
        autoReplyEnabled: projectResp.auto_reply_enabled,
        autoReplyText: projectResp.auto_reply_text ?? '',
        autoReplyTimezone: projectResp.auto_reply_timezone ?? 'Europe/Moscow',
        autoReplyAlways: projectResp.auto_reply_always,
        autoReplyStartTime: formatTimeForInput(projectResp.auto_reply_start_time),
        autoReplyEndTime: formatTimeForInput(projectResp.auto_reply_end_time),
        requireReply: projectResp.require_reply_for_sources,
        hideSystemMessages: projectResp.hide_system_messages,
      });
      setAvitoDeleteError(null);
      setTelegramDeleteError(null);
      setProjectDeleteError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!project) {
      return;
    }
    const previousTitle = document.title;
    document.title = `${project.name} — Проект | Tuberry`;
    return () => {
      document.title = previousTitle;
    };
  }, [project]);

  const projectSlug = useMemo(() => (project?.slug ? `/${project.slug}` : `#${project?.id ?? ''}`), [project]);
  const hasConnectedSources = useMemo(
    () => accounts.length > 0 || sources.length > 0,
    [accounts.length, sources.length],
  );

  const handleAutoReplySubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!project) {
        return;
      }

      if (autoReplyForm.autoReplyEnabled && !autoReplyForm.autoReplyText.trim()) {
        setAutoReplyError('Добавьте текст автоответа или отключите автоответчик.');
        return;
      }
      if (
        autoReplyForm.autoReplyEnabled &&
        !autoReplyForm.autoReplyAlways &&
        autoReplyForm.autoReplyStartTime === autoReplyForm.autoReplyEndTime
      ) {
        setAutoReplyError('Время начала и окончания не должны совпадать.');
        return;
      }

      setAutoReplySubmitting(true);
      setAutoReplyError(null);
      try {
        const payload: Record<string, unknown> = {
          auto_reply_enabled: autoReplyForm.autoReplyEnabled,
          auto_reply_text: autoReplyForm.autoReplyEnabled ? autoReplyForm.autoReplyText.trim() : null,
          auto_reply_timezone: autoReplyForm.autoReplyEnabled ? autoReplyForm.autoReplyTimezone : null,
          auto_reply_always: autoReplyForm.autoReplyAlways,
          require_reply_for_sources: autoReplyForm.requireReply,
          hide_system_messages: autoReplyForm.hideSystemMessages,
        };

        if (!autoReplyForm.autoReplyAlways) {
          payload.auto_reply_start_time = autoReplyForm.autoReplyStartTime;
          payload.auto_reply_end_time = autoReplyForm.autoReplyEndTime;
        } else {
          payload.auto_reply_start_time = null;
          payload.auto_reply_end_time = null;
        }

        await apiFetch(`/api/projects/${project.id}`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
        await load();
      } catch (err) {
        setAutoReplyError((err as Error).message);
      } finally {
        setAutoReplySubmitting(false);
      }
    },
    [autoReplyForm, load, project],
  );

  const handleCreateAvitoAccount = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!project) {
        return;
      }
      if (!project.bot_id) {
        setAvitoError('Для проекта не выбран Telegram-бот.');
        return;
      }
      if (!avitoForm.apiClientId.trim() || !avitoForm.apiClientSecret.trim()) {
        setAvitoError('Укажите client_id и client_secret, выданные в кабинете Авито.');
        return;
      }
      setAvitoSubmitting(true);
      setAvitoError(null);
      try {
        await apiFetch('/api/avito/accounts', {
          method: 'POST',
          body: JSON.stringify({
            name: avitoForm.name.trim() || undefined,
            api_client_id: avitoForm.apiClientId.trim(),
            api_client_secret: avitoForm.apiClientSecret.trim(),
            bot_id: project.bot_id,
            project_id: project.id,
            monitoring_enabled: avitoForm.monitoringEnabled,
          }),
        });
        setAvitoForm(initialAvitoForm);
        await load();
      } catch (err) {
        setAvitoError((err as Error).message);
      } finally {
        setAvitoSubmitting(false);
      }
    },
    [avitoForm, load, project],
  );

  const handleCreateTelegramSource = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!project) return;
      if (!project.bot_id) {
        setTelegramError('Привяжите управляющего бота к проекту, чтобы подключить источник.');
        return;
      }
      if (!telegramForm.token.trim()) {
        setTelegramError('Введите токен Telegram-бота.');
        return;
      }
      setTelegramSubmitting(true);
      setTelegramError(null);
      try {
        await apiFetch('/api/telegram-sources', {
          method: 'POST',
          body: JSON.stringify({
            token: telegramForm.token.trim(),
            display_name: telegramForm.displayName.trim() || undefined,
            description: telegramForm.description.trim() || undefined,
            bot_id: project.bot_id,
            project_id: project.id,
          }),
        });
        setTelegramForm(initialTelegramSourceForm);
        await load();
      } catch (err) {
        setTelegramError((err as Error).message);
      } finally {
        setTelegramSubmitting(false);
      }
    },
    [load, project, telegramForm],
  );

  const handleDeleteAvitoAccount = useCallback(
    async (accountId: number) => {
      setDeletingAvitoId(accountId);
      setAvitoDeleteError(null);
      try {
        await apiFetch(`/api/avito/accounts/${accountId}`, {
          method: 'DELETE',
        });
        await load();
      } catch (err) {
        setAvitoDeleteError((err as Error).message);
      } finally {
        setDeletingAvitoId(null);
      }
    },
    [load],
  );

  const handleDeleteTelegramSource = useCallback(
    async (sourceId: number) => {
      setDeletingSourceId(sourceId);
      setTelegramDeleteError(null);
      try {
        await apiFetch(`/api/telegram-sources/${sourceId}`, {
          method: 'DELETE',
        });
        await load();
      } catch (err) {
        setTelegramDeleteError((err as Error).message);
      } finally {
        setDeletingSourceId(null);
      }
    },
    [load],
  );

  const handleDeleteProject = useCallback(async () => {
    if (!project) {
      return;
    }
    if (accounts.length > 0 || sources.length > 0) {
      setProjectDeleteError('Удалите подключённые источники перед удалением проекта.');
      return;
    }
    setDeletingProject(true);
    setProjectDeleteError(null);
    try {
      await apiFetch(`/api/projects/${project.id}`, { method: 'DELETE' });
      router.replace('/client');
    } catch (err) {
      setProjectDeleteError((err as Error).message);
    } finally {
      setDeletingProject(false);
    }
  }, [accounts, project, router, sources]);

  if (!Number.isFinite(projectId)) {
    return (
      <div className="space-y-6">
        <Alert variant="destructive" appearance="light">
          <AlertTitle>Некорректный идентификатор проекта</AlertTitle>
          <AlertDescription>Проверьте адрес страницы и попробуйте снова.</AlertDescription>
        </Alert>
        <Button variant="outline" onClick={() => router.push('/client')}>
          <ArrowLeft className="mr-2 size-4" />
          Вернуться к списку проектов
        </Button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-72 items-center justify-center">
        <div className="glass-panel flex items-center gap-3 rounded-[28px] px-6 py-4 text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          <span>Загружаем данные проекта…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <Alert variant="destructive" appearance="light">
          <AlertTitle>Не удалось загрузить проект</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button variant="outline" onClick={() => router.push('/client')}>
          <ArrowLeft className="mr-2 size-4" />
          Вернуться к списку проектов
        </Button>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="space-y-6">
        <Alert appearance="light">
          <AlertTitle>Проект не найден</AlertTitle>
          <AlertDescription>
            Возможно, он был удалён. Вернитесь к списку проектов и выберите другой.
          </AlertDescription>
        </Alert>
        <Button variant="outline" onClick={() => router.push('/client')}>
          <ArrowLeft className="mr-2 size-4" />
          Вернуться назад
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-12 pb-14">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-3 text-xs uppercase tracking-[0.2em] text-muted-foreground">
            <Link href="/client" className="hover:text-foreground">
              Проекты
            </Link>
            <span>/</span>
            <span>{projectSlug}</span>
          </div>
          <h1 className="text-3xl font-semibold text-foreground">{project.name}</h1>
          {project.description && <p className="max-w-2xl text-sm text-muted-foreground">{project.description}</p>}
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => load()} disabled={loading}>
            <RefreshCcw className="mr-2 size-4" />
            Обновить
          </Button>
          <AlertDialog>
            <AlertDialogTrigger
              render={({ ref, ...triggerProps }) => (
                <Button
                  ref={ref}
                  {...triggerProps}
                  variant="destructive"
                  size="sm"
                  disabled={hasConnectedSources || deletingProject}
                  title={
                    hasConnectedSources
                      ? 'Удалите Авито аккаунты и Telegram источники, чтобы разблокировать удаление проекта'
                      : undefined
                  }
                >
                  {deletingProject ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Trash2 className="mr-2 size-4" />}
                  Удалить проект
                </Button>
              )}
            />
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Удалить проект «{project.name}»?</AlertDialogTitle>
                <AlertDialogDescription>
                  Проект и его настройки будут удалены без возможности восстановления. Убедитесь, что все важные данные
                  выгружены.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogClose
                  render={({ ref, ...closeProps }) => (
                    <Button ref={ref} {...closeProps} variant="outline" size="sm">
                      Отмена
                    </Button>
                  )}
                />
                <AlertDialogAction
                  onClick={async () => {
                    await handleDeleteProject();
                  }}
                  render={({ ref, ...actionProps }) => (
                    <Button
                      ref={ref}
                      {...actionProps}
                      variant="destructive"
                      size="sm"
                      disabled={deletingProject}
                    >
                      {deletingProject ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Trash2 className="mr-2 size-4" />}
                      Удалить
                    </Button>
                  )}
                />
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <Button asChild variant="secondary" size="sm">
            <Link href="/client">
              <ArrowLeft className="mr-2 size-4" />
              К проектам
            </Link>
          </Button>
        </div>
      </div>

      {hasConnectedSources && (
        <Alert variant="warning" appearance="light">
          <AlertTitle>В проекте есть подключённые источники</AlertTitle>
          <AlertDescription>
            Удалите все Avito аккаунты и Telegram источники, прежде чем удалять проект.
          </AlertDescription>
        </Alert>
      )}

      {projectDeleteError && (
        <Alert variant="destructive" appearance="light">
          <AlertDescription>{projectDeleteError}</AlertDescription>
        </Alert>
      )}

      <section className="space-y-6">
        <div className="glass-panel h-full rounded-[28px] border border-[var(--app-border)] p-6 shadow-lg shadow-blue-100">
          <div className="space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Основные параметры</p>
                <p className="text-sm text-muted-foreground">
                  Управляющий бот: {bot ? `@${bot.bot_username ?? `bot_${bot.id}`}` : 'не выбран'}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={project.auto_reply_enabled ? 'success' : 'secondary'} appearance="light" size="sm">
                  {project.auto_reply_enabled ? 'Автоответ включен' : 'Автоответ выключен'}
                </Badge>
                <Badge variant={project.hide_system_messages ? 'secondary' : 'warning'} appearance="light" size="sm">
                  {project.hide_system_messages ? 'Фильтрация системных сообщений' : 'Без фильтрации'}
                </Badge>
              </div>
            </div>
            <div className="rounded-2xl border border-dashed border-[var(--app-border)] p-4">
              <div className="grid gap-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Дата создания</span>
                  <span className="font-medium text-foreground">
                    {project.created_at
                      ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium' }).format(new Date(project.created_at))
                      : '—'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Идентификатор проекта</span>
                  <span className="font-medium text-foreground">#{project.id}</span>
                </div>
              </div>
            </div>
            <div className="flex items-center justify-between gap-3 rounded-2xl border border-dashed border-[var(--app-border)] p-4">
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">Требовать цитирование ответов</p>
                <p className="text-xs text-muted-foreground">
                  При включении операторам нужно отвечать с цитатой сообщения клиента независимо от источника.
                </p>
              </div>
              <Switch
                checked={autoReplyForm.requireReply}
                onCheckedChange={(value) => setAutoReplyForm((prev) => ({ ...prev, requireReply: value }))}
              />
            </div>
            {!project.bot_id && (
              <Alert appearance="light" variant="warning" className="border-yellow-200/70 bg-yellow-50/70">
                <AlertTitle>Не выбран управляющий бот</AlertTitle>
                <AlertDescription>
                  Привяжите Telegram-бота к проекту через раздел управления ботами, чтобы подключать источники и отправлять
                  сообщения в Авито.
                </AlertDescription>
              </Alert>
            )}
          </div>
        </div>

        <form
          className="glass-panel h-full rounded-[28px] border border-[var(--app-border)] p-6 shadow-lg shadow-blue-100 space-y-6"
          onSubmit={handleAutoReplySubmit}
        >
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-foreground">Автоответ и фильтрация</h2>
              <p className="text-sm text-muted-foreground">Настройте правила автоответчика и поведение диалогов.</p>
            </div>
            <Switch
              checked={autoReplyForm.autoReplyEnabled}
              onCheckedChange={(value) => setAutoReplyForm((prev) => ({ ...prev, autoReplyEnabled: value }))}
            />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="space-y-2 lg:col-span-2">
              <Label htmlFor="auto-reply-text">Текст автоответа</Label>
              <Textarea
                id="auto-reply-text"
                value={autoReplyForm.autoReplyText}
                onChange={(event) => setAutoReplyForm((prev) => ({ ...prev, autoReplyText: event.target.value }))}
                placeholder="Спасибо за обращение! Наш менеджер свяжется с вами в ближайшее время."
                rows={3}
                disabled={!autoReplyForm.autoReplyEnabled}
              />
            </div>
            <div className="space-y-2">
              <Label>Часовой пояс</Label>
              <Select
                value={autoReplyForm.autoReplyTimezone}
                onValueChange={(value: string) => setAutoReplyForm((prev) => ({ ...prev, autoReplyTimezone: value }))}
                disabled={!autoReplyForm.autoReplyEnabled}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Выберите часовой пояс" />
                </SelectTrigger>
                <SelectContent>
                  {TIMEZONE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Режим</Label>
              <div className="flex items-center gap-3 rounded-2xl border border-dashed border-[var(--app-border)] p-4">
                <div className="space-y-1 text-sm">
                  <p className="font-medium text-foreground">Отправлять всегда</p>
                  <p className="text-xs text-muted-foreground">
                    Если выключить, автоответ сработает только в рабочее время.
                  </p>
                </div>
                <Switch
                  checked={autoReplyForm.autoReplyAlways}
                  onCheckedChange={(value) => setAutoReplyForm((prev) => ({ ...prev, autoReplyAlways: value }))}
                  disabled={!autoReplyForm.autoReplyEnabled}
                />
              </div>
            </div>
            {!autoReplyForm.autoReplyAlways && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="start-time">Начало</Label>
                  <Select
                value={autoReplyForm.autoReplyStartTime}
                onValueChange={(value: string) => setAutoReplyForm((prev) => ({ ...prev, autoReplyStartTime: value }))}
                disabled={!autoReplyForm.autoReplyEnabled}
              >
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите время" />
                    </SelectTrigger>
                    <SelectContent>
                      {TIME_OPTIONS.map((time) => (
                        <SelectItem key={time} value={time}>
                          {time}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="end-time">Завершение</Label>
                  <Select
                    value={autoReplyForm.autoReplyEndTime}
                    onValueChange={(value: string) => setAutoReplyForm((prev) => ({ ...prev, autoReplyEndTime: value }))}
                    disabled={!autoReplyForm.autoReplyEnabled}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите время" />
                    </SelectTrigger>
                    <SelectContent>
                      {TIME_OPTIONS.map((time) => (
                        <SelectItem key={time} value={time}>
                          {time}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}
          </div>

          {autoReplyError && (
            <Alert variant="destructive" appearance="light">
              <AlertDescription>{autoReplyError}</AlertDescription>
            </Alert>
          )}

          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">
              Автоответ отправляется один раз за интервал. При ручном ответе запланированные автоответы отменяются.
            </p>
            <Button type="submit" disabled={autoReplySubmitting}>
              {autoReplySubmitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : <ShieldCheck className="mr-2 size-4" />}
              Сохранить настройки
            </Button>
          </div>
        </form>
      </section>

      <section className="space-y-6">
        <div className="glass-panel rounded-[28px] border border-[var(--app-border)] p-6 shadow-lg shadow-blue-100 space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-foreground">Avito аккаунты</h2>
            <p className="text-sm text-muted-foreground">Подключенные акаунты используются для отправки сообщений и получения диалогов.</p>
          </div>
          <div className="grid gap-3 rounded-2xl border border-dashed border-[var(--app-border)] p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">Скрывать системные сообщения</p>
                <p className="text-xs text-muted-foreground">Удаляет служебные уведомления площадок из диалога.</p>
              </div>
              <Switch
                checked={autoReplyForm.hideSystemMessages}
                onCheckedChange={(value) => setAutoReplyForm((prev) => ({ ...prev, hideSystemMessages: value }))}
              />
            </div>
          </div>
          {accounts.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Название</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead>Мониторинг</TableHead>
                  <TableHead className="w-[140px] text-right">Действия</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accounts.map((account) => (
                  <TableRow key={account.id}>
                    <TableCell className="font-medium">{account.name || `Account #${account.id}`}</TableCell>
                    <TableCell>
                      <Badge appearance="light" variant={account.status === 'active' ? 'success' : account.status === 'expired' ? 'warning' : 'secondary'} size="sm">
                        {account.status === 'active' ? 'Активен' : account.status === 'expired' ? 'Требует обновления' : 'Заблокирован'}
                      </Badge>
                    </TableCell>
                    <TableCell>{account.monitoring_enabled ? 'Вкл.' : 'Выкл.'}</TableCell>
                    <TableCell className="text-right">
                      <AlertDialog>
                        <AlertDialogTrigger
                          render={({ ref, ...triggerProps }) => (
                            <Button
                              ref={ref}
                              {...triggerProps}
                              variant="ghost"
                              size="sm"
                              className="text-destructive hover:text-destructive"
                              disabled={deletingAvitoId === account.id}
                            >
                              {deletingAvitoId === account.id ? (
                                <>
                                  <Loader2 className="mr-2 size-4 animate-spin" />
                                  Удаляем...
                                </>
                              ) : (
                                <>
                                  <Trash2 className="mr-2 size-4" />
                                  Удалить
                                </>
                              )}
                            </Button>
                          )}
                        />
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Удалить аккаунт «{account.name || `Account #${account.id}`}»?</AlertDialogTitle>
                            <AlertDialogDescription>
                              Интеграция будет отключена, вебхук в Авито удалится автоматически, связанные диалоги будут очищены.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogClose
                              render={({ ref, ...closeProps }) => (
                                <Button ref={ref} {...closeProps} variant="outline" size="sm">
                                  Отмена
                                </Button>
                              )}
                            />
                            <AlertDialogAction
                              onClick={async () => {
                                await handleDeleteAvitoAccount(account.id);
                              }}
                              render={({ ref, ...actionProps }) => (
                                <Button
                                  ref={ref}
                                  {...actionProps}
                                  variant="destructive"
                                  size="sm"
                                  disabled={deletingAvitoId === account.id}
                                >
                                  {deletingAvitoId === account.id ? (
                                    <Loader2 className="mr-2 size-4 animate-spin" />
                                  ) : (
                                    <Trash2 className="mr-2 size-4" />
                                  )}
                                  Удалить
                                </Button>
                              )}
                            />
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">Подключений пока нет. Добавьте данные OAuth клиента, чтобы получать диалоги.</p>
          )}
          {avitoDeleteError && (
            <Alert variant="destructive" appearance="light">
              <AlertDescription>{avitoDeleteError}</AlertDescription>
            </Alert>
          )}
          <form className="space-y-4 rounded-2xl border border-dashed border-[var(--app-border)] p-4" onSubmit={handleCreateAvitoAccount}>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="avito-name">Название</Label>
                <Input
                  id="avito-name"
                  value={avitoForm.name}
                  onChange={(event) => setAvitoForm((prev) => ({ ...prev, name: event.target.value }))}
                  placeholder="Например, «Главный аккаунт»"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="avito-client-id">client_id</Label>
                <Input
                  id="avito-client-id"
                  value={avitoForm.apiClientId}
                  onChange={(event) => setAvitoForm((prev) => ({ ...prev, apiClientId: event.target.value }))}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="avito-client-secret">client_secret</Label>
                <Input
                  id="avito-client-secret"
                  value={avitoForm.apiClientSecret}
                  onChange={(event) => setAvitoForm((prev) => ({ ...prev, apiClientSecret: event.target.value }))}
                  required
                />
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-dashed border-[var(--app-border)] p-3 md:col-span-2">
                <div className="space-y-1 text-sm">
                  <p className="font-medium text-foreground">Включить мониторинг</p>
                  <p className="text-xs text-muted-foreground">Отключите, если хотите использовать аккаунт только для отправки.</p>
                </div>
                <Switch
                  checked={avitoForm.monitoringEnabled}
                  onCheckedChange={(value) => setAvitoForm((prev) => ({ ...prev, monitoringEnabled: value }))}
                />
              </div>
            </div>
            {avitoError && (
              <Alert variant="destructive" appearance="light">
                <AlertDescription>{avitoError}</AlertDescription>
              </Alert>
            )}
            <Button type="submit" disabled={avitoSubmitting || !project.bot_id}>
              {avitoSubmitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Sparkles className="mr-2 size-4" />}
              Добавить аккаунт
            </Button>
          </form>
        </div>

        <div className="glass-panel rounded-[28px] border border-[var(--app-border)] p-6 shadow-lg shadow-blue-100 space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-foreground">Telegram источники</h2>
            <p className="text-sm text-muted-foreground">Источники переводят сообщения из других ботов и каналов в рабочий чат проекта.</p>
          </div>
          {sources.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Источник</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead>Описание</TableHead>
                  <TableHead className="w-[140px] text-right">Действия</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sources.map((source) => (
                  <TableRow key={source.id}>
                    <TableCell className="font-medium">{source.display_name || `Источник #${source.id}`}</TableCell>
                    <TableCell>
                      <Badge
                        appearance="light"
                        variant={
                          source.status === 'active'
                            ? 'success'
                            : source.status === 'error'
                              ? 'warning'
                              : 'secondary'
                        }
                        size="sm"
                      >
                        {source.status === 'active' ? 'Активен' : source.status === 'error' ? 'Ошибка' : 'Неактивен'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{source.description || '—'}</TableCell>
                    <TableCell className="text-right">
                      <AlertDialog>
                        <AlertDialogTrigger
                          render={({ ref, ...triggerProps }) => (
                            <Button
                              ref={ref}
                              {...triggerProps}
                              variant="ghost"
                              size="sm"
                              className="text-destructive hover:text-destructive"
                              disabled={deletingSourceId === source.id}
                            >
                              {deletingSourceId === source.id ? (
                                <>
                                  <Loader2 className="mr-2 size-4 animate-spin" />
                                  Удаляем...
                                </>
                              ) : (
                                <>
                                  <Trash2 className="mr-2 size-4" />
                                  Удалить
                                </>
                              )}
                            </Button>
                          )}
                        />
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Удалить источник «{source.display_name || `Источник #${source.id}`}»?</AlertDialogTitle>
                            <AlertDialogDescription>
                              Вебхук источника будет отключён, а связанные диалоги очищены.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogClose
                              render={({ ref, ...closeProps }) => (
                                <Button ref={ref} {...closeProps} variant="outline" size="sm">
                                  Отмена
                                </Button>
                              )}
                            />
                            <AlertDialogAction
                              onClick={async () => {
                                await handleDeleteTelegramSource(source.id);
                              }}
                              render={({ ref, ...actionProps }) => (
                                <Button
                                  ref={ref}
                                  {...actionProps}
                                  variant="destructive"
                                  size="sm"
                                  disabled={deletingSourceId === source.id}
                                >
                                  {deletingSourceId === source.id ? (
                                    <Loader2 className="mr-2 size-4 animate-spin" />
                                  ) : (
                                    <Trash2 className="mr-2 size-4" />
                                  )}
                                  Удалить
                                </Button>
                              )}
                            />
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">Источников пока нет. Подключите бота, чтобы собирать сообщения из каналов.</p>
          )}
          {telegramDeleteError && (
            <Alert variant="destructive" appearance="light">
              <AlertDescription>{telegramDeleteError}</AlertDescription>
            </Alert>
          )}
          <form className="space-y-4 rounded-2xl border border-dashed border-[var(--app-border)] p-4" onSubmit={handleCreateTelegramSource}>
            <div className="space-y-2">
              <Label htmlFor="telegram-token">Token</Label>
              <Input
                id="telegram-token"
                value={telegramForm.token}
                onChange={(event) => setTelegramForm((prev) => ({ ...prev, token: event.target.value }))}
                placeholder="123456:ABC-DEF..."
                required
              />
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="telegram-display-name">Отображаемое имя</Label>
                <Input
                  id="telegram-display-name"
                  value={telegramForm.displayName}
                  onChange={(event) => setTelegramForm((prev) => ({ ...prev, displayName: event.target.value }))}
                  placeholder="Чат поддержки"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="telegram-description">Описание</Label>
                <Input
                  id="telegram-description"
                  value={telegramForm.description}
                  onChange={(event) => setTelegramForm((prev) => ({ ...prev, description: event.target.value }))}
                  placeholder="Например, канал обратной связи"
                />
              </div>
            </div>
            {telegramError && (
              <Alert variant="destructive" appearance="light">
                <AlertDescription>{telegramError}</AlertDescription>
              </Alert>
            )}
            <Button type="submit" disabled={telegramSubmitting || !project.bot_id}>
              {telegramSubmitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Sparkles className="mr-2 size-4" />}
              Подключить источник
            </Button>
          </form>
        </div>
      </section>
    </div>
  );
}
