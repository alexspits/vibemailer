import { request } from '@/apiService/httpClient';

import serversListAdapter from './adapters/serversListAdapter';
import type {
  GetPanelClientsInput,
  ListPanelClientsResponseWire,
  ListServersResponseWire,
  Server,
} from './serversApiTypes';

export const serversApiService = {
  getServers: async (): Promise<Server[]> => {
    const response = await request<ListServersResponseWire>('GET', '/servers');

    return serversListAdapter.adaptResponseData(response) ?? [];
  },

  getPanelClients: async (input: GetPanelClientsInput): Promise<string[]> => {
    const response = await request<ListPanelClientsResponseWire>(
      'GET',
      `/servers/${input.serverKey}/clients`,
    );

    return response.status === 'success' && response.result ? response.result : [];
  },
};

export default serversApiService;
