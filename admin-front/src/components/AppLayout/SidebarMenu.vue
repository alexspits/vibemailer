<template>
  <SidebarGroup>
    <SidebarGroupContent>
      <SidebarMenu :class="$style.menu">
        <SidebarMenuItem
          v-for="item in items"
          :key="item.title"
        >
          <SidebarMenuButton
            :is-active="isActive(item.url)"
            as-child
          >
            <RouterLink :to="item.url">
              <component :is="item.icon" />
              <span>{{ item.title }}</span>
            </RouterLink>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarGroupContent>
  </SidebarGroup>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';
import { Home, Inbox, Server } from '@lucide/vue';
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar';

interface NavItem {
  title: string;
  url: string;
  icon: typeof Home;
}

const items: NavItem[] = [
  { title: 'Кампании', url: '/campaigns', icon: Home },
  { title: 'Серверы', url: '/servers', icon: Server },
  { title: 'Тестовая страница', url: '/test', icon: Inbox },
];

const route = useRoute();

const isActive = (url: string): boolean => route.path === url;
</script>

<style module>
.menu {
  gap: 0.25rem;
}
</style>
