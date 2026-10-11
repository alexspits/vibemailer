import type { components } from '@/apiService/types/vibe-mail';

/** Панель, которую ставит плейбук. Значения — те же, что в его `vpn_panels`. */
export type ProvisionPanel = '3x-ui' | 'amneziawg';

export type ProvisionStatus = 'running' | 'done' | 'failed' | 'cancelled';

/** Значения для формы: прочитаны из `group_vars/all.yml` самих сценариев. */
export interface ProvisionDefaults {
  /** Можно ли вообще поднимать серверы: есть ли сценарии и сам ansible. */
  available: boolean;
  /** Почему нельзя — подсказка у выключенной кнопки. */
  reason: string;
  adminUser: string;
  sshPort: number;
  bootstrapUser: string;
  /** Порты панелей на самом сервере: панель слушает localhost, ходим через SSH. */
  xuiPort: number;
  awgPort: number;
  awgVpnPorts: number[];
}

export interface StartProvisionInput {
  /** Ключ и название, под которыми сервер допишется в servers.yml по успеху. */
  key: string;
  title: string;
  host: string;
  panel: ProvisionPanel;
  /** Кем и на каком порту сервер будет жить после настройки. */
  adminUser: string;
  sshPort: number;
  /** Первый вход на свежий сервер: у хостеров это root или ubuntu на 22. */
  bootstrapUser: string;
  /** Пусто — вход по ключу, который хостер уже положил на сервер. */
  bootstrapPassword?: string;
  /** Пароль рабочего пользователя для VNC-консоли хостера. */
  adminPassword?: string;
  /** Пароль панели. Пусто — сгенерирует бэкенд. */
  panelPassword?: string;
  /** Порт панели. 0 или пусто — из group_vars сценариев. */
  panelPort?: number;
  /** 3x-ui: порты inbound'ов для UFW («443/tcp»). */
  openPorts?: string[];
  /** AmneziaWG: UDP-порты VPN-серверов панели. */
  vpnPorts?: number[];
}

export interface ProvisionRun {
  id: number;
  serverKey: string;
  title: string;
  host: string;
  panel: string;
  status: ProvisionStatus;
  /** Текущий шаг плейбука: последний `TASK [...]`. */
  step: string;
  /** Итог одной строкой: `PLAY RECAP` по нашему хосту. */
  recap: string;
  error: string;
  /** Дописан ли сервер в servers.yml: прогон мог пройти, а запись упасть. */
  registered: boolean;
  startedAt: string;
  finishedAt: string | null;
  /** Докуда прочитан лог — это смещение уедет в следующий запрос. */
  offset: number;
  chunk: string;
  /** Приходит, пока прогон жив в памяти процесса: показать пароль один раз. */
  panelPassword: string;
  tunnel: string;
  panelUrl: string;
}

export interface GetProvisionRunInput {
  id: number;
  /** Сколько байт лога уже получено: придёт только то, что после. */
  offset?: number;
}

export interface CancelProvisionInput {
  id: number;
}

export type ProvisionDefaultsWire = components['schemas']['ProvisionDefaults'];
export type ProvisionRunWire = components['schemas']['ProvisionRunRead'];
type ProvisionInWire = components['schemas']['ProvisionIn'];

/** Поля с умолчаниями не посылаем: их подставит модель на бэкенде. */
export type ProvisionRequestWire =
  Partial<ProvisionInWire>
  & Pick<ProvisionInWire, 'key' | 'title' | 'host' | 'panel' | 'admin_user' | 'ssh_port'>;

export type ProvisionDefaultsResponseWire = components['schemas']['ProvisionDefaultsEnvelope'];
export type ProvisionRunResponseWire = components['schemas']['ProvisionRunEnvelope'];
export type ListProvisionRunsResponseWire = components['schemas']['ListProvisionRunEnvelope'];
