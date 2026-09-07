<template>
  <Dialog v-model:open="isOpen">
    <DialogContent
      :class="$style.dialogContent"
      data-test="bind-config-dialog"
    >
      <DialogHeader>
        <DialogTitle>Привязать клиентов с панели</DialogTitle>

        <DialogDescription>
          {{ description }}
        </DialogDescription>
      </DialogHeader>

      <div :class="$style.body">
        <p
          v-if="config?.isExternal"
          :class="$style.currentBinding"
          data-test="current-binding"
        >
          Сейчас к этой строке привязан <strong>{{ config.externalName }}</strong>.
        </p>

        <Input
          v-model="search"
          placeholder="Поиск по имени"
          data-test="bind-search-input"
        />

        <p
          v-if="isLoadingClients"
          :class="$style.hint"
        >
          Читаем список с панели…
        </p>

        <p
          v-else-if="!clients.length"
          :class="$style.hint"
          data-test="bind-empty"
        >
          На панели нет клиентов — привязывать нечего.
        </p>

        <p
          v-else-if="!filtered.length"
          :class="$style.hint"
        >
          Ничего не нашлось по запросу «{{ search }}».
        </p>

        <div
          v-else
          :class="$style.list"
          data-test="bind-client-list"
        >
          <button
            v-for="name in filtered"
            :key="name"
            :class="[
              $style.clientRow,
              selected.has(name) ? $style.clientRowSelected : '',
              takenBy(name) ? $style.clientRowTaken : '',
            ]"
            :disabled="Boolean(takenBy(name))"
            :title="takenBy(name) ?? ''"
            type="button"
            data-test="bind-client-option"
            @click="toggle(name)"
          >
            <span :class="$style.marker">
              <Check
                v-if="selected.has(name)"
                :class="$style.markerIcon"
              />
            </span>

            <span :class="$style.clientName">{{ name }}</span>

            <span
              v-if="takenBy(name)"
              :class="$style.takenLabel"
            >{{ takenBy(name) }}</span>
          </button>
        </div>

        <p
          :class="$style.hint"
          data-test="bind-summary"
        >
          {{ summary }}
        </p>
      </div>

      <DialogFooter :class="$style.footer">
        <Button
          v-if="config?.isExternal"
          :disabled="isBusy"
          variant="outline"
          data-test="unbind-button"
          @click="onUnbind"
        >
          Снять привязку
        </Button>

        <Button
          :disabled="isReplaceDisabled"
          variant="outline"
          title="Заменить клиента у этой строки конфига"
          data-test="bind-replace-button"
          @click="onReplace"
        >
          <LoaderCircle
            v-if="isBinding"
            :class="$style.spinner"
          />

          Заменить
        </Button>

        <Button
          :disabled="isAddDisabled"
          title="Завести под каждого выбранного клиента отдельный конфиг"
          data-test="bind-add-button"
          @click="onAdd"
        >
          <LoaderCircle
            v-if="isAdding"
            :class="$style.spinner"
          />

          Привязать ещё
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';

import { Check, LoaderCircle } from '@lucide/vue';
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
import useBindConfig from '@/composables/data/useBindConfig';
import useBindNewConfigs from '@/composables/data/useBindNewConfigs';
import useGetPanelClients from '@/composables/data/useGetPanelClients';
import useToast from '@/composables/useToast';
import useUnbindConfig from '@/composables/data/useUnbindConfig';
import type { Config, Recipient } from '@/apiService/recipients/recipientsApiTypes';

interface Props {
  config: Config | null;
  recipient: Recipient | null;
  /** Все получатели кампании — чтобы разобранные клиенты были видны сразу, а не ошибкой. */
  recipients: Recipient[];
  serverTitle: string;
}

const props = defineProps<Props>();

const emit = defineEmits<{ bound: [] }>();

const isOpen = defineModel<boolean>('open', { default: false });

const toast = useToast();

const {
  isLoading: isLoadingClients,
  panelClients,
  getPanelClients,
} = useGetPanelClients();

const {
  isLoading: isBinding,
  bindConfig,
  onDone: onBindDone,
} = useBindConfig();

const {
  isLoading: isAdding,
  bindNewConfigs,
  onDone: onAddDone,
} = useBindNewConfigs();

const {
  isLoading: isUnbinding,
  unbindConfig,
  onDone: onUnbindDone,
} = useUnbindConfig();

const search = ref('');

// Множество: выбирают по одному, порядок не важен, а проверка «выбран ли» тут частая.
const selected = ref<Set<string>>(new Set());

const clients = computed(() => panelClients.value ?? []);

const isBusy = computed(() => isBinding.value || isAdding.value || isUnbinding.value);

const description = computed(() => (
  props.config
    ? `Сервер «${props.serverTitle}», получатель ${props.recipient?.email ?? ''}. `
    + 'Отметьте клиентов, заведённых на панели вручную, — программа заберёт их конфиги, '
    + 'а не создаст новых. Имена, которые видит получатель, останутся своими.'
    : ''
));

const filtered = computed(() => {
  const query = search.value.trim().toLowerCase();

  return query ? clients.value.filter((name) => name.toLowerCase().includes(query)) : clients.value;
});

/**
 * Кем в кампании уже занято имя клиента; null — свободно.
 *
 * Один клиент панели достаётся одному конфигу: иначе двое получат один и тот же
 * доступ. Бэкенд это и так отклоняет, но узнать об этом лучше до нажатия кнопки.
 */
function takenBy(name: string): string | null {
  const serverKey = props.config?.serverKey;

  const owner = props.recipients
    .flatMap((recipient) => recipient.configs.map((config) => ({ recipient, config })))
    .find(({ config }) => config.serverKey === serverKey && config.panelName === name);

  if (!owner) {
    return null;
  }

  if (owner.config.id === props.config?.id) {
    return 'привязан здесь';
  }

  return owner.recipient.id === props.recipient?.id
    ? `занят ${owner.config.name}`
    : `занят ${owner.recipient.email}`;
}

const isReplaceDisabled = computed(() => isBusy.value || selected.value.size !== 1);

const isAddDisabled = computed(() => isBusy.value || selected.value.size === 0);

const summary = computed(() => {
  if (!selected.value.size) {
    return 'Отметьте одного клиента, чтобы заменить привязку этой строки, '
      + 'или нескольких — чтобы завести под них отдельные конфиги.';
  }

  const names = [...selected.value].join(', ');

  return selected.value.size === 1
    ? `Выбран ${names}: «Заменить» перепривяжет эту строку, «Привязать ещё» добавит новую.`
    : `Выбрано ${selected.value.size}: ${names}. Появится столько же новых конфигов.`;
});

function toggle(name: string): void {
  if (takenBy(name)) {
    return;
  }

  const next = new Set(selected.value);

  if (next.has(name)) {
    next.delete(name);
  } else {
    next.add(name);
  }

  selected.value = next;
}

function onReplace(): void {
  const [name] = [...selected.value];

  if (!props.config || !name) {
    return;
  }

  bindConfig({ configId: props.config.id, externalName: name });
}

function onAdd(): void {
  if (!props.recipient || !props.config || !selected.value.size) {
    return;
  }

  bindNewConfigs({
    recipientId: props.recipient.id,
    serverKey: props.config.serverKey,
    names: [...selected.value],
  });
}

function onUnbind(): void {
  if (!props.config) {
    return;
  }

  unbindConfig({ configId: props.config.id });
}

function close(message: string): void {
  toast.success(message);
  isOpen.value = false;
  emit('bound');
}

onBindDone(() => close('Клиент привязан — конфиг заберём с панели'));

onAddDone(() => close('Клиенты привязаны — под каждого завели свой конфиг'));

onUnbindDone(() => close('Привязка снята'));

// Список тянем на открытии: он ходит на живую панель, и держать его заранее незачем.
watch(isOpen, (opened) => {
  search.value = '';
  selected.value = new Set();

  if (opened && props.config) {
    getPanelClients({ serverKey: props.config.serverKey });
  }
});
</script>

<style module>
.dialogContent {
  max-width: 32rem;
}

.body {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.currentBinding {
  color: var(--muted-foreground);
  font-size: 0.875rem;
}

.hint {
  color: var(--muted-foreground);
  font-size: 0.875rem;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  max-height: 18rem;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.25rem;
}

.clientRow {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  text-align: left;
  padding: 0.5rem 0.625rem;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: none;
  color: var(--foreground);
  font-size: 0.875rem;
  cursor: pointer;
}

.clientRow:hover:not(:disabled) {
  background-color: var(--muted);
}

/* Выбранное должно читаться с одного взгляда, поэтому не жирность, а фон и рамка. */
.clientRowSelected,
.clientRowSelected:hover:not(:disabled) {
  background-color: var(--primary);
  border-color: var(--primary);
  color: var(--primary-foreground);
  font-weight: 500;
}

.clientRowTaken {
  color: var(--muted-foreground);
  cursor: not-allowed;
}

.marker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 1.125rem;
  height: 1.125rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.clientRowSelected .marker {
  border-color: var(--primary-foreground);
}

.markerIcon {
  width: 0.875rem;
  height: 0.875rem;
}

.clientName {
  flex: 1;
}

.takenLabel {
  font-size: 0.75rem;
  color: var(--muted-foreground);
}

.footer {
  gap: 0.5rem;
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
