'use client';

import { FormEvent, ReactElement, cloneElement, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Accordion,
  AccordionHeader,
  AccordionItem,
  AccordionPanel,
  AccordionTrigger,
} from '@/components/ui/base-accordion';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/base-alert-dialog';
import { Badge } from '@/components/ui/base-badge';
import { Input } from '@/components/ui/base-input';
import { Label } from '@/components/ui/base-label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/base-select';
import { Switch } from '@/components/ui/base-switch';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { apiFetch } from '@/lib/api';
import type { AvitoAccount, Bot, Dialog, TelegramChat, TelegramSource } from '../types';
import { Eye, EyeOff, Loader2, RefreshCcw, Trash2 } from 'lucide-react';

const initialBotForm = {
  token: '',
};

const initialAvitoForm = {
  name: '',
  api_client_id: '',
  api_client_secret: '',
  bot_id: '',
};

const initialTelegramSourceForm = {
  token: '',
  bot_id: '',
  display_name: '',
  description: '',
};

const DEFAULT_AUTO_REPLY_START = '09:00';
const DEFAULT_AUTO_REPLY_END = '18:00';
const DEFAULT_AUTO_REPLY_TIMEZONE = 'Europe/Moscow';

const RUSSIAN_TIMEZONES = [
  { value: 'Europe/Kaliningrad', city: 'Калининград' },
  { value: 'Europe/Moscow', city: 'Москва' },
  { value: 'Europe/Samara', city: 'Самара' },
  { value: 'Asia/Yekaterinburg', city: 'Екатеринбург' },
  { value: 'Asia/Omsk', city: 'Омск' },
  { value: 'Asia/Novosibirsk', city: 'Новосибирск' },
  { value: 'Asia/Krasnoyarsk', city: 'Красноярск' },
  { value: 'Asia/Irkutsk', city: 'Иркутск' },
  { value: 'Asia/Yakutsk', city: 'Якутск' },
  { value: 'Asia/Vladivostok', city: 'Владивосток' },
  { value: 'Asia/Sakhalin', city: 'Южно-Сахалинск' },
  { value: 'Asia/Magadan', city: 'Магадан' },
  { value: 'Asia/Kamchatka', city: 'Петропавловск-Камчатский' },
  { value: 'Asia/Anadyr', city: 'Анадырь' },
];

function formatTimeValue(value: string | null | undefined, fallback: string): string {
  if (!value) {
    return fallback;
  }
  return value.slice(0, 5);
}

type ConfirmActionProps = {
  title: string;
  description: string;
  confirmLabel?: string;
  onConfirm: () => void | Promise<void>;
  children: ReactElement;
};

function ConfirmAction({ title, description, confirmLabel = 'Подтвердить', onConfirm, children }: ConfirmActionProps) {
  return (
    <AlertDialog>
      <AlertDialogTrigger
        render={({ ref, ...triggerProps }) => cloneElement(children, { ref, ...triggerProps })}
      />
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogAction
            className="min-w-[120px]"
            onClick={async () => {
              await onConfirm();
            }}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export default function ClientSettingsPage() {
  const [bots, setBots] = useState<Bot[]>([]);
  const [accounts, setAccounts] = useState<AvitoAccount[]>([]);
  const [dialogs, setDialogs] = useState<Dialog[]>([]);
  const [telegramSources, setTelegramSources] = useState<TelegramSource[]>([]);

  const [botForm, setBotForm] = useState(initialBotForm);
  const [avitoForm, setAvitoForm] = useState(initialAvitoForm);
  const [telegramSourceForm, setTelegramSourceForm] = useState(initialTelegramSourceForm);
  const [filterText, setFilterText] = useState('');
  const [requireReply, setRequireReply] = useState(false);
  const [hideSystemMessages, setHideSystemMessages] = useState(true);
  const [autoReplyEnabled, setAutoReplyEnabled] = useState(false);
  const [autoReplyAlways, setAutoReplyAlways] = useState(false);
  const [autoReplyStartTime, setAutoReplyStartTime] = useState(DEFAULT_AUTO_REPLY_START);
  const [autoReplyEndTime, setAutoReplyEndTime] = useState(DEFAULT_AUTO_REPLY_END);
  const [autoReplyTimezone, setAutoReplyTimezone] = useState(DEFAULT_AUTO_REPLY_TIMEZONE);
  const [autoReplyText, setAutoReplyText] = useState('');
  const [showBotToken, setShowBotToken] = useState(false);
  const [showAvitoClientId, setShowAvitoClientId] = useState(false);
  const [showAvitoClientSecret, setShowAvitoClientSecret] = useState(false);
  const [botChats, setBotChats] = useState<Record<number, TelegramChat[]>>({});
  const [botChatsLoading, setBotChatsLoading] = useState<Record<number, boolean>>({});

  const [loading, setLoading] = useState(false);
  const [botSubmitting, setBotSubmitting] = useState(false);
  const [avitoSubmitting, setAvitoSubmitting] = useState(false);
  const [telegramSourceSubmitting, setTelegramSourceSubmitting] = useState(false);
  const [filterSubmitting, setFilterSubmitting] = useState(false);
  const [autoReplySubmitting, setAutoReplySubmitting] = useState(false);
  const [timeTick, setTimeTick] = useState(() => Date.now());

  const [flash, setFlash] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copiedSourceId, setCopiedSourceId] = useState<number | null>(null);
  const copyTimerRef = useRef<NodeJS.Timeout | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [clientResp, botsResp, accountsResp, dialogsResp, telegramSourcesResp] = await Promise.all([
        apiFetch('/api/clients/me'),
        apiFetch('/api/bots/'),
        apiFetch('/api/avito/accounts'),
        apiFetch('/api/dialogs/'),
        apiFetch('/api/telegram-sources'),
      ]);
      const botsData = botsResp as Bot[];
      setFilterText(clientResp.filter_keywords ?? '');
      setRequireReply(Boolean(clientResp.require_reply_for_avito));
      setHideSystemMessages(clientResp.hide_system_messages ?? true);
      setAutoReplyEnabled(Boolean(clientResp.auto_reply_enabled));
      setAutoReplyAlways(Boolean(clientResp.auto_reply_always));
      setAutoReplyTimezone(clientResp.auto_reply_timezone ?? DEFAULT_AUTO_REPLY_TIMEZONE);
      setAutoReplyStartTime(
        formatTimeValue(clientResp.auto_reply_start_time, DEFAULT_AUTO_REPLY_START),
      );
      setAutoReplyEndTime(
        formatTimeValue(clientResp.auto_reply_end_time, DEFAULT_AUTO_REPLY_END),
      );
      setAutoReplyText(clientResp.auto_reply_text ?? '');
      setBots(botsData);
      setTelegramSources(telegramSourcesResp as TelegramSource[]);
      setBotChats((prev) => {
        const allowed = new Set(botsData.map((bot) => bot.id));
        const next: Record<number, TelegramChat[]> = {};
        Object.entries(prev).forEach(([key, value]) => {
          const numericKey = Number(key);
          if (allowed.has(numericKey)) {
            next[numericKey] = value;
          }
        });
        return next;
      });
      setBotChatsLoading((prev) => {
        const allowed = new Set(botsData.map((bot) => bot.id));
        const next: Record<number, boolean> = {};
        Object.entries(prev).forEach(([key, value]) => {
          const numericKey = Number(key);
          if (allowed.has(numericKey)) {
            next[numericKey] = value;
          }
        });
        return next;
      });
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
    document.title = 'Настройки | Tuberry';
    return () => {
      document.title = previousTitle;
    };
  }, []);

  const botOptions = useMemo(
    () => bots.map((bot) => ({ value: String(bot.id), label: bot.bot_username ?? `Bot #${bot.id}` })),
    [bots],
  );
  const botLookup = useMemo(() => new Map(bots.map((bot) => [bot.id, bot])), [bots]);
  const timeOptions = useMemo(() => {
    const result: string[] = [];
    for (let hour = 0; hour < 24; hour += 1) {
      for (const minute of [0, 30]) {
        const value = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
        result.push(value);
      }
    }
    return result;
  }, []);
  const timezoneOptions = useMemo(() => {
    const now = new Date(timeTick);
    const options = RUSSIAN_TIMEZONES.map(({ value, city }) => {
      let timeLabel = '';
      try {
        timeLabel = new Intl.DateTimeFormat('ru-RU', {
          hour: '2-digit',
          minute: '2-digit',
          timeZone: value,
        }).format(now);
      } catch (error) {
        console.warn('Failed to format timezone', value, error);
      }
      return {
        value,
        label: city,
        timeLabel,
      };
    });
    if (autoReplyTimezone && autoReplyTimezone !== '' && !options.some((option) => option.value === autoReplyTimezone)) {
      let fallbackLabel = autoReplyTimezone;
      try {
        const timeLabel = new Intl.DateTimeFormat('ru-RU', {
          hour: '2-digit',
          minute: '2-digit',
          timeZone: autoReplyTimezone,
        }).format(now);
        fallbackLabel = `${autoReplyTimezone} — ${timeLabel}`;
      } catch (error) {
        console.warn('Failed to format current timezone label', autoReplyTimezone, error);
      }
      options.unshift({ value: autoReplyTimezone, label: fallbackLabel, timeLabel: '' });
    }
    return options;
  }, [timeTick, autoReplyTimezone]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setTimeTick(Date.now());
    }, 60_000);
    return () => window.clearInterval(interval);
  }, []);

  const handleBotSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBotSubmitting(true);
    setError(null);
    setFlash(null);
    try {
      await apiFetch('/api/bots/', {
        method: 'POST',
        body: JSON.stringify({
          token: botForm.token,
          bot_username: null,
          group_chat_id: null,
          topic_mode: true,
        }),
      });
      setBotForm(initialBotForm);
      await load();
      setFlash('Telegram-бот подключён.');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBotSubmitting(false);
    }
  };

  const handleAvitoSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAvitoSubmitting(true);
    setError(null);
    setFlash(null);
    try {
      await apiFetch('/api/avito/accounts', {
        method: 'POST',
        body: JSON.stringify({
          name: avitoForm.name || null,
          api_client_id: avitoForm.api_client_id,
          api_client_secret: avitoForm.api_client_secret,
          bot_id: avitoForm.bot_id ? Number(avitoForm.bot_id) : null,
          monitoring_enabled: true,
        }),
      });
      setAvitoForm(initialAvitoForm);
      await load();
      setFlash('Аккаунт Avito сохранён.');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setAvitoSubmitting(false);
    }
  };

  const handleTelegramSourceSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!telegramSourceForm.token.trim()) {
      setError('Укажите токен Telegram-бота.');
      return;
    }
    if (!telegramSourceForm.bot_id) {
      setError('Выберите управляющего бота для обработки диалогов.');
      return;
    }
    setTelegramSourceSubmitting(true);
    setError(null);
    setFlash(null);
    try {
      await apiFetch('/api/telegram-sources', {
        method: 'POST',
        body: JSON.stringify({
          token: telegramSourceForm.token.trim(),
          bot_id: Number(telegramSourceForm.bot_id),
          display_name: telegramSourceForm.display_name.trim() || undefined,
          description: telegramSourceForm.description.trim() || undefined,
        }),
      });
      setTelegramSourceForm(initialTelegramSourceForm);
      await load();
      setFlash('Telegram-бот источника подключён.');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setTelegramSourceSubmitting(false);
    }
  };

  const handleDeleteTelegramSource = async (sourceId: number) => {
    setError(null);
    setFlash(null);
    try {
      await apiFetch(`/api/telegram-sources/${sourceId}`, { method: 'DELETE' });
      await load();
      setFlash('Источник удалён.');
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleCopyWebhook = useCallback(
    async (webhook: string, sourceId: number) => {
      try {
        await navigator.clipboard.writeText(webhook);
        if (copyTimerRef.current) {
          clearTimeout(copyTimerRef.current);
          copyTimerRef.current = null;
        }
        setCopiedSourceId(sourceId);
        copyTimerRef.current = setTimeout(() => {
          setCopiedSourceId((prev) => (prev === sourceId ? null : prev));
          copyTimerRef.current = null;
        }, 2500);
      } catch (err) {
        setError('Не удалось скопировать ссылку вебхука. Скопируйте вручную.');
      }
    },
    [],
  );

  useEffect(
    () => () => {
      if (copyTimerRef.current) {
        clearTimeout(copyTimerRef.current);
      }
    },
    [],
  );

  const handleFilterSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFilterSubmitting(true);
    setError(null);
    setFlash(null);
    try {
      await apiFetch('/api/clients/me', {
        method: 'PATCH',
        body: JSON.stringify({ filter_keywords: filterText }),
      });
      await load();
      setFlash('Фильтр обновлён.');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setFilterSubmitting(false);
    }
  };

  const handleAutoReplySubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAutoReplySubmitting(true);
    setError(null);
    setFlash(null);

    const trimmed = autoReplyText.trim();
    if (autoReplyEnabled && !trimmed) {
      setAutoReplySubmitting(false);
      setError('Введите текст автоответа.');
      return;
    }

    if (autoReplyEnabled && !autoReplyTimezone) {
      setAutoReplySubmitting(false);
      setError('Укажите часовой пояс для автоответа.');
      return;
    }

    if (autoReplyEnabled && !autoReplyAlways && (!autoReplyStartTime || !autoReplyEndTime)) {
      setAutoReplySubmitting(false);
      setError('Укажите время начала и окончания автоответа.');
      return;
    }

    const payload: Record<string, unknown> = {
      auto_reply_enabled: autoReplyEnabled,
      auto_reply_always: autoReplyAlways,
      auto_reply_timezone: autoReplyTimezone || null,
      auto_reply_text: trimmed || null,
    };

    if (autoReplyStartTime) {
      payload.auto_reply_start_time = autoReplyStartTime;
    }
    if (autoReplyEndTime) {
      payload.auto_reply_end_time = autoReplyEndTime;
    }

    try {
      await apiFetch('/api/clients/me', {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      await load();
      setFlash('Настройки автоответа сохранены.');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setAutoReplySubmitting(false);
    }
  };

  const handleToggleMonitoring = useCallback(
    async (account: AvitoAccount) => {
      setError(null);
      setFlash(null);
      try {
        await apiFetch(`/api/avito/accounts/${account.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ monitoring_enabled: !account.monitoring_enabled }),
        });
        await load();
        setFlash(!account.monitoring_enabled ? 'Мониторинг включён.' : 'Мониторинг отключён.');
      } catch (err) {
        setError((err as Error).message);
      }
    },
    [load],
  );

  const refreshBotChats = useCallback(
    async (botId: number) => {
      setError(null);
      setBotChatsLoading((prev) => ({ ...prev, [botId]: true }));
      try {
        const chats: TelegramChat[] = await apiFetch(`/api/bots/${botId}/chats`);
        setBotChats((prev) => ({ ...prev, [botId]: chats }));
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setBotChatsLoading((prev) => ({ ...prev, [botId]: false }));
      }
    },
    [],
  );

  const handleAssignChat = useCallback(
    async (bot: Bot, value: string) => {
      const target = value || null;
      setError(null);
      setFlash(null);
      try {
        await apiFetch(`/api/bots/${bot.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ group_chat_id: target }),
        });
        await load();
        await refreshBotChats(bot.id);
        setFlash(target ? 'Группа для бота обновлена.' : 'Привязка к группе снята.');
      } catch (err) {
        setError((err as Error).message);
      }
    },
    [load, refreshBotChats],
  );

  useEffect(() => {
    bots.forEach((bot) => {
      if (!botChats[bot.id]) {
        void refreshBotChats(bot.id);
      }
    });
  }, [bots, botChats, refreshBotChats]);

  useEffect(() => {
    bots.forEach((bot) => {
      const chats = botChats[bot.id] ?? [];
      if (chats.length === 1 && !bot.group_chat_id) {
        void handleAssignChat(bot, chats[0].chat_id);
      }
    });
  }, [bots, botChats, handleAssignChat]);

  const handleRequireReplyToggle = useCallback(async () => {
    const previous = requireReply;
    const next = !previous;
    setRequireReply(next);
    setError(null);
    setFlash(null);
    try {
      await apiFetch('/api/clients/me', {
        method: 'PATCH',
        body: JSON.stringify({ require_reply_for_avito: next }),
      });
      setFlash(
        next
          ? 'Требование цитирования включено.'
          : 'Отправка сообщений снова доступна без цитирования.',
      );
    } catch (err) {
      setRequireReply(previous);
      setError((err as Error).message);
    }
  }, [requireReply]);

  const handleHideSystemMessagesToggle = useCallback(async () => {
    const previous = hideSystemMessages;
    const next = !previous;
    setHideSystemMessages(next);
    setError(null);
    setFlash(null);
    try {
      await apiFetch('/api/clients/me', {
        method: 'PATCH',
        body: JSON.stringify({ hide_system_messages: next }),
      });
      setFlash(
        next
          ? 'Системные сообщения Авито скрываются.'
          : 'Системные сообщения Авито снова отображаются в темах.',
      );
    } catch (err) {
      setHideSystemMessages(previous);
      setError((err as Error).message);
    }
  }, [hideSystemMessages]);

  const handleDeleteBot = useCallback(
    async (botId: number) => {
      setError(null);
      setFlash(null);
      try {
        await apiFetch(`/api/bots/${botId}`, { method: 'DELETE' });
        await load();
        setFlash('Telegram-бот удалён.');
      } catch (err) {
        setError((err as Error).message);
      }
    },
    [load],
  );

  const handleDeleteAvito = useCallback(
    async (accountId: number) => {
      setError(null);
      setFlash(null);
      try {
        await apiFetch(`/api/avito/accounts/${accountId}`, { method: 'DELETE' });
        await load();
        setFlash('Аккаунт Avito удалён.');
      } catch (err) {
        setError((err as Error).message);
      }
    },
    [load],
  );

  return (
    <div className="space-y-6 pb-12">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">Настройки</h1>
        <p className="text-muted-foreground">
          Управляйте фильтрами, подключёнными ботами и аккаунтами Avito. Все изменения вступают в силу мгновенно.
        </p>
        <Button
          variant="outline"
          size="sm"
          className="w-fit"
          onClick={() => load()}
          disabled={loading}
        >
          {loading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <RefreshCcw className="mr-2 size-4" />}
          Обновить данные
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" className="glass-panel border border-red-200/60">
          <AlertTitle>Не удалось выполнить действие</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {flash && (
        <Alert className="glass-panel border border-emerald-200/60 text-emerald-900">
          <AlertTitle>Готово</AlertTitle>
          <AlertDescription>{flash}</AlertDescription>
        </Alert>
      )}

      <Accordion multiple variant="outline" defaultValue={["filter", "bot"]} className="space-y-3">
        <AccordionItem value="filter" className="glass-panel rounded-2xl border border-[var(--app-border)]">
          <AccordionHeader>
            <AccordionTrigger>
              <span className="text-base font-semibold">Фильтр сообщений Avito</span>
            </AccordionTrigger>
          </AccordionHeader>
          <AccordionPanel>
            <form onSubmit={handleFilterSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="filter-keywords">Стоп-слова</Label>
                <Textarea
                  id="filter-keywords"
                  value={filterText}
                  onChange={(event) => setFilterText(event.target.value)}
                  placeholder={"пример:\nскупка\nопт\nреклама"}
                  rows={6}
                />
                <p className="text-xs text-muted-foreground">Поиск выполняется без учёта регистра.</p>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-2xl border border-[var(--app-border)] bg-secondary/30 p-4">
                  <div className="mb-3 space-y-1">
                    <p className="text-sm font-medium text-foreground">Обязательное цитирование клиента Avito</p>
                    <p className="text-xs text-muted-foreground">
                      Если включено, менеджеры смогут отправлять ответы только через цитирование исходного сообщения.
                    </p>
                  </div>
                  <div className="flex justify-end">
                    <Switch checked={requireReply} onCheckedChange={() => void handleRequireReplyToggle()} />
                  </div>
                </div>
                <div className="rounded-2xl border border-[var(--app-border)] bg-secondary/30 p-4">
                  <div className="mb-3 space-y-1">
                    <p className="text-sm font-medium text-foreground">Скрывать системные сообщения от Авито</p>
                    <p className="text-xs text-muted-foreground">
                      Сообщения, содержащие метку «[Системное сообщение]», не будут попадать в Telegram-темы.
                    </p>
                  </div>
                  <div className="flex justify-end">
                    <Switch
                      checked={hideSystemMessages}
                      onCheckedChange={() => void handleHideSystemMessagesToggle()}
                    />
                  </div>
                </div>
              </div>
              <div className="flex justify-end">
                <Button type="submit" disabled={filterSubmitting}>
                  {filterSubmitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
                  Сохранить фильтр
                </Button>
              </div>
            </form>
          </AccordionPanel>
        </AccordionItem>

        <AccordionItem value="auto-reply" className="glass-panel rounded-2xl border border-[var(--app-border)]">
          <AccordionHeader>
            <AccordionTrigger>
              <span className="text-base font-semibold">Автоответ</span>
            </AccordionTrigger>
          </AccordionHeader>
          <AccordionPanel>
            <form onSubmit={handleAutoReplySubmit} className="space-y-5">
              <div className="flex items-center justify-between gap-4 rounded-2xl border border-[var(--app-border)] bg-secondary/30 p-4">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-foreground">Включить автоответ</p>
                  <p className="text-xs text-muted-foreground">
                    Автоматически отправлять приветственное сообщение в рабочее время при входящем обращении из Avito.
                  </p>
                </div>
                <Switch checked={autoReplyEnabled} onCheckedChange={(value) => setAutoReplyEnabled(Boolean(value))} />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="auto-reply-timezone">Часовой пояс</Label>
                  <Select
                    value={autoReplyTimezone}
                    onValueChange={(value) =>
                      setAutoReplyTimezone(typeof value === 'string' ? value : '')
                    }
                  >
                    <SelectTrigger id="auto-reply-timezone" className="w-full justify-between">
                      <SelectValue placeholder="Выберите часовой пояс" />
                    </SelectTrigger>
                    <SelectContent className="max-h-64 w-72">
                      <SelectItem value="">Не выбрано</SelectItem>
                      {timezoneOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Расписание рассчитывается относительно выбранного часового пояса.
                  </p>
                </div>
                <div className="rounded-2xl border border-[var(--app-border)] bg-secondary/30 p-4">
                  <div className="mb-3 flex items-center justify-between gap-2">
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-foreground">Круглосуточно</p>
                      <p className="text-xs text-muted-foreground">Включите, чтобы отправлять автоответ без расписания.</p>
                    </div>
                    <Switch checked={autoReplyAlways} onCheckedChange={(value) => setAutoReplyAlways(Boolean(value))} />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1">
                      <Label htmlFor="auto-reply-start">Начало</Label>
                      <Select
                        value={autoReplyStartTime}
                        onValueChange={(value) =>
                          setAutoReplyStartTime(typeof value === 'string' ? value : '')
                        }
                        disabled={autoReplyAlways}
                      >
                        <SelectTrigger id="auto-reply-start" className="w-full justify-between">
                          <SelectValue placeholder="--:--" />
                        </SelectTrigger>
                        <SelectContent className="max-h-64 w-36">
                          {timeOptions.map((option) => (
                            <SelectItem key={option} value={option}>
                              {option}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="auto-reply-end">Окончание</Label>
                      <Select
                        value={autoReplyEndTime}
                        onValueChange={(value) =>
                          setAutoReplyEndTime(typeof value === 'string' ? value : '')
                        }
                        disabled={autoReplyAlways}
                      >
                        <SelectTrigger id="auto-reply-end" className="w-full justify-between">
                          <SelectValue placeholder="--:--" />
                        </SelectTrigger>
                        <SelectContent className="max-h-64 w-36">
                          {timeOptions.map((option) => (
                            <SelectItem key={option} value={option}>
                              {option}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="auto-reply-text">Текст автоответа</Label>
                <Textarea
                  id="auto-reply-text"
                  value={autoReplyText}
                  onChange={(event) => setAutoReplyText(event.target.value)}
                  placeholder="Здравствуйте! Мы вернёмся к вам в рабочее время..."
                  rows={4}
                />
                <p className="text-xs text-muted-foreground">
                  В Авито отправляется только текст сообщения. В Telegram тема получит отметку «Автоответчик».
                </p>
              </div>

              <div className="flex justify-end">
                <Button type="submit" disabled={autoReplySubmitting}>
                  {autoReplySubmitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
                  Сохранить автоответ
                </Button>
              </div>
            </form>
          </AccordionPanel>
        </AccordionItem>

        <AccordionItem value="bot" className="glass-panel rounded-2xl border border-[var(--app-border)]">
          <AccordionHeader>
            <AccordionTrigger>
              <span className="text-base font-semibold">Подключение Telegram-бота</span>
            </AccordionTrigger>
          </AccordionHeader>
          <AccordionPanel>
            <form onSubmit={handleBotSubmit} className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="bot-token">Bot API token</Label>
                <div className="relative">
                  <Input
                    id="bot-token"
                    placeholder="1234567890:ABCDEF..."
                    type={showBotToken ? 'text' : 'password'}
                    value={botForm.token}
                    autoComplete="off"
                    onChange={(event) => setBotForm((prev) => ({ ...prev, token: event.target.value }))}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowBotToken((prev) => !prev)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground transition hover:text-foreground"
                    aria-label={showBotToken ? 'Скрыть токен бота' : 'Показать токен бота'}
                  >
                    {showBotToken ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </div>
              <div className="rounded-xl border border-dashed border-muted-foreground/40 bg-secondary/30 px-4 py-3 text-sm text-muted-foreground">
                Сохраните токен, добавьте бота в нужные группы Telegram и затем выберите группу в таблице
                «Подключённые боты» ниже.
              </div>
              <div className="flex justify-end">
                <Button type="submit" disabled={botSubmitting}>
                  {botSubmitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
                  Сохранить бота
                </Button>
              </div>
            </form>
          </AccordionPanel>
        </AccordionItem>

        <AccordionItem value="avito" className="glass-panel rounded-2xl border border-[var(--app-border)]">
          <AccordionHeader>
            <AccordionTrigger>
              <span className="text-base font-semibold">Аккаунты Avito</span>
            </AccordionTrigger>
          </AccordionHeader>
          <AccordionPanel>
            <form onSubmit={handleAvitoSubmit} className="grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="avito-name">Название (необязательно)</Label>
                <Input
                  id="avito-name"
                  placeholder="Например, Основной аккаунт"
                  value={avitoForm.name}
                  onChange={(event) => setAvitoForm((prev) => ({ ...prev, name: event.target.value }))}
                />
              </div>
              <div className="grid gap-2 md:grid-cols-2 md:gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="avito-client-id">client_id</Label>
                  <div className="relative">
                    <Input
                      id="avito-client-id"
                      placeholder="client_id"
                      type={showAvitoClientId ? 'text' : 'password'}
                      autoComplete="off"
                      value={avitoForm.api_client_id}
                      onChange={(event) => setAvitoForm((prev) => ({ ...prev, api_client_id: event.target.value }))}
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowAvitoClientId((prev) => !prev)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground transition hover:text-foreground"
                      aria-label={showAvitoClientId ? 'Скрыть client_id' : 'Показать client_id'}
                    >
                      {showAvitoClientId ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="avito-client-secret">client_secret</Label>
                  <div className="relative">
                    <Input
                      id="avito-client-secret"
                      type={showAvitoClientSecret ? 'text' : 'password'}
                      placeholder="client_secret"
                      autoComplete="off"
                      value={avitoForm.api_client_secret}
                      onChange={(event) => setAvitoForm((prev) => ({ ...prev, api_client_secret: event.target.value }))}
                      required
                    />
                    <button
                      type="button"
                      onClick={() => setShowAvitoClientSecret((prev) => !prev)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground transition hover:text-foreground"
                      aria-label={showAvitoClientSecret ? 'Скрыть client_secret' : 'Показать client_secret'}
                    >
                      {showAvitoClientSecret ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                </div>
              </div>
              <div className="grid gap-2">
                <Label>Привязать к боту</Label>
                <Select
                  value={avitoForm.bot_id}
                  onValueChange={(value: string) => setAvitoForm((prev) => ({ ...prev, bot_id: value ?? '' }))}
                >
                  <SelectTrigger className="w-full justify-between">
                    <SelectValue placeholder="Выберите бота" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">Не привязывать</SelectItem>
                    {botOptions.map((bot) => (
                      <SelectItem key={bot.value} value={bot.value}>
                        {bot.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex justify-end">
                <Button type="submit" disabled={avitoSubmitting}>
                  {avitoSubmitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
                  Сохранить аккаунт
                </Button>
              </div>
            </form>
          </AccordionPanel>
        </AccordionItem>

        <AccordionItem value="telegram-sources" className="glass-panel rounded-2xl border border-[var(--app-border)]">
          <AccordionHeader>
            <AccordionTrigger>
              <span className="text-base font-semibold">Источники — Telegram-боты</span>
            </AccordionTrigger>
          </AccordionHeader>
          <AccordionPanel>
            <div className="grid gap-6 lg:grid-cols-[minmax(0,360px)_1fr]">
              <form onSubmit={handleTelegramSourceSubmit} className="grid gap-4 rounded-2xl border border-dashed border-blue-200/60 bg-blue-50/40 p-4">
                <div className="grid gap-2">
                  <Label htmlFor="telegram-source-token">Bot API token источника</Label>
                  <Input
                    id="telegram-source-token"
                    placeholder="0000000000:ABCDEF..."
                    value={telegramSourceForm.token}
                    onChange={(event) => setTelegramSourceForm((prev) => ({ ...prev, token: event.target.value }))}
                    required
                    autoComplete="off"
                  />
                </div>
                <div className="grid gap-2">
                  <Label>Управляющий бот</Label>
                  <Select
                    value={telegramSourceForm.bot_id}
                    onValueChange={(value: string) => setTelegramSourceForm((prev) => ({ ...prev, bot_id: value ?? '' }))}
                  >
                    <SelectTrigger className="w-full justify-between">
                      <SelectValue placeholder={bots.length === 0 ? 'Нет подключённых ботов' : 'Выберите бота'} />
                    </SelectTrigger>
                    <SelectContent>
                      {bots.length === 0 ? (
                        <div className="px-3 py-2 text-sm text-muted-foreground">Сначала добавьте управляющего бота.</div>
                      ) : (
                        bots.map((bot) => (
                          <SelectItem key={bot.id} value={String(bot.id)}>
                            {bot.bot_username ?? `Bot #${bot.id}`}
                          </SelectItem>
                        ))
                      )}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="telegram-source-name">Название для команды (опционально)</Label>
                  <Input
                    id="telegram-source-name"
                    placeholder="Телеграм витрина"
                    value={telegramSourceForm.display_name}
                    onChange={(event) => setTelegramSourceForm((prev) => ({ ...prev, display_name: event.target.value }))}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="telegram-source-description">Описание (опционально)</Label>
                  <Textarea
                    id="telegram-source-description"
                    placeholder="Добавьте подсказку для коллег, зачем нужен этот бот."
                    rows={3}
                    value={telegramSourceForm.description}
                    onChange={(event) => setTelegramSourceForm((prev) => ({ ...prev, description: event.target.value }))}
                  />
                </div>
                <div className="flex justify-end">
                  <Button type="submit" disabled={telegramSourceSubmitting || bots.length === 0}>
                    {telegramSourceSubmitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
                    Подключить источник
                  </Button>
                </div>
              </form>

              <div className="space-y-4">
                <div>
                  <h3 className="text-sm font-semibold text-foreground">Подключённые источники</h3>
                  <p className="text-xs text-muted-foreground">
                    Каждый источник принимает входящие сообщения пользователей и создаёт темы в рабочем чате.
                  </p>
                </div>
                {telegramSources.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-white/70 p-4 text-sm text-muted-foreground">
                    Источники Telegram пока не добавлены. Подключите бота источника, чтобы принимать обращения из Telegram.
                  </div>
                ) : (
                  <div className="overflow-hidden rounded-2xl border border-slate-200/70 bg-white/80 shadow-sm">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Источник</TableHead>
                          <TableHead>Управляющий бот</TableHead>
                          <TableHead>Webhook</TableHead>
                          <TableHead>Статус</TableHead>
                          <TableHead className="w-16 text-right" />
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {telegramSources.map((source) => {
                          const linkedBot = botLookup.get(source.bot_id);
                          return (
                            <TableRow key={source.id}>
                              <TableCell>
                                <div className="flex flex-col">
                                  <span className="font-medium text-foreground">
                                    {source.display_name || source.bot_username || `Источник #${source.id}`}
                                  </span>
                                  <span className="text-xs text-muted-foreground">
                                    {source.bot_username ? `@${source.bot_username}` : 'username не задан'}
                                  </span>
                                </div>
                              </TableCell>
                              <TableCell>
                                {linkedBot ? linkedBot.bot_username ?? `Bot #${linkedBot.id}` : '—'}
                              </TableCell>
                              <TableCell>
                                {source.webhook_url ? (
                                  <div className="flex flex-col gap-1">
                                    <div className="flex flex-wrap items-center gap-2">
                                      <Badge variant="success" appearance="light" size="xs">
                                        Webhook активен
                                      </Badge>
                                      <Button
                                        type="button"
                                        variant="ghost"
                                        size="sm"
                                        className="text-xs"
                                        onClick={() => void handleCopyWebhook(source.webhook_url!, source.id)}
                                      >
                                        {copiedSourceId === source.id ? 'Скопировано' : 'Скопировать ссылку'}
                                      </Button>
                                    </div>
                                    <p className="text-[11px] text-muted-foreground">
                                      Настройка выполнена автоматически, Telegram уже отправляет обновления.
                                    </p>
                                  </div>
                                ) : (
                                  <span className="text-xs text-muted-foreground">—</span>
                                )}
                              </TableCell>
                              <TableCell>
                                <Badge variant={source.status === 'active' ? 'success' : source.status === 'error' ? 'destructive' : 'secondary'} appearance="light" size="xs">
                                  {source.status}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-right">
                                <ConfirmAction
                                  title="Удалить источник?"
                                  description="Диалоги и сообщения, связанные с источником, будут очищены. Продолжить?"
                                  confirmLabel="Удалить"
                                  onConfirm={() => handleDeleteTelegramSource(source.id)}
                                >
                                  <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-destructive">
                                    <Trash2 className="size-4" />
                                  </Button>
                                </ConfirmAction>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </div>
            </div>
          </AccordionPanel>
        </AccordionItem>
      </Accordion>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="glass-panel rounded-2xl border border-[var(--app-border)] p-6 shadow-xl">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Подключённые боты</h2>
              <p className="text-sm text-muted-foreground">Всего: {bots.length}</p>
            </div>
            <Badge variant="info" appearance="light" size="sm">
              {loading ? 'Обновляем…' : 'Актуально'}
            </Badge>
          </div>
          <div className="overflow-hidden rounded-xl border border-border/60">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-20">ID</TableHead>
                  <TableHead>Username</TableHead>
                  <TableHead>Группа</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead className="w-16 text-right" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                      Обновляем данные…
                    </TableCell>
                  </TableRow>
                ) : bots.length > 0 ? (
                  bots.map((bot) => {
                    const chatsForBot = botChats[bot.id] ?? [];
                    const selectedChat = chatsForBot.find((chat) => chat.chat_id === bot.group_chat_id);
                    const selectedTitle =
                      selectedChat?.title ?? selectedChat?.username ?? selectedChat?.chat_id ?? undefined;

                    return (
                      <TableRow key={bot.id}>
                        <TableCell className="font-medium">{bot.id}</TableCell>
                        <TableCell>{bot.bot_username ?? '—'}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Select
                              value={bot.group_chat_id ?? ''}
                              onValueChange={(value) =>
                                void handleAssignChat(
                                  bot,
                                  typeof value === 'string' ? value : '',
                                )
                              }
                              disabled={Boolean(botChatsLoading[bot.id])}
                            >
                              <SelectTrigger className="w-[220px] justify-between">
                                <SelectValue placeholder="Выберите группу">
                                  {selectedTitle}
                                </SelectValue>
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="">Не выбрано</SelectItem>
                                {chatsForBot.map((chat) => (
                                  <SelectItem key={chat.chat_id} value={chat.chat_id}>
                                    {chat.title ?? chat.chat_id}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => void refreshBotChats(bot.id)}
                              disabled={Boolean(botChatsLoading[bot.id])}
                              aria-label="Обновить список групп"
                            >
                              {botChatsLoading[bot.id] ? (
                                <Loader2 className="size-4 animate-spin" />
                              ) : (
                                <RefreshCcw className="size-4" />
                              )}
                            </Button>
                          </div>
                          <p className="mt-1 text-xs text-muted-foreground">
                            {selectedChat
                              ? `Выбрана группа: ${selectedTitle ?? selectedChat.chat_id} (ID: ${selectedChat.chat_id})`
                              : chatsForBot.length > 0
                                ? 'Выберите группу для привязки.'
                                : 'Добавьте бота в группу и обновите список.'}
                          </p>
                        </TableCell>
                        <TableCell>
                        <Badge size="sm" appearance="light">
                          {bot.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <ConfirmAction
                          title="Удалить Telegram-бота?"
                          description="Диалоги и привязки будут очищены."
                          confirmLabel="Удалить"
                          onConfirm={() => handleDeleteBot(bot.id)}
                        >
                          <Button variant="ghost" size="icon">
                            <Trash2 className="size-4" />
                          </Button>
                        </ConfirmAction>
                      </TableCell>
                    </TableRow>
                    );
                  })
                ) : (
                  <TableRow>
                    <TableCell colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                      Боты не подключены
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </div>

        <div className="glass-panel rounded-2xl border border-[var(--app-border)] p-6 shadow-xl">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Аккаунты Avito</h2>
              <p className="text-sm text-muted-foreground">Всего: {accounts.length}</p>
            </div>
            <Badge variant="info" appearance="light" size="sm">
              {dialogs.length ? `${dialogs.length} диалогов` : 'Диалоги не найдены'}
            </Badge>
          </div>
          <div className="overflow-hidden rounded-xl border border-border/60">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">ID</TableHead>
                  <TableHead>Название</TableHead>
                  <TableHead>client_id</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead>Мониторинг</TableHead>
                  <TableHead>Bot</TableHead>
                  <TableHead className="w-16 text-right" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={7} className="py-8 text-center text-sm text-muted-foreground">
                      Обновляем данные…
                    </TableCell>
                  </TableRow>
                ) : accounts.length > 0 ? (
                  accounts.map((account) => (
                    <TableRow key={account.id}>
                      <TableCell className="font-medium">{account.id}</TableCell>
                      <TableCell>{account.name ?? '—'}</TableCell>
                      <TableCell className="font-mono text-sm text-muted-foreground">
                        {account.api_client_id ?? '—'}
                      </TableCell>
                      <TableCell>
                        <Badge size="sm" appearance="light">
                          {account.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Switch
                          size="sm"
                          checked={account.monitoring_enabled}
                          onCheckedChange={() => void handleToggleMonitoring(account)}
                        />
                      </TableCell>
                      <TableCell>{account.bot_id ?? '—'}</TableCell>
                      <TableCell className="text-right">
                        <ConfirmAction
                          title="Удалить аккаунт Avito?"
                          description="После удаления поллер остановится, диалоги будут очищены."
                          confirmLabel="Удалить"
                          onConfirm={() => handleDeleteAvito(account.id)}
                        >
                          <Button variant="ghost" size="icon">
                            <Trash2 className="size-4" />
                          </Button>
                        </ConfirmAction>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={7} className="py-8 text-center text-sm text-muted-foreground">
                      Аккаунты не подключены
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      </div>
    </div>
  );
}
