import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { Campaign, CloneCampaignInput } from '@/apiService/campaigns/campaignsApiTypes';

export const ERROR_MESSAGE = 'Не удалось создать кампанию на основе прежней';

export default function useCloneCampaign() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<Campaign, [CloneCampaignInput]>(
    apiService.campaigns.cloneCampaign,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    campaign: data,
    cloneCampaign: execute,
    onDone,
    onError,
  };
}
