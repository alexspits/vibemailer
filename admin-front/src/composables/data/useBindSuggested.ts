import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { BindSuggestedInput, Recipient } from '@/apiService/recipients/recipientsApiTypes';

export const ERROR_MESSAGE = 'Не удалось привязать выбранных клиентов';

export default function useBindSuggested() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<Recipient, [BindSuggestedInput]>(
    apiService.recipients.bindSuggested,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    recipient: data,
    bindSuggested: execute,
    onDone,
    onError,
  };
}
