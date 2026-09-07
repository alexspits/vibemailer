import type {
  GenerateConfigsInput,
  GenerateConfigsRequestWire,
  GenerateConfigsResponseWire,
} from '../campaignsApiTypes';

const generateConfigsAdapter = {
  adaptParams: (input: GenerateConfigsInput): GenerateConfigsRequestWire => ({
    servers: input.servers ?? [],
  }),

  adaptResponseData: (response: GenerateConfigsResponseWire): string | undefined =>
    response.status === 'success' && response.result
      ? response.result.detail
      : undefined,
};

export default generateConfigsAdapter;
