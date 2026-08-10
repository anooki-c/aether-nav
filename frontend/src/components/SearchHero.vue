<script setup>
import { ref, watch } from 'vue'
import { store } from '../store'

const props = defineProps({
  // 固定顶部形态：收紧上下留白，避免吸顶条过高
  sticky: { type: Boolean, default: false },
})
const emit = defineEmits(['search'])
const engines = [
  { id: 'local', label: '站内' },
  { id: 'google', label: '谷歌' },
  { id: 'baidu', label: '百度' },
  { id: 'bing', label: '必应' },
]
const engine = ref('local')
const query = ref('')

function onInput() {
  if (engine.value === 'local') emit('search', { engine: 'local', q: query.value })
}

function onEnter() {
  if (engine.value === 'local') {
    emit('search', { engine: 'local', q: query.value })
    return
  }
  const q = encodeURIComponent(query.value)
  const urls = {
    google: `https://www.google.com/search?q=${q}`,
    baidu: `https://www.baidu.com/s?wd=${q}`,
    bing: `https://www.bing.com/search?q=${q}`,
  }
  if (query.value.trim()) window.open(urls[engine.value], '_blank')
}

function pickEngine(e) {
  engine.value = e
  if (e === 'local') emit('search', { engine: 'local', q: query.value })
}

// 移动端底栏"搜索"触发聚焦 + 回到顶部
// 注意：主内容区已是独立滚动容器（#main-scroll），window.scrollTo 无效
const inputEl = ref(null)
watch(
  () => store.searchNonce,
  () => {
    if (inputEl.value) inputEl.value.focus()
    const scroller = document.getElementById('main-scroll')
    if (scroller) scroller.scrollTo({ top: 0, behavior: 'smooth' })
    else window.scrollTo({ top: 0, behavior: 'smooth' })
  }
)
</script>

<template>
  <section
    class="flex flex-col items-center w-full max-w-2xl mx-auto"
    :class="props.sticky ? 'py-3' : 'mt-3 mb-8'"
  >
    <!-- 引擎切换 pill -->
    <div class="flex gap-2 flex-wrap justify-center" :class="props.sticky ? 'mb-3' : 'mb-4'">
      <button
        v-for="e in engines"
        :key="e.id"
        class="px-6 py-2 rounded-full font-headline-sm text-headline-sm transition-[transform,background-color,color] active:scale-95"
        :class="engine === e.id ? 'bg-brand text-white shadow-sm' : 'bg-surface-container text-on-surface-variant hover:bg-surface-variant'"
        @click="pickEngine(e.id)"
      >
        {{ e.label }}
      </button>
    </div>
    <!-- 搜索框 -->
    <div
      class="w-full relative search-focus rounded-xl bg-surface-container-lowest border border-outline-variant shadow-[0_4px_20px_-5px_rgba(108,92,231,0.1)] transition-shadow"
    >
      <span class="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant">search</span>
      <input
        ref="inputEl"
        v-model="query"
        class="w-full pl-12 pr-4 bg-transparent border-none rounded-xl font-body-md text-body-md text-on-background focus:ring-0 placeholder:text-outline outline-none"
        :class="props.sticky ? 'py-3' : 'py-4'"
        placeholder="搜索你的导航…"
        @input="onInput"
        @keyup.enter="onEnter"
      />
    </div>
  </section>
</template>
