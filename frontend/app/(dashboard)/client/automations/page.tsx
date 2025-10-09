'use client';

import { Badge } from '@/components/ui/base-badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Switch } from '@/components/ui/base-switch';
import { Clock3, MessageSquare, Rocket, Sparkles } from 'lucide-react';

const scenarios = [
  {
    name: 'Приветственный автоответ',
    description: 'Отправляет клиенту приветственное сообщение и собирает основную информацию.',
    status: true,
    eta: 'Активно',
  },
  {
    name: 'Повторное напоминание',
    description: 'Если клиент не ответил в течение 12 часов, отправляется мягкое напоминание.',
    status: false,
    eta: 'Черновик',
  },
  {
    name: 'Передача в отдел продаж',
    description: 'Передаёт диалог менеджеру после позитивного ответа клиента на оффер.',
    status: true,
    eta: 'Активно',
  },
];

export default function AutomationsPage() {
  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <Badge variant="success" appearance="light" size="xs">
            Автоответы
          </Badge>
          <h1 className="text-2xl font-semibold text-foreground">Сценарии автоматизации</h1>
          <p className="text-sm text-muted-foreground">
            Экономьте время команды — настройте цепочки сообщений и условия переходов.
          </p>
        </div>
        <Button>
          <Sparkles className="mr-2 size-4" /> Создать сценарий
        </Button>
      </header>

      <section className="space-y-4">
        {scenarios.map((scenario) => (
          <article
            key={scenario.name}
            className="flex flex-col gap-4 rounded-3xl bg-white/80 p-6 shadow-[0_18px_60px_-40px_rgba(30,64,175,0.55)] ring-1 ring-white/70 md:flex-row md:items-center md:justify-between"
          >
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold text-foreground">{scenario.name}</h2>
                <Badge variant="secondary" appearance="light" size="xs">
                  {scenario.eta}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">{scenario.description}</p>
            </div>
            <div className="flex items-center gap-4">
              <Switch size="sm" checked={scenario.status} readOnly />
              <Button variant="outline" size="sm">
                Настроить
              </Button>
            </div>
          </article>
        ))}
      </section>

      <Alert appearance="light" className="border-blue-200/70 bg-blue-50/70 text-blue-800">
        <div className="flex items-start gap-3">
          <Rocket className="mt-1 size-4" />
          <div>
            <AlertTitle>Интеллектуальные сценарии в разработке</AlertTitle>
            <AlertDescription>
              Скоро появится возможность запускать сценарии в зависимости от тональности сообщений клиентов.
            </AlertDescription>
          </div>
        </div>
      </Alert>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl bg-white/80 p-4 shadow-inner shadow-blue-100 ring-1 ring-white/60">
          <Clock3 className="mb-2 size-5 text-blue-500" />
          <p className="text-sm font-medium text-foreground">Настраивайте расписание отправки</p>
          <p className="text-xs text-muted-foreground">Укажите часы работы и автоматизируйте ответы в ночное время.</p>
        </div>
        <div className="rounded-2xl bg-white/80 p-4 shadow-inner shadow-blue-100 ring-1 ring-white/60">
          <MessageSquare className="mb-2 size-5 text-blue-500" />
          <p className="text-sm font-medium text-foreground">Шаблоны сообщений</p>
          <p className="text-xs text-muted-foreground">Заранее подготовьте текст, чтобы ускорить работу менеджеров.</p>
        </div>
        <div className="rounded-2xl bg-white/80 p-4 shadow-inner shadow-blue-100 ring-1 ring-white/60">
          <Sparkles className="mb-2 size-5 text-blue-500" />
          <p className="text-sm font-medium text-foreground">Динамические переменные</p>
          <p className="text-xs text-muted-foreground">Подставляйте имя клиента и продукт автоматически в текст сообщений.</p>
        </div>
      </div>
    </div>
  );
}
