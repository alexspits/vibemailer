import type { components } from '@/apiService/types/vibe-mail';
import type { Config, Recipient } from '@/apiService/recipients/recipientsApiTypes';

export interface BindConfigInput {
  configId: number;
  /** Имя клиента на панели, заведённого вручную. */
  externalName: string;
}

export interface UnbindConfigInput {
  configId: number;
}

export interface DeleteConfigInput {
  configId: number;
}

export type BindConfigRequestWire = components['schemas']['BindConfigIn'];
export type ConfigResponseWire = components['schemas']['ConfigReadEnvelope'];
export type RecipientResponseWire = components['schemas']['RecipientReadEnvelope'];

export type { Config, Recipient };
