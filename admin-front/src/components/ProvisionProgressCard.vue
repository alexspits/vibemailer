<template>
  <div
    :class="$style.provisionProgressCard"
    data-test="provision-card"
  >
    <div :class="$style.headerRow">
      <div :class="$style.heading">
        <span :class="$style.title">
          {{ isRunning ? 'Поднимается сервер' : 'Прогон' }}: {{ run.title }}
        </span>

        <span :class="$style.host">{{ run.host }} · {{ run.panel }}</span>
      </div>

      <div :class="$style.headerActions">
        <Badge
          :class="$style[badgeClass]"
          data-test="provision-status"
        >
          {{ STATUS_LABELS[run.status] }}
        </Badge>

        <Button
          v-if="isRunning"
          :disabled="isCancelling"
          variant="outline"
          size="sm"
          data-test="provision-cancel"
          @click="emit('cancel')"
        >
          <LoaderCircle
            v-if="isCancelling"
            :class="$style.spinner"
          />

          Прервать
        </Button>

        <Button
          v-else
          variant="ghost"
          size="sm"
          data-test="provision-hide"
          @click="emit('hide')"
        >
          Скрыть
        </Button>
      </div>
    </div>

    <p
      v-if="isRunning"
      :class="$style.step"
      data-test="provision-step"
    >
      <LoaderCircle :class="$style.spinner" />

      {{ run.step || 'Запуск плейбука' }}
    </p>

    <p
      v-if="run.recap"
      :class="$style.recap"
      data-test="provision-recap"
    >
      {{ run.recap }}
    </p>

    <template v-if="isDone">
      <p :class="$style.hint">
        <template v-if="run.registered">
          Сервер дописан в servers.yml и пока выключен: в новые рассылки не попадёт.
          Зайдите в панель, убедитесь кнопкой «Проверить», что она отвечает, и включите
          переключателем.
        </template>

        <template v-else>
          Сервер поднят, но в список не дописан — добавьте его кнопкой
          «Подключить готовый».
        </template>
      </p>

      <p
        v-if="isXui"
        :class="$style.hint"
      >
        На свежей панели 3x-ui нет ни одного inbound'а: создайте его в панели, иначе
        конфиги на этом сервере не заведутся. В servers.yml записан
        <code>inbound_ids: [1]</code> — поправьте, если номер окажется другим.
      </p>

      <p
        v-else
        :class="$style.hint"
      >
        Панель AmneziaWG поднимается без сервера внутри — создайте его в UI, иначе
        проверка так и будет отвечать «на панели нет ни одного сервера». Версия
        протокола (AWG 2.0 или 3.1) задаётся там же, при создании, и потом не меняется.
      </p>

      <div
        v-if="run.panelPassword"
        :class="$style.field"
      >
        <span :class="$style.fieldLabel">Пароль панели (лежит в servers.yml)</span>

        <code
          :class="$style.value"
          data-test="provision-panel-password"
        >{{ run.panelPassword }}</code>
      </div>

      <div
        v-if="run.tunnel"
        :class="$style.field"
      >
        <span :class="$style.fieldLabel">Туннель до панели и адрес в браузере</span>
        <code :class="$style.value">{{ run.tunnel }}</code>
        <code :class="$style.value">{{ run.panelUrl }}</code>
      </div>

      <div :class="$style.field">
        <span :class="$style.fieldLabel">
          Хост для inventory.yml ваших сценариев — прогон шёл по одноразовому
        </span>

        <pre :class="$style.snippet">{{ inventorySnippet }}</pre>
      </div>
    </template>

    <p
      v-if="run.error"
      :class="$style.error"
      data-test="provision-run-error"
    >
      {{ run.error }}
    </p>

    <details :class="$style.logBox">
      <summary :class="$style.logSummary">
        Лог прогона
      </summary>

      <pre
        ref="logElement"
        :class="$style.log"
        data-test="provision-log"
      >{{ log || 'Пока пусто' }}</pre>
    </details>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';

import { LoaderCircle } from '@lucide/vue';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import type { ProvisionRun, ProvisionStatus } from '@/apiService/provision/provisionApiTypes';

const STATUS_LABELS: Record<ProvisionStatus, string> = {
  running: 'идёт',
  done: 'готово',
  failed: 'ошибка',
  cancelled: 'прервано',
};

interface Props {
  run: ProvisionRun;
  log: string;
  isCancelling?: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{ cancel: []; hide: [] }>();

const logElement = ref<HTMLElement | null>(null);

const isRunning = computed(() => props.run.status === 'running');
const isDone = computed(() => props.run.status === 'done');
const isXui = computed(() => props.run.panel === '3x-ui');

// Имя класса, а не сам класс: хешированные имена CSS-модуля доступны в шаблоне
// через $style, а в скрипте их пришлось бы тащить через useCssModule.
const badgeClass = computed(() => {
  if (isRunning.value) {
    return 'badgeRunning';
  }

  return isDone.value ? 'badgeOk' : 'badgeFail';
});

const inventorySnippet = computed(() => [
  '    vpn:',
  '      hosts:',
  `        ${props.run.serverKey}_server:`,
  `          ansible_host: ${props.run.host}`,
].join('\n'));

// Лог догружается по смещению, поэтому доматывать его надо самим: иначе интересное
// (текущий шаг и ошибки) уезжает за нижний край.
watch(() => props.log, async () => {
  await nextTick();

  if (logElement.value) {
    logElement.value.scrollTop = logElement.value.scrollHeight;
  }
});
</script>

<style module>
.provisionProgressCard {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.headerRow {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.heading {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.headerActions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.title {
  font-weight: 600;
  color: var(--foreground);
}

.host {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8125rem;
  color: var(--muted-foreground);
}

.step {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--foreground);
}

.recap {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8125rem;
  color: var(--muted-foreground);
  overflow-wrap: anywhere;
}

.hint {
  color: var(--muted-foreground);
  font-size: 0.875rem;
  max-width: 60rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.fieldLabel {
  font-size: 0.8125rem;
  color: var(--muted-foreground);
}

.value {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8125rem;
  overflow-wrap: anywhere;
  user-select: all;
}

.snippet {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8125rem;
  margin: 0;
  white-space: pre;
  overflow-x: auto;
  user-select: all;
}

.error {
  color: var(--destructive);
  font-size: 0.875rem;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.logBox {
  border-top: 1px solid var(--border);
  padding-top: 0.5rem;
}

.logSummary {
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--muted-foreground);
}

.log {
  margin: 0.5rem 0 0;
  max-height: 22rem;
  overflow: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.75rem;
  line-height: 1.4;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.badgeRunning {
  background-color: #e0e7ff;
  color: #3730a3;
}

:global(.dark) .badgeRunning {
  background-color: #312e81;
  color: #c7d2fe;
}

.badgeOk {
  background-color: #dcfce7;
  color: #166534;
}

:global(.dark) .badgeOk {
  background-color: #14532d;
  color: #bbf7d0;
}

.badgeFail {
  background-color: #fee2e2;
  color: #991b1b;
}

:global(.dark) .badgeFail {
  background-color: #7f1d1d;
  color: #fecaca;
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
