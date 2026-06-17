<template>
  <div class="rich-editor border border-slate-200 rounded-lg overflow-hidden">
    <!-- 工具栏 -->
    <div class="flex items-center gap-1 px-2 py-1.5 bg-slate-50 border-b border-slate-200">
      <button v-for="t in tools" :key="t.cmd" type="button" :title="t.title"
        class="w-7 h-7 rounded hover:bg-slate-200 text-slate-600 text-sm flex items-center justify-center transition-colors"
        @mousedown.prevent="exec(t.cmd, t.value)">
        <span :class="t.class">{{ t.label }}</span>
      </button>
    </div>
    <!-- 编辑区 -->
    <div
      ref="editorRef"
      contenteditable="true"
      class="editor-area px-3 py-2.5 min-h-[220px] max-h-[45vh] overflow-y-auto text-sm text-slate-700 leading-relaxed focus:outline-none"
      :data-placeholder="placeholder"
      @input="onInput"
      @paste="onPaste"
    ></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'

const props = defineProps<{ modelValue?: string; placeholder?: string }>()
const emit = defineEmits<{
  (e: 'update:modelValue', val: string): void
  (e: 'update:text', val: string): void
}>()

const editorRef = ref<HTMLDivElement | null>(null)

const tools = [
  { cmd: 'bold', label: 'B', title: '加粗', class: 'font-bold', value: '' },
  { cmd: 'italic', label: 'I', title: '斜体', class: 'italic', value: '' },
  { cmd: 'underline', label: 'U', title: '下划线', class: 'underline', value: '' },
  { cmd: 'insertOrderedList', label: '1.', title: '有序列表', class: '', value: '' },
  { cmd: 'insertUnorderedList', label: '•', title: '无序列表', class: '', value: '' },
  { cmd: 'removeFormat', label: '⌫', title: '清除格式', class: '', value: '' },
]

function exec(cmd: string, value = '') {
  document.execCommand(cmd, false, value)
  editorRef.value?.focus()
  emitChange()
}

function emitChange() {
  const el = editorRef.value
  if (!el) return
  emit('update:modelValue', el.innerHTML)
  emit('update:text', el.innerText)
}

function onInput() { emitChange() }

// 粘贴时只保留纯文本，避免带入外部杂乱样式
function onPaste(e: ClipboardEvent) {
  e.preventDefault()
  const text = e.clipboardData?.getData('text/plain') || ''
  document.execCommand('insertText', false, text)
  emitChange()
}

onMounted(() => {
  if (editorRef.value && props.modelValue) {
    editorRef.value.innerHTML = props.modelValue
  }
})

// 外部清空时同步
watch(() => props.modelValue, (val) => {
  const el = editorRef.value
  if (el && val !== el.innerHTML) {
    el.innerHTML = val || ''
  }
})

defineExpose({
  clear() { if (editorRef.value) { editorRef.value.innerHTML = ''; emitChange() } },
  getText() { return editorRef.value?.innerText || '' },
})
</script>

<style scoped>
.editor-area:empty::before {
  content: attr(data-placeholder);
  color: #94a3b8;
}
.editor-area :deep(ul) { list-style: disc; padding-left: 1.4em; }
.editor-area :deep(ol) { list-style: decimal; padding-left: 1.4em; }
</style>
