import type {
  ClientSuggestion,
  RecipientSuggestion,
  SuggestClientsInput,
  SuggestClientsRequestWire,
  SuggestClientsResponseWire,
} from '../campaignsApiTypes';

const suggestClientsAdapter = {
  adaptParams: (input: SuggestClientsInput): SuggestClientsRequestWire => ({
    recipient_ids: input.recipientIds ?? null,
    hints: input.hints ?? {},
  }),

  adaptResponseData: (
    response: SuggestClientsResponseWire,
  ): RecipientSuggestion[] | undefined => {
    if (response.status !== 'success' || !response.result) {
      return undefined;
    }

    return response.result.recipients.map((recipient) => ({
      recipientId: recipient.recipient_id,
      email: recipient.email,
      clientName: recipient.client_name,
      servers: (recipient.servers ?? []).map((server) => ({
        serverKey: server.server_key,
        serverTitle: server.server_title,
        error: server.error ?? null,
        candidates: (server.candidates ?? []).map((candidate): ClientSuggestion => ({
          name: candidate.name,
          score: candidate.score,
          suggested: candidate.suggested ?? false,
          takenBy: candidate.taken_by ?? null,
          source: candidate.source === 'history' ? 'history' : 'match',
        })),
      })),
    }));
  },
};

export default suggestClientsAdapter;
