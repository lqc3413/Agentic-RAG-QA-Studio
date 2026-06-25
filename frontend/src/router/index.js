import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '@/components/layout/AppShell.vue'
import ChatView from '@/views/ChatView.vue'
import DocumentsView from '@/views/DocumentsView.vue'
import EvalReportsView from '@/views/EvalReportsView.vue'
import LoginView from '@/views/LoginView.vue'
import MemoryView from '@/views/MemoryView.vue'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/',
    component: AppShell,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/chat'
      },
      {
        path: 'chat',
        name: 'chat',
        component: ChatView
      },
      {
        path: 'documents',
        name: 'documents',
        component: DocumentsView
      },
      {
        path: 'eval',
        name: 'eval',
        component: EvalReportsView
      },
      {
        path: 'memory',
        name: 'memory',
        component: MemoryView
      }
    ]
  },
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { guestOnly: true }
  }
]


const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth)
  const guestOnly = to.matched.some((record) => record.meta.guestOnly)

  if (authStore.token && !authStore.user && !authStore.loading) {
    try {
      await authStore.fetchCurrentUser()
    } catch {
      if (requiresAuth) {
        return { name: 'login', query: { redirect: to.fullPath } }
      }
    }
  }

  if (requiresAuth && !authStore.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (guestOnly && authStore.isAuthenticated) {
    return { name: 'chat' }
  }

  return true
})

export default router
