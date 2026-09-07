import { request } from '@/apiService/httpClient';

import createCampaignAdapter from './adapters/createCampaignAdapter';
import deleteCampaignAdapter from './adapters/deleteCampaignAdapter';
import generateConfigsAdapter from './adapters/generateConfigsAdapter';
import startCampaignAdapter from './adapters/startCampaignAdapter';
import retryFailedAdapter from './adapters/retryFailedAdapter';
import stopCampaignAdapter from './adapters/stopCampaignAdapter';
import campaignsItemAdapter from './adapters/campaignsItemAdapter';
import campaignsListAdapter from './adapters/campaignsListAdapter';
import type {
  Campaign,
  CreateCampaignInput,
  CreateCampaignResponseWire,
  DeleteCampaignInput,
  DeleteCampaignResponseWire,
  GenerateConfigsInput,
  GenerateConfigsResponseWire,
  GetCampaignInput,
  GetCampaignResponseWire,
  ListCampaignsResponseWire,
  StartCampaignInput,
  StartCampaignResponseWire,
  RetryFailedInput,
  RetryFailedResponseWire,
  StopCampaignInput,
  StopCampaignResponseWire,
} from './campaignsApiTypes';

export const campaignsApiService = {
  getCampaigns: async (): Promise<Campaign[]> => {
    const response = await request<ListCampaignsResponseWire>('GET', '/campaigns');

    return campaignsListAdapter.adaptResponseData(response) ?? [];
  },

  getCampaign: async (input: GetCampaignInput): Promise<Campaign | undefined> => {
    const response = await request<GetCampaignResponseWire>('GET', `/campaigns/${input.id}`);

    return campaignsItemAdapter.adaptResponseData(response);
  },

  createCampaign: async (input: CreateCampaignInput): Promise<Campaign> => {
    const response = await request<CreateCampaignResponseWire>(
      'POST',
      '/campaigns',
      createCampaignAdapter.adaptParams(input),
    );

    const campaign = createCampaignAdapter.adaptResponseData(response);

    if (!campaign) {
      throw new Error('Не удалось создать кампанию');
    }

    return campaign;
  },

  deleteCampaign: async (input: DeleteCampaignInput): Promise<number> => {
    const response = await request<DeleteCampaignResponseWire>(
      'DELETE',
      `/campaigns/${input.id}`,
    );

    const campaignId = deleteCampaignAdapter.adaptResponseData(response);

    if (campaignId === undefined) {
      throw new Error('Не удалось удалить кампанию');
    }

    return campaignId;
  },

  startCampaign: async (input: StartCampaignInput): Promise<number> => {
    const response = await request<StartCampaignResponseWire>(
      'POST',
      `/campaigns/${input.id}/start`,
    );

    const campaignId = startCampaignAdapter.adaptResponseData(response);

    if (campaignId === undefined) {
      throw new Error('Не удалось запустить рассылку');
    }

    return campaignId;
  },

  retryFailed: async (input: RetryFailedInput): Promise<number> => {
    const response = await request<RetryFailedResponseWire>(
      'POST',
      `/campaigns/${input.id}/retry-failed`,
    );

    const campaignId = retryFailedAdapter.adaptResponseData(response);

    if (campaignId === undefined) {
      throw new Error('Не удалось вернуть письма в очередь');
    }

    return campaignId;
  },

  stopCampaign: async (input: StopCampaignInput): Promise<number> => {
    const response = await request<StopCampaignResponseWire>(
      'POST',
      `/campaigns/${input.id}/stop`,
    );

    const campaignId = stopCampaignAdapter.adaptResponseData(response);

    if (campaignId === undefined) {
      throw new Error('Не удалось остановить рассылку');
    }

    return campaignId;
  },

  generateConfigs: async (input: GenerateConfigsInput): Promise<string> => {
    const response = await request<GenerateConfigsResponseWire>(
      'POST',
      `/campaigns/${input.id}/configs/generate`,
      generateConfigsAdapter.adaptParams(input),
    );

    const detail = generateConfigsAdapter.adaptResponseData(response);

    if (detail === undefined) {
      throw new Error('Не удалось запустить генерацию конфигов');
    }

    return detail;
  },
};

export default campaignsApiService;
