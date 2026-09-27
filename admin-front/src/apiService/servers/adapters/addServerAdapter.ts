import type {
  AddServerInput,
  Server,
  ServerCreateRequestWire,
  ServerResponseWire,
} from '../serversApiTypes';
import serversItemAdapter from './serversItemAdapter';

/** Пустой список не отправляем: у модели на бэкенде для него своё умолчание. */
const listOrNothing = <T,>(values?: T[]): T[] | undefined => (values?.length ? values : undefined);

const addServerAdapter = {
  // Пустые поля не отправляем вовсе: бэкенд подставит умолчания модели, а фронт не
  // дублирует их значения.
  adaptParams: (input: AddServerInput): ServerCreateRequestWire => ({
    key: input.key,
    title: input.title,
    panel: input.panel,
    transport: input.transport,
    enabled: input.enabled,
    base_url: input.baseUrl,
    ssh: input.ssh
      ? {
        host: input.ssh.host,
        user: input.ssh.user || undefined,
        port: input.ssh.port ?? undefined,
        key_file: input.ssh.keyFile || undefined,
      }
      : undefined,
    auth: input.auth
      ? {
        token: input.auth.token || undefined,
        username: input.auth.username || undefined,
        password: input.auth.password || undefined,
      }
      : undefined,
    inbound_ids: listOrNothing(input.inboundIds),
    flow: input.flow || undefined,
    sub_base: input.subBase || undefined,
    panel_server_id: input.panelServerId || undefined,
    verify_tls: input.verifyTls,
    artifact: input.artifact,
    name_suffixes: listOrNothing(input.nameSuffixes),
  }),

  adaptResponseData: (response: ServerResponseWire): Server | undefined =>
    serversItemAdapter.adaptResponseData(response),
};

export default addServerAdapter;
