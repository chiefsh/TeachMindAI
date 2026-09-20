import { createRouter, createWebHistory } from 'vue-router'
import { nextTick } from 'vue'
import { useAuthStore } from '@/stores/auth'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'

NProgress.configure({ showSpinner: false, trickleSpeed: 120 })

function releasePageLock() {
  document.body.classList.remove('el-popup-parent--hidden')
  document.body.style.removeProperty('overflow')
  document.body.style.removeProperty('padding-right')
  document.body.style.removeProperty('width')
  document.querySelectorAll('body > .el-overlay').forEach((el) => {
    if (el.querySelector('.mobile-nav-drawer, .profile-drawer')) return
    el.remove()
  })
}

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
        { path: 'students',     name: 'Students',    component: () => import('@/views/students/StudentsView.vue'), meta: { perm: 'classroom.view' } },
        { path: 'textbook',     name: 'Textbook',    component: () => import('@/views/textbook/TextbookView.vue'), meta: { perm: 'textbook.view' } },
        { path: 'question-bank',name: 'QuestionBank',component: () => import('@/views/question-bank/QuestionBankView.vue'), meta: { perm: 'question.view' } },
        { path: 'courseware',   name: 'Courseware',  component: () => import('@/views/courseware/CoursewareView.vue'), meta: { perm: 'courseware.view' } },
        { path: 'courseware/:id', name: 'CoursewareDetail', component: () => import('@/views/courseware/CoursewareDetail.vue'), meta: { perm: 'courseware.view' } },
        { path: 'animations',   name: 'Animations',  component: () => import('@/views/animation/AnimationsView.vue'), meta: { perm: 'animation.view' } },
        { path: 'homework',     name: 'Homework',    component: () => import('@/views/homework/HomeworkView.vue'), meta: { perm: 'homework.view' } },
        { path: 'grading',      name: 'Grading',     component: () => import('@/views/grading/GradingView.vue'), meta: { perm: 'grading.view' } },
        { path: 'grading/:id',  name: 'GradingDetail', component: () => import('@/views/grading/GradingDetail.vue'), meta: { perm: 'grading.view' } },
        { path: 'grading/:id/student/:studentId', name: 'GradingStudent', component: () => import('@/views/grading/GradingStudent.vue'), meta: { perm: 'grading.view' } },
        { path: 'wrong-questions', name: 'WrongQuestions', component: () => import('@/views/grading/WrongQuestionsView.vue'), meta: { perm: 'wrong_question.view' } },
        { path: 'question-analysis', name: 'QuestionAnalysis', component: () => import('@/views/question-analysis/QuestionAnalysisView.vue'), meta: { perm: 'analysis.view' } },
        { path: 'question-analysis/:id', name: 'QuestionAnalysisDetail', component: () => import('@/views/question-analysis/QuestionAnalysisDetail.vue'), meta: { perm: 'analysis.view' } },
        { path: 'grades',       name: 'Grades',      component: () => import('@/views/grades/GradesView.vue'), meta: { perm: 'grade.view' } },
        { path: 'knowledge',    name: 'Knowledge',   component: () => import('@/views/knowledge/KnowledgeGraphView.vue'), meta: { perm: 'knowledge.view' } },
        { path: 'users',        name: 'Users',       component: () => import('@/views/org/UsersView.vue'), meta: { perm: 'user.view' } },
        { path: 'roles',        name: 'Roles',       component: () => import('@/views/org/RolesView.vue'), meta: { perm: 'role.view' } },
        { path: 'settings', redirect: '/settings/models' },
        { path: 'settings/profile', redirect: '/dashboard' },
        { path: 'settings/:tab', name: 'Settings', component: () => import('@/views/settings/SettingsView.vue') },
      ],
    },
  ],
})

router.beforeEach(async (to, from) => {
  if (to.fullPath !== from.fullPath) NProgress.start()
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn()) {
    return '/login'
  }
  if (!to.meta.public && auth.isLoggedIn() && !auth.meLoaded) {
    await auth.fetchMe()
    if (!auth.isLoggedIn()) return '/login'
  }
  const perm = to.meta.perm as string | undefined
  if (perm && auth.isLoggedIn() && !auth.can(perm)) {
    return '/dashboard'
  }
  if (to.name === 'Settings' && auth.isLoggedIn()) {
    const tab = String(to.params.tab || '')
    if (tab === 'models' && !auth.can('settings.llm')) return '/dashboard'
    if (tab === 'prompts' && !auth.can('settings.prompt')) return '/dashboard'
  }
})

router.afterEach(() => {
  NProgress.done()
  nextTick(releasePageLock)
})

router.onError(() => {
  NProgress.done()
  nextTick(releasePageLock)
})

export default router
