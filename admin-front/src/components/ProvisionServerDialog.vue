<template>
  <Dialog v-model:open="isOpen">
    <DialogScrollContent
      :class="$style.dialogContent"
      data-test="provision-server-dialog"
    >
      <DialogHeader>
        <DialogTitle>Поднять новый сервер</DialogTitle>

        <DialogDescription>
          Плейбук настроит чистый VPS: пользователь с ключом, SSH на своём порту, UFW,
          fail2ban, docker и панель. Это минуты, в конце возможна перезагрузка.
          По успеху сервер допишется в servers.yml выключенным — включите его, когда
          проверите панель.
        </DialogDescription>
      </DialogHeader>

      <div :class="$style.body">
        <div :class="$style.row">
          <div :class="$style.field">
            <Label for="provision-key">Ключ</Label>

            <Input
              id="provision-key"
              v-model="key"
              placeholder="de3"
              data-test="provision-key-input"
            />
          </div>

          <div :class="$style.field">
            <Label for="provision-title">Название</Label>

            <Input
              id="provision-title"
              v-model="title"
              placeholder="Германия 3 (AmneziaWG)"
              data-test="provision-title-input"
            />
          </div>
        </div>

        <div :class="$style.row">
          <div :class="$style.field">
            <Label for="provision-host">IP сервера</Label>

            <Input
              id="provision-host"
              v-model="host"
              placeholder="203.0.113.10"
              data-test="provision-host-input"
            />
          </div>

          <div :class="$style.field">
            <Label for="provision-panel">Панель</Label>

            <Select v-model="panel">
              <SelectTrigger
                id="provision-panel"
                :class="$style.select"
                data-test="provision-panel-select"
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
        </div>

        <Separator />

        <p :class="$style.sectionTitle">
          Первый вход на свежий сервер
        </p>

        <div :class="$style.row">
          <div :class="$style.field">
            <Label for="provision-bootstrap-user">Пользователь</Label>

            <Input
              id="provision-bootstrap-user"
              v-model="bootstrapUser"
              placeholder="root"
              data-test="provision-bootstrap-user-input"
            />

            <p :class="$style.hint">
              У некоторых хостеров это ubuntu. Порт при первом входе всегда 22.
            </p>
          </div>

          <div :class="$style.field">
            <Label for="provision-bootstrap-password">Пароль</Label>

            <Input
              id="provision-bootstrap-password"
              v-model="bootstrapPassword"
              type="password"
              autocomplete="new-password"
              data-test="provision-bootstrap-password-input"
            />

            <p :class="$style.hint">
              Пусто — если хостер уже положил на сервер ваш SSH-ключ.
            </p>
          </div>
        </div>

        <Separator />

        <p :class="$style.sectionTitle">
          Каким сервер станет
        </p>

        <div :class="$style.row">
          <div :class="$style.field">
            <Label for="provision-admin-user">Пользователь</Label>

            <Input
              id="provision-admin-user"
              v-model="adminUser"
              data-test="provision-admin-user-input"
            />
          </div>

          <div :class="$style.field">
            <Label for="provision-ssh-port">Порт SSH</Label>

            <Input
              id="provision-ssh-port"
              v-model="sshPort"
              inputmode="numeric"
              data-test="provision-ssh-port-input"
            />

            <p :class="$style.hint">
              Порт 22 плейбук закроет после того, как войдёт на новый.
            </p>
          </div>
        </div>

        <div :class="$style.field">
          <Label for="provision-admin-password">Пароль пользователя (для VNC-консоли)</Label>

          <Input
            id="provision-admin-password"
            v-model="adminPassword"
            type="password"
            autocomplete="new-password"
            data-test="provision-admin-password-input"
          />

          <p :class="$style.hint">
            Нужен, только чтобы войти через консоль хостера, если SSH сломается.
            По SSH вход всё равно по ключу. Можно оставить пустым.
          </p>
        </div>

        <Separator />

        <p :class="$style.sectionTitle">
          Панель
        </p>

        <div :class="$style.row">
          <div :class="$style.field">
            <Label for="provision-panel-password">Пароль панели</Label>

            <Input
              id="provision-panel-password"
              v-model="panelPassword"
              type="password"
              autocomplete="new-password"
              data-test="provision-panel-password-input"
            />

            <p :class="$style.hint">
              Пусто — сгенерируем сами и покажем после прогона. Свой — не короче
              {{ MIN_PANEL_PASSWORD }} символов.
            </p>
          </div>

          <div :class="$style.field">
            <Label for="provision-panel-port">Порт панели</Label>

            <Input
              id="provision-panel-port"
              v-model="panelPort"
              inputmode="numeric"
              data-test="provision-panel-port-input"
            />

            <p :class="$style.hint">
              Панель слушает только localhost сервера — ходить к ней будем по SSH.
            </p>
          </div>
        </div>

        <div
          v-if="isXui"
          :class="$style.field"
        >
          <Label for="provision-open-ports">Порты inbound'ов</Label>

          <Input
            id="provision-open-ports"
            v-model="openPorts"
            placeholder="443/tcp"
            data-test="provision-open-ports-input"
          />

          <p :class="$style.hint">
            Через запятую; UFW откроет их на сервере. На свежей панели inbound'ов ещё
            нет — можно оставить пустым и открыть порты позже.
          </p>
        </div>

        <div
          v-else
          :class="$style.field"
        >
          <Label for="provision-vpn-ports">UDP-порты VPN</Label>

          <Input
            id="provision-vpn-ports"
            v-model="vpnPorts"
            placeholder="51820"
            data-test="provision-vpn-ports-input"
          />

          <p :class="$style.hint">
            Через запятую. Сервер, созданный в панели, должен слушать порт из этого
            списка, иначе снаружи он будет недоступен.
          </p>
        </div>

        <p
          v-if="problem"
          :class="$style.error"
          data-test="provision-error"
        >
          {{ problem }}
        </p>
      </div>

      <DialogFooter>
        <Button
          :disabled="isLoading || Boolean(problem)"
          data-test="provision-submit"
          @click="onSubmit"
        >
          <LoaderCircle
            v-if="isLoading"
            :class="$style.spinner"
          />

          Поднять сервер
        </Button>
      </DialogFooter>
    </DialogScrollContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';

import { LoaderCircle } from '@lucide/vue';
import { Button } from '@/components/ui/button';
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
import useStartProvision from '@/composables/data/useStartProvision';
import type {
  ProvisionDefaults,
  ProvisionPanel,
  ProvisionRun,
} from '@/apiService/provision/provisionApiTypes';

// Те же ограничения, что и на бэкенде: ключ уезжает в имена вложений и в адреса ручек.
const KEY_RE = /^[a-z0-9][a-z0-9_-]*$/;
const UNIX_USER_RE = /^[a-z_][a-z0-9_-]*$/;
const OPEN_PORT_RE = /^\d{1,5}(\/(tcp|udp))?$/;

// Плейбук откажется ставить панель с паролем короче — скажем об этом в форме.
const MIN_PANEL_PASSWORD = 12;

const PANELS: { value: ProvisionPanel; label: string }[] = [
  { value: 'amneziawg', label: 'AmneziaWG Web UI (файл .conf)' },
  { value: '3x-ui', label: '3x-ui (ссылка подписки)' },
];

interface Props {
  defaults: ProvisionDefaults | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{ started: [run: ProvisionRun] }>();

const isOpen = defineModel<boolean>('open', { default: false });

const { isLoading, run, startProvision, onDone } = useStartProvision();

const key = ref('');
const title = ref('');
const host = ref('');
const panel = ref<ProvisionPanel>('amneziawg');

const bootstrapUser = ref('root');
const bootstrapPassword = ref('');

const adminUser = ref('');
const sshPort = ref('');
const adminPassword = ref('');

const panelPassword = ref('');
const panelPort = ref('');
const openPorts = ref('');
const vpnPorts = ref('');

const isXui = computed(() => panel.value === '3x-ui');

const parsedOpenPorts = computed(() => splitList(openPorts.value));
const parsedVpnPorts = computed(() => splitList(vpnPorts.value));

function splitList(raw: string): string[] {
  return raw.split(',').map((part) => part.trim()).filter(Boolean);
}

function toNumber(raw: string): number {
  return Number(raw.trim());
}

function isPort(value: number): boolean {
  return Number.isInteger(value) && value >= 1 && value <= 65535;
}

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

  if (!host.value.trim()) {
    return 'IP сервера обязателен.';
  }

  if (!UNIX_USER_RE.test(adminUser.value.trim())) {
    return 'Пользователь: имя для Linux — строчные буквы, цифры, _ и -.';
  }

  if (!UNIX_USER_RE.test(bootstrapUser.value.trim())) {
    return 'Пользователь первого входа: имя для Linux.';
  }

  if (!isPort(toNumber(sshPort.value))) {
    return 'Порт SSH: число от 1 до 65535.';
  }

  if (panelPort.value.trim() && !isPort(toNumber(panelPort.value))) {
    return 'Порт панели: число от 1 до 65535.';
  }

  if (panelPassword.value && panelPassword.value.length < MIN_PANEL_PASSWORD) {
    return `Пароль панели короче ${MIN_PANEL_PASSWORD} символов — плейбук такой не примет.`;
  }

  if (isXui.value && parsedOpenPorts.value.some((port) => !OPEN_PORT_RE.test(port))) {
    return 'Порты inbound\'ов: 443 или 443/tcp, через запятую.';
  }

  if (!isXui.value && parsedVpnPorts.value.some((port) => !isPort(Number(port)))) {
    return 'UDP-порты: числа через запятую.';
  }

  return '';
});

function onSubmit(): void {
  startProvision({
    key: key.value.trim(),
    title: title.value.trim(),
    host: host.value.trim(),
    panel: panel.value,
    adminUser: adminUser.value.trim(),
    sshPort: toNumber(sshPort.value),
    bootstrapUser: bootstrapUser.value.trim(),
    bootstrapPassword: bootstrapPassword.value,
    adminPassword: adminPassword.value,
    panelPassword: panelPassword.value,
    panelPort: panelPort.value.trim() ? toNumber(panelPort.value) : undefined,
    openPorts: isXui.value ? parsedOpenPorts.value : undefined,
    vpnPorts: isXui.value ? undefined : parsedVpnPorts.value.map(Number),
  });
}

onDone(() => {
  if (run.value) {
    emit('started', run.value);
  }

  isOpen.value = false;
});

// Порт панели следует за выбранной панелью, пока его не трогали руками: у 3x-ui и
// AmneziaWG умолчания разные, и подставлять чужое было бы хуже, чем ничего.
watch([panel, () => props.defaults], () => {
  if (!props.defaults) {
    return;
  }

  panelPort.value = String(isXui.value ? props.defaults.xuiPort : props.defaults.awgPort);
  vpnPorts.value = props.defaults.awgVpnPorts.join(', ');
});

// Поля чистим при открытии, а не при закрытии: если запуск упал, диалог закрывается
// с сохранённым вводом, и человек не набирает доступы заново.
watch(isOpen, (opened) => {
  if (!opened) {
    return;
  }

  key.value = '';
  title.value = '';
  host.value = '';
  bootstrapPassword.value = '';
  adminPassword.value = '';
  panelPassword.value = '';
  openPorts.value = '';

  if (props.defaults) {
    adminUser.value = props.defaults.adminUser;
    sshPort.value = String(props.defaults.sshPort);
    bootstrapUser.value = props.defaults.bootstrapUser;
    panelPort.value = String(isXui.value ? props.defaults.xuiPort : props.defaults.awgPort);
    vpnPorts.value = props.defaults.awgVpnPorts.join(', ');
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
}

.select {
  width: 100%;
}

.sectionTitle {
  font-weight: 600;
  color: var(--foreground);
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
