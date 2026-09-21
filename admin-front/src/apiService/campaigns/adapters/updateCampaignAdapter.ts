import type {
  Campaign,
  GetCampaignResponseWire,
  UpdateCampaignInput,
  UpdateCampaignRequestWire,
} from '../campaignsApiTypes';
import campaignsItemAdapter from './campaignsItemAdapter';

const updateCampaignAdapter = {
  adaptParams: (input: UpdateCampaignInput): UpdateCampaignRequestWire => ({
    name: input.name,
    subject: input.subject,
    body: input.body,
  }),

  adaptResponseData: (response: GetCampaignResponseWire): Campaign | undefined =>
    campaignsItemAdapter.adaptResponseData(response),
};

export default updateCampaignAdapter;
