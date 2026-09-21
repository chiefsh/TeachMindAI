<template>
  <div class="h-full flex flex-col" style="background: var(--sidebar-bg); color: var(--sidebar-text)">
    <div class="h-[60px] flex items-center px-4 gap-2.5 flex-shrink-0" style="border-bottom: 1px solid var(--border-subtle)">
      <img src="@/assets/logo-mark.png" alt="知序台" class="w-8 h-8 flex-shrink-0 object-contain" />
      <div class="min-w-0">
        <p class="font-semibold text-[15px] tracking-tight leading-none" style="color: var(--sidebar-text-active)">知序台</p>
        <p class="text-[11px] truncate mt-1.5 leading-none" style="color: var(--ink-muted)">让教学变得有序</p>
      </div>
    </div>

    <nav ref="navRef" class="flex-1 overflow-y-auto py-2 px-2.5">
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
        <details
          v-else
          class="nav-group"
          name="sidebar-nav"
          :data-key="item.key"
          @toggle="$emit('toggle', item, $event)"
          @mouseenter="$emit('prefetch', item)"
        >
          <summary
            class="nav-item w-full"
            :class="{ 'nav-group-on': isGroupActive(item) }"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span class="flex-1 text-left">{{ item.label }}</span>
            <el-icon class="nav-caret text-[11px]" style="color: var(--ink-muted)">
              <ArrowDown />
            </el-icon>
          </summary>
          <div class="ml-4 pl-2 border-l" style="border-color: var(--border)">
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
        </details>
      </div>
    </nav>

    <div class="p-2.5 flex-shrink-0" style="border-top: 1px solid var(--border-subtle)">
      <div class="flex items-center gap-2 rounded-xl px-2 py-2 user-row">
        <button
          type="button"
          class="flex items-center gap-2.5 flex-1 min-w-0 text-left"
          @click="$emit('profile')"
        >
          <el-avatar :size="32" class="text-white flex-shrink-0 text-sm">
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
import { ref, watch, nextTick } from 'vue'
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

const props = defineProps<{
  navMenu: NavItem[]
  expandedKey: string
  isChildActive: (path: string) => boolean
  isGroupActive: (item: NavItem) => boolean
}>()

defineEmits<{
  toggle: [item: NavItem, e?: Event]
  prefetch: [item: NavItem]
  profile: []
  logout: []
}>()

const auth = useAuthStore()
const navRef = ref<HTMLElement | null>(null)

watch(
  () => props.expandedKey,
  (key) => {
    nextTick(() => {
      navRef.value?.querySelectorAll<HTMLDetailsElement>('details.nav-group').forEach((el) => {
        const shouldOpen = el.dataset.key === key
        if (el.open !== shouldOpen) el.open = shouldOpen
      })
    })
  },
  { immediate: true },
)
</script>

<style scoped>
.nav-item {
  @apply flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm mb-0.5;
  color: var(--sidebar-text);
  touch-action: manipulation;
  transition: background 160ms ease, color 160ms ease, box-shadow 160ms ease;
}
.nav-group > summary {
  list-style: none;
  cursor: pointer;
}
.nav-group > summary::-webkit-details-marker {
  display: none;
}
.nav-caret {
  transition: transform 150ms ease;
}
.nav-group[open] .nav-caret {
  transform: rotate(180deg);
}
.nav-item:hover {
  background: var(--hover);
  color: var(--sidebar-text-active);
}
.nav-item.active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary-dark-2);
  font-weight: 600;
  box-shadow: inset 3px 0 0 var(--el-color-primary);
}
.nav-item .el-icon { @apply text-base; }
.nav-group-on {
  color: var(--el-color-primary-dark-2);
  font-weight: 600;
}
.user-row {
  transition: background 160ms ease;
}
.user-row:hover {
  background: var(--hover);
}
.logout-btn {
  color: var(--ink-muted) !important;
}
.logout-btn:hover {
  color: var(--ink) !important;
}
</style>
