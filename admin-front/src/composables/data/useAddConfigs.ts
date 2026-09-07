import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { AddConfigsInput, Recipient } from '@/apiService/recipients/recipientsApiTypes';

export const ERROR_MESSAGE = 'Не удалось добавить конфиги';

export default function useAddConfigs() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<Recipient, [AddConfigsInput]>(
    apiService.recipients.addConfigs,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    recipient: data,
    addConfigs: execute,
    onDone,
    onError,
  };
}
