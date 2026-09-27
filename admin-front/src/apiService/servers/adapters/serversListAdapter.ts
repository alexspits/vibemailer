import type {
  ListServersResponseWire,
  Server,
  ServerReadWire,
} from '../serversApiTypes';

export const adaptServer = (server: ServerReadWire): Server => ({
  key: server.key,
  title: server.title,
  panel: server.panel,
  transport: server.transport,
  artifact: server.artifact,
  enabled: server.enabled,
  where: server.where,
  configs: server.configs,
  unfinished: server.unfinished,
});

const serversListAdapter = {
  adaptParams: () => undefined,

  adaptResponseData: (response: ListServersResponseWire): Server[] | undefined =>
    response.status === 'success' && response.result
      ? response.result.map(adaptServer)
      : undefined,
};

export default serversListAdapter;
