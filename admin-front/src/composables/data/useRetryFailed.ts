import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { RetryFailedInput } from '@/apiService/campaigns/campaignsApiTypes';

export const ERROR_MESSAGE = 'Не удалось вернуть письма в очередь';

export default function useRetryFailed() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<number, [RetryFailedInput]>(
    apiService.campaigns.retryFailed,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    campaignId: data,
    retryFailed: execute,
    onDone,
    onError,
  };
}
