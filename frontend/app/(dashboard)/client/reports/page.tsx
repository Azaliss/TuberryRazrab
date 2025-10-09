'use client';

import { Badge } from '@/components/ui/base-badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { CardStackIcon } from '@radix-ui/react-icons';
import { FileText, Printer } from 'lucide-react';

const reportTemplates = [
  {
    title: 'Сводный отчёт по отделу продаж',
    description: 'Показывает динамику обращений и ответов менеджеров за выбранный период.',
    frequency: 'Еженедельно',
  },
  {
    title: 'Отчёт по рекламным каналам',
    description: 'Содержит распределение запросов по источникам и окупаемость трафика.',
    frequency: 'Ежемесячно',
  },
  {
    title: 'Качество обслуживания',
    description: 'Анализирует скорость ответа и удовлетворённость клиентов по последним диалогам.',
    frequency: 'По запросу',
  },
];

export default function ReportsPage() {
  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <Badge variant="info" appearance="light" size="xs">
            Бета-функция
          </Badge>
          <h1 className="text-2xl font-semibold text-foreground">Отчёты и презентации</h1>
          <p className="text-sm text-muted-foreground">
            Соберите ключевые показатели в один документ и отправьте команде или клиенту.
          </p>
        </div>
        <Button>
          <FileText className="mr-2 size-4" /> Создать отчёт
        </Button>
      </header>

      <section className="grid gap-4 md:grid-cols-2">
        {reportTemplates.map((report) => (
          <article
            key={report.title}
            className="rounded-3xl bg-white/80 p-6 shadow-[0_18px_60px_-40px_rgba(30,64,175,0.55)] ring-1 ring-white/70"
          >
            <div className="flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-xl bg-blue-500/10 text-blue-600">
                <CardStackIcon className="size-5" />
              </span>
              <div>
                <h2 className="text-lg font-semibold text-foreground">{report.title}</h2>
                <p className="text-xs text-muted-foreground">{report.frequency}</p>
              </div>
            </div>
            <p className="mt-4 text-sm text-muted-foreground">{report.description}</p>
            <div className="mt-6 flex gap-2">
              <Button size="sm" variant="outline">
                <Printer className="mr-2 size-4" /> Печать
              </Button>
              <Button size="sm" variant="ghost">
                <FileText className="mr-2 size-4" /> Экспорт PDF
              </Button>
            </div>
          </article>
        ))}
      </section>

      <Alert appearance="light" className="border border-dashed border-primary/30 bg-primary/5 text-primary">
        <AlertTitle>Автоматические рассылки</AlertTitle>
        <AlertDescription>
          В ближайшем обновлении отчёты можно будет отправлять по расписанию в Telegram или email.
        </AlertDescription>
      </Alert>
    </div>
  );
}
