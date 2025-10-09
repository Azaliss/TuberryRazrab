'use client';

import { Badge } from '@/components/ui/base-badge';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ArrowUpRight, Download } from 'lucide-react';

const metrics = [
  { label: 'Ответы за сутки', value: '146', delta: '+18%', trend: 'positive' },
  { label: 'Среднее время ответа', value: '3 мин.', delta: '-22%', trend: 'positive' },
  { label: 'Заявок из рекламы', value: '62', delta: '+9%', trend: 'positive' },
];

const topChannels = [
  { channel: 'Telegram', sessions: 92, conversion: '34%' },
  { channel: 'Avito', sessions: 58, conversion: '27%' },
  { channel: 'VK', sessions: 31, conversion: '18%' },
];

export default function AnalyticsPage() {
  return (
    <div className="space-y-8">
      <section className="grid gap-4 md:grid-cols-3">
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className="rounded-3xl bg-white/80 p-6 shadow-[0_18px_60px_-40px_rgba(30,64,175,0.55)] ring-1 ring-white/70"
          >
            <p className="text-sm text-muted-foreground">{metric.label}</p>
            <div className="mt-2 flex items-baseline gap-2">
              <h3 className="text-3xl font-semibold text-foreground">{metric.value}</h3>
              <Badge
                variant={metric.trend === 'positive' ? 'success' : 'destructive'}
                appearance="light"
                size="xs"
              >
                {metric.delta}
              </Badge>
            </div>
          </div>
        ))}
      </section>

      <section className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="rounded-3xl bg-white/80 p-6 shadow-[0_18px_60px_-40px_rgba(30,64,175,0.55)] ring-1 ring-white/70">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-foreground">Распределение диалогов</h2>
              <p className="text-sm text-muted-foreground">Показывает активность операторов по каналам за прошедшую неделю.</p>
            </div>
            <Button variant="outline" size="sm">
              <Download className="mr-2 size-4" /> Экспорт
            </Button>
          </div>
          <div className="mt-6 overflow-hidden rounded-2xl border border-border/60">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Канал</TableHead>
                  <TableHead>Диалогов</TableHead>
                  <TableHead>Конверсия</TableHead>
                  <TableHead className="text-right">Детали</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {topChannels.map((channel) => (
                  <TableRow key={channel.channel}>
                    <TableCell className="font-medium">{channel.channel}</TableCell>
                    <TableCell>{channel.sessions}</TableCell>
                    <TableCell>{channel.conversion}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm">
                        Смотреть
                        <ArrowUpRight className="ml-1 size-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>

        <aside className="space-y-4 rounded-3xl bg-white/80 p-6 shadow-[0_18px_60px_-40px_rgba(30,64,175,0.55)] ring-1 ring-white/70">
          <h3 className="text-lg font-semibold text-foreground">Советы по улучшению</h3>
          <Alert appearance="light" className="border-blue-200/70 bg-blue-50/70 text-blue-800">
            <AlertDescription>
              Подключите автоответы в разделе «Сценарии», чтобы сократить время реакции на входящие заявки.</AlertDescription>
          </Alert>
          <Alert appearance="light" className="border-emerald-200/70 bg-emerald-50/70 text-emerald-800">
            <AlertDescription>
              Настройте интеграцию с CRM и синхронизируйте источники лидов в один отчёт.
            </AlertDescription>
          </Alert>
        </aside>
      </section>
    </div>
  );
}
