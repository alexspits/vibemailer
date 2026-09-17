import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type {
  RecipientSuggestion,
  SuggestClientsInput,
} from '@/apiService/campaigns/campaignsApiTypes';

export const ERROR_MESSAGE = 'Не удалось подобрать клиентов на панелях';

export default function useSuggestClients() {
  const {
    isLoading,
    data,
    hasError,
    execute,
    onDone,
    onError,
  } = useApiService<RecipientSuggestion[], [SuggestClientsInput]>(
    apiService.campaigns.suggestClients,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    hasError,
    suggestions: data,
    suggestClients: execute,
    onDone,
    onError,
  };
}
