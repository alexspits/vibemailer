import { request } from '@/apiService/httpClient';

import addConfigsAdapter from './adapters/addConfigsAdapter';
import bindNewConfigsAdapter from './adapters/bindNewConfigsAdapter';
import importRecipientsAdapter from './adapters/importRecipientsAdapter';
import previewRecipientsImportAdapter from './adapters/previewRecipientsImportAdapter';
import recipientsListAdapter from './adapters/recipientsListAdapter';
import type {
  AddConfigsInput,
  BindNewConfigsInput,
  BindSuggestedInput,
  GetRecipientsInput,
  ImportPreview,
  ImportPreviewResponseWire,
  ImportRecipientsInput,
  ImportResult,
  ImportResultResponseWire,
  ListRecipientsResponseWire,
  PreviewRecipientsImportInput,
  Recipient,
  RecipientResponseWire,
} from './recipientsApiTypes';

export const recipientsApiService = {
  getRecipients: async (input: GetRecipientsInput): Promise<Recipient[]> => {
    const response = await request<ListRecipientsResponseWire>(
      'GET',
      `/campaigns/${input.campaignId}/recipients`,
    );

    return recipientsListAdapter.adaptResponseData(response) ?? [];
  },

  previewRecipientsImport: async (
    input: PreviewRecipientsImportInput,
  ): Promise<ImportPreview> => {
    const response = await request<ImportPreviewResponseWire>(
      'POST',
      `/campaigns/${input.campaignId}/recipients/preview`,
      previewRecipientsImportAdapter.adaptParams(input),
    );

    const preview = previewRecipientsImportAdapter.adaptResponseData(response);

    if (!preview) {
      throw new Error('Не удалось разобрать список');
    }

    return preview;
  },

  importRecipients: async (input: ImportRecipientsInput): Promise<ImportResult> => {
    const response = await request<ImportResultResponseWire>(
      'POST',
      `/campaigns/${input.campaignId}/recipients/import`,
      importRecipientsAdapter.adaptParams(input),
    );

    const result = importRecipientsAdapter.adaptResponseData(response);

    if (!result) {
      throw new Error('Не удалось добавить получателей');
    }

    return result;
  },

  addConfigs: async (input: AddConfigsInput): Promise<Recipient> => {
    const response = await request<RecipientResponseWire>(
      'POST',
      `/recipients/${input.recipientId}/configs`,
      addConfigsAdapter.adaptParams(input),
    );

    const recipient = addConfigsAdapter.adaptResponseData(response);

    if (!recipient) {
      throw new Error('Не удалось добавить конфиги');
    }

    return recipient;
  },

  /**
   * Привязка подобранного сразу по нескольким серверам.
   *
   * Серверы обходятся по очереди, а не параллельно: каждый запрос читает список
   * клиентов своей панели, и пачка одновременных заходов по SSH ничего не ускорит.
   * Упавший сервер не отменяет уже привязанное — о нём сообщаем отдельно.
   */
  bindSuggested: async (input: BindSuggestedInput): Promise<Recipient> => {
    const entries = Object.entries(input.selections).filter(([, names]) => names.length);

    if (!entries.length) {
      throw new Error('Не выбрано ни одного клиента');
    }

    let recipient: Recipient | null = null;

    for (const [serverKey, names] of entries) {
      recipient = await recipientsApiService.bindNewConfigs({
        recipientId: input.recipientId,
        serverKey,
        names,
      });
    }

    return recipient as Recipient;
  },

  bindNewConfigs: async (input: BindNewConfigsInput): Promise<Recipient> => {
    const response = await request<RecipientResponseWire>(
      'POST',
      `/recipients/${input.recipientId}/configs/bind`,
      bindNewConfigsAdapter.adaptParams(input),
    );

    const recipient = bindNewConfigsAdapter.adaptResponseData(response);

    if (!recipient) {
      throw new Error('Не удалось привязать клиентов');
    }

    return recipient;
  },
};

export default recipientsApiService;
