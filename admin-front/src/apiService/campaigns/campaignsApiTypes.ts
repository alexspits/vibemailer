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

export interface GenerateConfigsInput {
  id: number;
  /** Ключи серверов; пусто — все включённые («Сгенерировать все»). */
  servers?: string[];
}

export type GenerateConfigsRequestWire = components['schemas']['GenerateConfigsIn'];

export type GenerateConfigsResponseWire = components['schemas']['MessageOutEnvelope'];
