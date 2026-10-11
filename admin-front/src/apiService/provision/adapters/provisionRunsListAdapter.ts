import type { ListProvisionRunsResponseWire, ProvisionRun } from '../provisionApiTypes';

import { adaptRun } from './provisionRunAdapter';

const provisionRunsListAdapter = {
  adaptParams: () => undefined,

  adaptResponseData: (
    response: ListProvisionRunsResponseWire,
  ): ProvisionRun[] | undefined =>
    response.status === 'success' && response.result
      ? response.result.map(adaptRun)
      : undefined,
};

export default provisionRunsListAdapter;
