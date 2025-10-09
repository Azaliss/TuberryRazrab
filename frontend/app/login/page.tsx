'use client';

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/base-badge';
import { Input } from '@/components/ui/base-input';
import { Label } from '@/components/ui/base-label';
import { Button } from '@/components/ui/button';
import { apiFetch } from '@/lib/api';
import { ChevronDown, Loader2, Lock, LogIn } from 'lucide-react';

type TelegramWidgetUser = {
  id: number | string;
  auth_date: number | string;
  hash: string;
  first_name?: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  language_code?: string;
  allows_write_to_pm?: boolean;
};

const normaliseBotUsername = (value: string): string => value.trim().replace(/^@/, '');

declare global {
  interface Window {
    tuberryTelegramAuth?: (user: TelegramWidgetUser) => void;
  }
}

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
  } catch (error) {
    console.warn('Не удалось распарсить JWT:', error);
    return undefined;
  }
};

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [showCredentials, setShowCredentials] = useState(false);

  const initialBot = useMemo(() => normaliseBotUsername(process.env.NEXT_PUBLIC_TELEGRAM_LOGIN_BOT || ''), []);
  const [telegramLoginBot, setTelegramLoginBot] = useState(initialBot);
  const [configLoading, setConfigLoading] = useState(!initialBot);
  const [configError, setConfigError] = useState<string | null>(null);
  const telegramContainerRef = useRef<HTMLDivElement | null>(null);

  const handleTelegramAuth = useCallback(
    async (user: TelegramWidgetUser) => {
      setError(null);
      setStatus(null);
      setLoading(true);

      try {
        const payload = {
          id: Number(user.id),
          auth_date: Number(user.auth_date),
          hash: user.hash,
          first_name: user.first_name,
          last_name: user.last_name,
          username: user.username,
          photo_url: user.photo_url,
          language_code: user.language_code,
          allows_write_to_pm: user.allows_write_to_pm,
        };

        const response = await apiFetch('/api/auth/telegram', {
          method: 'POST',
          body: JSON.stringify(payload),
        });

        const accessToken: string | undefined = response?.access_token;
        if (!accessToken) {
          throw new Error('Не удалось получить токен.');
        }

        if (typeof window !== 'undefined') {
          window.localStorage.setItem('tuberry_token', accessToken);
        }

        const role = decodeRole(accessToken);
        const target = role === 'admin' ? '/admin' : '/client';
        setStatus(role === 'admin' ? 'Добро пожаловать, администратор!' : 'Готовим личный кабинет…');
        router.replace(target);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [router],
  );

  const handleCredentialsLogin = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setError(null);
      setStatus(null);
      setLoading(true);

      try {
        const response = await apiFetch('/api/auth/login', {
          method: 'POST',
          body: JSON.stringify({
            email: login.trim(),
            password,
          }),
        });

        const accessToken: string | undefined = response?.access_token;
        if (!accessToken) {
          throw new Error('Не удалось получить токен.');
        }

        if (typeof window !== 'undefined') {
          window.localStorage.setItem('tuberry_token', accessToken);
        }

        const role = decodeRole(accessToken);
        const target = role === 'admin' ? '/admin' : '/client';
        setStatus(role === 'admin' ? 'Входим в админ-панель…' : 'Открываем личный кабинет…');
        router.replace(target);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [login, password, router],
  );

  useEffect(() => {
    let cancelled = false;

    const loadConfig = async () => {
      if (initialBot) {
        setConfigLoading(false);
        return;
      }

      setConfigLoading(true);
      setConfigError(null);
      try {
        const response = await apiFetch('/api/auth/telegram/config');
        const fetchedBot = typeof response?.bot_username === 'string' ? normaliseBotUsername(response.bot_username) : '';
        if (!cancelled && fetchedBot) {
          setTelegramLoginBot(fetchedBot);
        }
      } catch (err) {
        if (!cancelled) {
          setConfigError((err as Error).message);
        }
      } finally {
        if (!cancelled) {
          setConfigLoading(false);
        }
      }
    };

    void loadConfig();

    return () => {
      cancelled = true;
    };
  }, [initialBot]);

  useEffect(() => {
    if (!telegramLoginBot || typeof window === 'undefined') {
      return;
    }

    window.tuberryTelegramAuth = (user: TelegramWidgetUser) => {
      if (!loading) {
        void handleTelegramAuth(user);
      }
    };

    const container = telegramContainerRef.current;
    if (container) {
      container.innerHTML = '';
      const script = document.createElement('script');
      script.src = 'https://telegram.org/js/telegram-widget.js?22';
      script.async = true;
      script.setAttribute('data-telegram-login', telegramLoginBot);
      script.setAttribute('data-size', 'large');
      script.setAttribute('data-request-access', 'write');
      script.setAttribute('data-userpic', 'false');
      script.setAttribute('data-lang', 'ru');
      script.setAttribute('data-radius', '20');
      script.setAttribute('data-onauth', 'tuberryTelegramAuth(user)');
      container.appendChild(script);
    }

    return () => {
      delete window.tuberryTelegramAuth;
      if (container) {
        container.innerHTML = '';
      }
    };
  }, [handleTelegramAuth, loading, telegramLoginBot]);

  return (
    <div className="relative min-h-screen bg-[var(--app-gradient)] py-16">
      <div className="absolute inset-0 -z-10 bg-gradient-to-br from-white/60 via-white/30 to-transparent backdrop-blur-xl" />
      <div className="mx-auto flex w-full max-w-md flex-col gap-6 rounded-[30px] border border-[var(--app-border)] bg-white/75 p-8 shadow-[0_30px_120px_-50px_rgba(30,64,175,0.35)] backdrop-blur-2xl">
        <header className="space-y-3">
          <Badge variant="info" appearance="light" size="xs" className="uppercase tracking-[0.3em] text-[10px]">
            Tuberry
          </Badge>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-500/15 text-blue-600 shadow-inner">
              <Lock className="size-5" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold">Вход в личный кабинет</h1>
              <p className="text-sm text-muted-foreground">Подключите аккаунт, чтобы управлять диалогами и интеграциями.</p>
            </div>
          </div>
        </header>

        <div className="space-y-4">
          {telegramLoginBot ? (
            <div className="flex flex-col items-center gap-4 rounded-2xl border border-[var(--app-border)] bg-white/70 p-8 text-center shadow-inner">
              {(loading || configLoading) ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="size-4 animate-spin" />
                  {configLoading ? 'Загружаем настройки…' : 'Подтверждаем вход…'}
                </div>
              ) : null}
              <div ref={telegramContainerRef} className="flex justify-center" />
            </div>
          ) : (
            <Alert variant="destructive" appearance="light" className="glass-panel border border-red-200/70">
              <AlertTitle>Виджет недоступен</AlertTitle>
              <AlertDescription>
                {configLoading && !configError
                  ? 'Загружаем настройки…'
                  : configError
                    ? `Не удалось получить имя Telegram-бота: ${configError}`
                    : 'Укажите в админке отображаемое имя бота (поле "Отображаемое имя") или переменную окружения `NEXT_PUBLIC_TELEGRAM_LOGIN_BOT`.'}
              </AlertDescription>
            </Alert>
          )}
        </div>

        <div className="space-y-3">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="w-full justify-between rounded-2xl border border-transparent bg-white/70 px-4 py-5 text-sm font-medium text-muted-foreground shadow-inner transition hover:border-[var(--app-border)] hover:text-foreground"
            onClick={() => {
              setShowCredentials((prev) => !prev);
              setError(null);
              setStatus(null);
            }}
            aria-expanded={showCredentials}
          >
            <span>{showCredentials ? 'Скрыть вход по логину и паролю' : 'Войти по логину и паролю'}</span>
            <ChevronDown className={`size-4 transition-transform ${showCredentials ? 'rotate-180' : ''}`} />
          </Button>

          {showCredentials ? (
            <form
              onSubmit={handleCredentialsLogin}
              className="glass-panel space-y-4 rounded-[24px] border border-[var(--app-border)] bg-white/75 p-6"
            >
              <div className="space-y-2">
                <Label htmlFor="login-email">Логин</Label>
                <Input
                  id="login-email"
                  placeholder="Введите логин"
                  autoComplete="username"
                  value={login}
                  onChange={(event) => setLogin(event.target.value)}
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="login-password">Пароль</Label>
                <Input
                  id="login-password"
                  type="password"
                  placeholder="Введите пароль"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </div>

              <Button type="submit" disabled={loading} className="w-full">
                {loading ? <Loader2 className="mr-2 size-4 animate-spin" /> : <LogIn className="mr-2 size-4" />}
                {loading ? 'Проверяем данные…' : 'Войти'}
              </Button>
            </form>
          ) : null}
        </div>

        {status && (
          <Alert variant="success" appearance="light" className="glass-panel border border-emerald-200/70">
            <AlertTitle>Готово</AlertTitle>
            <AlertDescription>{status}</AlertDescription>
          </Alert>
        )}

        {error && (
          <Alert variant="destructive" appearance="light" className="glass-panel border border-red-200/70">
            <AlertTitle>Ошибка входа</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </div>
    </div>
  );
}
