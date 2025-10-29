import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('../views/DashboardView.vue')
  },
  {
    path: '/users',
    name: 'users',
    component: () => import('../views/UsersView.vue')
  },
  {
    path: '/users/:id/tasks',
    name: 'UserTasks',
    component: () => import('../views/TasksView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
