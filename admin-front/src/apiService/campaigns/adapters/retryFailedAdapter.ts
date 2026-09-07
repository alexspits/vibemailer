import type {
  RetryFailedInput,
  RetryFailedResponseWire,
} from '../campaignsApiTypes';

const retryFailedAdapter = {
  adaptParams: (_input: RetryFailedInput) => undefined,

  adaptResponseData: (response: RetryFailedResponseWire): number | undefined =>
    response.status === 'success' && response.result
      ? response.result.campaign_id
      : undefined,
};

export default retryFailedAdapter;
