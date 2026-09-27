import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type { CheckServerInput, ServerCheckResult } from '@/apiService/servers/serversApiTypes';

export const ERROR_MESSAGE = 'Не удалось проверить сервер';

export default function useCheckServer() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<ServerCheckResult, [CheckServerInput]>(
    apiService.servers.checkServer,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    result: data,
    checkServer: execute,
    onDone,
    onError,
  };
}
