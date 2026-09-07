import { readonly, ref } from 'vue';

/**
 * Светлая и тёмная тема.
 *
 * Токены обеих тем уже лежат в `style.css` (`:root` и `.dark`), поэтому всё, что нужно
 * снаружи, — держать класс `dark` на `<html>`. Состояние вынесено в модуль, а не в
 * компонент: тему переключают из шапки, а знать о ней должно всё приложение.
 */

export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'vibe-mail-theme';

const theme = ref<Theme>('light');

/** Выбор пользователя, если он был. Приватный режим и запрет хранилища — не ошибка. */
function storedTheme(): Theme | null {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);

    return saved === 'light' || saved === 'dark' ? saved : null;
  } catch {
    return null;
  }
}

function systemTheme(): Theme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function apply(next: Theme): void {
  theme.value = next;

  const root = document.documentElement;
  root.classList.toggle('dark', next === 'dark');
  // Чтобы в тон пришли и вещи, которые рисует сам браузер: полосы прокрутки,
  // выпадающие списки, поля ввода.
  root.style.colorScheme = next;
}

export function setTheme(next: Theme): void {
  apply(next);

  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // Тема просто не переживёт перезагрузку — работать это не мешает.
  }
}

/**
 * Ставит тему до первой отрисовки. Вызывается из `main.ts` перед `mount`, иначе
 * страница на миг моргнёт светлым.
 */
export function initTheme(): void {
  apply(storedTheme() ?? systemTheme());

  // За системной темой следим, пока человек не выбрал сам: после явного выбора
  // переключать интерфейс у него под руками — грубо.
  window
    .matchMedia('(prefers-color-scheme: dark)')
    .addEventListener('change', (event) => {
      if (!storedTheme()) {
        apply(event.matches ? 'dark' : 'light');
      }
    });
}

export default function useTheme() {
  return {
    theme: readonly(theme),
    setTheme,
    toggleTheme: () => setTheme(theme.value === 'dark' ? 'light' : 'dark'),
  };
}
