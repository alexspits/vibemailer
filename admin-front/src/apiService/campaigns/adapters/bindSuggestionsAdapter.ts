import type {
  BindSuggestionsInput,
  BindSuggestionsRequestWire,
  BindSuggestionsResponseWire,
  BindSuggestionsSummary,
} from '../campaignsApiTypes';

const bindSuggestionsAdapter = {
  adaptParams: (input: BindSuggestionsInput): BindSuggestionsRequestWire => ({
    items: input.items.map((item) => ({
      recipient_id: item.recipientId,
      server_key: item.serverKey,
      names: item.names,
    })),
  }),

  adaptResponseData: (
    response: BindSuggestionsResponseWire,
  ): BindSuggestionsSummary | undefined => (
    response.status === 'success' && response.result
      ? { bound: response.result.bound, recipients: response.result.recipients }
      : undefined
  ),
};

export default bindSuggestionsAdapter;
