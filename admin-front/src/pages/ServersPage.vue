<template>
  <section
    :class="$style.serversPage"
    data-test="servers-page"
  >
    <div :class="$style.headerRow">
      <h1 :class="$style.title">
        Серверы
      </h1>

      <div :class="$style.headerActions">
        <Button
          :disabled="isChecking || !serversList.length"
          variant="outline"
          data-test="check-all-button"
          @click="checkAll"
        >
          <LoaderCircle
            v-if="isChecking"
            :class="$style.spinner"
          />

          Проверить все
        </Button>

        <Button
          variant="outline"
          data-test="add-server-button"
          @click="isAddOpen = true"
        >
          Добавить сервер
        </Button>
      </div>
    </div>

    <p :class="$style.subtitle">
      Панели, с которых берутся конфиги. Выключенный сервер остаётся в списке, но
      в новые рассылки не попадает; уже заведённые конфиги он не теряет.
    </p>

    <div :class="$style.tableWrap">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Ключ</TableHead>
            <TableHead>Название</TableHead>
            <TableHead>Панель</TableHead>
            <TableHead>Куда ходим</TableHead>
            <TableHead>Конфиги</TableHead>
            <TableHead>В рассылках</TableHead>
            <TableHead>Проверка</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>

        <TableBody>
          <template v-if="isInitialLoading">
            <TableRow
              v-for="n in 3"
              :key="n"
              data-test="server-skeleton-row"
            >
              <TableCell><Skeleton :class="$style.skKey" /></TableCell>
              <TableCell><Skeleton :class="$style.skTitle" /></TableCell>
              <TableCell><Skeleton :class="$style.skKey" /></TableCell>
              <TableCell><Skeleton :class="$style.skWhere" /></TableCell>
              <TableCell><Skeleton :class="$style.skKey" /></TableCell>
              <TableCell><Skeleton :class="$style.skKey" /></TableCell>
              <TableCell><Skeleton :class="$style.skWhere" /></TableCell>
              <TableCell><Skeleton :class="$style.skKey" /></TableCell>
            </TableRow>
          </template>

          <template v-else>
            <TableEmpty
              v-if="!serversList.length"
              :colspan="8"
            >
              Серверов нет — добавьте первый
            </TableEmpty>

            <TableRow
              v-for="server in serversList"
              v-else
              :key="server.key"
              data-test="server-row"
            >
              <TableCell :class="$style.mono">
                {{ server.key }}
              </TableCell>

              <TableCell>{{ server.title }}</TableCell>

              <TableCell>
                {{ server.panel }}
                <span :class="$style.muted">
                  · {{ server.artifact === 'file' ? 'файл' : 'ссылка' }}
                </span>
              </TableCell>

              <TableCell :class="$style.where">
                {{ server.where }}
              </TableCell>

              <TableCell>
                {{ server.configs }}

                <span
                  v-if="server.unfinished"
                  :class="$style.muted"
                >
                  · не готовы {{ server.unfinished }}
                </span>
              </TableCell>

              <TableCell>
                <Switch
                  :model-value="server.enabled"
                  :disabled="isUpdating"
                  :aria-label="`Сервер ${server.title} в рассылках по умолчанию`"
                  data-test="server-enabled-switch"
                  @update:model-value="(value) => onToggle(server, value === true)"
                />
              </TableCell>

              <TableCell>
                <div :class="$style.checkCell">
                  <Button
                    :disabled="isChecking"
                    variant="ghost"
                    size="sm"
                    data-test="check-server-button"
                    @click="checkOne(server.key)"
                  >
                    <LoaderCircle
                      v-if="checkingKey === server.key"
                      :class="$style.spinner"
                    />

                    Проверить
                  </Button>

                  <Badge
                    v-if="results[server.key]"
                    :class="results[server.key].ok ? $style.badgeOk : $style.badgeFail"
                    :title="resultTitle(results[server.key])"
                    data-test="server-check-result"
                  >
                    {{ resultLabel(results[server.key]) }}
                  </Badge>
                </div>
              </TableCell>

              <TableCell>
                <Button
                  :aria-label="`Удалить сервер ${server.title}`"
                  variant="ghost"
                  size="icon"
                  data-test="delete-server-button"
                  @click="openDelete(server)"
                >
                  <Trash :class="$style.iconBtn" />
                </Button>
              </TableCell>
            </TableRow>
          </template>
        </TableBody>
      </Table>
    </div>

    <AlertDialog v-model:open="isDeleteOpen">
      <AlertDialogContent data-test="delete-server-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle>Удалить сервер?</AlertDialogTitle>

          <AlertDialogDescription>
            <template v-if="pendingServer?.configs">
              Сервер «{{ pendingServer?.title }}» уберётся из списка, но на него
              ссылаются конфиги в рассылках: {{ pendingServer?.configs }}. Эти строки
              останутся в базе как история — генерировать по ним будет нечем.
              Клиентов на самой панели никто не тронет.
            </template>

            <template v-else>
              Сервер «{{ pendingServer?.title }}» уберётся из списка. Конфигов на него
              в рассылках нет, так что терять нечего.
            </template>
          </AlertDialogDescription>
        </AlertDialogHeader>

        <AlertDialogFooter>
          <Button
            :disabled="isDeleting"
            variant="outline"
            data-test="cancel-delete-server"
            @click="isDeleteOpen = false"
          >
            Отмена
          </Button>

          <Button
            :disabled="isDeleting"
            variant="destructive"
            data-test="confirm-delete-server"
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

    <AddServerDialog
      v-model:open="isAddOpen"
      @added="load"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import { LoaderCircle, Trash } from '@lucide/vue';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableEmpty,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import AddServerDialog from '@/components/AddServerDialog.vue';
import useCheckServer from '@/composables/data/useCheckServer';
import useDeleteServer from '@/composables/data/useDeleteServer';
import useGetServers from '@/composables/data/useGetServers';
import useUpdateServer from '@/composables/data/useUpdateServer';
import useToast from '@/composables/useToast';
import type { Server, ServerCheckResult } from '@/apiService/servers/serversApiTypes';

const toast = useToast();

const { servers, getServers: load, onDone: onLoaded, onError: onLoadFailed } = useGetServers();
const { isLoading: isUpdating, server: updatedServer, updateServer, onDone: onUpdated } = useUpdateServer();
const { isLoading: isDeleting, detail: deleteDetail, deleteServer, onDone: onDeleted } = useDeleteServer();
const {
  isLoading: isChecking,
  result: checkResult,
  checkServer,
  onDone: onChecked,
  onError: onCheckFailed,
} = useCheckServer();

const isInitialLoading = ref(true);
const isAddOpen = ref(false);
const isDeleteOpen = ref(false);
const pendingServer = ref<Server | null>(null);

const results = ref<Record<string, ServerCheckResult>>({});
const checkingKey = ref('');
// Очередь «проверить все»: панели опрашиваются по одной, каждая — отдельный заход
// по SSH, и четыре одновременных сессии ради секунды выигрыша не нужны.
const queue = ref<string[]>([]);

const serversList = computed(() => servers.value ?? []);

function resultLabel(result: ServerCheckResult): string {
  if (!result.ok) {
    return 'не отвечает';
  }

  const parts = [`клиентов ${result.clients ?? 0}`];

  if (result.protocol) {
    parts.push(result.protocol);
  }

  return parts.join(' · ');
}

function resultTitle(result: ServerCheckResult): string {
  if (!result.ok) {
    return result.hint ? `${result.error}\n\nПодсказка: ${result.hint}` : result.error;
  }

  const lines = [`Ответила за ${result.elapsedMs} мс`];

  if (result.sample.length) {
    lines.push(`Например: ${result.sample.join(', ')}`);
  }

  if (result.subscription) {
    lines.push(`Подписка: ${result.subscription}<имя конфига>`);
  }

  return lines.join('\n');
}

function checkOne(key: string): void {
  checkingKey.value = key;
  checkServer({ serverKey: key });
}

function checkAll(): void {
  queue.value = serversList.value.map((server) => server.key);
  checkNext();
}

function checkNext(): void {
  const next = queue.value.shift();

  if (next === undefined) {
    checkingKey.value = '';
    return;
  }

  checkOne(next);
}

function onToggle(server: Server, enabled: boolean): void {
  updateServer({ key: server.key, enabled });
}

function openDelete(server: Server): void {
  pendingServer.value = server;
  isDeleteOpen.value = true;
}

function confirmDelete(): void {
  if (!pendingServer.value) {
    return;
  }

  // force всегда: про оставшиеся конфиги в диалоге уже сказано, и второй отказ от
  // бэкенда человеку ничего не добавит.
  deleteServer({ key: pendingServer.value.key, force: true });
}

onLoaded(() => {
  isInitialLoading.value = false;
});

onLoadFailed(() => {
  isInitialLoading.value = false;
});

onUpdated(() => {
  const server = updatedServer.value;

  if (!server) {
    return;
  }

  toast.success(
    server.enabled
      ? `${server.title}: включён в рассылки по умолчанию`
      : `${server.title}: исключён из рассылок по умолчанию`,
  );

  // Незаполненные конфиги на выключенном сервере не дадут запустить рассылку: кнопок
  // генерации у него больше нет, а валидация всё ещё требует готовый конфиг.
  if (!server.enabled && server.unfinished) {
    toast.info(
      `В рассылках осталось незаполненных конфигов на этом сервере: ${server.unfinished}. `
      + 'Такие рассылки не запустятся, пока строки не удалить.',
    );
  }

  load();
});

onDeleted(() => {
  toast.success(deleteDetail.value ?? 'Сервер удалён');
  isDeleteOpen.value = false;
  pendingServer.value = null;
  load();
});

onChecked(() => {
  if (checkResult.value) {
    results.value[checkResult.value.key] = checkResult.value;
  }

  checkNext();
});

onCheckFailed(() => {
  // Обрываем пачку: если не отвечает сама программа, следующие проверки дадут то же
  // самое, только тостов будет четыре.
  queue.value = [];
  checkingKey.value = '';
});

onMounted(load);
</script>

<style module>
.serversPage {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.headerRow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.headerActions {
  display: flex;
  gap: 0.5rem;
}

.title {
  font-size: 1.5rem;
  line-height: 2rem;
  font-weight: 600;
  color: var(--foreground);
}

.subtitle {
  color: var(--muted-foreground);
  max-width: 60rem;
}

.tableWrap {
  overflow-x: auto;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.where {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8125rem;
  color: var(--muted-foreground);
  max-width: 22rem;
  overflow-wrap: anywhere;
}

.muted {
  color: var(--muted-foreground);
  font-size: 0.8125rem;
}

.checkCell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
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

.iconBtn {
  width: 1rem;
  height: 1rem;
}

.skKey {
  width: 4rem;
  height: 1rem;
}

.skTitle {
  width: 10rem;
  height: 1rem;
}

.skWhere {
  width: 14rem;
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
</style>
