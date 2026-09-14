<script setup>
import { ref, watch, computed, onBeforeUnmount } from 'vue'
import { store } from '../store'

const props = defineProps({
  // 固定顶部形态：收紧上下留白，避免吸顶条过高
  sticky: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  localOnly: { type: Boolean, default: false },
  excludeLocal: { type: Boolean, default: false },
  placeholder: { type: String, default: '搜索你的导航…' },
})
const emit = defineEmits(['search'])
const engines = computed(() => store.searchEngines.filter((item) => {
  if (item.enabled === false) return false
  if (props.localOnly) return item.id === 'local'
  if (props.excludeLocal) return item.id !== 'local'
  return true
}))
const engine = ref(props.localOnly ? 'local' : (store.defaultSearchEngine || engines.value[0]?.id || 'local'))
const query = ref('')

watch(() => store.defaultSearchEngine, (value) => {
  if (!props.localOnly && engines.value.some((item) => item.id === value)) engine.value = value
})
watch(engines, (items) => {
  if (!items.some((item) => item.id === engine.value)) engine.value = items[0]?.id || 'local'
})

/* 本地过滤：按键即发请求会让内容区每敲一下都换一遍数据。键盘输入属 100+/天 级动作
   （improve-animations §1），既不该每键一次网络往返，也不该每次重播内容入场。
   这里做 250ms 尾随防抖，只在停顿后查一次；回车提交 / 点「站内」引擎走 flushInput() 立即出结果。 */
let inputTimer = null
function onInput() {
  if (engine.value !== 'local') return
  clearTimeout(inputTimer)
  inputTimer = setTimeout(() => {
    if (engine.value === 'local') emit('search', { engine: 'local', q: query.value })
  }, 250)
}
/* 取消防抖并立即触发，避免回车时还要多等 250ms */
function flushInput() {
  clearTimeout(inputTimer)
  inputTimer = null
  emit('search', { engine: 'local', q: query.value })
}
onBeforeUnmount(() => clearTimeout(inputTimer))

function onEnter() {
  if (engine.value === 'local') {
    flushInput()
    return
  }
  const q = encodeURIComponent(query.value)
  const selected = engines.value.find((item) => item.id === engine.value)
  const url = selected?.url?.replaceAll('{q}', q)
  emit('search', { engine: engine.value, q: query.value })
  if (query.value.trim() && url) window.open(url, '_blank', 'noopener,noreferrer')
}

function pickEngine(e) {
  engine.value = e
  if (e === 'local') flushInput()
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
    class="search-hero flex flex-col items-center w-full mx-auto"
    :class="[props.compact ? 'is-compact max-w-[360px]' : 'max-w-2xl', props.compact ? 'h-full' : (props.sticky ? 'pt-2 pb-4' : 'mt-3 mb-8')]"
  >
    <!-- 引擎切换 pill -->
    <div v-if="!props.compact" class="flex gap-1.5 flex-wrap justify-center" :class="props.sticky ? 'mb-3' : 'mb-4'">
      <button
        v-for="e in engines"
        :key="e.id"
        class="search-engine-pill box-border px-3 py-1.5 rounded-full font-label-sm text-label-sm border border-transparent transition-[transform,background-color,color,box-shadow] active:scale-95"
        :class="engine === e.id ? 'bg-primary-fixed text-primary ring-1 ring-inset ring-primary/40' : 'bg-surface-container text-on-surface-variant hover:bg-surface-variant hover:border-outline-variant'"
        @click="pickEngine(e.id)"
      >
        {{ e.label }}
      </button>
    </div>
    <!-- 搜索框 -->
    <div
      class="search-field w-full relative search-focus rounded-2xl bg-surface-container-lowest border border-outline-variant"
    >
      <span class="material-symbols-outlined ui-icon-hover absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant">search</span>
      <input
        ref="inputEl"
        v-model="query"
        class="w-full pl-12 pr-4 bg-transparent border-none rounded-xl font-body-md text-body-md text-on-background focus:ring-0 placeholder:text-outline outline-none"
        :class="[props.compact ? 'pr-4' : '', props.compact ? 'py-2' : (props.sticky ? 'py-2.5' : 'py-4')]"
        :placeholder="props.placeholder"
        @input="onInput"
        @keyup.enter="onEnter"
      />
    </div>
  </section>
</template>
