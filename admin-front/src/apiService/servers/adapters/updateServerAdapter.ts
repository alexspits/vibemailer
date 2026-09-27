import type {
  Server,
  ServerResponseWire,
  UpdateServerInput,
  UpdateServerRequestWire,
} from '../serversApiTypes';
import serversItemAdapter from './serversItemAdapter';

const updateServerAdapter = {
  adaptParams: (input: UpdateServerInput): UpdateServerRequestWire => ({
    enabled: input.enabled,
  }),

  adaptResponseData: (response: ServerResponseWire): Server | undefined =>
    serversItemAdapter.adaptResponseData(response),
};

export default updateServerAdapter;
