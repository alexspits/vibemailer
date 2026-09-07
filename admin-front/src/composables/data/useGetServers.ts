import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';

export const ERROR_MESSAGE = 'Не удалось загрузить список серверов';

export default function useGetServers() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<Awaited<ReturnType<typeof apiService.servers.getServers>>, []>(
    apiService.servers.getServers,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    servers: data,
    getServers: execute,
    onDone,
    onError,
  };
}
