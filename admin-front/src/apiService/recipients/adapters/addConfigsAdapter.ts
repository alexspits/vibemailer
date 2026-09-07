import type {
  AddConfigsInput,
  ConfigsAddWire,
  Recipient,
  RecipientResponseWire,
} from '../recipientsApiTypes';
import { adaptRecipient } from './recipientsListAdapter';

const addConfigsAdapter = {
  adaptParams: (input: AddConfigsInput): ConfigsAddWire => ({
    servers: input.serverKeys,
    count: input.count,
  }),

  adaptResponseData: (response: RecipientResponseWire): Recipient | undefined =>
    response.status === 'success' && response.result
      ? adaptRecipient(response.result)
      : undefined,
};

export default addConfigsAdapter;
