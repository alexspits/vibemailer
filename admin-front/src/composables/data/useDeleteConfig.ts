import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { DeleteConfigInput, Recipient } from '@/apiService/configs/configsApiTypes';

export const ERROR_MESSAGE = 'Не удалось удалить конфиг';

export default function useDeleteConfig() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<Recipient, [DeleteConfigInput]>(
    apiService.configs.deleteConfig,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    recipient: data,
    deleteConfig: execute,
    onDone,
    onError,
  };
}
