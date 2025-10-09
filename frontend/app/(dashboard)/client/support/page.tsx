'use client';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/base-badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/base-input';
import { Textarea } from '@/components/ui/textarea';
import { Mail, MessageCircle, Send } from 'lucide-react';

export default function SupportPage() {
  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <Badge variant="info" appearance="light" size="xs">
          Служба поддержки
        </Badge>
        <h1 className="text-2xl font-semibold text-foreground">Помощь и обучение</h1>
        <p className="text-sm text-muted-foreground">
          Свяжитесь с командой Tuberry или оставьте запрос — мы ответим в течение нескольких минут.
        </p>
      </header>

      <section className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <form className="rounded-3xl bg-white/80 p-6 shadow-[0_18px_60px_-40px_rgba(30,64,175,0.55)] ring-1 ring-white/70 space-y-4">
          <div>
            <label className="text-sm font-medium text-foreground" htmlFor="topic">
              Тема обращения
            </label>
            <Input id="topic" placeholder="Например, подключить новую интеграцию" className="mt-2" />
          </div>
          <div>
            <label className="text-sm font-medium text-foreground" htmlFor="message">
              Сообщение
            </label>
            <Textarea id="message" rows={5} placeholder="Опишите вопрос или проблему" className="mt-2" />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Button type="submit">
              <Send className="mr-2 size-4" /> Отправить запрос
            </Button>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <MessageCircle className="size-4" />
              Среднее время ответа — 5 минут
            </div>
          </div>
        </form>

        <aside className="space-y-4">
          <Alert appearance="light" className="border-blue-200/70 bg-blue-50/70 text-blue-800">
            <AlertTitle>Приоритетная поддержка</AlertTitle>
            <AlertDescription>
              На тарифе Business Unlimited вас сопровождает персональный менеджер. Напишите на <a className="underline" href="mailto:support@tuberry.io">support@tuberry.io</a> — ответим быстрее.
            </AlertDescription>
          </Alert>
          <div className="rounded-3xl bg-white/80 p-6 shadow-[0_18px_60px_-40px_rgba(30,64,175,0.55)] ring-1 ring-white/70 space-y-3 text-sm text-muted-foreground">
            <div className="flex items-center gap-3">
              <Mail className="size-4 text-blue-500" />
              <span>support@tuberry.io</span>
            </div>
            <div className="flex items-center gap-3">
              <MessageCircle className="size-4 text-blue-500" />
              <span>@tuberry_support в Telegram</span>
            </div>
            <div className="flex items-center gap-3">
              <Send className="size-4 text-blue-500" />
              <span>Каталог обучающих материалов готовится</span>
            </div>
          </div>
        </aside>
      </section>
    </div>
  );
}
