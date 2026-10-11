import type {
  ProvisionPanel,
  ProvisionRun,
  ProvisionRunResponseWire,
  ProvisionRunWire,
} from '../provisionApiTypes';

export const adaptRun = (wire: ProvisionRunWire): ProvisionRun => ({
  id: wire.id,
  serverKey: wire.server_key,
  title: wire.title,
  host: wire.host,
  panel: wire.panel as ProvisionPanel,
  status: wire.status,
  step: wire.step,
  recap: wire.recap,
  error: wire.error ?? '',
  registered: wire.registered,
  startedAt: wire.started_at,
  finishedAt: wire.finished_at ?? null,
  offset: wire.offset,
  chunk: wire.chunk,
  panelPassword: wire.panel_password,
  tunnel: wire.tunnel,
  panelUrl: wire.panel_url,
});

const provisionRunAdapter = {
  adaptParams: () => undefined,

  adaptResponseData: (response: ProvisionRunResponseWire): ProvisionRun | undefined =>
    response.status === 'success' && response.result
      ? adaptRun(response.result)
      : undefined,
};

export default provisionRunAdapter;
