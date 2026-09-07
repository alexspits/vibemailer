import type { Config } from '@/apiService/recipients/recipientsApiTypes';

import type {
  BindConfigInput,
  BindConfigRequestWire,
  ConfigResponseWire,
} from '../configsApiTypes';

const bindConfigAdapter = {
  adaptParams: (input: BindConfigInput): BindConfigRequestWire => ({
    external_name: input.externalName,
  }),

  adaptResponseData: (response: ConfigResponseWire): Config | undefined => {
    if (response.status !== 'success' || !response.result) {
      return undefined;
    }

    const { result } = response;

    return {
      id: result.id,
      name: result.name,
      panelName: result.panel_name,
      seq: result.seq,
      externalName: result.external_name ?? null,
      isExternal: result.is_external ?? false,
      serverKey: result.server_key,
      kind: result.kind,
      status: result.status,
      filename: result.filename ?? null,
      link: result.link ?? null,
      size: result.size ?? 0,
      error: result.error ?? null,
    };
  },
};

export default bindConfigAdapter;
