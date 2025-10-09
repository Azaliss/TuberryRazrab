'use client';

import { ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AccordionMenu,
  AccordionMenuGroup,
  AccordionMenuItem,
  AccordionMenuLabel,
  AccordionMenuSeparator,
} from '@/components/ui/accordion-menu';
import { Badge } from '@/components/ui/base-badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  BarChart3,
  Bot,
  CreditCard,
  Home,
  LifeBuoy,
  Link as LinkIcon,
  LogOut,
  MessageSquare,
  Pin,
  PinOff,
  Settings2,
  Sparkles,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

interface ClientShellProps {
  children: ReactNode;
}

type NavItem = {
  label: string;
  href: string;
  icon: ReactNode;
  description?: string;
};

type NavGroup = {
  label: string;
  items: NavItem[];
};

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Рабочая область',
    items: [
      { label: 'Дашборд', href: '/client', icon: <Home className="size-4" /> },
      { label: 'Диалоги', href: '/client/dialogs', icon: <MessageSquare className="size-4" /> },
      { label: 'Настройки', href: '/client/settings', icon: <Settings2 className="size-4" /> },
    ],
  },
  {
    label: 'Аналитика',
    items: [
      { label: 'Показатели', href: '/client/analytics', icon: <BarChart3 className="size-4" /> },
      { label: 'Отчёты', href: '/client/reports', icon: <Sparkles className="size-4" /> },
    ],
  },
  {
    label: 'Автоматизация',
    items: [
      { label: 'Сценарии', href: '/client/automations', icon: <Bot className="size-4" /> },
      { label: 'Интеграции', href: '/client/integrations', icon: <LinkIcon className="size-4" /> },
    ],
  },
  {
    label: 'Финансы и поддержка',
    items: [
      { label: 'Биллинг', href: '/client/billing', icon: <CreditCard className="size-4" /> },
      { label: 'Поддержка', href: '/client/support', icon: <LifeBuoy className="size-4" /> },
    ],
  },
];

export function ClientShell({ children }: ClientShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true);
  const [isSidebarContentVisible, setIsSidebarContentVisible] = useState(false);
  const [isSidebarPinned, setIsSidebarPinned] = useState(false);
  const collapseTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const matchPath = useCallback(
    (href: string) => {
      if (!pathname) return false;
      return pathname === href || pathname.startsWith(`${href}/`);
    },
    [pathname],
  );

  const handleNavigate = useCallback(
    (value: string) => {
      if (value && value !== pathname) {
        router.push(value);
      }
    },
    [pathname, router],
  );

  const handleLogout = useCallback(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem('tuberry_token');
    }
    router.replace('/login');
  }, [router]);

  const handleSidebarEnter = useCallback(() => {
    if (isSidebarPinned) {
      return;
    }
    if (collapseTimeoutRef.current) {
      clearTimeout(collapseTimeoutRef.current);
      collapseTimeoutRef.current = null;
    }
    setIsSidebarCollapsed(false);
    setIsSidebarContentVisible(true);
  }, [isSidebarPinned]);

  const handleSidebarLeave = useCallback(() => {
    if (isSidebarPinned) {
      return;
    }
    if (collapseTimeoutRef.current) {
      clearTimeout(collapseTimeoutRef.current);
    }
    setIsSidebarContentVisible(false);
    collapseTimeoutRef.current = setTimeout(() => {
      setIsSidebarCollapsed(true);
      collapseTimeoutRef.current = null;
    }, 720);
  }, [isSidebarPinned]);

  useEffect(() => {
    return () => {
      if (collapseTimeoutRef.current) {
        clearTimeout(collapseTimeoutRef.current);
      }
    };
  }, []);

  const selectedValue = useMemo(() => pathname ?? '/client', [pathname]);
  const flatNavItems = useMemo(() => NAV_GROUPS.flatMap((group) => group.items), []);

  return (
    <div className="relative min-h-screen">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[var(--app-gradient)]" aria-hidden="true" />
      <div className="mx-auto flex min-h-screen w-full max-w-screen-2xl gap-5 px-4 py-8 lg:gap-6 lg:px-8">
        <aside
          className={cn('relative hidden xl:flex', isSidebarPinned ? 'w-[300px]' : '')}
          onMouseEnter={handleSidebarEnter}
          onMouseLeave={handleSidebarLeave}
        >
          <div
            className={cn(
              'glass-panel flex h-full flex-col items-center gap-6 rounded-[28px] border border-[var(--app-border)] shadow-[0_28px_100px_-48px_rgba(30,64,175,0.45)] backdrop-blur-2xl z-30 transition-all duration-[2000ms] ease-out',
              isSidebarPinned
                ? 'w-0 px-0 py-0 opacity-0 pointer-events-none'
                : 'w-[88px] px-3 py-6 opacity-100 pointer-events-auto',
              !isSidebarPinned && !isSidebarCollapsed && 'opacity-60',
            )}
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/80 text-sm font-semibold text-primary shadow-sm shadow-blue-100">
              Tb
            </div>
            <div className="flex w-full flex-1 flex-col items-center gap-6 overflow-hidden">
              {NAV_GROUPS.map((group, index) => (
                <div key={group.label} className="flex flex-col items-center gap-2">
                  <div className="h-5" aria-hidden="true" />
                  {group.items.map((item) => {
                    const active = matchPath(item.href);
                    return (
                      <button
                        key={item.href}
                        type="button"
                        onClick={() => handleNavigate(item.href)}
                        className={cn(
                          'flex h-10 w-10 items-center justify-center rounded-2xl transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40',
                          active
                            ? 'bg-primary/15 text-primary shadow-sm shadow-primary/20'
                            : 'bg-white/70 text-muted-foreground hover:bg-primary/10 hover:text-primary',
                        )}
                        aria-label={item.label}
                      >
                        {item.icon}
                      </button>
                    );
                  })}
                  {index < NAV_GROUPS.length - 1 ? (
                    <div className="mt-3 h-px w-8 bg-[var(--app-border)]/60" aria-hidden="true" />
                  ) : null}
                </div>
              ))}
            </div>
            <div className="mt-auto flex flex-col items-center gap-3">
              <Button asChild variant="secondary" size="icon" className="rounded-2xl">
                <Link href="/register" aria-label="Пригласить коллегу">
                  <Sparkles className="size-4" />
                </Link>
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="rounded-2xl text-muted-foreground hover:text-foreground"
                onClick={handleLogout}
                aria-label="Выйти из кабинета"
              >
                <LogOut className="size-4" />
              </Button>
            </div>
          </div>

          <div
            className={cn(
              'absolute top-0 left-0 z-40 h-full w-[300px] origin-left transform-gpu transition-transform duration-[2000ms] ease-in-out',
              isSidebarCollapsed && !isSidebarPinned
                ? 'pointer-events-none scale-x-0 opacity-0'
                : 'pointer-events-auto scale-x-100 opacity-100'
            )}
            onMouseEnter={handleSidebarEnter}
            onMouseLeave={handleSidebarLeave}
          >
            <div
              className={cn(
                'glass-panel relative flex h-full w-[300px] flex-col gap-6 rounded-[28px] border border-[var(--app-border)] px-6 py-6 shadow-[0_28px_100px_-48px_rgba(30,64,175,0.5)] drop-shadow-[0_36px_60px_rgba(15,23,42,0.35)] backdrop-blur-2xl transition-[opacity,transform] duration-[2000ms] ease-in-out',
                isSidebarContentVisible || isSidebarPinned
                  ? 'translate-x-0 opacity-100'
                  : '-translate-x-4 opacity-0 pointer-events-none',
              )}
            >
              <div className="pointer-events-none absolute -bottom-2 left-6 right-6 h-4 rounded-full bg-slate-900/15 blur-lg -z-10" aria-hidden="true" />
              <div className="flex items-center justify-between">
                <Badge variant="secondary" appearance="light" size="xs" className="tracking-[0.32em] uppercase">
                  Tuberry
                </Badge>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-xl text-muted-foreground transition-colors hover:text-primary"
                  onClick={() => {
                    setIsSidebarPinned((prev) => {
                      const next = !prev;
                      if (next) {
                        setIsSidebarCollapsed(false);
                        setIsSidebarContentVisible(true);
                      } else {
                        setIsSidebarContentVisible(false);
                        setIsSidebarCollapsed(true);
                      }
                      return next;
                    });
                  }}
                  aria-label={isSidebarPinned ? 'Открепить меню' : 'Закрепить меню'}
                >
                  {isSidebarPinned ? <PinOff className="size-4" /> : <Pin className="size-4" />}
                </Button>
              </div>

              <AccordionMenu
                type="multiple"
                selectedValue={selectedValue}
                matchPath={matchPath}
                onItemClick={(value, event) => {
                  event.preventDefault();
                  handleNavigate(value);
                }}
                classNames={{
                  item: 'data-[selected=true]:border border-[var(--app-border)] bg-white/80 shadow-sm shadow-blue-100',
                }}
              >
                {NAV_GROUPS.map((group, index) => (
                  <AccordionMenuGroup key={group.label} className="space-y-2">
                    <AccordionMenuLabel className="px-2 text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground/80">
                      {group.label}
                    </AccordionMenuLabel>
                    {group.items.map((item) => (
                      <AccordionMenuItem key={item.href} value={item.href} asChild>
                        <button
                          type="button"
                          className="flex h-10 items-center gap-3 rounded-2xl px-2 transition-colors hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                          onClick={() => handleNavigate(item.href)}
                        >
                          <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white/80 text-primary shadow-sm shadow-blue-100">
                            {item.icon}
                          </span>
                          <span className="flex h-full flex-1 flex-col justify-center text-start leading-tight">
                            <span className="text-sm font-medium text-foreground">{item.label}</span>
                            {item.description ? (
                              <span className="text-xs text-muted-foreground">{item.description}</span>
                            ) : null}
                          </span>
                        </button>
                      </AccordionMenuItem>
                    ))}
                    {index < NAV_GROUPS.length - 1 ? <AccordionMenuSeparator /> : null}
                  </AccordionMenuGroup>
                ))}
              </AccordionMenu>

              <div className="mt-auto space-y-4">
                <div className="rounded-2xl bg-gradient-to-br from-blue-500/20 via-blue-400/10 to-white/70 p-4 text-sm shadow-inner shadow-blue-200 ring-1 ring-blue-300/40">
                  <p className="font-medium text-foreground">Нужен ещё один менеджер?</p>
                  <p className="mt-1 text-muted-foreground">Пригласите коллегу и распределите диалоги всего в несколько кликов.</p>
                  <Button asChild size="sm" className="mt-4 w-full">
                    <Link href="/register">Пригласить коллегу</Link>
                  </Button>
                </div>
                <Button
                  variant="primary"
                  className="w-full justify-center gap-2 shadow-[0_16px_40px_-25px_rgba(30,64,175,0.65)]"
                  onClick={handleLogout}
                >
                  <LogOut className="size-4" />
                  Выйти из кабинета
                </Button>
              </div>
            </div>
          </div>
        </aside>

        <div className="flex min-h-full flex-1 flex-col gap-6">
          <header className="glass-panel rounded-[28px] border border-[var(--app-border)] px-6 py-5 shadow-[0_28px_100px_-60px_rgba(30,64,175,0.45)] backdrop-blur-2xl">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.32em] text-muted-foreground">Tuberry</p>
                <h1 className="mt-1 text-2xl font-semibold text-foreground">
                  {matchPath('/client/settings') ? 'Настройки кабинета' : 'Обновлённый интерфейс Tuberry'}
                </h1>
              </div>
              <div className="flex items-center gap-2">
                <Button asChild variant="outline" size="sm" className="md:hidden">
                  <Link href="/register">Пригласить коллегу</Link>
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground hover:text-foreground md:hidden"
                  onClick={handleLogout}
                >
                  <LogOut className="mr-2 size-4" /> Выйти
                </Button>
              </div>
            </div>
            <div className="mt-4 grid gap-3 text-sm text-muted-foreground md:grid-cols-3">
              <div className="rounded-2xl bg-white/70 p-3 shadow-inner shadow-blue-100 ring-1 ring-white/60">
                <p className="font-medium text-foreground">Быстрый доступ</p>
                <p className="text-xs text-muted-foreground">Выберите раздел в меню слева и продолжайте работу.</p>
              </div>
              <div className="rounded-2xl bg-white/70 p-3 shadow-inner shadow-blue-100 ring-1 ring-white/60">
                <p className="font-medium text-foreground">Активные интеграции</p>
                <p className="text-xs text-muted-foreground">Подключите CRM или командный чат, чтобы автоматизировать ответы.</p>
              </div>
              <div className="rounded-2xl bg-white/70 p-3 shadow-inner shadow-blue-100 ring-1 ring-white/60">
                <p className="font-medium text-foreground">Поддержка 24/7</p>
                <p className="text-xs text-muted-foreground">Служба поддержки отвечает в течение 5 минут.</p>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2 md:hidden">
              {flatNavItems.map((item) => (
                <Button
                  key={item.href}
                  variant={matchPath(item.href) ? 'primary' : 'outline'}
                  size="sm"
                  className="min-w-[120px]"
                  onClick={() => handleNavigate(item.href)}
                >
                  {item.label}
                </Button>
              ))}
            </div>
          </header>

          <main
            className={cn(
              'rounded-[28px] bg-white/70 p-6 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.55)] ring-1 ring-white/70 backdrop-blur-2xl lg:p-8',
            )}
          >
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
