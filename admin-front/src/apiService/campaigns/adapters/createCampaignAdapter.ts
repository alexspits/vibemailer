import campaignsItemAdapter from './campaignsItemAdapter';
import type {
  Campaign,
  CreateCampaignInput,
  CreateCampaignWire,
  CreateCampaignResponseWire,
} from '../campaignsApiTypes';

const createCampaignAdapter = {
  adaptParams: (input: CreateCampaignInput): CreateCampaignWire => ({
    name: input.name,
    subject: input.subject,
    body: input.body,
    servers: input.servers,
  }),

  adaptResponseData: (response: CreateCampaignResponseWire): Campaign | undefined =>
    campaignsItemAdapter.adaptResponseData(response),
};

export default createCampaignAdapter;
