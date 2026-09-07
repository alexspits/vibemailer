import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { StopCampaignInput } from '@/apiService/campaigns/campaignsApiTypes';

export const ERROR_MESSAGE = 'Не удалось остановить рассылку';

export default function useStopCampaign() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<number, [StopCampaignInput]>(
    apiService.campaigns.stopCampaign,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    campaignId: data,
    stopCampaign: execute,
    onDone,
    onError,
  };
}
