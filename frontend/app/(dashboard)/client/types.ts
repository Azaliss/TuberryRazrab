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
  project_id?: number;
}

export type AutoReplyMode = 'always' | 'first';

export interface Project {
  id: number;
  client_id: number;
  name: string;
  slug?: string;
  description?: string;
  status: string;
  bot_id?: number;
  filter_keywords?: string;
  require_reply_for_sources: boolean;
  hide_system_messages: boolean;
  auto_reply_enabled: boolean;
  auto_reply_mode: AutoReplyMode;
  auto_reply_always: boolean;
  auto_reply_start_time?: string;
  auto_reply_end_time?: string;
  auto_reply_timezone?: string;
  auto_reply_text?: string;
  topic_intro_template?: string;
  created_at?: string;
  updated_at?: string;
}

export interface Dialog {
  id: number;
  source: 'avito' | 'telegram';
  telegram_source_id?: number;
  avito_dialog_id: string;
  telegram_topic_id?: string;
  last_message_at?: string;
  telegram_chat_id?: string;
  state?: string;
  created_at?: string;
  external_reference?: string;
  external_display_name?: string;
  external_username?: string;
  project_id?: number;
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
  direction: 'avito' | 'telegram' | 'telegram_source_in' | 'telegram_source_out';
  body: string;
  status: string;
  created_at?: string;
  attachments?: unknown;
}

export interface TelegramSource {
  id: number;
  bot_id: number;
  display_name?: string;
  bot_username?: string;
  status: string;
  webhook_secret?: string;
  webhook_url?: string;
  description?: string;
  project_id?: number;
}

export interface DialogDetail {
  dialog: Dialog;
  messages: DialogMessage[];
}
