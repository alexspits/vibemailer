import type {
  ListRecipientsResponseWire,
  Recipient,
  RecipientReadWire,
} from '../recipientsApiTypes';

export const adaptRecipient = (recipient: RecipientReadWire): Recipient => ({
  id: recipient.id,
  campaignId: recipient.campaign_id,
  email: recipient.email,
  name: recipient.name ?? null,
  clientName: recipient.client_name,
  configCount: recipient.config_count,
  status: recipient.status,
  error: recipient.error ?? null,
  sentAt: recipient.sent_at ?? null,
  configs: (recipient.configs ?? []).map((config) => ({
    id: config.id,
    name: config.name,
    panelName: config.panel_name,
    seq: config.seq,
    externalName: config.external_name ?? null,
    isExternal: config.is_external ?? false,
    serverKey: config.server_key,
    kind: config.kind,
    status: config.status,
    filename: config.filename ?? null,
    link: config.link ?? null,
    size: config.size ?? 0,
    error: config.error ?? null,
  })),
});

const listAdapter = {
  adaptParams: () => undefined,

  adaptResponseData: (response: ListRecipientsResponseWire): Recipient[] | undefined =>
    response.status === 'success' && response.result
      ? response.result.map(adaptRecipient)
      : undefined,
};

export default listAdapter;
