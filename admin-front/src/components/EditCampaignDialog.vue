<template>
  <Dialog v-model:open="isOpen">
    <DialogContent
      :class="$style.dialogContent"
      data-test="edit-campaign-dialog"
    >
      <DialogHeader>
        <DialogTitle>Изменить письмо</DialogTitle>

        <DialogDescription>
          Править можно, пока рассылка не запущена. После первого отправленного письма
          текст замораживается: иначе люди получили бы разные письма.
        </DialogDescription>
      </DialogHeader>

      <div :class="$style.body">
        <div :class="$style.field">
          <Label for="edit-name">Название</Label>

          <Input
            id="edit-name"
            v-model="name"
            data-test="edit-name-input"
          />
        </div>

        <div :class="$style.field">
          <Label for="edit-subject">Тема письма</Label>

          <Input
            id="edit-subject"
            v-model="subject"
            data-test="edit-subject-input"
          />
        </div>

        <div :class="$style.field">
          <Label for="edit-body">Текст письма</Label>

          <Textarea
            id="edit-body"
            v-model="body"
            :class="$style.textarea"
            rows="12"
            data-test="edit-body-input"
          />

          <p :class="$style.hint">
            Ссылки подписки и инструкция по приложениям добавятся в конец письма сами.
          </p>
        </div>

        <p
          v-if="emptyField"
          :class="$style.error"
          data-test="edit-campaign-error"
        >
          {{ emptyField }} не может быть пустым.
        </p>
      </div>

      <DialogFooter>
        <Button
          :disabled="isSaveDisabled"
          data-test="edit-campaign-save"
          @click="onSave"
        >
          <LoaderCircle
            v-if="isLoading"
            :class="$style.spinner"
          />

          Сохранить
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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import useUpdateCampaign from '@/composables/data/useUpdateCampaign';
import useToast from '@/composables/useToast';
import type { Campaign } from '@/apiService/campaigns/campaignsApiTypes';

interface Props {
  campaign: Campaign | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{ saved: [] }>();

const isOpen = defineModel<boolean>('open', { default: false });

const toast = useToast();

const { isLoading, updateCampaign, onDone } = useUpdateCampaign();

const name = ref('');
const subject = ref('');
const body = ref('');

const emptyField = computed(() => {
  if (!name.value.trim()) {
    return 'Название';
  }

  if (!subject.value.trim()) {
    return 'Тема';
  }

  return body.value.trim() ? '' : 'Текст';
});

const isChanged = computed(() => (
  Boolean(props.campaign)
  && (name.value.trim() !== props.campaign?.name
    || subject.value.trim() !== props.campaign?.subject
    || body.value !== props.campaign?.body)
));

const isSaveDisabled = computed(
  () => isLoading.value || Boolean(emptyField.value) || !isChanged.value,
);

function onSave(): void {
  if (!props.campaign) {
    return;
  }

  // Текст не обрезаем: пустые строки в конце — часть вёрстки письма.
  updateCampaign({
    id: props.campaign.id,
    name: name.value.trim(),
    subject: subject.value.trim(),
    body: body.value,
  });
}

onDone(() => {
  toast.success('Письмо сохранено');
  isOpen.value = false;
  emit('saved');
});

// Значения снимаются при открытии, а не следят за кампанией: полинг обновляет её
// в фоне, и вписанное руками затиралось бы на каждом тике.
watch(isOpen, (opened) => {
  if (opened && props.campaign) {
    name.value = props.campaign.name;
    subject.value = props.campaign.subject;
    body.value = props.campaign.body;
  }
});
</script>

<style module>
.dialogContent {
  max-width: 42rem;
}

.body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-height: 70vh;
  overflow-y: auto;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.textarea {
  min-height: 14rem;
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
