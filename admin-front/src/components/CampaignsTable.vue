<template>
  <div
    :class="$style.campaignsTable"
    data-test="campaigns-table"
  >
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>ID</TableHead>
          <TableHead>Название</TableHead>
          <TableHead>Тема</TableHead>

          <TableHead :class="$style.statusCell">
            Статус
          </TableHead>

          <TableHead>Прогресс</TableHead>
          <TableHead>Серверы</TableHead>
          <TableHead>Создана</TableHead>
          <TableHead>Действия</TableHead>
        </TableRow>
      </TableHeader>

      <TableBody>
        <template v-if="props.isLoading">
          <TableRow
            v-for="n in 5"
            :key="n"
            data-test="campaign-skeleton-row"
          >
            <TableCell><Skeleton :class="$style.skId" /></TableCell>
            <TableCell><Skeleton :class="$style.skName" /></TableCell>
            <TableCell><Skeleton :class="$style.skSubject" /></TableCell>
            <TableCell><Skeleton :class="$style.skStatus" /></TableCell>
            <TableCell><Skeleton :class="$style.skProgress" /></TableCell>
            <TableCell><Skeleton :class="$style.skServers" /></TableCell>
            <TableCell><Skeleton :class="$style.skDate" /></TableCell>
            <TableCell><Skeleton :class="$style.skAction" /></TableCell>
          </TableRow>
        </template>

        <template v-else>
          <TableEmpty
            v-if="props.campaigns.length === 0"
            :colspan="8"
          >
            Кампании не найдены
          </TableEmpty>

          <TableRow
            v-for="campaign in props.campaigns"
            v-else
            :key="campaign.id"
            data-test="campaign-row"
          >
            <TableCell>{{ campaign.id }}</TableCell>

            <TableCell :class="$style.cellName">
              <RouterLink
                :to="{ name: 'campaign-details', params: { id: campaign.id } }"
                :class="$style.link"
                data-test="campaign-link"
              >
                {{ campaign.name }}
              </RouterLink>
            </TableCell>

            <TableCell>{{ campaign.subject }}</TableCell>

            <TableCell>
              <Badge :class="statusClass(campaign.status)">
                {{ statusLabel(campaign.status) }}
              </Badge>
            </TableCell>

            <TableCell>
              <span v-if="campaign.totals">
                {{ processedCount(campaign.totals) }} / {{ campaign.totals.total }}
              </span>

              <span v-else>—</span>
            </TableCell>

            <TableCell>
              <span
                :title="serversTitle(campaign)"
                data-test="campaign-servers"
              >
                {{ serversLabel(campaign) }}
              </span>
            </TableCell>

            <TableCell>{{ formatDate(campaign.createdAt) }}</TableCell>

            <TableCell>
              <Button
                :aria-label="`Удалить кампанию ${campaign.name}`"
                variant="ghost"
                size="icon"
                data-test="delete-button"
                @click="openDialog(campaign)"
              >
                <Trash :class="$style.iconBtn" />
              </Button>
            </TableCell>
          </TableRow>
        </template>
      </TableBody>
    </Table>

    <AlertDialog v-model:open="isDialogOpen">
      <AlertDialogContent data-test="delete-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle>Удалить кампанию?</AlertDialogTitle>

          <AlertDialogDescription>
            Кампания «{{ pendingCampaign?.name }}» будет удалена вместе со всеми
            получателями и конфигами. Действие необратимо.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <AlertDialogFooter>
          <Button
            :disabled="isDeleting"
            variant="outline"
            data-test="cancel-delete-button"
            @click="closeDialog"
          >
            Отмена
          </Button>

          <Button
            :disabled="isDeleting"
            variant="destructive"
            data-test="confirm-delete-button"
            @click="confirmDelete"
          >
            <LoaderCircle
              v-if="isDeleting"
              :class="$style.spinner"
            />

            {{ isDeleting ? 'Удаление…' : 'Удалить' }}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, useCssModule } from 'vue';

import { LoaderCircle, Trash } from '@lucide/vue';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableEmpty,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type {
  Campaign,
  CampaignStatus,
  CampaignTotals,
} from '@/apiService/campaigns/campaignsApiTypes';
import type { Server } from '@/apiService/servers/serversApiTypes';
import useDeleteCampaign from '@/composables/data/useDeleteCampaign';
import useToast from '@/composables/useToast';

interface Props {
  campaigns?: Campaign[];
  /** Все настроенные серверы: из них считается «сколько из скольких» у рассылки. */
  servers?: Server[];
  isLoading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  campaigns: () => [],
  servers: () => [],
  isLoading: false,
});

const emit = defineEmits<{ deleted: [] }>();

const styles = useCssModule();

const toast = useToast();
const { isLoading: isDeleting, deleteCampaign, onDone } = useDeleteCampaign();

const pendingCampaign = ref<Campaign | null>(null);
const isDialogOpen = ref(false);

function openDialog(campaign: Campaign) {
  pendingCampaign.value = campaign;
  isDialogOpen.value = true;
}

function closeDialog() {
  isDialogOpen.value = false;
}

function confirmDelete() {
  if (!pendingCampaign.value) {
    return;
  }

  deleteCampaign({ id: pendingCampaign.value.id });
}

onDone(() => {
  toast.success('Кампания удалена');

  isDialogOpen.value = false;

  emit('deleted');
});

const STATUS_LABEL: Record<CampaignStatus, string> = {
  new: 'Новая',
  in_progress: 'В работе',
  done: 'Завершена',
  done_with_errors: 'Завершена с ошибками',
  error: 'Ошибка',
};

const STATUS_CLASS: Record<CampaignStatus, string> = {
  new: styles.statusNew,
  in_progress: styles.statusInProgress,
  done: styles.statusDone,
  done_with_errors: styles.statusDoneWithErrors,
  error: styles.statusError,
};

function statusLabel(status: CampaignStatus): string {
  return STATUS_LABEL[status];
}

function statusClass(status: CampaignStatus): string {
  return STATUS_CLASS[status];
}

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

const enabledServers = computed(() => props.servers.filter((server) => server.enabled));

// Набор рассылки без выключенных — ровно то же правило, по которому бэкенд заводит
// конфиги. У кампаний, созданных до появления выбора, набор не задан: это все включённые.
function campaignServers(campaign: Campaign): Server[] {
  const chosen = campaign.servers;

  return enabledServers.value.filter((server) => !chosen || chosen.includes(server.key));
}

function serversLabel(campaign: Campaign): string {
  if (!props.servers.length) {
    return '—';
  }

  return `${campaignServers(campaign).length} / ${enabledServers.value.length}`;
}

function serversTitle(campaign: Campaign): string {
  if (!props.servers.length) {
    return '';
  }

  const chosen = campaignServers(campaign);
  const names = chosen.map((server) => server.title).join(', ') || 'ни одного';

  return campaign.servers
    ? `Рассылка идёт на: ${names}`
    : `Набор не задан — идёт на все включённые: ${names}`;
}

// Обработано = все получатели, чей статус отличен от «ожидает» (sent + failed).
// Так прогресс честно отражает, что рассылка прошла по всем, даже если все с ошибкой.
function processedCount(totals: CampaignTotals): number {
  return totals.total - totals.pending;
}
</script>

<style module>
.statusCell {
  width: 172px;
}

.campaignsTable {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.cellName {
  font-weight: 500;
}

.link {
  text-decoration: none;
}

.link:hover {
  text-decoration: underline;
}

.iconBtn {
  width: 1rem;
  height: 1rem;
}

.spinner {
  width: 1rem;
  height: 1rem;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.skId {
  height: 1rem;
  width: 2rem;
}

.skName {
  height: 1rem;
  width: 10rem;
}

.skSubject {
  height: 1rem;
  width: 12rem;
}

.skStatus {
  height: 1.25rem;
  width: 5rem;
  border-radius: 9999px;
}

.skProgress {
  height: 1rem;
  width: 4rem;
}

.skServers {
  width: 3rem;
  height: 1rem;
}

.skDate {
  height: 1rem;
  width: 6rem;
}

.skAction {
  height: 2rem;
  width: 2rem;
  border-radius: var(--radius-md);
}

.statusNew {
  background-color: #dbeafe;
  color: #1d4ed8;
}

.statusInProgress {
  background-color: #fef9c3;
  color: #854d0e;
}

.statusDone {
  background-color: #dcfce7;
  color: #15803d;
}

.statusDoneWithErrors,
.statusError {
  background-color: #fee2e2;
  color: #b91c1c;
}

:global(.dark) .statusNew {
  background-color: rgba(30, 58, 138, 0.4);
  color: #93c5fd;
}

:global(.dark) .statusInProgress {
  background-color: rgba(113, 63, 18, 0.4);
  color: #fde047;
}

:global(.dark) .statusDone {
  background-color: rgba(20, 83, 45, 0.4);
  color: #86efac;
}

:global(.dark) .statusDoneWithErrors,
:global(.dark) .statusError {
  background-color: rgba(127, 29, 29, 0.4);
  color: #fca5a5;
}
</style>
