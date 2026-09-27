import type { DeleteServerInput, DeleteServerResponseWire } from '../serversApiTypes';

const deleteServerAdapter = {
  adaptParams: (_input: DeleteServerInput) => undefined,

  adaptResponseData: (response: DeleteServerResponseWire): string | undefined =>
    response.status === 'success' && response.result
      ? response.result.detail
      : undefined,
};

export default deleteServerAdapter;
