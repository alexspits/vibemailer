import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { Server, UpdateServerInput } from '@/apiService/servers/serversApiTypes';

export const ERROR_MESSAGE = 'Не удалось изменить сервер';

export default function useUpdateServer() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<Server, [UpdateServerInput]>(
    apiService.servers.updateServer,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    server: data,
    updateServer: execute,
    onDone,
    onError,
  };
}
