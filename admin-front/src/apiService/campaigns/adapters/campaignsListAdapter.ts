import type {
  CampaignReadWire,
  CampaignStatus,
  CampaignTotals,
  Campaign,
  ListCampaignsResponseWire,
} from '../campaignsApiTypes';

const adaptTotals = (totals: CampaignReadWire['totals']): CampaignTotals | null => {
  if (!totals) {
    return null;
  }

  return {
    sent: Number(totals.sent ?? 0),
    failed: Number(totals.failed ?? 0),
    pending: Number(totals.pending ?? 0),
    total: Number(totals.total ?? 0),
  };
};

export const adaptCampaign = (campaign: CampaignReadWire): Campaign => ({
  id: campaign.id,
  name: campaign.name,
  subject: campaign.subject,
  body: campaign.body,
  status: campaign.status as CampaignStatus,
  servers: campaign.servers ?? null,
  createdAt: campaign.created_at,
  totals: adaptTotals(campaign.totals),
});

const listAdapter = {
  adaptParams: () => undefined,

  adaptResponseData: (response: ListCampaignsResponseWire): Campaign[] | undefined =>
    response.status === 'success' && response.result
      ? response.result.map(adaptCampaign)
      : undefined,
};

export default listAdapter;
