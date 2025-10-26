'use client';

import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/base-badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/base-input';
import { Label } from '@/components/ui/base-label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/base-select';
import { Switch } from '@/components/ui/base-switch';
import { Textarea } from '@/components/ui/textarea';
import { apiFetch } from '@/lib/api';
import type { AvitoAccount, Bot, Project, TelegramSource, TelegramChat, PersonalTelegramAccount } from './types';
import { Loader2, PlusCircle, RefreshCcw, Sparkles, Plug } from 'lucide-react';

type CreateProjectFormState = {
  name: string;
  description: string;
  botId: string;
  botToken: string;
  botGroupChatId: string;
  useBotAsSource: boolean;
};

const initialFormState: CreateProjectFormState = {
  name: '',
  description: '',
  botId: '',
  botToken: '',
  botGroupChatId: '',
  useBotAsSource: false,
};

function formatCountLabel(count: number, singular: string, plural: string) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function ProjectStatusBadge({ project }: { project: Project }) {
  if (!project.auto_reply_enabled) {
    return null;
  }
  return (
    <Badge variant="success" appearance="light" size="sm">
      Автоответ активен
    </Badge>
  );
}

export default function ClientProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [bots, setBots] = useState<Bot[]>([]);
  const [accounts, setAccounts] = useState<AvitoAccount[]>([]);
  const [sources, setSources] = useState<TelegramSource[]>([]);
  const [personalAccounts, setPersonalAccounts] = useState<PersonalTelegramAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formState, setFormState] = useState<CreateProjectFormState>(initialFormState);
  const [formError, setFormError] = useState<string | null>(null);
  const [formNotice, setFormNotice] = useState<string | null>(null);
  const [formSubmitting, setFormSubmitting] = useState(false);
  const [botChats, setBotChats] = useState<TelegramChat[]>([]);
  const [botChatsLoading, setBotChatsLoading] = useState(false);
  const [botConnectLoading, setBotConnectLoading] = useState(false);
  const [autoReplyUpdatingId, setAutoReplyUpdatingId] = useState<number | null>(null);

  const fetchBots = useCallback(async (): Promise<Bot[]> => {
    const botsResp = await apiFetch('/api/bots/');
    setBots(botsResp);
    return botsResp as Bot[];
  }, []);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [projectsResp, accountsResp, sourcesResp, personalAccountsResp] = await Promise.all([
        apiFetch('/api/projects'),
        apiFetch('/api/avito/accounts'),
        apiFetch('/api/telegram-sources'),
        apiFetch('/api/personal-telegram-accounts'),
      ]);
      const botsResp = await fetchBots();
      setProjects(projectsResp as Project[]);
      setAccounts(accountsResp as AvitoAccount[]);
      setSources(sourcesResp as TelegramSource[]);
      setPersonalAccounts(personalAccountsResp as PersonalTelegramAccount[]);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchBotChats = useCallback(
    async (botId: number, preferredChatId?: string | null) => {
      setBotChatsLoading(true);
      try {
        const chats = (await apiFetch(`/api/bots/${botId}/chats`)) as TelegramChat[];
        setBotChats(chats);
        setFormState((prev) => {
          const baseCandidate = preferredChatId ?? prev.botGroupChatId;
          const trimmedCandidate = baseCandidate.trim();
          const candidatePresent = trimmedCandidate !== '' && chats.some((chat) => chat.chat_id === trimmedCandidate);
          let nextValue = trimmedCandidate;
          if (!candidatePresent) {
            const botRecord = bots.find((bot) => bot.id === botId);
            const existingGroup = botRecord?.group_chat_id ?? '';
            if (existingGroup && chats.some((chat) => chat.chat_id === existingGroup)) {
              nextValue = existingGroup;
            } else if (chats.length === 1) {
              nextValue = chats[0].chat_id;
            } else {
              nextValue = '';
            }
          }
          return { ...prev, botGroupChatId: nextValue };
        });
        setFormNotice(
          chats.length === 0
            ? 'Группы не найдены. Добавьте бота в форум-группу Telegram и нажмите «Обновить список».'
            : null,
        );
      } catch (err) {
        setFormError((err as Error).message);
        setBotChats([]);
      } finally {
        setBotChatsLoading(false);
      }
    },
    [bots, setFormError, setFormNotice],
  );

  const handleConnectBotFromToken = useCallback(async () => {
    const trimmedToken = formState.botToken.trim();
    if (!trimmedToken) {
      setFormError('Введите токен Telegram-бота.');
      return;
    }

    setBotConnectLoading(true);
    setFormError(null);
    setFormNotice(null);

    try {
      const connectedBot = (await apiFetch('/api/bots/', {
        method: 'POST',
        body: JSON.stringify({
          token: trimmedToken,
          bot_username: null,
          group_chat_id: null,
          topic_mode: true,
        }),
      })) as Bot;

      if (!connectedBot || typeof connectedBot.id !== 'number') {
        throw new Error('Не удалось подключить бота. Повторите попытку.');
      }

      const botId = connectedBot.id;

      await fetchBots();

      setFormState((prev) => ({
        ...prev,
        botId: String(botId),
        botToken: '',
        botGroupChatId: connectedBot.group_chat_id ?? '',
      }));
      setFormNotice('Бот подключён. Добавьте его в форум-группу Telegram и выберите её из списка ниже.');

      await fetchBotChats(botId, connectedBot.group_chat_id);
    } catch (err) {
      setFormError((err as Error).message);
    } finally {
      setBotConnectLoading(false);
    }
  }, [fetchBotChats, fetchBots, formState.botToken, setFormError, setFormNotice]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const selectedBotId = formState.botId ? Number(formState.botId) : null;
    if (!selectedBotId) {
      setBotChats([]);
      setFormState((prev) => (prev.botGroupChatId === '' ? prev : { ...prev, botGroupChatId: '' }));
      return;
    }
    void fetchBotChats(selectedBotId);
  }, [fetchBotChats, formState.botId]);

  useEffect(() => {
    if (formState.botToken.trim() && formState.botId) {
      setFormState((prev) => ({ ...prev, botId: '' }));
    }
  }, [formState.botToken, formState.botId]);

  useEffect(() => {
    const previousTitle = document.title;
    document.title = 'Проекты | Tuberry';
    return () => {
      document.title = previousTitle;
    };
  }, []);

  const assignedBotIds = useMemo(() => {
    const ids = new Set<number>();
    projects.forEach((project) => {
      if (project.bot_id) {
        ids.add(project.bot_id);
      }
    });
    return ids;
  }, [projects]);

  const availableBots = useMemo(
    () => bots.filter((bot) => !assignedBotIds.has(bot.id)),
    [bots, assignedBotIds],
  );

  const currentBotId = useMemo(() => (formState.botId ? Number(formState.botId) : null), [formState.botId]);
  const currentBot = useMemo(() => (currentBotId ? bots.find((bot) => bot.id === currentBotId) : undefined), [currentBotId, bots]);

  const handleCreateProject = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!formState.name.trim()) {
        setFormError('Введите название проекта.');
        return;
      }
      const isUsingExistingBot = Boolean(formState.botId);
      const enteredToken = formState.botToken.trim();
      const groupChatId = formState.botGroupChatId.trim();

      if (!isUsingExistingBot && !enteredToken) {
        setFormError('Введите токен Telegram-бота или выберите существующего.');
        return;
      }
      if (!groupChatId) {
        setFormError('Выберите или укажите группу, где бот будет создавать топики.');
        return;
      }

      setFormSubmitting(true);
      setFormError(null);
      try {
        const payload: Record<string, unknown> = {
          name: formState.name.trim(),
          description: formState.description.trim() || undefined,
          use_bot_as_source: formState.useBotAsSource,
          bot_group_chat_id: groupChatId,
        };

        if (enteredToken) {
          payload.bot_token = enteredToken;
        } else if (isUsingExistingBot) {
          payload.bot_id = Number(formState.botId);
        }

        await apiFetch('/api/projects', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        setFormState(initialFormState);
        setBotChats([]);
        setFormNotice(null);
        setFormError(null);
        setShowCreateForm(false);
        await load();
      } catch (err) {
        setFormError((err as Error).message);
      } finally {
        setFormSubmitting(false);
      }
    },
    [formState, load],
  );

  const handleToggleAutoReply = useCallback(
    async (project: Project, nextValue: boolean) => {
      setError(null);

      if (nextValue) {
        if (!project.auto_reply_text || !project.auto_reply_timezone) {
          setError('Перед включением задайте текст и часовой пояс автоответчика в настройках проекта.');
          return;
        }
        if (
          !project.auto_reply_always &&
          (!project.auto_reply_start_time || !project.auto_reply_end_time || project.auto_reply_start_time === project.auto_reply_end_time)
        ) {
          setError('Перед включением задайте расписание автоответчика в настройках проекта.');
          return;
        }
      }

      setAutoReplyUpdatingId(project.id);
      try {
        const payload: Record<string, unknown> = {
          auto_reply_enabled: nextValue,
        };
        if (nextValue) {
          payload.auto_reply_text = project.auto_reply_text;
          payload.auto_reply_timezone = project.auto_reply_timezone;
          payload.auto_reply_always = project.auto_reply_always;
          payload.auto_reply_start_time = project.auto_reply_start_time;
          payload.auto_reply_end_time = project.auto_reply_end_time;
          payload.auto_reply_mode = project.auto_reply_mode;
        }
        await apiFetch(`/api/projects/${project.id}`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
        await load();
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setAutoReplyUpdatingId(null);
      }
    },
    [load],
  );

  return (
    <div className="space-y-10 pb-14">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">Проекты</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Проект объединяет Telegram-бота, рабочую группу и подключенные каналы. Создавайте отдельные проекты для
            каждой команды или направления, чтобы управлять источниками и настройками независимо.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => load()} disabled={loading}>
            {loading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <RefreshCcw className="mr-2 size-4" />}
            Обновить
          </Button>
          <Button
            onClick={() =>
                  setShowCreateForm((value) => {
                    if (value) {
                      setFormState(initialFormState);
                      setFormError(null);
                      setFormNotice(null);
                  setBotChats([]);
                }
                return !value;
              })
            }
          >
            <PlusCircle className="mr-2 size-4" />
            {showCreateForm ? 'Скрыть форму' : 'Создать проект'}
          </Button>
        </div>
      </header>

      {error && (
        <Alert variant="destructive" appearance="light">
          <AlertTitle>Не удалось загрузить проекты</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {showCreateForm && (
        <section className="glass-panel rounded-3xl border border-dashed border-[var(--app-border)] p-6 shadow-sm">
          <form className="space-y-6" onSubmit={handleCreateProject}>
            <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="project-name">Название проекта</Label>
            <Input
              id="project-name"
              value={formState.name}
              onChange={(event) => setFormState((prev) => ({ ...prev, name: event.target.value }))}
              placeholder="Например, «Отдел продаж»"
              required
            />
          </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="project-description">Описание</Label>
                <Textarea
                  id="project-description"
                  value={formState.description}
                  onChange={(event) => setFormState((prev) => ({ ...prev, description: event.target.value }))}
                  placeholder="Кратко опишите назначение проекта — это поможет команде ориентироваться."
                  rows={3}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="bot-token">Токен Telegram-бота</Label>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <Input
                    id="bot-token"
                    value={formState.botToken}
                    onChange={(event) => setFormState((prev) => ({ ...prev, botToken: event.target.value }))}
                    placeholder="123456:ABC-DEF..."
                    className="sm:flex-1"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      void handleConnectBotFromToken();
                    }}
                    disabled={botConnectLoading || !formState.botToken.trim()}
                  >
                    {botConnectLoading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Plug className="mr-2 size-4" />}
                    Подключить бота
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Укажите токен, чтобы автоматически привязать бота и настроить вебхук. После подключения добавьте бота в нужную
                  форум-группу Telegram.
                </p>
              </div>
              <div className="space-y-2">
                <Label>Telegram-бот</Label>
                <Select
                  value={formState.botId}
                  onValueChange={(value: string) => {
                    setFormState((prev) => ({
                      ...prev,
                      botId: value,
                      botToken: '',
                      botGroupChatId: '',
                    }));
                    setFormNotice(null);
                  }}
                  disabled={Boolean(formState.botToken.trim())}
                >
                  <SelectTrigger>
                    <SelectValue
                      placeholder={
                        formState.botToken.trim()
                          ? 'Будет создан новый бот по токену'
                          : availableBots.length
                          ? 'Выберите бота'
                          : 'Нет подключённых ботов'
                      }
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {availableBots.length === 0 ? (
                      <SelectItem value="__none" disabled>
                        Нет подключённых ботов — укажите токен выше
                      </SelectItem>
                    ) : (
                      availableBots.map((bot) => (
                        <SelectItem key={bot.id} value={String(bot.id)}>
                          @{bot.bot_username || `bot_${bot.id}`} — {bot.status === 'active' ? 'активен' : 'в ожидании'}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label>Рабочая группа Telegram</Label>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <Select
                    value={formState.botGroupChatId}
                    onValueChange={(value: string) => {
                      setFormState((prev) => ({ ...prev, botGroupChatId: value }));
                      setFormNotice(null);
                    }}
                    disabled={!currentBotId}
                  >
                    <SelectTrigger className="sm:w-[320px] sm:flex-1 justify-between">
                      <SelectValue
                        placeholder={
                          currentBotId
                            ? botChatsLoading
                              ? 'Загружаем группы...'
                              : 'Выберите группу из списка'
                            : 'Подключите или выберите бота'
                        }
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {botChats.length === 0 ? (
                        <SelectItem value="__empty" disabled>
                          {botChatsLoading ? 'Загружаем...' : 'Нет доступных групп'}
                        </SelectItem>
                      ) : (
                        botChats.map((chat) => (
                          <SelectItem key={chat.chat_id} value={chat.chat_id}>
                            {chat.title ?? chat.username ?? chat.chat_id}
                          </SelectItem>
                        ))
                      )}
                    </SelectContent>
                  </Select>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => {
                      if (currentBotId) {
                        void fetchBotChats(currentBotId);
                      }
                    }}
                    disabled={!currentBotId || botChatsLoading}
                    aria-label="Обновить список групп"
                  >
                    {botChatsLoading ? <Loader2 className="size-4 animate-spin" /> : <RefreshCcw className="size-4" />}
                  </Button>
                </div>
                <Input
                  id="bot-group-chat"
                  value={formState.botGroupChatId}
                  onChange={(event) => {
                    setFormState((prev) => ({ ...prev, botGroupChatId: event.target.value }));
                    setFormNotice(null);
                  }}
                  placeholder="Если группы нет в списке, введите ID вручную, например -1001234567890"
                />
                <p className="text-xs text-muted-foreground">
                  Укажите форум-группу, куда бот будет создавать топики. Без выбора группы проект сохранить нельзя.
                </p>
              </div>
              <div className="flex flex-col justify-end gap-3 rounded-2xl border border-dashed border-[var(--app-border)] p-4 md:flex-row md:items-center">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-foreground">Использовать этого бота как источник</p>
                  <p className="text-xs text-muted-foreground">
                    При включении входящие сообщения этого бота будут автоматически попадать в проект через Telegram источник.
                  </p>
                </div>
                <Switch
                  checked={formState.useBotAsSource}
                  onCheckedChange={(value) => setFormState((prev) => ({ ...prev, useBotAsSource: value }))}
                />
              </div>
            </div>

            {formNotice && (
              <Alert variant="info" appearance="light">
                <AlertDescription>{formNotice}</AlertDescription>
              </Alert>
            )}

            {formError && (
              <Alert variant="destructive" appearance="light">
                <AlertDescription>{formError}</AlertDescription>
              </Alert>
            )}

            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-muted-foreground">
                После создания проекта можно настроить автоответчики, фильтры и подключить дополнительные источники.
              </p>
              <div className="flex items-center gap-3">
                <Button type="submit" disabled={formSubmitting || !formState.botGroupChatId.trim()}>
                  {formSubmitting ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Sparkles className="mr-2 size-4" />}
                  Создать проект
                </Button>
              </div>
            </div>
          </form>
        </section>
      )}

      <section className="grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
        {projects.map((project) => {
          const projectAccounts = accounts.filter((account) => account.project_id === project.id);
          const projectSources = sources.filter((source) => source.project_id === project.id);
          const projectPersonal = personalAccounts.filter((account) => account.project_id === project.id);
          const projectBot = project.bot_id ? bots.find((bot) => bot.id === project.bot_id) : undefined;

          return (
            <article
              key={project.id}
              className="glass-panel flex h-full flex-col justify-between rounded-[28px] border border-[var(--app-border)] p-6 shadow-lg shadow-blue-100"
            >
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-semibold text-foreground">{project.name}</h2>
                    {project.slug && <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">/{project.slug}</p>}
                  </div>
                  <ProjectStatusBadge project={project} />
                </div>
                {project.description ? (
                  <p className="text-sm text-muted-foreground line-clamp-3">{project.description}</p>
                ) : (
                  <p className="text-sm text-muted-foreground italic">Добавьте описание, чтобы команде было проще ориентироваться.</p>
                )}
                <div className="rounded-2xl border border-dashed border-[var(--app-border)] p-4">
                  <div className="grid gap-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm text-muted-foreground">Telegram-бот</div>
                      <Badge appearance="light" variant={projectBot?.status === 'active' ? 'success' : 'warning'} size="sm">
                        {projectBot ? `@${projectBot.bot_username ?? `bot_${projectBot.id}`}` : 'Не привязан'}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm text-muted-foreground">Avito аккаунты</div>
                      <span className="text-sm font-medium text-foreground">
                        {formatCountLabel(projectAccounts.length, 'подключение', 'подключений')}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm text-muted-foreground">Telegram источники</div>
                      <span className="text-sm font-medium text-foreground">
                        {formatCountLabel(projectSources.length, 'канал', 'каналов')}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm text-muted-foreground">Личные аккаунты</div>
                      <span className="text-sm font-medium text-foreground">
                        {formatCountLabel(projectPersonal.length, 'аккаунт', 'аккаунтов')}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm text-muted-foreground">Цитирование</div>
                      <Badge appearance="light" variant={project.require_reply_for_sources ? 'warning' : 'secondary'} size="sm">
                        {project.require_reply_for_sources ? 'Требуется' : 'Не требуется'}
                      </Badge>
                    </div>
                  </div>
                </div>
              </div>
              <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span>
                    Создан {project.created_at ? new Intl.DateTimeFormat('ru-RU').format(new Date(project.created_at)) : '—'}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Автоответ</span>
                    <Switch
                      checked={project.auto_reply_enabled}
                      disabled={autoReplyUpdatingId === project.id}
                      onCheckedChange={(value) => void handleToggleAutoReply(project, Boolean(value))}
                      aria-label="Переключить автоответ"
                    />
                    {autoReplyUpdatingId === project.id ? (
                      <Loader2 className="size-4 animate-spin text-muted-foreground" />
                    ) : null}
                  </div>
                  <Button asChild variant="outline" size="sm">
                    <Link href={`/client/projects/${project.id}`}>Открыть проект</Link>
                  </Button>
                </div>
              </div>
            </article>
          );
        })}
      </section>

      {!loading && projects.length === 0 && (
        <div className="glass-panel flex flex-col items-center justify-center gap-4 rounded-[32px] border border-dashed border-[var(--app-border)] p-12 text-center shadow-inner shadow-blue-100">
          <Sparkles className="size-8 text-blue-500" />
          <div className="space-y-2">
            <h2 className="text-xl font-semibold text-foreground">У вас ещё нет проектов</h2>
            <p className="max-w-md text-sm text-muted-foreground">
              Создайте первый проект, чтобы связать Telegram-бота, рабочую группу и источники сообщений в единое рабочее пространство.
            </p>
          </div>
      <Button onClick={() => setShowCreateForm(true)}>
        <PlusCircle className="mr-2 size-4" />
        Создать проект
      </Button>
    </div>
  )}
</div>
);
}
