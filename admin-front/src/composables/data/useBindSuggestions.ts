import { apiService } from '@/apiService';
import useApiService from '@/composables/useApiService';
import type {
  BindSuggestionsInput,
  BindSuggestionsSummary,
} from '@/apiService/campaigns/campaignsApiTypes';

export const ERROR_MESSAGE = 'Не удалось привязать отмеченных клиентов';

export default function useBindSuggestions() {
  const {
    isLoading,
    data,
    execute,
    onDone,
    onError,
  } = useApiService<BindSuggestionsSummary, [BindSuggestionsInput]>(
    apiService.campaigns.bindSuggestions,
    { errorMessage: ERROR_MESSAGE },
  );

  return {
    isLoading,
    summary: data,
    bindSuggestions: execute,
    onDone,
    onError,
  };
}
