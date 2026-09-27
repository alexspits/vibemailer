<template>
  <section
    :class="$style.createCampaignPage"
    data-test="create-campaign-page"
  >
    <div :class="$style.headerRow">
      <h1 :class="$style.title">
        Новая кампания
      </h1>

      <Button
        :disabled="isLoading"
        variant="outline"
        data-test="cancel-button"
        @click="goBack"
      >
        Отмена
      </Button>
    </div>

    <form
      :class="$style.form"
      data-test="create-campaign-form"
      @submit="onSubmit"
    >
      <FormField
        v-slot="{ componentField }"
        name="name"
      >
        <FormItem>
          <FormLabel>Название</FormLabel>

          <FormControl>
            <Input
              id="name"
              :disabled="isLoading"
              data-test="name-input"
              v-bind="componentField"
            />
          </FormControl>

          <FormMessage data-test="name-error" />
        </FormItem>
      </FormField>

      <FormField
        v-slot="{ componentField }"
        name="subject"
      >
        <FormItem>
          <FormLabel>Тема письма</FormLabel>

          <FormControl>
            <Input
              id="subject"
              :disabled="isLoading"
              data-test="subject-input"
              v-bind="componentField"
            />
          </FormControl>

          <FormMessage data-test="subject-error" />
        </FormItem>
      </FormField>

      <FormField
        v-slot="{ componentField }"
        name="body"
      >
        <FormItem>
          <FormLabel>Текст письма</FormLabel>

          <FormControl>
            <Textarea
              id="body"
              :disabled="isLoading"
              data-test="body-input"
              rows="4"
              v-bind="componentField"
            />
          </FormControl>

          <FormMessage data-test="body-error" />
        </FormItem>
      </FormField>

      <div :class="$style.serversBlock">
        <Label>Серверы рассылки</Label>

        <p :class="$style.hint">
          Конфиги заведутся только на отмеченных серверах. Набор потом не меняется:
          исключить сервер позже — значит удалять уже заведённые строки конфигов.
        </p>

        <div
          v-if="isServersLoading && !enabledServers.length"
          :class="$style.hint"
        >
          Загружаем список серверов…
        </div>

        <p
          v-else-if="!enabledServers.length"
          :class="$style.error"
          data-test="no-servers-note"
        >
          Включённых серверов нет — заведите их на странице «Серверы», иначе конфиги
          заводить будет негде.
        </p>

        <label
          v-for="server in enabledServers"
          :key="server.key"
          :class="$style.serverRow"
          data-test="server-checkbox-row"
        >
          <Checkbox
            :model-value="selectedKeys.includes(server.key)"
            :disabled="isLoading"
            data-test="server-checkbox"
            @update:model-value="(value) => toggleServer(server.key, value === true)"
          />

          <span>
            {{ server.title }}

            <span :class="$style.serverMeta">
              · {{ server.key }} · {{ server.artifact === 'file' ? 'файл' : 'ссылка подписки' }}
            </span>
          </span>
        </label>

        <p
          v-if="enabledServers.length && !selectedKeys.length"
          :class="$style.error"
          data-test="servers-error"
        >
          Выберите хотя бы один сервер.
        </p>
      </div>

      <Button
        :disabled="isSubmitDisabled"
        type="submit"
        data-test="submit-button"
      >
        <LoaderCircle
          v-if="isLoading"
          :class="$style.spinner"
        />

        {{ isLoading ? 'Создание…' : 'Создать' }}
      </Button>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import { toTypedSchema } from '@vee-validate/zod';
import { useForm } from 'vee-validate';
import { useRouter } from 'vue-router';
import { z } from 'zod';

import { LoaderCircle } from '@lucide/vue';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import useCreateCampaign from '@/composables/data/useCreateCampaign';
import useGetServers from '@/composables/data/useGetServers';
import useToast from '@/composables/useToast';

const router = useRouter();
const toast = useToast();

const { isLoading, createCampaign, onDone } = useCreateCampaign();
const { isLoading: isServersLoading, servers, getServers, onDone: onServersLoaded } = useGetServers();

// Набор серверов держим отдельным ref, а не полем формы: галочек столько, сколько
// серверов, и zod-схеме тут делать нечего — проверка одна, «хотя бы один».
const selectedKeys = ref<string[]>([]);

const enabledServers = computed(() => (servers.value ?? []).filter((server) => server.enabled));

const isSubmitDisabled = computed(() => isLoading.value || !selectedKeys.value.length);

function toggleServer(key: string, checked: boolean): void {
  selectedKeys.value = checked
    ? [...selectedKeys.value, key]
    : selectedKeys.value.filter((item) => item !== key);
}

// По умолчанию отмечены все включённые: обычная рассылка идёт на все панели, а
// исключение — редкий случай.
onServersLoaded(() => {
  selectedKeys.value = enabledServers.value.map((server) => server.key);
});

onMounted(getServers);

const formSchema = toTypedSchema(
  z.object({
    name: z
      .string({ required_error: 'Это поле обязательно' })
      .min(1, 'Это поле обязательно')
      .max(255, 'Название слишком длинное'),
    subject: z
      .string({ required_error: 'Это поле обязательно' })
      .min(1, 'Это поле обязательно')
      .max(1024, 'Тема слишком длинная'),
    body: z
      .string({ required_error: 'Это поле обязательно' })
      .min(1, 'Это поле обязательно'),
  }),
);

const { handleSubmit } = useForm({ validationSchema: formSchema });

const onSubmit = handleSubmit((values) => {
  if (!selectedKeys.value.length) {
    return;
  }

  createCampaign({ ...values, servers: selectedKeys.value });
});

onDone(() => {
  toast.success('Кампания создана');

  router.push('/campaigns');
});

function goBack() {
  router.push('/campaigns');
}
</script>

<style module>
.createCampaignPage {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  max-width: 42rem;
}

.headerRow {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title {
  font-size: 1.5rem;
  line-height: 2rem;
  font-weight: 600;
  color: var(--foreground);
}

.form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.serversBlock {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.serverRow {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--foreground);
  cursor: pointer;
}

.serverMeta {
  color: var(--muted-foreground);
  font-size: 0.8125rem;
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
