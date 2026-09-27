import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { DeleteServerInput } from '@/apiService/servers/serversApiTypes';

export const ERROR_MESSAGE = 'Не удалось удалить сервер';

export default function useDeleteServer() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<string, [DeleteServerInput]>(
    apiService.servers.deleteServer,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    detail: data,
    deleteServer: execute,
    onDone,
    onError,
  };
}
