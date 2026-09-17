<template>
  <Dialog v-model:open="isOpen">
    <DialogContent
      :class="$style.dialogContent"
      data-test="suggest-clients-dialog"
    >
      <DialogHeader>
        <DialogTitle>Найти клиентов на панелях</DialogTitle>

        <DialogDescription>
          {{ description }}
        </DialogDescription>
      </DialogHeader>

      <div :class="$style.body">
        <div :class="$style.searchRow">
          <Input
            v-model="hint"
            placeholder="Подсказка: фамилия или кусок имени с панели"
            data-test="suggest-hint-input"
            @keyup.enter="search"
          />

          <Button
            :disabled="isSearching"
            variant="outline"
            data-test="suggest-search-button"
            @click="search"
          >
            <LoaderCircle
              v-if="isSearching"
              :class="$style.spinner"
            />

            Искать
          </Button>
        </div>

        <p :class="$style.hint">
          {{ hintExplanation }}
        </p>

        <p
          v-if="isSearching"
          :class="$style.hint"
        >
          Читаем списки клиентов со всех панелей…
        </p>

        <div
          v-for="server in servers"
          v-else
          :key="server.serverKey"
          :class="$style.server"
        >
          <p :class="$style.serverTitle">
            {{ server.serverTitle }}
          </p>

          <p
            v-if="server.error"
            :class="$style.serverError"
          >
            Панель не ответила: {{ server.error }}
          </p>

          <p
            v-else-if="!server.candidates.length"
            :class="$style.hint"
            data-test="suggest-empty"
          >
            Не нашлось — привяжите вручную или оставьте, тогда заведём нового клиента.
          </p>

          <div
            v-else
            :class="$style.list"
          >
            <button
              v-for="candidate in server.candidates"
              :key="candidate.name"
              :class="[
                $style.clientRow,
                isChecked(server.serverKey, candidate.name) ? $style.clientRowSelected : '',
                candidate.takenBy ? $style.clientRowTaken : '',
              ]"
              :disabled="Boolean(candidate.takenBy)"
              type="button"
              data-test="suggest-candidate"
              @click="toggle(server.serverKey, candidate.name)"
            >
              <span :class="$style.marker">
                <Check
                  v-if="isChecked(server.serverKey, candidate.name)"
                  :class="$style.markerIcon"
                />
              </span>

              <span :class="$style.clientName">{{ candidate.name }}</span>

              <span
                v-if="candidate.takenBy"
                :class="$style.note"
              >занят {{ candidate.takenBy }}</span>

              <span
                v-else
                :class="$style.note"
              >{{ confidenceLabel(candidate.score) }}</span>
            </button>
          </div>
        </div>

        <p
          :class="$style.hint"
          data-test="suggest-summary"
        >
          {{ summary }}
        </p>
      </div>

      <DialogFooter>
        <Button
          :disabled="isBindDisabled"
          data-test="suggest-bind-button"
          @click="onBind"
        >
          <LoaderCircle
            v-if="isBinding"
            :class="$style.spinner"
          />

          Привязать отмеченные
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
import useBindSuggested from '@/composables/data/useBindSuggested';
import useSuggestClients from '@/composables/data/useSuggestClients';
import useToast from '@/composables/useToast';
import type { Recipient } from '@/apiService/recipients/recipientsApiTypes';

interface Props {
  campaignId: number;
  recipient: Recipient | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{ bound: [] }>();

const isOpen = defineModel<boolean>('open', { default: false });

const toast = useToast();

const {
  isLoading: isSearching,
  suggestions,
  suggestClients,
  onDone: onSearchDone,
} = useSuggestClients();

const {
  isLoading: isBinding,
  bindSuggested,
  onDone: onBindDone,
} = useBindSuggested();

const hint = ref('');

// Ключ сервера → отмеченные имена. Отдельно от выдачи: повторный поиск не должен
// сбрасывать то, что человек уже успел отметить руками.
const checked = ref<Record<string, Set<string>>>({});

const servers = computed(() => suggestions.value?.[0]?.servers ?? []);

const description = computed(() => (
  props.recipient
    ? `Получатель ${props.recipient.email}. Ищем на всех панелях клиентов, похожих на `
    + 'него, — по почте и базовому имени. Отмеченные привяжутся, ненайденные останутся '
    + 'пустыми: их можно привязать вручную или сгенерировать новыми.'
    : ''
));

const hintExplanation = computed(() => {
  const base = props.recipient?.clientName ?? '';
  const local = props.recipient?.email.split('@')[0] ?? '';

  return `Ищем по «${local}» и «${base}». Если на панелях человек назван иначе — `
    + 'впишите подсказку и нажмите «Искать».';
});

const totalChecked = computed(
  () => Object.values(checked.value).reduce((sum, names) => sum + names.size, 0),
);

const summary = computed(() => {
  if (isSearching.value) {
    return '';
  }

  if (!suggestions.value) {
    return 'Нажмите «Искать».';
  }

  const found = servers.value.filter((server) => server.candidates.length).length;

  if (!found) {
    return 'Ни на одной панели похожих клиентов нет.';
  }

  return totalChecked.value
    ? `Отмечено ${totalChecked.value} — столько конфигов и привяжется.`
    : `Есть совпадения на ${found} ${found === 1 ? 'панели' : 'панелях'}. Отметьте нужные.`;
});

const isBindDisabled = computed(() => isBinding.value || isSearching.value || !totalChecked.value);

/** Словами, а не числом: точность подбора — не та величина, которую стоит показывать. */
function confidenceLabel(score: number): string {
  if (score >= 0.85) {
    return 'очень похоже';
  }

  return score >= 0.7 ? 'похоже' : 'возможно';
}

function isChecked(serverKey: string, name: string): boolean {
  return Boolean(checked.value[serverKey]?.has(name));
}

function toggle(serverKey: string, name: string): void {
  const next = { ...checked.value };
  const names = new Set(next[serverKey] ?? []);

  if (names.has(name)) {
    names.delete(name);
  } else {
    names.add(name);
  }

  next[serverKey] = names;
  checked.value = next;
}

function search(): void {
  if (!props.recipient) {
    return;
  }

  const hints = hint.value.trim()
    ? { [String(props.recipient.id)]: hint.value.trim() }
    : {};

  suggestClients({
    id: props.campaignId,
    recipientIds: [props.recipient.id],
    hints,
  });
}

function onBind(): void {
  if (!props.recipient) {
    return;
  }

  const selections = Object.fromEntries(
    Object.entries(checked.value).map(([key, names]) => [key, [...names]]),
  );

  bindSuggested({ recipientId: props.recipient.id, selections });
}

// Галочки расставляет подбор: уверенные совпадения отмечены заранее, остальные — нет.
onSearchDone(() => {
  const next: Record<string, Set<string>> = {};

  for (const server of servers.value) {
    next[server.serverKey] = new Set(
      server.candidates.filter((candidate) => candidate.suggested).map((c) => c.name),
    );
  }

  checked.value = next;
});

onBindDone(() => {
  toast.success('Клиенты привязаны — конфиги заберём с панелей');
  isOpen.value = false;
  emit('bound');
});

// Ищем сразу при открытии: диалог открывают именно ради поиска, и лишнее нажатие
// здесь только раздражает.
watch(isOpen, (opened) => {
  hint.value = '';
  checked.value = {};

  if (opened) {
    search();
  }
});
</script>

<style module>
.dialogContent {
  max-width: 34rem;
}

.body {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-height: 60vh;
  overflow-y: auto;
}

.searchRow {
  display: flex;
  gap: 0.5rem;
}

.hint {
  color: var(--muted-foreground);
  font-size: 0.875rem;
}

.server {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.serverTitle {
  font-size: 0.875rem;
  font-weight: 500;
}

.serverError {
  color: var(--destructive);
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

.note {
  font-size: 0.75rem;
  color: var(--muted-foreground);
}

.clientRowSelected .note {
  color: var(--primary-foreground);
  opacity: 0.85;
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
