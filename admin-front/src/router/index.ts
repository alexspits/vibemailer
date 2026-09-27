import { createRouter, createWebHistory } from 'vue-router'
import CampaignsPage from '@/pages/CampaignsPage.vue'
import CreateCampaignPage from '@/pages/CreateCampaignPage.vue'
import CampaignDetailsPage from '@/pages/CampaignDetailsPage.vue'
import ServersPage from '@/pages/ServersPage.vue'
import TestPage from '@/pages/TestPage.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/campaigns',
    },

    {
      path: '/campaigns',
      name: 'campaigns',
      component: CampaignsPage
    },

    {
      path: '/create-campaign',
      name: 'create-campaign',
      component: CreateCampaignPage
    },

    {
      path: '/campaigns/:id',
      name: 'campaign-details',
      component: CampaignDetailsPage
    },

    {
      path: '/servers',
      name: 'servers',
      component: ServersPage
    },

    {
      path: '/test',
      name: 'test',
      component: TestPage
    },

    {
      path: '/:pathMatch(.*)*',
      redirect: '/campaigns',
    },
  ],
})
