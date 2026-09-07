import type {
  StopCampaignInput,
  StopCampaignResponseWire,
} from '../campaignsApiTypes';

const stopCampaignAdapter = {
  adaptParams: (_input: StopCampaignInput) => undefined,

  adaptResponseData: (response: StopCampaignResponseWire): number | undefined =>
    response.status === 'success' && response.result
      ? response.result.campaign_id
      : undefined,
};

export default stopCampaignAdapter;
