'use client';

import { Badge } from '@/components/ui/base-badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { CheckCircle2, PlugZap } from 'lucide-react';

const integrations = [
  {
    name: 'Telegram Bot API',
    status: 'Активно',
    description: 'Bidirectional синхронизация сообщений и вложений.',
    connectedAt: '12 сентября 2025',
  },
  {
    name: 'Bitrix24 CRM',
    status: 'Включено',
    description: 'Передача лидов и статусов сделок каждые 5 минут.',
    connectedAt: '4 сентября 2025',
  },
  {
    name: 'Google Sheets',
    status: 'Отключено',
    description: 'Экспорт диалогов в таблицу для аналитики.',
    connectedAt: '—',
  },
];

export default function IntegrationsPage() {
  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <Badge variant="secondary" appearance="light" size="xs">
            Интеграции
          </Badge>
          <h1 className="text-2xl font-semibold text-foreground">Подключённые сервисы</h1>
          <p className="text-sm text-muted-foreground">
            Управляйте подключениям к CRM, BI-системам и мессенджерам.
          </p>
        </div>
        <Button>
          <PlugZap className="mr-2 size-4" /> Добавить интеграцию
        </Button>
      </header>

      <div className="rounded-3xl bg-white/80 p-6 shadow-[0_18px_60px_-40px_rgba(30,64,175,0.55)] ring-1 ring-white/70">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Сервис</TableHead>
              <TableHead>Статус</TableHead>
              <TableHead>Описание</TableHead>
              <TableHead>Подключено</TableHead>
              <TableHead className="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {integrations.map((integration) => (
              <TableRow key={integration.name}>
                <TableCell className="font-medium">{integration.name}</TableCell>
                <TableCell>
                  <Badge
                    variant={integration.status === 'Активно' || integration.status === 'Включено' ? 'success' : 'secondary'}
                    appearance="light"
                    size="xs"
                  >
                    {integration.status}
                  </Badge>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{integration.description}</TableCell>
                <TableCell>{integration.connectedAt}</TableCell>
                <TableCell className="text-right">
                  <Button variant="outline" size="sm">
                    Управлять
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Alert appearance="light" className="border-emerald-200/70 bg-emerald-50/70 text-emerald-800">
        <div className="flex items-start gap-3">
          <CheckCircle2 className="mt-0.5 size-4" />
          <AlertDescription>
            Подключите Webhook в разделе «Сценарии», чтобы автоматически отправлять заявки в CRM и считать конверсию.
          </AlertDescription>
        </div>
      </Alert>
    </div>
  );
}
