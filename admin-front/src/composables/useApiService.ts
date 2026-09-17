import { ref, type Ref } from 'vue';
import useToast from '@/composables/useToast';

interface UseApiServiceOptions {
  errorMessage?: string;
}

export interface UseApiServiceResult<T, V extends unknown[] = []> {
  isLoading: Ref<boolean>;
  data: Ref<T | null>;
  /** Последний вызов закончился ошибкой. Нужен, чтобы «не смогли прочитать» не
   *  выглядело как «ничего не нашлось»: на втором человек заводит клиентов заново. */
  hasError: Ref<boolean>;
  execute: (...args: V) => void;
  onDone: (cb: () => void) => void;
  onError: (cb: () => void) => void;
}

export default function useApiService<T, V extends unknown[] = []>(
  apiServiceMethod: (...args: V) => Promise<T>,
  options?: UseApiServiceOptions,
): UseApiServiceResult<T, V> {
  const isLoading = ref<boolean>(false);
  const data: Ref<T | null> = ref(null);
  const hasError = ref<boolean>(false);

  let onDoneCb: (() => void) | undefined;
  let onErrorCb: (() => void) | undefined;

  const onDone = (cb: () => void) => {
    onDoneCb = cb;
  };

  const onError = (cb: () => void) => {
    onErrorCb = cb;
  };

  const execute = async (...args: V) => {
    isLoading.value = true;
    hasError.value = false;

    try {
      const response = await apiServiceMethod(...args);

      data.value = response;

      if (typeof onDoneCb === 'function') {
        onDoneCb();
      }
    } catch (e) {
      console.error(e);

      // Данные прошлого вызова стираем: иначе диалог, открытый для другого получателя
      // или сервера, покажет то, что нашлось в прошлый раз, и человек привяжет чужое.
      data.value = null;
      hasError.value = true;

      if (options?.errorMessage) {
        // Текст от бэкенда дописываем: он конкретный («Неизвестные серверы: de2»),
        // а общее «не удалось» не говорит, что именно чинить.
        const detail = e instanceof Error ? e.message : '';

        useToast().error(detail ? `${options.errorMessage}: ${detail}` : options.errorMessage);
      }

      if (typeof onErrorCb === 'function') {
        onErrorCb();
      }
    } finally {
      isLoading.value = false;
    }
  };

  return {
    isLoading,
    data,
    hasError,
    execute,
    onDone,
    onError,
  };
}
