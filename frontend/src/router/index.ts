import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    { path: '/s/:token', name: 'SessionPlay', component: () => import('@/views/public/SessionPlay.vue'), meta: { public: true } },
    { path: '/share/:token', name: 'ShareView', component: () => import('@/views/public/ShareView.vue'), meta: { public: true } },
    { path: '/c/:token', name: 'CollectPages', component: () => import('@/views/public/CollectPages.vue'), meta: { public: true } },
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
        { path: 'students',     name: 'Students',    component: () => import('@/views/students/StudentsView.vue') },
        { path: 'homework',     name: 'Homework',    component: () => import('@/views/homework/HomeworkView.vue') },
        { path: 'grading',      name: 'Grading',     component: () => import('@/views/grading/GradingView.vue') },
        { path: 'grading/:id',  name: 'GradingDetail', component: () => import('@/views/grading/GradingDetail.vue') },
        { path: 'grading/:id/student/:studentId', name: 'GradingStudent', component: () => import('@/views/grading/GradingStudent.vue') },
        { path: 'wrong-questions', name: 'WrongQuestions', component: () => import('@/views/grading/WrongQuestionsView.vue') },
        { path: 'question-analysis', name: 'QuestionAnalysis', component: () => import('@/views/question-analysis/QuestionAnalysisView.vue') },
        { path: 'question-analysis/:id', name: 'QuestionAnalysisDetail', component: () => import('@/views/question-analysis/QuestionAnalysisDetail.vue') },
        { path: 'grades',       name: 'Grades',      component: () => import('@/views/grades/GradesView.vue') },
        { path: 'knowledge',    name: 'Knowledge',   component: () => import('@/views/knowledge/KnowledgeGraphView.vue') },
        { path: 'settings', redirect: '/settings/profile' },
        { path: 'settings/:tab', name: 'Settings', component: () => import('@/views/settings/SettingsView.vue') },
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
