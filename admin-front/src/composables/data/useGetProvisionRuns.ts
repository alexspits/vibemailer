import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { ProvisionRun } from '@/apiService/provision/provisionApiTypes';

export const ERROR_MESSAGE = 'Не удалось получить список прогонов';

export default function useGetProvisionRuns() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<ProvisionRun[], []>(
    apiService.provision.getProvisionRuns,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    runs: data,
    getProvisionRuns: execute,
    onDone,
    onError,
  };
}
