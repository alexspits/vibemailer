import type {
  ListServersResponseWire,
  Server,
  ServerReadWire,
} from '../serversApiTypes';

const adaptServer = (server: ServerReadWire): Server => ({
  key: server.key,
  title: server.title,
  panel: server.panel,
  artifact: server.artifact,
  enabled: server.enabled,
});

const serversListAdapter = {
  adaptParams: () => undefined,

  adaptResponseData: (response: ListServersResponseWire): Server[] | undefined =>
    response.status === 'success' && response.result
      ? response.result.map(adaptServer)
      : undefined,
};

export default serversListAdapter;
