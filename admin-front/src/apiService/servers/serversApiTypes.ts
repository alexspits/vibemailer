import type { components } from '@/apiService/types/vibe-mail';

/** Что сервер отдаёт получателю: файл .conf либо ссылку подписки. */
export type ArtifactKind = 'file' | 'link';

export type PanelKind = 'amnezia' | '3x-ui' | 'wg-easy' | 'fake';

export interface Server {
  key: string;
  title: string;
  panel: PanelKind;
  artifact: ArtifactKind;
  enabled: boolean;
}

export interface GetPanelClientsInput {
  serverKey: string;
}

export type ServerReadWire = components['schemas']['ServerRead'];
export type ListPanelClientsResponseWire = components['schemas']['ListPanelClientsEnvelope'];
export type ListServersResponseWire = components['schemas']['ListServerReadEnvelope'];
