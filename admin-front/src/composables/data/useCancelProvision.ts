import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { CancelProvisionInput, ProvisionRun } from '@/apiService/provision/provisionApiTypes';

export const ERROR_MESSAGE = 'Не удалось прервать прогон';

export default function useCancelProvision() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<ProvisionRun, [CancelProvisionInput]>(
    apiService.provision.cancelProvision,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    run: data,
    cancelProvision: execute,
    onDone,
    onError,
  };
}
