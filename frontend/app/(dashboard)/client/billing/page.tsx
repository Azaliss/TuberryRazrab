'use client';

import { Badge } from '@/components/ui/base-badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { CreditCard, Wallet } from 'lucide-react';

const invoices = [
  { id: 'INV-1029', period: 'Сентябрь 2025', amount: '12 900 ₽', status: 'Оплачено', method: 'Карта' },
  { id: 'INV-1028', period: 'Август 2025', amount: '11 500 ₽', status: 'Оплачено', method: 'СБП' },
  { id: 'INV-1027', period: 'Июль 2025', amount: '11 500 ₽', status: 'Просрочено', method: 'Карта' },
];

export default function BillingPage() {
  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <Badge variant="secondary" appearance="light" size="xs">
            Финансы
          </Badge>
          <h1 className="text-2xl font-semibold text-foreground">Оплата и тарифы</h1>
          <p className="text-sm text-muted-foreground">
            Контролируйте оплату сервиса и управляйте тарифным планом команды.
          </p>
        </div>
        <Button>
          <CreditCard className="mr-2 size-4" /> Пополнить баланс
        </Button>
      </header>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-3xl bg-white/80 p-6 shadow-[0_18px_60px_-40px_rgba(30,64,175,0.55)] ring-1 ring-white/70">
          <p className="text-sm text-muted-foreground">Текущий тариф</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">Business Unlimited</h2>
          <p className="mt-2 text-sm text-muted-foreground">Неограниченные диалоги и до 15 операторов в одной команде.</p>
          <Button variant="outline" size="sm" className="mt-4">
            Изменить тариф
          </Button>
        </div>
        <div className="rounded-3xl bg-white/80 p-6 shadow-[0_18px_60px_-40px_rgba(30,64,175,0.55)] ring-1 ring-white/70">
          <p className="text-sm text-muted-foreground">Баланс</p>
          <div className="mt-2 flex items-baseline gap-2">
            <h3 className="text-3xl font-semibold text-foreground">18 430 ₽</h3>
            <Badge variant="success" appearance="light" size="xs">
              Хватает на 45 дней
            </Badge>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">Автосписание подключено 1 числа каждого месяца.</p>
        </div>
      </section>

      <div className="rounded-3xl bg-white/80 p-6 shadow-[0_18px_60px_-40px_rgba(30,64,175,0.55)] ring-1 ring-white/70">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-foreground">История счетов</h2>
            <p className="text-sm text-muted-foreground">Скачайте закрывающие документы или повторите оплату.</p>
          </div>
          <Button variant="outline" size="sm">
            <Wallet className="mr-2 size-4" /> Управлять способами оплаты
          </Button>
        </div>
        <div className="mt-5 overflow-hidden rounded-2xl border border-border/60">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Счёт</TableHead>
                <TableHead>Период</TableHead>
                <TableHead>Сумма</TableHead>
                <TableHead>Статус</TableHead>
                <TableHead>Метод</TableHead>
                <TableHead className="text-right">Действия</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invoices.map((invoice) => (
                <TableRow key={invoice.id}>
                  <TableCell className="font-medium">{invoice.id}</TableCell>
                  <TableCell>{invoice.period}</TableCell>
                  <TableCell>{invoice.amount}</TableCell>
                  <TableCell>
                    <Badge
                      variant={invoice.status === 'Просрочено' ? 'destructive' : 'success'}
                      appearance="light"
                      size="xs"
                    >
                      {invoice.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{invoice.method}</TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm">
                      Скачать акт
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>

      <Alert appearance="light" className="border-orange-200/70 bg-orange-50/70 text-orange-800">
        <AlertDescription>
          Для подключения безналичных оплат свяжитесь с менеджером поддержки — мы подготовим индивидуальный договор.
        </AlertDescription>
      </Alert>
    </div>
  );
}
