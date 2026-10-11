import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { ProvisionRun, StartProvisionInput } from '@/apiService/provision/provisionApiTypes';

export const ERROR_MESSAGE = 'Не удалось запустить прогон';

export default function useStartProvision() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<ProvisionRun, [StartProvisionInput]>(
    apiService.provision.startProvision,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    run: data,
    startProvision: execute,
    onDone,
    onError,
  };
}
