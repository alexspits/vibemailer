<template>
  <Dialog v-model:open="isOpen">
    <DialogContent
      :class="$style.dialogContent"
      data-test="add-recipients-dialog"
    >
      <DialogHeader>
        <DialogTitle>Добавить получателей</DialogTitle>

        <DialogDescription>
          {{ description }}
        </DialogDescription>
      </DialogHeader>

      <div
        v-if="isInputStep"
        :class="$style.step"
        data-test="input-step"
      >
        <Tabs v-model="mode">
          <TabsList>
            <TabsTrigger
              value="paste"
              data-test="paste-tab"
            >
              Вставить список
            </TabsTrigger>

            <TabsTrigger
              value="manual"
              data-test="manual-tab"
            >
              Вручную
            </TabsTrigger>
          </TabsList>

          <TabsContent value="paste">
            <Textarea
              v-model="text"
              :class="$style.textarea"
              placeholder="Markin_Sergey&#9;shpenator@gmail.com"
              data-test="recipients-textarea"
            />
          </TabsContent>

          <TabsContent value="manual">
            <div :class="$style.manualForm">
              <div :class="$style.field">
                <label
                  :class="$style.fieldLabel"
                  for="manual-email"
                >
                  Почта
                </label>

                <Input
                  id="manual-email"
                  v-model="manualEmail"
                  placeholder="shpenator@gmail.com"
                  data-test="manual-email-input"
                />
              </div>

              <div :class="$style.field">
                <span :class="$style.fieldLabel">Имя конфига</span>

                <Input
                  v-model="manualClientName"
                  placeholder="Markin_Sergey"
                  data-test="manual-config-input"
                />
              </div>

              <div :class="$style.field">
                <span :class="$style.fieldLabel">Сколько конфигов</span>

                <Input
                  v-model="manualCount"
                  type="number"
                  min="1"
                  data-test="manual-count-input"
                />

                <span :class="$style.fieldHint">
                  Имена получатся нумерацией: {{ manualNamesHint }}. Каждое заводится
                  на всех серверах сразу.
                </span>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>

      <div
        v-else-if="preview"
        :class="$style.step"
        data-test="preview-step"
      >
        <p
          :class="$style.summary"
          data-test="preview-summary"
        >
          {{ preview.totalRows }} {{ rowsLabel }} → {{ preview.groups.length }} {{ lettersLabel }},
          новых получателей {{ preview.totalRecipients }}, конфигов {{ preview.totalConfigs }}
        </p>

        <div
          v-if="preview.problems.length"
          :class="$style.problems"
          data-test="preview-problems"
        >
          <p :class="$style.problemsTitle">
            Не добавим {{ preview.problems.length }} {{ problemsLabel }}:
          </p>

          <p
            v-for="problem in preview.problems"
            :key="problem.line"
            :class="$style.problem"
            data-test="preview-problem"
          >
            Строка {{ problem.line }}: {{ problem.raw || '—' }} — {{ problem.reason }}
          </p>
        </div>

        <div :class="$style.groups">
          <div
            v-for="group in preview.groups"
            :key="group.email"
            :class="$style.group"
            data-test="preview-group"
          >
            <div :class="$style.groupHeader">
              <span :class="$style.email">{{ group.email }}</span>

              <Badge
                v-if="group.isExisting"
                :class="$style.existingBadge"
                data-test="existing-badge"
              >
                уже в кампании
              </Badge>

              <span :class="$style.count">
                {{ group.count }} {{ configsLabel(group.count) }}
              </span>
            </div>

            <div
              v-if="group.newNames.length"
              :class="$style.chips"
            >
              <span
                v-for="name in group.newNames"
                :key="name"
                :class="$style.chip"
                data-test="config-chip"
              >
                {{ name }}
              </span>
            </div>

            <p
              v-if="group.newConfigs"
              :class="$style.groupNote"
              data-test="group-servers"
            >
              Заведём {{ group.newConfigs }} на серверах:
              {{ group.servers.map(serverTitle).join(', ') }}
            </p>

            <p
              v-if="Object.keys(group.bindings).length"
              :class="$style.groupNote"
              data-test="group-bindings"
            >
              Привяжем к уже заведённым: {{ bindingsLabel(group.bindings) }}
            </p>

            <p
              v-else
              :class="$style.groupNote"
              data-test="group-servers"
            >
              Всё уже заведено — ничего не изменится.
            </p>

            <p
              v-if="group.existingClientName && group.existingClientName !== group.clientName"
              :class="$style.nameConflict"
              data-test="name-conflict"
            >
              У получателя уже есть имя {{ group.existingClientName }} — оно и останется.
            </p>
          </div>
        </div>
      </div>

      <DialogFooter>
        <Button
          v-if="isInputStep"
          :disabled="isPreviewDisabled"
          data-test="parse-button"
          @click="onParse"
        >
          <LoaderCircle
            v-if="isPreviewLoading"
            :class="$style.spinner"
          />

          {{ parseLabel }}
        </Button>

        <template v-else>
          <Button
            :disabled="isImporting"
            variant="outline"
            data-test="back-button"
            @click="goBack"
          >
            Назад
          </Button>

          <Button
            :disabled="isImportDisabled"
            data-test="import-button"
            @click="onImport"
          >
            <LoaderCircle
              v-if="isImporting"
              :class="$style.spinner"
            />

            {{ importLabel }}
          </Button>
        </template>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';

import { LoaderCircle } from '@lucide/vue';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import useGetServers from '@/composables/data/useGetServers';
import useImportRecipients from '@/composables/data/useImportRecipients';
import usePreviewRecipientsImport from '@/composables/data/usePreviewRecipientsImport';
import useToast from '@/composables/useToast';

interface Props {
  campaignId: number;
}

const props = defineProps<Props>();

const emit = defineEmits<{ added: [] }>();

const isOpen = defineModel<boolean>('open', { default: false });

const toast = useToast();

const {
  isLoading: isPreviewLoading,
  preview,
  previewRecipientsImport,
  onDone: onPreviewDone,
} = usePreviewRecipientsImport();

const {
  isLoading: isImporting,
  importResult,
  importRecipients,
  onDone: onImportDone,
} = useImportRecipients();

const {
  servers,
  getServers,
} = useGetServers();

const serverTitles = computed(
  () => new Map((servers.value ?? []).map((server) => [server.key, server.title])),
);

function serverTitle(serverKey: string): string {
  return serverTitles.value.get(serverKey) ?? serverKey;
}

function bindingsLabel(bindings: Record<string, string>): string {
  return Object.entries(bindings)
    .map(([serverKey, panelName]) => `${serverTitle(serverKey)} → ${panelName}`)
    .join(', ');
}

type Mode = 'paste' | 'manual';

const mode = ref<Mode>('paste');
const text = ref('');
const manualEmail = ref('');
const manualClientName = ref('');
const manualCount = ref('1');
const isInputStep = ref(true);

const isManualMode = computed(() => mode.value === 'manual');

const description = computed(() => (
  isManualMode.value
    ? 'Одна почта, имя конфига и сколько их нужно. Имена получатся нумерацией.'
    : 'Вставьте из таблицы: имя конфига, почту, количество (необязательно) и привязки к уже заведённым на панелях клиентам вида «ru:adonm» (тоже необязательно).'
));

const parseLabel = computed(() => (isManualMode.value ? 'Продолжить' : 'Разобрать'));

// Количество из поля: пустое или мусорное считаем за один конфиг, а не за ошибку —
// бэкенд всё равно проверит, а форма не должна залипать на полпути ввода.
const parsedManualCount = computed(() => {
  const parsed = Number.parseInt(manualCount.value, 10);

  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
});

// Повторяет CONFIG_NAME_SEPARATOR из app/db/models.py: подсказка рисуется до похода
// на бэкенд, поэтому разделитель приходится знать и здесь. Сами имена в предпросмотре
// приходят уже с сервера.
const NAME_SEPARATOR = '-';

const manualNamesHint = computed(() => {
  const base = manualClientName.value.trim() || 'alice';
  const count = parsedManualCount.value;
  const name = (n: number) => `${base}${NAME_SEPARATOR}${n}`;
  const names = Array.from({ length: Math.min(count, 3) }, (_, i) => name(i + 1));

  return count > 3 ? `${names.join(', ')}, …${name(count)}` : names.join(', ');
});

// Обе вкладки шлют на бэк один и тот же формат — колонки через таб.
const importText = computed(() => {
  if (!isManualMode.value) {
    return text.value;
  }

  const email = manualEmail.value.trim();
  const clientName = manualClientName.value.trim();

  return email && clientName ? `${clientName}\t${email}\t${parsedManualCount.value}` : '';
});

const isPreviewDisabled = computed(() => isPreviewLoading.value || !importText.value.trim());

const isImportDisabled = computed(
  () => isImporting.value || !preview.value || preview.value.groups.length === 0,
);

function plural(count: number, one: string, few: string, many: string): string {
  const mod100 = count % 100;

  if (mod100 >= 11 && mod100 <= 14) {
    return many;
  }

  const mod10 = count % 10;

  if (mod10 === 1) {
    return one;
  }

  if (mod10 >= 2 && mod10 <= 4) {
    return few;
  }

  return many;
}

const rowsLabel = computed(() => plural(preview.value?.totalRows ?? 0, 'строка', 'строки', 'строк'));

const lettersLabel = computed(
  () => plural(preview.value?.groups.length ?? 0, 'письмо', 'письма', 'писем'),
);

const problemsLabel = computed(
  () => plural(preview.value?.problems.length ?? 0, 'строку', 'строки', 'строк'),
);

function configsLabel(count: number): string {
  return plural(count, 'конфиг', 'конфига', 'конфигов');
}

const importLabel = computed(() => {
  const groups = preview.value?.groups ?? [];
  const newCount = groups.filter((group) => !group.isExisting).length;
  const existingCount = groups.length - newCount;

  const parts: string[] = [];

  if (newCount) {
    parts.push(`Добавить ${newCount} ${plural(newCount, 'получателя', 'получателей', 'получателей')}`);
  }

  if (existingCount) {
    parts.push(newCount ? `дополнить ${existingCount}` : `Дополнить ${existingCount}`);
  }

  return parts.length ? parts.join(' и ') : 'Добавить';
});

function onParse() {
  previewRecipientsImport({ campaignId: props.campaignId, text: importText.value });
}

onPreviewDone(() => {
  isInputStep.value = false;
});

function goBack() {
  isInputStep.value = true;
}

function onImport() {
  importRecipients({ campaignId: props.campaignId, text: importText.value });
}

onImportDone(() => {
  const result = importResult.value;

  if (!result) {
    return;
  }

  const added = result.createdRecipients + result.updatedRecipients;
  const skipped = result.problems.length;

  toast.success(
    skipped
      ? `Добавлено ${added}, пропущено ${skipped}`
      : `Добавлено ${added}`,
  );

  emit('added');

  isOpen.value = false;
});

watch(isOpen, (opened) => {
  if (opened) {
    // Названия серверов нужны предпросмотру; список маленький и кешируется композаблом.
    getServers();
    return;
  }

  mode.value = 'paste';
  text.value = '';
  manualEmail.value = '';
  manualClientName.value = '';
  manualCount.value = '1';
  isInputStep.value = true;
});
</script>

<style module>
.dialogContent {
  max-width: 46rem;
}

.step {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-height: 60vh;
  overflow-y: auto;
}

.manualForm {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding-top: 0.75rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.fieldLabel {
  font-weight: 500;
  color: var(--foreground);
}

.fieldHint {
  color: var(--muted-foreground);
  font-size: 0.8125rem;
}

.nameConflict {
  color: var(--muted-foreground);
  font-size: 0.8125rem;
}

.groupNote {
  color: var(--muted-foreground);
  font-size: 0.8125rem;
}

.iconBtn {
  width: 1rem;
  height: 1rem;
}

.textarea {
  margin-top: 0.75rem;
  min-height: 14rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.summary {
  font-weight: 600;
  color: var(--foreground);
}

.problems {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  border: 1px solid var(--destructive);
  border-radius: var(--radius-md);
  padding: 0.75rem;
}

.problemsTitle {
  font-weight: 500;
  color: var(--destructive);
}

.problem {
  color: var(--muted-foreground);
  overflow-wrap: anywhere;
}

.groups {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.75rem;
}

.groupHeader {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.email {
  font-weight: 500;
  overflow-wrap: anywhere;
}

.count {
  margin-left: auto;
  white-space: nowrap;
  color: var(--muted-foreground);
}

.existingBadge {
  background-color: #dbeafe;
  color: #1d4ed8;
}

:global(.dark) .existingBadge {
  background-color: rgba(30, 58, 138, 0.4);
  color: #93c5fd;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.chip {
  border: 1px solid var(--border);
  border-radius: 9999px;
  padding: 0.125rem 0.5rem;
  overflow-wrap: anywhere;
}

.chipExisting {
  color: var(--muted-foreground);
  border-style: dashed;
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
</style>
