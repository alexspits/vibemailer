import type {
  BindNewConfigsInput,
  ConfigsBindWire,
  Recipient,
  RecipientResponseWire,
} from '../recipientsApiTypes';
import { adaptRecipient } from './recipientsListAdapter';

const bindNewConfigsAdapter = {
  adaptParams: (input: BindNewConfigsInput): ConfigsBindWire => ({
    server_key: input.serverKey,
    names: input.names,
  }),

  adaptResponseData: (response: RecipientResponseWire): Recipient | undefined =>
    response.status === 'success' && response.result
      ? adaptRecipient(response.result)
      : undefined,
};

export default bindNewConfigsAdapter;
