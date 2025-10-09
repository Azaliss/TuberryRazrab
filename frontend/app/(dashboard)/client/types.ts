export interface Bot {
  id: number;
  bot_username?: string;
  status: string;
  group_chat_id?: string;
  topic_mode: boolean;
}

export interface AvitoAccount {
  id: number;
  name?: string;
  api_client_id?: string;
  status: string;
  bot_id?: number;
  monitoring_enabled: boolean;
}

export interface Dialog {
  id: number;
  avito_dialog_id: string;
  telegram_topic_id?: string;
  last_message_at?: string;
  telegram_chat_id?: string;
  state?: string;
  created_at?: string;
}

export interface ClientProfile {
  filter_keywords?: string;
  require_reply_for_avito?: boolean;
  hide_system_messages?: boolean;
  auto_reply_enabled?: boolean;
  auto_reply_always?: boolean;
  auto_reply_start_time?: string;
  auto_reply_end_time?: string;
  auto_reply_timezone?: string;
  auto_reply_text?: string;
}

export interface TelegramChat {
  chat_id: string;
  title?: string;
  chat_type?: string;
  username?: string;
  is_forum?: boolean;
  is_active: boolean;
  last_status?: string;
}

export interface DialogMessage {
  id: number;
  direction: 'avito' | 'telegram';
  body: string;
  status: string;
  created_at?: string;
  attachments?: unknown;
}

export interface DialogDetail {
  dialog: Dialog;
  messages: DialogMessage[];
}
