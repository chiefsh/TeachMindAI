<template>
  <div class="h-full flex flex-col" style="background: var(--sidebar-bg); color: var(--sidebar-text)">
    <div class="h-[60px] flex items-center px-5 gap-2.5 flex-shrink-0">
      <div class="brand-mark w-8 h-8">
        <el-icon class="text-sm"><Reading /></el-icon>
      </div>
      <div class="leading-tight">
        <p class="font-semibold text-[15px] tracking-wide" style="color: var(--sidebar-text-active)">智课星</p>
        <p class="text-[10px] tracking-wider uppercase" style="color: var(--ink-muted)">TeachMind</p>
      </div>
    </div>

    <nav class="flex-1 overflow-y-auto py-2 px-2.5">
      <div v-for="item in navMenu" :key="item.key" class="mb-0.5">
        <router-link
          v-if="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: isChildActive(item.path) }"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </router-link>
        <template v-else>
          <button
            type="button"
            class="nav-item w-full"
            :class="{ 'nav-group-on': isGroupActive(item) }"
            :aria-expanded="expandedKey === item.key"
            @click="$emit('toggle', item)"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span class="flex-1 text-left">{{ item.label }}</span>
            <el-icon
              class="text-[11px] transition-transform duration-150"
              style="color: var(--ink-muted)"
              :class="{ 'rotate-180': expandedKey === item.key }"
            >
              <ArrowDown />
            </el-icon>
          </button>
          <div
            v-show="expandedKey === item.key"
            class="ml-4 pl-2 border-l"
            style="border-color: var(--border)"
          >
            <router-link
              v-for="child in item.children"
              :key="child.path"
              :to="child.path"
              class="nav-item !py-2 !text-[13px]"
              :class="{ active: isChildActive(child.path) }"
            >
              <el-icon><component :is="child.icon" /></el-icon>
              <span>{{ child.label }}</span>
            </router-link>
          </div>
        </template>
      </div>
    </nav>

    <div class="p-2.5 flex-shrink-0" style="border-top: 1px solid var(--border-subtle)">
      <div class="flex items-center gap-2 rounded-xl px-2 py-2 user-row">
        <button
          type="button"
          class="flex items-center gap-2.5 flex-1 min-w-0 text-left"
          @click="$emit('profile')"
        >
          <el-avatar :size="32" class="!bg-indigo-500 text-white flex-shrink-0 text-sm">
            {{ auth.teacher?.real_name?.charAt(0) || '师' }}
          </el-avatar>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium truncate" style="color: var(--sidebar-text-active)">
              {{ auth.teacher?.real_name }}
            </p>
            <p class="text-[11px] truncate" style="color: var(--ink-muted)">{{ auth.teacher?.username }}</p>
          </div>
        </button>
        <el-button link class="logout-btn !px-1" @click="$emit('logout')">
          <el-icon><SwitchButton /></el-icon>
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { ArrowDown } from '@element-plus/icons-vue'

export type NavChild = { path: string; label: string; icon: string; perm?: string }
export type NavItem = {
  key: string
  label: string
  icon: string
  path?: string
  perm?: string
  children?: NavChild[]
}

defineProps<{
  navMenu: NavItem[]
  expandedKey: string
  isChildActive: (path: string) => boolean
  isGroupActive: (item: NavItem) => boolean
}>()

defineEmits<{
  toggle: [item: NavItem]
  profile: []
  logout: []
}>()

const auth = useAuthStore()
</script>

<style scoped>
.nav-item {
  @apply flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm mb-0.5 transition-colors duration-150;
  color: var(--sidebar-text);
}
.nav-item:hover {
  background: #efece4;
  color: var(--sidebar-text-active);
}
.nav-item.active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary-dark-2);
  font-weight: 600;
}
.nav-item .el-icon { @apply text-base; }
.nav-group-on {
  color: var(--el-color-primary-dark-2);
  font-weight: 600;
}
.user-row:hover {
  background: #efece4;
}
.logout-btn {
  color: var(--ink-muted) !important;
}
.logout-btn:hover {
  color: var(--ink) !important;
}
</style>
