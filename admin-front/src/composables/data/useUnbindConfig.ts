import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { Recipient, UnbindConfigInput } from '@/apiService/configs/configsApiTypes';

export const ERROR_MESSAGE = 'Не удалось снять привязку';

export default function useUnbindConfig() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<Recipient, [UnbindConfigInput]>(
    apiService.configs.unbindConfig,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    recipient: data,
    unbindConfig: execute,
    onDone,
    onError,
  };
}
