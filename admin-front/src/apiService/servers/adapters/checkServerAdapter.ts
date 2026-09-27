import type {
  CheckServerInput,
  ServerCheckResponseWire,
  ServerCheckResult,
} from '../serversApiTypes';

const checkServerAdapter = {
  adaptParams: (_input: CheckServerInput) => undefined,

  adaptResponseData: (response: ServerCheckResponseWire): ServerCheckResult | undefined => {
    if (response.status !== 'success' || !response.result) {
      return undefined;
    }

    const result = response.result;

    return {
      key: result.key,
      ok: result.ok,
      clients: result.clients ?? null,
      sample: result.sample,
      protocol: result.protocol,
      subscription: result.subscription,
      error: result.error,
      hint: result.hint,
      elapsedMs: result.elapsed_ms,
    };
  },
};

export default checkServerAdapter;
