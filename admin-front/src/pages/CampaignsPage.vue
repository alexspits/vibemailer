<template>
  <section
    :class="$style.campaignsPage"
    data-test="campaigns-page"
  >
    <div :class="$style.headerRow">
      <h1 :class="$style.title">
        Кампании
      </h1>

      <RouterLink to="/create-campaign">
        <Button
          data-test="create-campaign-button"
          variant="outline"
        >
          Создать кампанию
        </Button>
      </RouterLink>
    </div>

    <p :class="$style.subtitle">
      Список кампаний и управление рассылками.
    </p>

    <CampaignsTable
      :campaigns="campaigns ?? []"
      :is-loading="isInitialLoading"
      @deleted="load"
    />
  </section>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';

import { Button } from '@/components/ui/button';
import CampaignsTable from '@/components/CampaignsTable.vue';
import useGetCampaigns from '@/composables/data/useGetCampaigns';
import type { Campaign } from '@/apiService/campaigns/campaignsApiTypes';

const { campaigns, getCampaigns: load, onDone, onError } = useGetCampaigns();

// Скелетоны показываем только при первой загрузке; фоновые опросы обновляют
// таблицу «тихо», не мигая скелетонами на каждом тике.
const isInitialLoading = ref(true);

const POLL_INTERVAL = 3000;
let pollTimer: number | undefined;
let pollInFlight = false;

function hasInProgress(list: Campaign[]): boolean {
  return list.some((campaign) => campaign.status === 'in_progress');
}

function stopPolling() {
  if (pollTimer !== undefined) {
    clearInterval(pollTimer);
    pollTimer = undefined;
  }
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(pollOnce, POLL_INTERVAL);
}

function pollOnce() {
  if (pollInFlight) {
    return;
  }

  pollInFlight = true;
  load();
}

// Опрашиваем только пока есть хотя бы одна кампания в рассылке (in_progress);
// для `new`/завершённых/пустого списка опрос не нужен.
function syncPolling() {
  const shouldPoll = campaigns.value !== null && hasInProgress(campaigns.value);

  if (shouldPoll && pollTimer === undefined) {
    startPolling();
  } else if (!shouldPoll) {
    stopPolling();
  }
}

onDone(() => {
  isInitialLoading.value = false;
  pollInFlight = false;
  syncPolling();
});

onError(() => {
  isInitialLoading.value = false;
  pollInFlight = false;
  // Иначе опрос продолжает бить каждые три секунды и сыпать тостами: условие запуска
  // считается по данным, которых после ошибки уже нет.
  syncPolling();
});

onMounted(load);

onUnmounted(stopPolling);
</script>

<style module>
.campaignsPage {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.headerRow {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title {
  font-size: 1.5rem;
  line-height: 2rem;
  font-weight: 600;
  color: var(--foreground);
}

.subtitle {
  color: var(--muted-foreground);
}
</style>
