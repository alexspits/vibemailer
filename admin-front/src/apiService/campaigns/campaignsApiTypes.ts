import type { components } from '@/apiService/types/vibe-mail';

export type CampaignStatusWire = components['schemas']['CampaignStatus'];
export type CampaignReadWire = components['schemas']['CampaignRead'];
export type ListCampaignsResponseWire = components['schemas']['ListCampaignReadEnvelope'];
export type GetCampaignResponseWire = components['schemas']['CampaignReadEnvelope'];

export type CreateCampaignWire = components['schemas']['CreateCampaign'];
export type CreateCampaignResponseWire = components['schemas']['CampaignReadEnvelope'];

export type CampaignStatus = 'new' | 'in_progress' | 'done' | 'done_with_errors' | 'error';

export interface CreateCampaignInput {
  name: string;
  subject: string;
  body: string;
}

export interface CampaignTotals {
  sent: number;
  failed: number;
  pending: number;
  total: number;
}

export interface Campaign {
  id: number;
  name: string;
  subject: string;
  body: string;
  status: CampaignStatus;
  createdAt: string;
  totals: CampaignTotals | null;
}

export interface GetCampaignInput {
  id: number;
}

export interface DeleteCampaignInput {
  id: number;
}

export type DeleteCampaignResponseWire = components['schemas']['MessageOutEnvelope'];

export interface StartCampaignInput {
  id: number;
}

export type StartCampaignResponseWire = components['schemas']['MessageOutEnvelope'];

export interface StopCampaignInput {
  id: number;
}

export type StopCampaignResponseWire = components['schemas']['MessageOutEnvelope'];

export interface RetryFailedInput {
  id: number;
}

export type RetryFailedResponseWire = components['schemas']['MessageOutEnvelope'];

export interface SuggestClientsInput {
  id: number;
  /** Пусто — подбираем всей кампании: панели опрашиваются один раз на запрос. */
  recipientIds?: number[];
  /** id получателя строкой → подсказка для поиска. */
  hints?: Record<string, string>;
}

export interface ClientSuggestion {
  name: string;
  score: number;
  suggested: boolean;
  takenBy: string | null;
}

export interface ServerSuggestion {
  serverKey: string;
  serverTitle: string;
  candidates: ClientSuggestion[];
  error: string | null;
}

export interface RecipientSuggestion {
  recipientId: number;
  email: string;
  clientName: string;
  servers: ServerSuggestion[];
}

export type SuggestClientsRequestWire = components['schemas']['SuggestClientsIn'];
export type SuggestClientsResponseWire = components['schemas']['SuggestResultEnvelope'];

export interface BindSuggestionItem {
  recipientId: number;
  serverKey: string;
  names: string[];
}

export interface BindSuggestionsInput {
  id: number;
  items: BindSuggestionItem[];
}

export interface BindSuggestionsSummary {
  bound: number;
  recipients: number;
}

export type BindSuggestionsRequestWire = components['schemas']['BindSuggestionsIn'];
export type BindSuggestionsResponseWire = components['schemas']['BindSuggestionsEnvelope'];

export interface GenerateConfigsInput {
  id: number;
  /** Ключи серверов; пусто — все включённые («Сгенерировать все»). */
  servers?: string[];
}

export type GenerateConfigsRequestWire = components['schemas']['GenerateConfigsIn'];

export type GenerateConfigsResponseWire = components['schemas']['MessageOutEnvelope'];
