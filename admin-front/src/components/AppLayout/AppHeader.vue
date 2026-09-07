<template>
  <header
    :class="cn(styles.appHeader, $props.class)"
  >
    <div :class="styles.inner">
      <SidebarTrigger :class="styles.trigger" />

      <Separator
        :class="styles.separator"
        orientation="vertical"
      />

      <h1 :class="styles.title">
        Documents
      </h1>

      <button
        :class="styles.themeButton"
        :title="theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'"
        :aria-label="theme === 'dark' ? 'Включить светлую тему' : 'Включить тёмную тему'"
        type="button"
        data-test="theme-toggle"
        @click="toggleTheme"
      >
        <Sun
          v-if="theme === 'dark'"
          :class="styles.themeIcon"
        />

        <Moon
          v-else
          :class="styles.themeIcon"
        />
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import type { HTMLAttributes } from 'vue';
import { useCssModule } from 'vue';

import { Moon, Sun } from '@lucide/vue';
import { Separator } from '@/components/ui/separator';
import { SidebarTrigger } from '@/components/ui/sidebar';
import { cn } from '@/lib/utils';
import useTheme from '@/composables/useTheme';

const styles = useCssModule();

const { theme, toggleTheme } = useTheme();

withDefaults(defineProps<{ class?: HTMLAttributes['class'] }>(), {
  class: undefined,
});
</script>

<style module>
.appHeader {
  display: flex;
  height: var(--header-height);
  flex-shrink: 0;
  align-items: center;
  gap: 0.5rem;
  border-bottom: 1px solid var(--border);
  transition-property: width, height;
  transition-timing-function: linear;
}

.inner {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 0.25rem;
  padding-left: 1rem;
  padding-right: 1rem;
}

@media (min-width: 1024px) {
  .inner {
    gap: 0.5rem;
    padding-left: 1.5rem;
    padding-right: 1.5rem;
  }
}

.trigger {
  margin-left: -0.25rem;
}

.separator {
  margin-left: 0.5rem;
  margin-right: 0.5rem;
}

.title {
  font-size: 1rem;
  line-height: 1.5rem;
  font-weight: 500;
}

/* Прижата вправо: это переключатель, а не часть заголовка. */
.themeButton {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-left: auto;
  width: 2rem;
  height: 2rem;
  border: none;
  border-radius: var(--radius-md);
  background: none;
  color: var(--muted-foreground);
  cursor: pointer;
}

.themeButton:hover {
  background-color: var(--muted);
  color: var(--foreground);
}

.themeIcon {
  width: 1.125rem;
  height: 1.125rem;
}
</style>
