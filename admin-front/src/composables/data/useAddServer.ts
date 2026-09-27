import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { AddServerInput, Server } from '@/apiService/servers/serversApiTypes';

export const ERROR_MESSAGE = 'Не удалось добавить сервер';

export default function useAddServer() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<Server, [AddServerInput]>(
    apiService.servers.addServer,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    server: data,
    addServer: execute,
    onDone,
    onError,
  };
}
