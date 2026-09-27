<template>
  <Dialog v-model:open="isOpen">
    <DialogScrollContent
      :class="$style.dialogContent"
      data-test="add-server-dialog"
    >
      <DialogHeader>
        <DialogTitle>Добавить сервер</DialogTitle>

        <DialogDescription>
          Сервер допишется в servers.yml. Ключ потом не поменять — он лежит в базе
          у каждого конфига и уезжает в имя вложения.
        </DialogDescription>
      </DialogHeader>

      <div :class="$style.body">
        <div :class="$style.row">
          <div :class="$style.field">
            <Label for="server-key">Ключ</Label>

            <Input
              id="server-key"
              v-model="key"
              placeholder="de3"
              data-test="server-key-input"
            />
          </div>

          <div :class="$style.field">
            <Label for="server-title">Название</Label>

            <Input
              id="server-title"
              v-model="title"
              placeholder="Германия 3 (AmneziaWG)"
              data-test="server-title-input"
            />
          </div>
        </div>

        <div :class="$style.row">
          <div :class="$style.field">
            <Label for="server-panel">Панель</Label>

            <Select v-model="panel">
              <SelectTrigger
                id="server-panel"
                :class="$style.select"
                data-test="server-panel-select"
              >
                <SelectValue placeholder="Выберите панель" />
              </SelectTrigger>

              <SelectContent>
                <SelectItem
                  v-for="option in PANELS"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div :class="$style.field">
            <Label for="server-transport">Как ходим</Label>

            <Select v-model="transport">
              <SelectTrigger
                id="server-transport"
                :class="$style.select"
                data-test="server-transport-select"
              >
                <SelectValue placeholder="Выберите транспорт" />
              </SelectTrigger>

              <SelectContent>
                <SelectItem value="ssh">
                  Через SSH (панель слушает localhost)
                </SelectItem>

                <SelectItem value="direct">
                  Напрямую (панель смотрит наружу)
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div :class="$style.field">
          <Label for="server-base-url">Адрес API панели</Label>

          <Input
            id="server-base-url"
            v-model="baseUrl"
            placeholder="http://127.0.0.1:8080"
            data-test="server-base-url-input"
          />

          <p :class="$style.hint">
            {{ baseUrlHint }}
          </p>
        </div>

        <template v-if="isSsh">
          <Separator />

          <div :class="$style.row">
            <div :class="$style.field">
              <Label for="server-ssh-host">SSH: хост или алиас</Label>

              <Input
                id="server-ssh-host"
                v-model="sshHost"
                placeholder="de3-srv"
                data-test="server-ssh-host-input"
              />

              <p :class="$style.hint">
                Алиас из ~/.ssh/config или обычное имя хоста. Заданное здесь
                перекрывает найденное в ~/.ssh/config.
              </p>
            </div>

            <div :class="$style.field">
              <Label for="server-ssh-user">SSH: пользователь</Label>

              <Input
                id="server-ssh-user"
                v-model="sshUser"
                placeholder="root"
                data-test="server-ssh-user-input"
              />
            </div>
          </div>

          <div :class="$style.row">
            <div :class="$style.field">
              <Label for="server-ssh-port">SSH: порт</Label>

              <Input
                id="server-ssh-port"
                v-model="sshPort"
                inputmode="numeric"
                placeholder="22"
                data-test="server-ssh-port-input"
              />
            </div>

            <div :class="$style.field">
              <Label for="server-ssh-key">SSH: файл ключа</Label>

              <Input
                id="server-ssh-key"
                v-model="sshKeyFile"
                placeholder="~/.ssh/id_ed25519"
                data-test="server-ssh-key-input"
              />
            </div>
          </div>
        </template>

        <template v-if="isXui">
          <Separator />

          <div :class="$style.row">
            <div :class="$style.field">
              <Label for="server-inbounds">3x-ui: inbound_ids</Label>

              <Input
                id="server-inbounds"
                v-model="inboundIds"
                placeholder="1"
                data-test="server-inbounds-input"
              />

              <p :class="$style.hint">
                В какие inbound'ы заводить клиента, через запятую.
              </p>
            </div>

            <div :class="$style.field">
              <Label for="server-flow">3x-ui: flow</Label>

              <Input
                id="server-flow"
                v-model="flow"
                placeholder="xtls-rprx-vision"
                data-test="server-flow-input"
              />

              <p :class="$style.hint">
                Пусто — возьмём то, что стоит у соседей по inbound'у.
              </p>
            </div>
          </div>

          <div :class="$style.field">
            <Label for="server-sub-base">3x-ui: база ссылки подписки</Label>

            <Input
              id="server-sub-base"
              v-model="subBase"
              placeholder="https://sub.example.com/subs/"
              data-test="server-sub-base-input"
            />

            <p :class="$style.hint">
              Нужна, только если панель за прокси и показывает свой внутренний адрес.
              Пусто — спросим саму панель.
            </p>
          </div>
        </template>

        <template v-if="isAmnezia">
          <Separator />

          <div :class="$style.field">
            <Label for="server-panel-server">AmneziaWG: id сервера в панели</Label>

            <Input
              id="server-panel-server"
              v-model="panelServerId"
              data-test="server-panel-server-input"
            />

            <p :class="$style.hint">
              Пусто — возьмём единственный. Если серверов в панели несколько, id
              обязателен: версия протокола задаётся при создании сервера и у каждого своя.
            </p>
          </div>
        </template>

        <template v-if="isFake">
          <Separator />

          <div :class="$style.field">
            <Label for="server-artifact">Заглушка изображает</Label>

            <Select v-model="artifact">
              <SelectTrigger
                id="server-artifact"
                :class="$style.select"
                data-test="server-artifact-select"
              >
                <SelectValue placeholder="Что отдаёт" />
              </SelectTrigger>

              <SelectContent>
                <SelectItem value="file">
                  Файл .conf (как WireGuard)
                </SelectItem>

                <SelectItem value="link">
                  Ссылку подписки (как 3x-ui)
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </template>

        <template v-if="!isFake">
          <Separator />

          <div
            v-if="isXui"
            :class="$style.field"
          >
            <Label for="server-token">Токен API панели</Label>

            <Input
              id="server-token"
              v-model="authToken"
              type="password"
              autocomplete="off"
              data-test="server-token-input"
            />

            <p :class="$style.hint">
              Settings → Security → API Token. На старых версиях токена нет — заполните
              логин и пароль, тогда войдём через /login.
            </p>
          </div>

          <div :class="$style.row">
            <div :class="$style.field">
              <Label for="server-username">Логин панели</Label>

              <Input
                id="server-username"
                v-model="authUsername"
                autocomplete="off"
                data-test="server-username-input"
              />
            </div>

            <div :class="$style.field">
              <Label for="server-password">Пароль панели</Label>

              <Input
                id="server-password"
                v-model="authPassword"
                type="password"
                autocomplete="new-password"
                data-test="server-password-input"
              />
            </div>
          </div>
        </template>

        <Separator />

        <label
          v-if="isHttps"
          :class="$style.checkRow"
        >
          <Checkbox
            :model-value="verifyTls"
            data-test="server-verify-tls"
            @update:model-value="(value) => verifyTls = value === true"
          />

          <span>
            Проверять сертификат панели
            <span :class="$style.hint">
              — снимите, если сертификат самоподписанный или выписан на другое имя
            </span>
          </span>
        </label>

        <label :class="$style.checkRow">
          <Checkbox
            :model-value="enabled"
            data-test="server-enabled"
            @update:model-value="(value) => enabled = value === true"
          />

          <span>
            Включать в новые рассылки
          </span>
        </label>

        <p
          v-if="problem"
          :class="$style.error"
          data-test="add-server-error"
        >
          {{ problem }}
        </p>
      </div>

      <DialogFooter>
        <Button
          :disabled="isLoading"
          variant="outline"
          data-test="add-server-cancel"
          @click="isOpen = false"
        >
          Отмена
        </Button>

        <Button
          :disabled="isLoading || Boolean(problem)"
          data-test="add-server-save"
          @click="onSave"
        >
          <LoaderCircle
            v-if="isLoading"
            :class="$style.spinner"
          />

          Добавить
        </Button>
      </DialogFooter>
    </DialogScrollContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';

import { LoaderCircle } from '@lucide/vue';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogScrollContent,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import useAddServer from '@/composables/data/useAddServer';
import useToast from '@/composables/useToast';
import type { ArtifactKind, PanelKind, TransportKind } from '@/apiService/servers/serversApiTypes';

// Те же ограничения, что и на бэкенде: ключ уезжает в имена вложений и в адреса ручек.
const KEY_RE = /^[a-z0-9][a-z0-9_-]*$/;

const PANELS: { value: PanelKind; label: string }[] = [
  { value: 'amnezia', label: 'AmneziaWG Web UI (файл .conf)' },
  { value: '3x-ui', label: '3x-ui (ссылка подписки)' },
  { value: 'wg-easy', label: 'WireGuard Easy v15 (файл .conf)' },
  { value: 'fake', label: 'Заглушка для разработки' },
];

const DEFAULT_BASE_URL = 'http://127.0.0.1:8080';

const emit = defineEmits<{ added: [] }>();

const isOpen = defineModel<boolean>('open', { default: false });

const toast = useToast();

const { isLoading, addServer, onDone } = useAddServer();

const key = ref('');
const title = ref('');
const panel = ref<PanelKind>('amnezia');
const transport = ref<TransportKind>('ssh');
const baseUrl = ref(DEFAULT_BASE_URL);
const enabled = ref(true);
const verifyTls = ref(true);

const sshHost = ref('');
const sshUser = ref('');
const sshPort = ref('');
const sshKeyFile = ref('');

const authToken = ref('');
const authUsername = ref('');
const authPassword = ref('');

const inboundIds = ref('1');
const flow = ref('');
const subBase = ref('');
const panelServerId = ref('');
const artifact = ref<ArtifactKind>('file');

const isSsh = computed(() => transport.value === 'ssh');
const isXui = computed(() => panel.value === '3x-ui');
const isAmnezia = computed(() => panel.value === 'amnezia');
const isFake = computed(() => panel.value === 'fake');
const isHttps = computed(() => baseUrl.value.trim().startsWith('https'));

const baseUrlHint = computed(() => (isSsh.value
  ? 'Адрес, каким его видит сам сервер: curl запускается на нём. Порт — тот, что панель '
  + 'слушает на сервере, а не локальный из LocalForward в ~/.ssh/config.'
  : 'Полный адрес панели снаружи. Если у панели задан webBasePath, он входит в адрес.'));

const parsedInbounds = computed(() => inboundIds.value
  .split(',')
  .map((part) => part.trim())
  .filter(Boolean)
  .map(Number));

const problem = computed(() => {
  if (!key.value.trim()) {
    return 'Ключ обязателен.';
  }

  if (!KEY_RE.test(key.value.trim())) {
    return 'Ключ: строчные латинские буквы, цифры, дефис и подчёркивание.';
  }

  if (!title.value.trim()) {
    return 'Название обязательно.';
  }

  if (!baseUrl.value.trim()) {
    return 'Адрес API панели обязателен.';
  }

  if (isSsh.value && !sshHost.value.trim()) {
    return 'При доступе через SSH нужен хост.';
  }

  if (isXui.value && !parsedInbounds.value.length) {
    return 'Для 3x-ui нужен хотя бы один inbound_id.';
  }

  if (isXui.value && parsedInbounds.value.some(Number.isNaN)) {
    return 'inbound_ids — числа через запятую.';
  }

  return '';
});

function onSave(): void {
  addServer({
    key: key.value.trim(),
    title: title.value.trim(),
    panel: panel.value,
    transport: transport.value,
    baseUrl: baseUrl.value.trim(),
    enabled: enabled.value,
    verifyTls: verifyTls.value,
    ssh: isSsh.value
      ? {
          host: sshHost.value.trim(),
          user: sshUser.value.trim(),
          port: sshPort.value.trim() ? Number(sshPort.value.trim()) : null,
          keyFile: sshKeyFile.value.trim(),
        }
      : undefined,
    // Заглушке доступы не нужны, а пустой блок auth в файле только мешает читать.
    auth: isFake.value
      ? undefined
      : {
          token: authToken.value.trim(),
          username: authUsername.value.trim(),
          password: authPassword.value,
        },
    inboundIds: isXui.value ? parsedInbounds.value : undefined,
    flow: isXui.value ? flow.value.trim() : undefined,
    subBase: isXui.value ? subBase.value.trim() : undefined,
    panelServerId: isAmnezia.value ? panelServerId.value.trim() : undefined,
    artifact: isFake.value ? artifact.value : undefined,
  });
}

onDone(() => {
  toast.success('Сервер добавлен');
  isOpen.value = false;
  emit('added');
});

// Поля чистим при открытии, а не при закрытии: если добавление упало, диалог
// закрывается с сохранённым вводом, и человек не набирает доступы заново.
watch(isOpen, (opened) => {
  if (!opened) {
    return;
  }

  key.value = '';
  title.value = '';
  sshHost.value = '';
  sshUser.value = '';
  sshPort.value = '';
  sshKeyFile.value = '';
  authToken.value = '';
  authUsername.value = '';
  authPassword.value = '';
  panelServerId.value = '';
  flow.value = '';
  subBase.value = '';
});
</script>

<style module>
.dialogContent {
  max-width: 44rem;
}

.body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-width: 0;
}

.select {
  width: 100%;
}

.checkRow {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--foreground);
  cursor: pointer;
}

.hint {
  color: var(--muted-foreground);
  font-size: 0.8125rem;
}

.error {
  color: var(--destructive);
  font-size: 0.875rem;
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
