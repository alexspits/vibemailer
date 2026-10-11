import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { GetProvisionRunInput, ProvisionRun } from '@/apiService/provision/provisionApiTypes';

export const ERROR_MESSAGE = 'Не удалось прочитать состояние прогона';

export default function useGetProvisionRun() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<ProvisionRun, [GetProvisionRunInput]>(
    apiService.provision.getProvisionRun,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    run: data,
    getProvisionRun: execute,
    onDone,
    onError,
  };
}
