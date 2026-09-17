<template>
  <Dialog v-model:open="isOpen">
    <DialogContent
      :class="$style.dialogContent"
      data-test="suggest-all-dialog"
    >
      <DialogHeader>
        <DialogTitle>Найти всех на панелях</DialogTitle>

        <DialogDescription>
          Ищем каждого получателя кампании на всех серверах разом. Уверенные совпадения
          отмечены заранее, спорные — нет. Ненайденное останется пустым: эти конфиги
          привяжете вручную или сгенерируете новыми.
        </DialogDescription>
      </DialogHeader>

      <div :class="$style.body">
        <p
          v-if="isSearching"
          :class="$style.hint"
        >
          Читаем списки клиентов со всех панелей…
        </p>

        <p
          v-else-if="failed"
          :class="$style.serverError"
          data-test="suggest-all-failed"
        >
          Подбор не удался — списки клиентов прочитать не смогли. Это не «никого не
          нашлось»: повторите позже.
        </p>

        <template v-else-if="!failed">
          <div
            v-for="person in found"
            :key="person.recipientId"
            :class="$style.person"
          >
            <p :class="$style.personTitle">
              {{ person.email }}
              <span :class="$style.note">{{ person.clientName }}</span>
            </p>

            <div
              v-for="server in withCandidates(person)"
              :key="server.serverKey"
              :class="$style.serverRow"
            >
              <span :class="$style.serverTitle">{{ server.serverTitle }}</span>

              <div :class="$style.chips">
                <button
                  v-for="candidate in server.candidates"
                  :key="candidate.name"
                  :class="[
                    $style.chip,
                    isChecked(person.recipientId, server.serverKey, candidate.name)
                      ? $style.chipSelected : '',
                    candidate.takenBy ? $style.chipTaken : '',
                  ]"
                  :disabled="Boolean(candidate.takenBy)"
                  :title="candidate.takenBy ? `Занят ${candidate.takenBy}` : ''"
                  type="button"
                  data-test="suggest-all-chip"
                  @click="toggle(person.recipientId, server.serverKey, candidate.name)"
                >
                  {{ candidate.name }}
                </button>
              </div>
            </div>
          </div>

          <p
            v-if="missing.length"
            :class="$style.hint"
            data-test="suggest-all-missing"
          >
            Не нашлись нигде: {{ missing.map((person) => person.email).join(', ') }}.
          </p>

          <p
            v-for="server in brokenServers"
            :key="server.serverKey"
            :class="$style.serverError"
          >
            {{ server.serverTitle }}: панель не ответила, подбор по ней не делался.
          </p>
        </template>

        <p
          :class="$style.hint"
          data-test="suggest-all-summary"
        >
          {{ summary }}
        </p>
      </div>

      <DialogFooter>
        <Button
          :disabled="isBindDisabled"
          data-test="suggest-all-bind"
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

import { LoaderCircle } from '@lucide/vue';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import useBindSuggestions from '@/composables/data/useBindSuggestions';
import useSuggestClients from '@/composables/data/useSuggestClients';
import useToast from '@/composables/useToast';
import type {
  BindSuggestionItem,
  RecipientSuggestion,
  ServerSuggestion,
} from '@/apiService/campaigns/campaignsApiTypes';

interface Props {
  campaignId: number;
}

const props = defineProps<Props>();

const emit = defineEmits<{ bound: [] }>();

const isOpen = defineModel<boolean>('open', { default: false });

const toast = useToast();

const {
  isLoading: isSearching,
  hasError: failed,
  suggestions,
  suggestClients,
  onDone: onSearchDone,
} = useSuggestClients();

const {
  isLoading: isBinding,
  summary: bindSummary,
  bindSuggestions,
  onDone: onBindDone,
} = useBindSuggestions();

// «id получателя:ключ сервера» → отмеченные имена. Плоский ключ, потому что вложенные
// словари в реактивности Vue приходится пересобирать целиком на каждый клик.
const checked = ref<Record<string, Set<string>>>({});

const people = computed(() => suggestions.value ?? []);

const found = computed(
  () => people.value.filter((person) => withCandidates(person).length),
);

const missing = computed(
  () => people.value.filter((person) => !withCandidates(person).length),
);

/** Панели, которые не ответили: общие для всех, поэтому берём у первого же. */
const brokenServers = computed(
  () => (people.value[0]?.servers ?? []).filter((server) => server.error),
);

const totalChecked = computed(
  () => Object.values(checked.value).reduce((sum, names) => sum + names.size, 0),
);

const summary = computed(() => {
  if (isSearching.value || failed.value) {
    return '';
  }

  if (!people.value.length) {
    return 'В кампании нет получателей.';
  }

  const base = `Нашли для ${found.value.length} из ${people.value.length}.`;

  return totalChecked.value
    ? `${base} Отмечено ${totalChecked.value} — столько конфигов и привяжется.`
    : `${base} Ничего не отмечено — выберите нужных.`;
});

const isBindDisabled = computed(() => isBinding.value || isSearching.value || !totalChecked.value);

function withCandidates(person: RecipientSuggestion): ServerSuggestion[] {
  return person.servers.filter((server) => server.candidates.length);
}

function key(recipientId: number, serverKey: string): string {
  return `${recipientId}:${serverKey}`;
}

function isChecked(recipientId: number, serverKey: string, name: string): boolean {
  return Boolean(checked.value[key(recipientId, serverKey)]?.has(name));
}

function toggle(recipientId: number, serverKey: string, name: string): void {
  const id = key(recipientId, serverKey);
  const next = { ...checked.value };
  const names = new Set(next[id] ?? []);

  if (names.has(name)) {
    names.delete(name);
  } else {
    names.add(name);
  }

  next[id] = names;
  checked.value = next;
}

function onBind(): void {
  const items: BindSuggestionItem[] = Object.entries(checked.value)
    .filter(([, names]) => names.size)
    .map(([id, names]) => {
      const [recipientId, serverKey] = id.split(':');

      return { recipientId: Number(recipientId), serverKey, names: [...names] };
    });

  bindSuggestions({ id: props.campaignId, items });
}

onSearchDone(() => {
  const next: Record<string, Set<string>> = {};

  for (const person of people.value) {
    for (const server of person.servers) {
      const names = server.candidates.filter((c) => c.suggested).map((c) => c.name);

      if (names.length) {
        next[key(person.recipientId, server.serverKey)] = new Set(names);
      }
    }
  }

  checked.value = next;
});

onBindDone(() => {
  const summaryValue = bindSummary.value;

  toast.success(
    summaryValue
      ? `Привязано ${summaryValue.bound} у ${summaryValue.recipients} получателей`
      : 'Клиенты привязаны',
  );

  isOpen.value = false;
  emit('bound');
});

watch(isOpen, (opened) => {
  checked.value = {};

  if (opened) {
    suggestClients({ id: props.campaignId });
  }
});
</script>

<style module>
.dialogContent {
  max-width: 44rem;
}

.body {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-height: 60vh;
  overflow-y: auto;
}

.hint {
  color: var(--muted-foreground);
  font-size: 0.875rem;
}

.serverError {
  color: var(--destructive);
  font-size: 0.875rem;
}

.person {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}

.personTitle {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.note {
  font-size: 0.75rem;
  font-weight: 400;
  color: var(--muted-foreground);
}

.serverRow {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.serverTitle {
  flex: none;
  width: 13rem;
  font-size: 0.8125rem;
  color: var(--muted-foreground);
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.chip {
  padding: 0.125rem 0.5rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: none;
  color: var(--foreground);
  font-size: 0.8125rem;
  cursor: pointer;
}

.chip:hover:not(:disabled) {
  background-color: var(--muted);
}

.chipSelected,
.chipSelected:hover:not(:disabled) {
  background-color: var(--primary);
  border-color: var(--primary);
  color: var(--primary-foreground);
  font-weight: 500;
}

.chipTaken {
  color: var(--muted-foreground);
  cursor: not-allowed;
  text-decoration: line-through;
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
