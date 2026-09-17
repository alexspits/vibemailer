import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { GetPanelClientsInput } from '@/apiService/servers/serversApiTypes';

export const ERROR_MESSAGE = 'Не удалось получить список клиентов с панели';

export default function useGetPanelClients() {
  const {
    isLoading,
    data,
    hasError,
    execute,
    onDone,
    onError,
  } = useApiService<string[], [GetPanelClientsInput]>(
    apiService.servers.getPanelClients,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    hasError,
    panelClients: data,
    getPanelClients: execute,
    onDone,
    onError,
  };
}
