import type { ProvisionDefaults, ProvisionDefaultsResponseWire } from '../provisionApiTypes';

const provisionDefaultsAdapter = {
  adaptParams: () => undefined,

  adaptResponseData: (
    response: ProvisionDefaultsResponseWire,
  ): ProvisionDefaults | undefined => {
    if (response.status !== 'success' || !response.result) {
      return undefined;
    }

    const result = response.result;

    return {
      available: result.available,
      reason: result.reason,
      adminUser: result.admin_user,
      sshPort: result.ssh_port,
      bootstrapUser: result.bootstrap_user,
      xuiPort: result.xui_port,
      awgPort: result.awg_port,
      awgVpnPorts: result.awg_vpn_ports ?? [],
    };
  },
};

export default provisionDefaultsAdapter;
