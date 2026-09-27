import type { Server, ServerResponseWire } from '../serversApiTypes';

import { adaptServer } from './serversListAdapter';

const serversItemAdapter = {
  adaptParams: () => undefined,

  adaptResponseData: (response: ServerResponseWire): Server | undefined =>
    response.status === 'success' && response.result
      ? adaptServer(response.result)
      : undefined,
};

export default serversItemAdapter;
