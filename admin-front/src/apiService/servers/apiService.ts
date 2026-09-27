import { request } from '@/apiService/httpClient';

import addServerAdapter from './adapters/addServerAdapter';
import checkServerAdapter from './adapters/checkServerAdapter';
import deleteServerAdapter from './adapters/deleteServerAdapter';
import serversListAdapter from './adapters/serversListAdapter';
import updateServerAdapter from './adapters/updateServerAdapter';
import type {
  AddServerInput,
  CheckServerInput,
  DeleteServerInput,
  DeleteServerResponseWire,
  GetPanelClientsInput,
  ListPanelClientsResponseWire,
  ListServersResponseWire,
  Server,
  ServerCheckResponseWire,
  ServerCheckResult,
  ServerResponseWire,
  UpdateServerInput,
} from './serversApiTypes';

export const serversApiService = {
  getServers: async (): Promise<Server[]> => {
    const response = await request<ListServersResponseWire>('GET', '/servers');

    return serversListAdapter.adaptResponseData(response) ?? [];
  },

  addServer: async (input: AddServerInput): Promise<Server> => {
    const response = await request<ServerResponseWire>(
      'POST',
      '/servers',
      addServerAdapter.adaptParams(input),
    );

    const server = addServerAdapter.adaptResponseData(response);

    if (!server) {
      throw new Error('Не удалось добавить сервер');
    }

    return server;
  },

  updateServer: async (input: UpdateServerInput): Promise<Server> => {
    const response = await request<ServerResponseWire>(
      'PATCH',
      `/servers/${encodeURIComponent(input.key)}`,
      updateServerAdapter.adaptParams(input),
    );

    const server = updateServerAdapter.adaptResponseData(response);

    if (!server) {
      throw new Error('Не удалось изменить сервер');
    }

    return server;
  },

  deleteServer: async (input: DeleteServerInput): Promise<string> => {
    const response = await request<DeleteServerResponseWire>(
      'DELETE',
      `/servers/${encodeURIComponent(input.key)}${input.force ? '?force=true' : ''}`,
    );

    const detail = deleteServerAdapter.adaptResponseData(response);

    if (detail === undefined) {
      throw new Error('Не удалось удалить сервер');
    }

    return detail;
  },

  // Ходит на живую панель: ответ приходит через секунды, а по SSH и дольше.
  checkServer: async (input: CheckServerInput): Promise<ServerCheckResult> => {
    const response = await request<ServerCheckResponseWire>(
      'POST',
      `/servers/${encodeURIComponent(input.serverKey)}/check`,
    );

    const result = checkServerAdapter.adaptResponseData(response);

    if (!result) {
      throw new Error('Не удалось проверить сервер');
    }

    return result;
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
