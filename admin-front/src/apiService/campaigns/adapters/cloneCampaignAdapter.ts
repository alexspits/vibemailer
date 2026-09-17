import type {
  Campaign,
  CloneCampaignInput,
  CloneCampaignRequestWire,
  GetCampaignResponseWire,
} from '../campaignsApiTypes';
import campaignsItemAdapter from './campaignsItemAdapter';

const cloneCampaignAdapter = {
  adaptParams: (input: CloneCampaignInput): CloneCampaignRequestWire => ({
    name: input.name,
    subject: input.subject ?? null,
    body: input.body ?? null,
  }),

  adaptResponseData: (response: GetCampaignResponseWire): Campaign | undefined =>
    campaignsItemAdapter.adaptResponseData(response),
};

export default cloneCampaignAdapter;
