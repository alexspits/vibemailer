<template>
  <section
    :class="$style.campaignDetailsPage"
    data-test="campaign-details-page"
  >
    <div :class="$style.headerRow">
      <div :class="$style.titleGroup">
        <Button
          variant="outline"
          size="icon"
          data-test="back-button"
          @click="goBack"
        >
          <ArrowLeft :class="$style.iconBtn" />
        </Button>

        <div
          v-if="campaign"
          :class="$style.titleGroup"
        >
          <h1 :class="$style.title">
            {{ campaign.name }}
          </h1>

          <Badge :class="statusClass(currentStatus)">
            {{ statusLabel(currentStatus) }}
          </Badge>
        </div>

        <Skeleton
          v-else-if="isLoadingCampaign"
          :class="$style.skTitle"
        />
      </div>

      <div :class="$style.actions">
        <Button
          :disabled="isAddRecipientsDisabled"
          variant="outline"
          data-test="add-recipients-button"
          @click="openAddRecipients"
        >
          Добавить получателей
        </Button>

        <Button
          v-for="server in serversList"
          :key="server.key"
          :disabled="isServerGenerateDisabled(server.key)"
          variant="outline"
          data-test="generate-server-button"
          @click="onGenerateConfigs([server.key])"
        >
          <LoaderCircle
            v-if="isServerGenerating(server.key)"
            :class="$style.spinner"
          />

          {{ serverGenerateLabel(server) }}
        </Button>

        <Button
          :disabled="isGenerateDisabled"
          variant="outline"
          data-test="generate-configs-button"
          @click="onGenerateConfigs()"
        >
          <LoaderCircle
            v-if="isGeneratingConfigs"
            :class="$style.spinner"
          />

          {{ generateLabel }}
        </Button>

        <Button
          v-if="failedCount > 0 && !isRunning"
          :disabled="isRetrying"
          :title="'Вернуть в очередь письма, которые не ушли, и не трогать отправленные'"
          variant="outline"
          data-test="retry-failed-button"
          @click="onRetryFailed"
        >
          <LoaderCircle
            v-if="isRetrying"
            :class="$style.spinner"
          />

          Повторить неотправленные ({{ failedCount }})
        </Button>

        <Button
          v-if="isRunning"
          :disabled="isStopping"
          variant="outline"
          data-test="stop-button"
          @click="onStop"
        >
          <LoaderCircle
            v-if="isStopping"
            :class="$style.spinner"
          />

          {{ stopLabel }}
        </Button>

        <Button
          v-else
          :disabled="isButtonDisabled"
          :title="isWaitingConfigs ? 'Сначала сгенерируйте конфиги' : undefined"
          data-test="start-button"
          @click="onStart"
        >
          <LoaderCircle
            v-if="isButtonLoading"
            :class="$style.spinner"
          />

          {{ buttonLabel }}
        </Button>
      </div>
    </div>

    <div
      v-if="campaign"
      :class="$style.infoCard"
      data-test="campaign-info"
    >
      <div>
        <p :class="$style.label">
          Тема
        </p>

        <p :class="$style.value">
          {{ campaign.subject }}
        </p>
      </div>

      <div>
        <p :class="$style.label">
          Создана
        </p>

        <p :class="$style.value">
          {{ formatDate(campaign.createdAt) }}
        </p>
      </div>

      <div :class="$style.fullWidth">
        <p :class="$style.label">
          Текст письма
        </p>

        <p :class="$style.body">
          {{ campaign.body }}
        </p>
      </div>

      <div :class="$style.fullWidth">
        <p :class="$style.label">
          Прогресс
        </p>

        <p :class="$style.value">
          Отправлено: {{ progressTotals.sent }} /
          Всего: {{ progressTotals.total }} /
          Ошибки: {{ progressTotals.failed }} /
          Ожидают: {{ progressTotals.pending }}
        </p>
      </div>

      <div :class="$style.fullWidth">
        <p :class="$style.label">
          Конфиги
        </p>

        <p
          :class="$style.value"
          data-test="configs-progress"
        >
          Готовы: {{ configTotals.ready }} из {{ configTotals.total }}
          <template v-if="configTotals.failed">
            / Ошибки: {{ configTotals.failed }}
          </template>
        </p>

        <p
          v-for="server in serversList"
          :key="server.key"
          :class="$style.serverProgress"
          data-test="server-progress"
        >
          {{ server.title }}: {{ serverTotals(server.key).ready }}
          из {{ serverTotals(server.key).total }}
          <template v-if="serverTotals(server.key).failed">
            / ошибки: {{ serverTotals(server.key).failed }}
          </template>
        </p>
      </div>
    </div>

    <div
      :class="$style.logCard"
      data-test="recipients-log"
    >
      <div :class="$style.logHeader">
        <h2 :class="$style.logTitle">
          Лог отправленных писем
        </h2>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Email</TableHead>
            <TableHead>Имя</TableHead>

            <TableHead :class="$style.colStatus">
              Статус
            </TableHead>

            <TableHead :class="$style.colError">
              Ошибка
            </TableHead>

            <TableHead>Отправлено</TableHead>
            <TableHead>Конфиги</TableHead>
          </TableRow>
        </TableHeader>

        <TableBody>
          <template v-if="isInitRecipientsLoading">
            <TableRow
              v-for="n in 3"
              :key="n"
              data-test="recipient-skeleton-row"
            >
              <TableCell><Skeleton :class="$style.skEmail" /></TableCell>
              <TableCell><Skeleton :class="$style.skName" /></TableCell>
              <TableCell><Skeleton :class="$style.skStatus" /></TableCell>
              <TableCell><Skeleton :class="$style.skError" /></TableCell>
              <TableCell><Skeleton :class="$style.skSent" /></TableCell>
              <TableCell><Skeleton :class="$style.skConfigs" /></TableCell>
            </TableRow>
          </template>

          <template v-else>
            <TableEmpty
              v-if="recipientsList.length === 0"
              :colspan="6"
            >
              Получателей пока нет — добавьте их, вставив список из таблицы
            </TableEmpty>

            <TableRow
              v-for="recipient in recipientsList"
              v-else
              :key="recipient.id"
              data-test="recipient-row"
            >
              <TableCell>{{ recipient.email }}</TableCell>
              <TableCell>{{ recipient.name ?? '—' }}</TableCell>

              <TableCell>
                <Badge :class="recipientStatusClass(recipient.status)">
                  {{ recipientStatusLabel(recipient.status) }}
                </Badge>
              </TableCell>

              <TableCell :class="$style.cellError">
                <TooltipProvider v-if="recipient.error">
                  <Tooltip>
                    <TooltipTrigger as-child>
                      <span :class="$style.errorText">
                        {{ recipient.error }}
                      </span>
                    </TooltipTrigger>

                    <TooltipContent>
                      <p :class="$style.tooltipText">
                        {{ recipient.error }}
                      </p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>

                <span
                  v-else
                  :class="$style.errorEmpty"
                >—</span>
              </TableCell>

              <TableCell>
                {{ recipient.sentAt ? formatDate(recipient.sentAt) : '—' }}
              </TableCell>

              <TableCell>
                <div
                  v-for="config in recipient.configs"
                  :key="config.id"
                  :class="$style.configRow"
                  data-test="recipient-config"
                >
                  <span :class="$style.configName">
                    {{ config.name }} · {{ serverTitle(config.serverKey) }}

                    <span
                      v-if="config.isExternal"
                      :class="$style.panelName"
                      data-test="config-panel-name"
                    >на панели: {{ config.panelName }}</span>
                  </span>

                  <TooltipProvider v-if="config.error">
                    <Tooltip>
                      <TooltipTrigger as-child>
                        <Badge :class="configStatusClass(config.status)">
                          {{ configStatusLabel(config.status) }}
                        </Badge>
                      </TooltipTrigger>

                      <TooltipContent>
                        <p :class="$style.tooltipText">
                          {{ config.error }}
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>

                  <Badge
                    v-else
                    :class="configStatusClass(config.status)"
                  >
                    {{ configStatusLabel(config.status) }}
                  </Badge>

                  <!--
                    Имя файла задаёт сервер через Content-Disposition: в нём есть ключ
                    сервера, а у привязанного вручную конфига `filename` — это имя с
                    панели (`adonm.conf`), которое наружу показывать незачем.
                  -->
                  <a
                    v-if="config.status === 'ready' && config.kind === 'file'"
                    :href="configDownloadUrl(config.id)"
                    :class="$style.downloadLink"
                    :title="`Скачать (${formatSize(config.size)})`"
                    data-test="config-download-link"
                  >
                    <Download :class="$style.iconBtn" />
                  </a>

                  <button
                    v-else-if="config.status === 'ready' && config.link"
                    :class="$style.copyButton"
                    :title="config.link"
                    type="button"
                    data-test="config-copy-link"
                    @click="copyLink(config.link)"
                  >
                    <Copy :class="$style.iconBtn" />
                  </button>

                  <button
                    :class="$style.copyButton"
                    :title="config.isExternal
                      ? `Привязан клиент ${config.externalName}`
                      : 'Привязать клиентов с панели'"
                    type="button"
                    data-test="config-bind-button"
                    @click="openBind(recipient, config)"
                  >
                    <Link2 :class="[$style.iconBtn, config.isExternal ? $style.iconActive : '']" />
                  </button>

                  <button
                    :class="$style.copyButton"
                    :disabled="isDeletingConfig"
                    title="Удалить эту строку конфига. Клиент на панели останется."
                    type="button"
                    data-test="config-delete-button"
                    @click="onDeleteConfig(config)"
                  >
                    <Trash2 :class="$style.iconBtn" />
                  </button>
                </div>

                <span v-if="recipient.configs.length === 0">—</span>

                <button
                  :class="$style.addConfigButton"
                  title="Добавить получателю ещё конфиги"
                  type="button"
                  data-test="recipient-add-configs"
                  @click="openAddConfigs(recipient)"
                >
                  <Plus :class="$style.iconBtn" />

                  Добавить конфиг
                </button>
              </TableCell>
            </TableRow>
          </template>
        </TableBody>
      </Table>
    </div>

    <AddRecipientsDialog
      v-model:open="isAddRecipientsOpen"
      :campaign-id="campaignId"
      @added="load"
    />

    <BindConfigDialog
      v-model:open="isBindOpen"
      :config="bindTarget"
      :recipient="bindRecipient"
      :recipients="recipientsList"
      :server-title="bindTarget ? serverTitle(bindTarget.serverKey) : ''"
      @bound="load"
    />

    <AddConfigsDialog
      v-model:open="isAddConfigsOpen"
      :recipient="addConfigsTarget"
      @added="load"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, useCssModule } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { ArrowLeft, Copy, Download, Link2, LoaderCircle, Plus, Trash2 } from '@lucide/vue';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableEmpty,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import AddRecipientsDialog from '@/components/AddRecipientsDialog.vue';
import AddConfigsDialog from '@/components/AddConfigsDialog.vue';
import BindConfigDialog from '@/components/BindConfigDialog.vue';
import { API_BASE_URL } from '@/apiService/httpClient';
import useDeleteConfig from '@/composables/data/useDeleteConfig';
import useGenerateConfigs from '@/composables/data/useGenerateConfigs';
import useGetCampaign from '@/composables/data/useGetCampaign';
import useGetRecipients from '@/composables/data/useGetRecipients';
import useGetServers from '@/composables/data/useGetServers';
import useRetryFailed from '@/composables/data/useRetryFailed';
import useStartCampaign from '@/composables/data/useStartCampaign';
import useStopCampaign from '@/composables/data/useStopCampaign';
import useToast from '@/composables/useToast';
import type { CampaignStatus } from '@/apiService/campaigns/campaignsApiTypes';
import type { Server } from '@/apiService/servers/serversApiTypes';
import type {
  Config,
  ConfigStatus,
  Recipient,
  RecipientStatus,
} from '@/apiService/recipients/recipientsApiTypes';

const styles = useCssModule();

const route = useRoute();
const router = useRouter();
const toast = useToast();

const campaignId = computed(() => Number(route.params.id));

const {
  isLoading: isLoadingCampaign,
  campaign,
  getCampaign,
} = useGetCampaign();

const {
  recipients,
  getRecipients,
  onDone: onRecipientsDone,
  onError: onRecipientsError,
} = useGetRecipients();

const isInitRecipientsLoading = ref(true);
onRecipientsDone(() => {
  isInitRecipientsLoading.value = false;
});
onRecipientsError(() => {
  isInitRecipientsLoading.value = false;
});

const {
  startCampaign,
  onDone,
} = useStartCampaign();

const {
  isLoading: isStopping,
  stopCampaign,
  onDone: onStopDone,
} = useStopCampaign();

const {
  isLoading: isRetrying,
  retryFailed,
  onDone: onRetryDone,
} = useRetryFailed();

const recipientsList = computed(() => recipients.value ?? []);

const progressTotals = computed(() => {
  const list = recipientsList.value;

  return {
    sent: list.filter((recipient) => recipient.status === 'sent').length,
    failed: list.filter((recipient) => recipient.status === 'failed').length,
    pending: list.filter((recipient) => recipient.status === 'pending').length,
    total: list.length,
  };
});

const configs = computed(() => recipientsList.value.flatMap((recipient) => recipient.configs));

const configTotals = computed(() => {
  const list = configs.value;

  return {
    ready: list.filter((config) => config.status === 'ready').length,
    failed: list.filter((config) => config.status === 'failed').length,
    total: list.length,
  };
});

const isGeneratingConfigs = computed(
  () => configs.value.some((config) => config.status === 'queued' || config.status === 'generating'),
);

const {
  servers,
  getServers,
} = useGetServers();

// Выключенные серверы не показываем: конфиги на них не заводятся, и кнопка была бы
// заведомо неактивной.
const serversList = computed(() => (servers.value ?? []).filter((server) => server.enabled));

const serverTitles = computed(
  () => new Map(serversList.value.map((server) => [server.key, server.title])),
);

function serverTitle(serverKey: string): string {
  // Сервер мог исчезнуть из конфига уже после того, как конфиг завели, —
  // тогда показываем хотя бы ключ, а не пустую ячейку.
  return serverTitles.value.get(serverKey) ?? serverKey;
}

function serverConfigs(serverKey: string) {
  return configs.value.filter((config) => config.serverKey === serverKey);
}

function serverTotals(serverKey: string) {
  const list = serverConfigs(serverKey);

  return {
    ready: list.filter((config) => config.status === 'ready').length,
    failed: list.filter((config) => config.status === 'failed').length,
    total: list.length,
  };
}

function isServerGenerating(serverKey: string): boolean {
  return serverConfigs(serverKey).some(
    (config) => config.status === 'queued' || config.status === 'generating',
  );
}

function isServerGenerateDisabled(serverKey: string): boolean {
  const totals = serverTotals(serverKey);

  return isServerGenerating(serverKey) || totals.total === 0 || totals.ready === totals.total;
}

function serverGenerateLabel(server: Server): string {
  if (isServerGenerating(server.key)) {
    return `${server.title}: генерация…`;
  }

  const totals = serverTotals(server.key);

  return `${server.title} (${totals.ready}/${totals.total})`;
}

const {
  generateConfigs,
  onDone: onGenerateDone,
} = useGenerateConfigs();

const isGenerateDisabled = computed(
  () => isGeneratingConfigs.value
    || configTotals.value.total === 0
    || configTotals.value.ready === configTotals.value.total,
);

const generateLabel = computed(() => {
  if (isGeneratingConfigs.value) {
    return 'Генерация…';
  }

  if (configTotals.value.total > 0 && configTotals.value.ready === configTotals.value.total) {
    return 'Конфиги готовы';
  }

  return 'Сгенерировать все';
});

function onGenerateConfigs(serverKeys?: string[]) {
  // Пустой список серверов бэкенд трактует как «все включённые».
  generateConfigs({ id: campaignId.value, servers: serverKeys ?? [] });
}

const isBindOpen = ref(false);
const bindTarget = ref<Config | null>(null);
// Получателя диалог знает целиком: ему нужны и остальные конфиги на этом сервере,
// чтобы показать, какие клиенты уже разобраны.
const bindRecipient = ref<Recipient | null>(null);

function openBind(recipient: Recipient, config: Config) {
  bindTarget.value = config;
  bindRecipient.value = recipient;
  isBindOpen.value = true;
}

const {
  isLoading: isDeletingConfig,
  deleteConfig,
  onDone: onDeleteConfigDone,
} = useDeleteConfig();

function onDeleteConfig(config: Config) {
  deleteConfig({ configId: config.id });
}

onDeleteConfigDone(() => {
  toast.success('Конфиг удалён');
  load();
});

const isAddConfigsOpen = ref(false);
const addConfigsTarget = ref<Recipient | null>(null);

function openAddConfigs(recipient: Recipient) {
  addConfigsTarget.value = recipient;
  isAddConfigsOpen.value = true;
}

async function copyLink(link: string) {
  try {
    await navigator.clipboard.writeText(link);
    toast.success('Ссылка скопирована');
  } catch {
    // Буфер обмена недоступен без https и разрешения — молчать тут нельзя,
    // иначе нажатие выглядит как будто ничего не сделало.
    toast.error('Не удалось скопировать ссылку');
  }
}

onGenerateDone(() => {
  toast.success('Генерация конфигов запущена');

  load();
});

function configDownloadUrl(configId: number): string {
  return `${API_BASE_URL}/configs/${configId}/download`;
}

function formatSize(size: number): string {
  if (size < 1024) {
    return `${size} Б`;
  }

  return `${(size / 1024).toFixed(1)} КБ`;
}

const effectiveStatus = computed(() => campaign.value?.status);
const currentStatus = computed<CampaignStatus>(() => effectiveStatus.value ?? 'new');

const DISABLED_STATUSES: CampaignStatus[] = ['in_progress', 'done', 'done_with_errors', 'error'];

// Оптимистичный флаг: между нажатием и обновлением статуса кампания ещё NEW, и без
// него кнопка на миг предлагала бы запустить рассылку второй раз. Дальше правду
// говорит сам статус — иначе кнопка застревала бы на «Рассылка запущена» и после
// того, как рассылка закончилась сама.
const isCampaignStarted = ref(false);

const isAddRecipientsOpen = ref(false);

const isAddRecipientsDisabled = computed(() => currentStatus.value !== 'new');

function openAddRecipients() {
  isAddRecipientsOpen.value = true;
}

const isCompleted = computed(() => DISABLED_STATUSES.includes(currentStatus.value));

const isRunning = computed(() => currentStatus.value === 'in_progress');

const stopLabel = computed(() => (isStopping.value ? 'Останавливаем…' : 'Остановить'));

const failedCount = computed(() => progressTotals.value.failed);

function onRetryFailed() {
  if (campaign.value) {
    retryFailed({ id: campaign.value.id });
  }
}

onRetryDone(() => {
  toast.success('Письма с ошибкой вернули в очередь — запустите рассылку снова');
  load();
});

// Статус ушёл из NEW — значит, кампанию уже видно по-настоящему, и локальный флаг
// больше не нужен: и когда рассылка пошла, и когда она завершилась сама.
watch(currentStatus, (status) => {
  if (status !== 'new') {
    isCampaignStarted.value = false;
  }
});

const isButtonLoading = computed(
  () => isRunning.value || (isCampaignStarted.value && currentStatus.value === 'new'),
);

// Конфиги уезжают вложениями, поэтому без файлов рассылку не запускаем — бэкенд
// такой старт всё равно отклонит.
const isWaitingConfigs = computed(
  () => configTotals.value.total === 0 || configTotals.value.ready < configTotals.value.total,
);

const isButtonDisabled = computed(
  () => isButtonLoading.value || isCompleted.value || isWaitingConfigs.value,
);

const buttonLabel = computed(() => {
  if (isButtonLoading.value) {
    return 'Рассылка запущена';
  }

  if (isCompleted.value) {
    return 'Рассылка завершена';
  }

  if (isWaitingConfigs.value) {
    return 'Нужны конфиги';
  }

  return 'Запустить рассылку';
});

const POLL_INTERVAL = 3000;
let pollTimer: number | undefined;
let pollInFlight = false;

function load(): Promise<void> {
  const id = campaignId.value;

  return Promise.all([
    getCampaign({ id }),
    getRecipients({ campaignId: id }),
  ])
    .then(() => undefined)
    .catch(() => undefined);
}

function pollOnce() {
  if (pollInFlight) {
    return;
  }

  pollInFlight = true;
  Promise.all([
    getCampaign({ id: campaignId.value }),
    getRecipients({ campaignId: campaignId.value }),
  ])
    .then(() => undefined)
    .catch(() => undefined)
    .finally(() => {
      pollInFlight = false;
    });
}

function startPolling() {
  stopPolling();
  pollTimer = setInterval(pollOnce, POLL_INTERVAL);
}

function stopPolling() {
  if (pollTimer !== undefined) {
    clearInterval(pollTimer);
    pollTimer = undefined;
  }
}

function onStart() {
  if (!campaign.value) {
    return;
  }

  startCampaign({ id: campaign.value.id });
}

onDone(() => {
  toast.success('Рассылка запущена');

  isCampaignStarted.value = true;

  load();
});

function onStop() {
  if (!campaign.value) {
    return;
  }

  stopCampaign({ id: campaign.value.id });
}

onStopDone(() => {
  toast.success('Рассылка остановлена');

  // Кампания вернулась в NEW, поэтому снимаем локальный флаг: иначе кнопка запуска
  // осталась бы заблокированной до перезагрузки страницы.
  isCampaignStarted.value = false;

  load();
});

const isPollingNeeded = computed(
  () => effectiveStatus.value === 'in_progress' || isGeneratingConfigs.value,
);

watch(
  isPollingNeeded,
  (needed) => {
    if (needed) {
      startPolling();
      return;
    }

    const wasPolling = pollTimer !== undefined;
    stopPolling();
    if (wasPolling) {
      Promise.all([
        getCampaign({ id: campaignId.value }),
        getRecipients({ campaignId: campaignId.value }),
      ]);
    }
  },
  { immediate: true },
);

onMounted(() => {
  getServers();
  load();
});
onUnmounted(stopPolling);

function goBack() {
  router.push('/campaigns');
}

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

const RECIPIENT_STATUS_LABEL: Record<RecipientStatus, string> = {
  pending: 'Ожидает',
  sent: 'Отправлено',
  failed: 'Ошибка',
};

const RECIPIENT_STATUS_CLASS: Record<RecipientStatus, string> = {
  pending: styles.recPending,
  sent: styles.recSent,
  failed: styles.recFailed,
};

function recipientStatusLabel(status: RecipientStatus): string {
  return RECIPIENT_STATUS_LABEL[status];
}

function recipientStatusClass(status: RecipientStatus): string {
  return RECIPIENT_STATUS_CLASS[status];
}

const CONFIG_STATUS_LABEL: Record<ConfigStatus, string> = {
  pending: 'Нет файла',
  queued: 'В очереди',
  generating: 'Генерируется',
  ready: 'Готов',
  failed: 'Ошибка',
};

const CONFIG_STATUS_CLASS: Record<ConfigStatus, string> = {
  pending: styles.configPending,
  queued: styles.configQueued,
  generating: styles.configGenerating,
  ready: styles.configReady,
  failed: styles.configFailed,
};

function configStatusLabel(status: ConfigStatus): string {
  return CONFIG_STATUS_LABEL[status];
}

function configStatusClass(status: ConfigStatus): string {
  return CONFIG_STATUS_CLASS[status];
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
</script>

<style module>
.campaignDetailsPage {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.headerRow {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  /* Кнопок генерации столько же, сколько серверов, поэтому в одну строку они не
     помещаются — переносим, иначе страница едет горизонтально. */
  flex-wrap: wrap;
}

.titleGroup {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  /* Заголовок не должен ужиматься в узкую колонку из-за ряда кнопок рядом. */
  min-width: 0;
}

.title {
  font-size: 1.5rem;
  line-height: 2rem;
  font-weight: 600;
  color: var(--foreground);
}

.actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.skTitle {
  height: 2rem;
  width: 16rem;
}

.infoCard {
  display: grid;
  gap: 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 1rem;
}

@media (min-width: 640px) {
  .infoCard {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.label {
  font-size: 0.875rem;
  line-height: 1.25rem;
  color: var(--muted-foreground);
}

.value {
  font-weight: 500;
}

.body {
  white-space: pre-wrap;
  font-weight: 500;
}

.fullWidth {
  grid-column: span 2 / span 2;
}

.logCard {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.logHeader {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  border-bottom: 1px solid var(--border);
  padding: 1rem;
}

.logTitle {
  font-size: 1.125rem;
  line-height: 1.75rem;
  font-weight: 600;
}

.colStatus {
  width: 6.25rem;
}

.colError {
  width: 30rem;
  max-width: 30rem;
}

.cellError {
  width: 30rem;
  max-width: 30rem;
}

.errorText {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--destructive);
}

.errorEmpty {
  color: var(--destructive);
}

.tooltipText {
  max-width: 20rem;
  overflow-wrap: break-word;
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

.skEmail {
  height: 1rem;
  width: 10rem;
}

.skName {
  height: 1rem;
  width: 8rem;
}

.skStatus {
  height: 1.25rem;
  width: 5rem;
  border-radius: 9999px;
}

.skError {
  height: 1rem;
  width: 6rem;
}

.skSent {
  height: 1rem;
  width: 6rem;
}

.skConfigs {
  height: 1rem;
  width: 8rem;
}

.addConfigButton {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  margin-top: 0.25rem;
  padding: 0.125rem 0;
  border: none;
  background: none;
  color: var(--muted-foreground);
  font-size: 0.8125rem;
  cursor: pointer;
}

.addConfigButton:hover {
  color: var(--foreground);
}

.configRow {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.125rem 0;
}

.configName {
  overflow-wrap: anywhere;
}

.downloadLink {
  display: inline-flex;
  align-items: center;
  color: var(--muted-foreground);
}

.downloadLink:hover {
  color: var(--foreground);
}

.copyButton {
  display: inline-flex;
  align-items: center;
  padding: 0;
  border: none;
  background: none;
  color: var(--muted-foreground);
  cursor: pointer;
}

.copyButton:hover {
  color: var(--foreground);
}

.iconActive {
  color: var(--foreground);
}

.serverProgress {
  color: var(--muted-foreground);
  font-size: 0.8125rem;
}

.panelName {
  color: var(--muted-foreground);
  font-size: 0.75rem;
}

.configPending {
  background-color: #f3f4f6;
  color: #4b5563;
}

.configQueued,
.configGenerating {
  background-color: #fef9c3;
  color: #854d0e;
}

.configReady {
  background-color: #dcfce7;
  color: #15803d;
}

.configFailed {
  background-color: #fee2e2;
  color: #b91c1c;
}

:global(.dark) .configPending {
  background-color: rgba(55, 65, 81, 0.4);
  color: #d1d5db;
}

:global(.dark) .configQueued,
:global(.dark) .configGenerating {
  background-color: rgba(113, 63, 18, 0.4);
  color: #fde047;
}

:global(.dark) .configReady {
  background-color: rgba(20, 83, 45, 0.4);
  color: #86efac;
}

:global(.dark) .configFailed {
  background-color: rgba(127, 29, 29, 0.4);
  color: #fca5a5;
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

.recPending {
  background-color: #fef9c3;
  color: #854d0e;
}

.recSent {
  background-color: #dcfce7;
  color: #15803d;
}

.recFailed {
  background-color: #fee2e2;
  color: #b91c1c;
}

:global(.dark) .recPending {
  background-color: rgba(113, 63, 18, 0.4);
  color: #fde047;
}

:global(.dark) .recSent {
  background-color: rgba(20, 83, 45, 0.4);
  color: #86efac;
}

:global(.dark) .recFailed {
  background-color: rgba(127, 29, 29, 0.4);
  color: #fca5a5;
}
</style>
