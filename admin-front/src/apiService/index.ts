import campaignsApiService from './campaigns/apiService';
import configsApiService from './configs/apiService';
import recipientsApiService from './recipients/apiService';
import serversApiService from './servers/apiService';

export const apiService = {
  campaigns: campaignsApiService,
  configs: configsApiService,
  recipients: recipientsApiService,
  servers: serversApiService,
};

export default apiService;
