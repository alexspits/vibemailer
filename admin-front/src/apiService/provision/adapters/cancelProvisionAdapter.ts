import type {
  CancelProvisionInput,
  ProvisionRun,
  ProvisionRunResponseWire,
} from '../provisionApiTypes';

import provisionRunAdapter from './provisionRunAdapter';

const cancelProvisionAdapter = {
  adaptParams: (_input: CancelProvisionInput) => undefined,

  adaptResponseData: (response: ProvisionRunResponseWire): ProvisionRun | undefined =>
    provisionRunAdapter.adaptResponseData(response),
};

export default cancelProvisionAdapter;
