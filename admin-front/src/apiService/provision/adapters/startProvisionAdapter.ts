import type {
  ProvisionRequestWire,
  ProvisionRun,
  ProvisionRunResponseWire,
  StartProvisionInput,
} from '../provisionApiTypes';

import provisionRunAdapter from './provisionRunAdapter';

/** Пустой список не отправляем: у модели на бэкенде для него своё умолчание. */
const listOrNothing = <T,>(values?: T[]): T[] | undefined => (values?.length ? values : undefined);

const startProvisionAdapter = {
  // Пустые поля не отправляем вовсе: бэкенд подставит умолчания модели — пароль панели
  // сгенерирует сам, порт возьмёт из group_vars сценариев.
  adaptParams: (input: StartProvisionInput): ProvisionRequestWire => ({
    key: input.key,
    title: input.title,
    host: input.host,
    panel: input.panel,
    admin_user: input.adminUser,
    ssh_port: input.sshPort,
    bootstrap_user: input.bootstrapUser,
    bootstrap_password: input.bootstrapPassword || undefined,
    admin_password: input.adminPassword || undefined,
    panel_password: input.panelPassword || undefined,
    panel_port: input.panelPort || undefined,
    open_ports: listOrNothing(input.openPorts),
    vpn_ports: listOrNothing(input.vpnPorts),
  }),

  adaptResponseData: (response: ProvisionRunResponseWire): ProvisionRun | undefined =>
    provisionRunAdapter.adaptResponseData(response),
};

export default startProvisionAdapter;
