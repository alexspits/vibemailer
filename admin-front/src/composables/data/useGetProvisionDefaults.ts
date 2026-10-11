import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { ProvisionDefaults } from '@/apiService/provision/provisionApiTypes';

export const ERROR_MESSAGE = 'Не удалось узнать, можно ли поднимать серверы';

export default function useGetProvisionDefaults() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<ProvisionDefaults, []>(
    apiService.provision.getProvisionDefaults,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    defaults: data,
    getProvisionDefaults: execute,
    onDone,
    onError,
  };
}
