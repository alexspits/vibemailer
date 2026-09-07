<template>
  <Dialog v-model:open="isOpen">
    <DialogContent
      :class="$style.dialogContent"
      data-test="add-configs-dialog"
    >
      <DialogHeader>
        <DialogTitle>Добавить конфиги</DialogTitle>

        <DialogDescription>
          {{ description }}
        </DialogDescription>
      </DialogHeader>

      <div :class="$style.body">
        <p :class="$style.label">
          На каких серверах
        </p>

        <div
          :class="$style.list"
          data-test="add-configs-servers"
        >
          <button
            v-for="server in servers ?? []"
            :key="server.key"
            :class="[$style.serverRow, selected.has(server.key) ? $style.serverRowActive : '']"
            type="button"
            data-test="add-configs-server-option"
            @click="toggle(server.key)"
          >
            <span>{{ server.title }}</span>
            <span :class="$style.serverCount">сейчас {{ countOn(server.key) }}</span>
          </button>
        </div>

        <p :class="$style.label">
          Сколько добавить на каждый
        </p>

        <Input
          v-model="count"
          type="number"
          min="1"
          max="20"
          data-test="add-configs-count"
        />

        <p :class="$style.hint">
          {{ preview }}
        </p>
      </div>

      <DialogFooter>
        <Button
          :disabled="isDisabled"
          data-test="add-configs-button"
          @click="onAdd"
        >
          <LoaderCircle
            v-if="isLoading"
            :class="$style.spinner"
          />

          Добавить
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';

import { LoaderCircle } from '@lucide/vue';
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
import useAddConfigs from '@/composables/data/useAddConfigs';
import useGetServers from '@/composables/data/useGetServers';
import useToast from '@/composables/useToast';
import type { Recipient } from '@/apiService/recipients/recipientsApiTypes';

interface Props {
  recipient: Recipient | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{ added: [] }>();

const isOpen = defineModel<boolean>('open', { default: false });

const toast = useToast();

const { servers, getServers } = useGetServers();

const {
  isLoading,
  addConfigs,
  onDone,
} = useAddConfigs();

// Множество, а не массив: сервера отмечают по одному, и порядок здесь ничего не значит.
const selected = ref<Set<string>>(new Set());
const count = ref('1');

const parsedCount = computed(() => {
  const value = Number.parseInt(count.value, 10);

  return Number.isFinite(value) ? Math.min(Math.max(value, 1), 20) : 0;
});

const description = computed(() => (
  props.recipient
    ? `Получатель ${props.recipient.email}. Каждый конфиг — отдельный клиент на панели, `
    + 'поэтому добавлять их стоит столько, сколько у человека устройств. '
    + 'Привязать к существующему клиенту можно потом, у каждой строки отдельно.'
    : ''
));

const preview = computed(() => {
  if (!props.recipient || !selected.value.size || !parsedCount.value) {
    return 'Отметьте серверы и укажите количество.';
  }

  const names = [...selected.value]
    .map((key) => {
      const next = countOn(key) + 1;
      const last = countOn(key) + parsedCount.value;
      const base = props.recipient?.clientName ?? '';

      return next === last ? `${base}-${next}` : `${base}-${next}…${base}-${last}`;
    })
    .join(', ');

  return `Появятся: ${names}`;
});

const isDisabled = computed(() => (
  isLoading.value || !selected.value.size || !parsedCount.value
));

function countOn(serverKey: string): number {
  return (props.recipient?.configs ?? []).filter((config) => config.serverKey === serverKey).length;
}

function toggle(serverKey: string): void {
  const next = new Set(selected.value);

  if (next.has(serverKey)) {
    next.delete(serverKey);
  } else {
    next.add(serverKey);
  }

  selected.value = next;
}

function onAdd(): void {
  if (!props.recipient) {
    return;
  }

  addConfigs({
    recipientId: props.recipient.id,
    serverKeys: [...selected.value],
    count: parsedCount.value,
  });
}

onDone(() => {
  toast.success('Конфиги добавлены — осталось сгенерировать или привязать');
  isOpen.value = false;
  emit('added');
});

// Серверы тянем на открытии: список включённых меняется только правкой servers.yml.
watch(isOpen, (opened) => {
  if (opened) {
    selected.value = new Set();
    count.value = '1';
    getServers();
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

.label {
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
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.25rem;
}

.serverRow {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  text-align: left;
  padding: 0.5rem 0.625rem;
  border: none;
  border-radius: var(--radius-md);
  background: none;
  color: var(--foreground);
  font-size: 0.875rem;
  cursor: pointer;
}

.serverRow:hover {
  background-color: var(--muted);
}

.serverRowActive {
  background-color: var(--muted);
  font-weight: 500;
}

.serverCount {
  color: var(--muted-foreground);
  font-size: 0.75rem;
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
