import { request } from '@/apiService/httpClient';

import bindConfigAdapter from './adapters/bindConfigAdapter';
import { adaptRecipient } from '@/apiService/recipients/adapters/recipientsListAdapter';
import type {
  BindConfigInput,
  Config,
  ConfigResponseWire,
  DeleteConfigInput,
  Recipient,
  RecipientResponseWire,
  UnbindConfigInput,
} from './configsApiTypes';

export const configsApiService = {
  bindConfig: async (input: BindConfigInput): Promise<Config> => {
    const response = await request<ConfigResponseWire>(
      'POST',
      `/configs/${input.configId}/bind`,
      bindConfigAdapter.adaptParams(input),
    );

    const config = bindConfigAdapter.adaptResponseData(response);

    if (!config) {
      throw new Error('Не удалось привязать конфиг');
    }

    return config;
  },

  // Отвязка отвечает получателем, а не конфигом: лишней строки после неё может уже
  // не быть, и обновлять нужно весь список.
  unbindConfig: async (input: UnbindConfigInput): Promise<Recipient> => {
    const response = await request<RecipientResponseWire>(
      'POST',
      `/configs/${input.configId}/unbind`,
    );

    if (response.status !== 'success' || !response.result) {
      throw new Error('Не удалось снять привязку');
    }

    return adaptRecipient(response.result);
  },

  deleteConfig: async (input: DeleteConfigInput): Promise<Recipient> => {
    const response = await request<RecipientResponseWire>(
      'DELETE',
      `/configs/${input.configId}`,
    );

    if (response.status !== 'success' || !response.result) {
      throw new Error('Не удалось удалить конфиг');
    }

    return adaptRecipient(response.result);
  },
};

export default configsApiService;
