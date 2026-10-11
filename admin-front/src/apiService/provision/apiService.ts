import { request } from '@/apiService/httpClient';

import cancelProvisionAdapter from './adapters/cancelProvisionAdapter';
import provisionDefaultsAdapter from './adapters/provisionDefaultsAdapter';
import provisionRunAdapter from './adapters/provisionRunAdapter';
import provisionRunsListAdapter from './adapters/provisionRunsListAdapter';
import startProvisionAdapter from './adapters/startProvisionAdapter';
import type {
  CancelProvisionInput,
  GetProvisionRunInput,
  ListProvisionRunsResponseWire,
  ProvisionDefaults,
  ProvisionDefaultsResponseWire,
  ProvisionRun,
  ProvisionRunResponseWire,
  StartProvisionInput,
} from './provisionApiTypes';

export const provisionApiService = {
  getProvisionDefaults: async (): Promise<ProvisionDefaults> => {
    const response = await request<ProvisionDefaultsResponseWire>('GET', '/provision/defaults');

    const defaults = provisionDefaultsAdapter.adaptResponseData(response);

    if (!defaults) {
      throw new Error('Не удалось узнать, можно ли поднимать серверы');
    }

    return defaults;
  },

  getProvisionRuns: async (): Promise<ProvisionRun[]> => {
    const response = await request<ListProvisionRunsResponseWire>('GET', '/provision');

    return provisionRunsListAdapter.adaptResponseData(response) ?? [];
  },

  // Отдаёт 202 и строку прогона: плейбук идёт минутами, за состоянием страница ходит
  // отдельными запросами.
  startProvision: async (input: StartProvisionInput): Promise<ProvisionRun> => {
    const response = await request<ProvisionRunResponseWire>(
      'POST',
      '/provision',
      startProvisionAdapter.adaptParams(input),
    );

    const run = startProvisionAdapter.adaptResponseData(response);

    if (!run) {
      throw new Error('Не удалось запустить прогон');
    }

    return run;
  },

  getProvisionRun: async (input: GetProvisionRunInput): Promise<ProvisionRun> => {
    const response = await request<ProvisionRunResponseWire>(
      'GET',
      `/provision/${input.id}?offset=${input.offset ?? 0}`,
    );

    const run = provisionRunAdapter.adaptResponseData(response);

    if (!run) {
      throw new Error('Не удалось прочитать состояние прогона');
    }

    return run;
  },

  cancelProvision: async (input: CancelProvisionInput): Promise<ProvisionRun> => {
    const response = await request<ProvisionRunResponseWire>(
      'POST',
      `/provision/${input.id}/cancel`,
    );

    const run = cancelProvisionAdapter.adaptResponseData(response);

    if (!run) {
      throw new Error('Не удалось прервать прогон');
    }

    return run;
  },
};

export default provisionApiService;
