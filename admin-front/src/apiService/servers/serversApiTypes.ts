import type { components } from '@/apiService/types/vibe-mail';

/** Что сервер отдаёт получателю: файл .conf либо ссылку подписки. */
export type ArtifactKind = 'file' | 'link';

export type PanelKind = 'amnezia' | '3x-ui' | 'wg-easy' | 'fake';

/** Как ходим до панели: curl внутри SSH-сессии либо напрямую HTTP-клиентом. */
export type TransportKind = 'ssh' | 'direct';

export interface Server {
  key: string;
  title: string;
  panel: PanelKind;
  transport: TransportKind;
  artifact: ArtifactKind;
  enabled: boolean;
  /** Куда и чем ходим: `ssh de2 → http://127.0.0.1:8080` либо адрес панели. */
  where: string;
  /** Сколько строк конфигов ссылается на сервер и сколько из них ещё без артефакта. */
  configs: number;
  unfinished: number;
}

/** Доступы к панели. Наружу не отдаются — только приезжают при добавлении сервера. */
export interface ServerAuthInput {
  token?: string;
  username?: string;
  password?: string;
}

export interface ServerSshInput {
  host: string;
  user?: string;
  port?: number | null;
  keyFile?: string;
}

export interface AddServerInput {
  key: string;
  title: string;
  panel: PanelKind;
  transport: TransportKind;
  baseUrl: string;
  enabled: boolean;
  ssh?: ServerSshInput;
  auth?: ServerAuthInput;
  /** 3x-ui: в какие inbound'ы заводить клиента. */
  inboundIds?: number[];
  flow?: string;
  subBase?: string;
  /** AmneziaWG: id сервера внутри панели; пусто — единственный существующий. */
  panelServerId?: string;
  verifyTls?: boolean;
  /** Только для panel=fake: заглушка не знает, что изображает. */
  artifact?: ArtifactKind;
  /** Хвосты в именах клиентов этой панели — при автоподборе они игнорируются. */
  nameSuffixes?: string[];
}

export interface UpdateServerInput {
  key: string;
  enabled: boolean;
}

export interface DeleteServerInput {
  key: string;
  /** Удалять, даже если на сервер ссылаются конфиги в рассылках. */
  force?: boolean;
}

export interface CheckServerInput {
  serverKey: string;
}

export interface ServerCheckResult {
  key: string;
  ok: boolean;
  clients: number | null;
  sample: string[];
  /** AmneziaWG: версия протокола, которую получат новые клиенты. */
  protocol: string;
  /** 3x-ui: база ссылки подписки. */
  subscription: string;
  error: string;
  /** Подсказка к типовой ошибке настройки. */
  hint: string;
  elapsedMs: number;
}

export interface GetPanelClientsInput {
  serverKey: string;
}

export type ServerReadWire = components['schemas']['ServerRead'];
export type ServerCreateWire = components['schemas']['ServerCreate'];
type SshConfigWire = NonNullable<ServerCreateWire['ssh']>;
type PanelAuthWire = NonNullable<ServerCreateWire['auth']>;

/** Поля с умолчаниями не посылаем: их подставит модель на бэкенде, и фронт не
 *  дублирует значения вроде `~/.ssh/config` или таймаута SSH. */
export type ServerCreateRequestWire =
  Partial<Omit<ServerCreateWire, 'ssh' | 'auth'>>
  & Pick<ServerCreateWire, 'key' | 'title' | 'panel' | 'transport'>
  & {
    ssh?: Partial<SshConfigWire> & Pick<SshConfigWire, 'host'>;
    auth?: Partial<PanelAuthWire>;
  };
export type UpdateServerRequestWire = components['schemas']['UpdateServer'];
export type ListPanelClientsResponseWire = components['schemas']['ListPanelClientsEnvelope'];
export type ListServersResponseWire = components['schemas']['ListServerReadEnvelope'];
export type ServerResponseWire = components['schemas']['ServerReadEnvelope'];
export type ServerCheckResponseWire = components['schemas']['ServerCheckEnvelope'];
export type DeleteServerResponseWire = components['schemas']['ServerDeletedEnvelope'];
