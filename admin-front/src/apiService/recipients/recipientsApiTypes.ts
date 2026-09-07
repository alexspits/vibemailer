import type { components } from '@/apiService/types/vibe-mail';
import type { ArtifactKind } from '@/apiService/servers/serversApiTypes';

export type RecipientStatus = 'pending' | 'sent' | 'failed';

export type ConfigStatus = 'pending' | 'queued' | 'generating' | 'ready' | 'failed';

/** Конфиг получателя на одном сервере: либо файл, либо ссылка подписки. */
export interface Config {
  id: number;
  /** Имя для получателя: в имени вложения и рядом со ссылкой. */
  name: string;
  /** Имя клиента на самой панели; расходится с name у привязанных вручную. */
  panelName: string;
  /** Порядковый номер конфига у получателя, с единицы. */
  seq: number;
  /** Имя клиента на панели, если конфиг привязан к заведённому вручную. */
  externalName: string | null;
  isExternal: boolean;
  serverKey: string;
  kind: ArtifactKind;
  status: ConfigStatus;
  filename: string | null;
  link: string | null;
  size: number;
  error: string | null;
}

export interface Recipient {
  id: number;
  campaignId: number;
  email: string;
  name: string | null;
  clientName: string;
  /** Сколько конфигов заказано получателю. */
  configCount: number;
  status: RecipientStatus;
  error: string | null;
  sentAt: string | null;
  configs: Config[];
}

export interface ImportRowProblem {
  line: number;
  raw: string;
  reason: string;
}

export interface ImportGroup {
  email: string;
  clientName: string;
  /** Имя, которое останется у уже заведённого получателя. */
  existingClientName: string | null;
  isExisting: boolean;
  /** Сколько конфигов будет после импорта и сколько было. */
  count: number;
  existingCount: number;
  /** Сколько строк конфигов реально заведётся, по всем серверам. */
  newConfigs: number;
  /** Ключи серверов, которых коснётся импорт. */
  servers: string[];
  /** Имена конфигов, которые появятся: alice-1, alice-2, … */
  newNames: string[];
  /** Ключ сервера → имя клиента на панели, к которому привяжется первый конфиг. */
  bindings: Record<string, string>;
}

export interface ImportPreview {
  groups: ImportGroup[];
  problems: ImportRowProblem[];
  totalRows: number;
  totalRecipients: number;
  totalConfigs: number;
}

export interface ImportResult {
  createdRecipients: number;
  updatedRecipients: number;
  createdConfigs: number;
  problems: ImportRowProblem[];
}

export interface GetRecipientsInput {
  campaignId: number;
}

export interface PreviewRecipientsImportInput {
  campaignId: number;
  text: string;
}

export interface ImportRecipientsInput {
  campaignId: number;
  text: string;
}

export interface AddConfigsInput {
  recipientId: number;
  /** Ключи серверов; пусто — все включённые. */
  serverKeys?: string[];
  count: number;
}

export interface BindNewConfigsInput {
  recipientId: number;
  serverKey: string;
  /** Имена клиентов на панели: под каждое заводится отдельный конфиг. */
  names: string[];
}

export type RecipientReadWire = components['schemas']['RecipientRead'];
export type RecipientResponseWire = components['schemas']['RecipientReadEnvelope'];
export type ConfigsAddWire = components['schemas']['ConfigsAdd'];
export type ConfigsBindWire = components['schemas']['ConfigsBind'];
export type ListRecipientsResponseWire = components['schemas']['ListRecipientReadEnvelope'];
export type RecipientsImportTextWire = components['schemas']['RecipientsImportText'];
export type ImportPreviewResponseWire = components['schemas']['ImportPreviewEnvelope'];
export type ImportResultResponseWire = components['schemas']['ImportResultEnvelope'];
