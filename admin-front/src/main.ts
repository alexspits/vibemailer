import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'
import { initTheme } from '@/composables/useTheme'

// До монтирования: иначе страница успеет моргнуть светлой темой.
initTheme()

createApp(App).use(router).mount('#app')
