import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { BindConfigInput, Config } from '@/apiService/configs/configsApiTypes';

export const ERROR_MESSAGE = 'Не удалось привязать конфиг';

export default function useBindConfig() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<Config, [BindConfigInput]>(
    apiService.configs.bindConfig,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    config: data,
    bindConfig: execute,
    onDone,
    onError,
  };
}
