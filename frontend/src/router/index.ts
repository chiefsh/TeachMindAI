import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    {
      path: '/',
      component: () => import('@/components/layout/MainLayout.vue'),
      redirect: '/dashboard',
      children: [
        { path: 'dashboard',    name: 'Dashboard',   component: () => import('@/views/dashboard/DashboardView.vue') },
        { path: 'textbook',     name: 'Textbook',    component: () => import('@/views/textbook/TextbookView.vue') },
        { path: 'question-bank',name: 'QuestionBank',component: () => import('@/views/question-bank/QuestionBankView.vue') },
        { path: 'courseware',   name: 'Courseware',  component: () => import('@/views/courseware/CoursewareView.vue') },
        { path: 'courseware/:id', name: 'CoursewareDetail', component: () => import('@/views/courseware/CoursewareDetail.vue') },
        { path: 'homework',     name: 'Homework',    component: () => import('@/views/homework/HomeworkView.vue') },
        { path: 'grades',       name: 'Grades',      component: () => import('@/views/grades/GradesView.vue') },
        { path: 'settings',     name: 'Settings',    component: () => import('@/views/settings/SettingsView.vue') },
      ],
    },
  ],
})

router.beforeEach((to) => {
  NProgress.start()
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn()) {
    return '/login'
  }
})

router.afterEach(() => NProgress.done())

export default router
