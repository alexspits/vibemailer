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
      `/servers/${encodeURIComponent(input.serverKey)}/clients`,
    );

    if (response.status !== 'success' || !response.result) {
      // Не пустой список: «на панели никого нет» и «не смогли прочитать» — разные
      // вещи, и на втором человек заводит клиентов заново.
      throw new Error('Не удалось прочитать список клиентов с панели');
    }

    return response.result;
  },
};

export default serversApiService;
