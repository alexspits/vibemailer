import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { Campaign, UpdateCampaignInput } from '@/apiService/campaigns/campaignsApiTypes';

export const ERROR_MESSAGE = 'Не удалось сохранить письмо';

export default function useUpdateCampaign() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<Campaign, [UpdateCampaignInput]>(
    apiService.campaigns.updateCampaign,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    campaign: data,
    updateCampaign: execute,
    onDone,
    onError,
  };
}
