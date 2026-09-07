import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { BindNewConfigsInput, Recipient } from '@/apiService/recipients/recipientsApiTypes';

export const ERROR_MESSAGE = 'Не удалось привязать клиентов';

export default function useBindNewConfigs() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<Recipient, [BindNewConfigsInput]>(
    apiService.recipients.bindNewConfigs,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    recipient: data,
    bindNewConfigs: execute,
    onDone,
    onError,
  };
}
