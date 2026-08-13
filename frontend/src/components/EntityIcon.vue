<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  // 实体自带的图标值，支持以下来源：
  //  - 图片路径（/uploads/... 或 http(s):// 或 data:） → <img>
  //  - Material Symbols 名称（纯小写字母/数字/下划线） → 系统图标字体
  //  - feather:<name>                                → Feather 内联 SVG
  //  - bx bx-<name> / bxs bxs-<name> / bx-<name>     → Boxicons 字体
  //  - fa-solid fa-<name> / fas fa-<name> 等          → FontAwesome 字体
  //  - 其余非空值按 emoji / 文本原样渲染（兼容历史数据）
  icon: { type: String, default: '' },
  // 取不到图标时兜底的 Material Symbols 名称（不使用无关 emoji 占位）
  fallback: { type: String, default: 'link' },
  size: { type: [Number, String], default: 20 },
  alt: { type: String, default: '' },
  // 头像类场景：图片以 object-cover 填充容器（圆形裁切、无留白）；默认 false 用 object-contain（图标保持完整不被裁切）
  cover: { type: Boolean, default: false },
})

const value = computed(() => (props.icon || '').trim())
const px = computed(() => `${props.size}px`)

// 远程图标地址可能加载不到（无外网 / 内网不可达），失败后回退到 fallback 符号，避免破图
const imgError = ref(false)
watch(value, () => { imgError.value = false })

// 本地磁盘路径（如 D:\icons\a.png）：浏览器无法直接渲染，用占位图标代替，避免显示成乱码文本
const isLocalFsPath = computed(() => /^([A-Za-z]:[\\/]|\\\\|file:\/\/)/.test(value.value))
// 图片路径：本地上传路径(/uploads/...)或远程 http(s)
const isImagePath = computed(
  () => !isLocalFsPath.value && /^(\/|https?:\/\/|data:)/.test(value.value)
)
// 实际以 <img> 渲染：图片路径且未加载失败
const isImage = computed(() => isImagePath.value && !imgError.value)

// Feather 内联 SVG：feather:<name>（图标数据来自 index.html 注入的全局变量 window.feather）
const isFeather = computed(() => /^feather:/i.test(value.value))
const featherSvg = computed(() => {
  if (!isFeather.value) return ''
  const f = (typeof window !== 'undefined' && window.feather && window.feather.icons) || {}
  const name = value.value.replace(/^feather:/i, '').trim()
  const ic = f[name]
  if (!ic) return ''
  try {
    return ic.toSvg(props.size, props.size)
  } catch (e) {
    return ''
  }
})

// Boxicons：bx / bxs 开头
const isBx = computed(() => /^bxs?\b|^bx-/i.test(value.value))
// FontAwesome：fa-solid / fas / far / fal / fab / fa- 开头
const isFa = computed(() => /^fa[bsrl]?\b|^fa-/i.test(value.value))
// Material Symbols：仅小写字母/数字/下划线，如 folder、play_circle
const isSymbol = computed(() => /^[a-z0-9_]+$/.test(value.value))
// 其余非空值视为用户自定义 emoji / 文本图标，原样渲染
const isEmoji = computed(
  () => !!value.value && !isImagePath.value && !isFeather.value && !isBx.value && !isFa.value && !isSymbol.value && !isLocalFsPath.value
)
// 非法或空值时回退到 fallback，避免把图片路径塞进图标字体渲染成乱码
const symbolName = computed(() => (isSymbol.value ? value.value : props.fallback))
</script>

<template>
  <img
    v-if="isImage"
    :src="value"
    :alt="alt"
    :class="cover ? 'w-full h-full object-cover' : 'object-contain shrink-0'"
    :style="cover ? null : { width: px, height: px }"
    @error="imgError = true"
  />
  <span v-else-if="isFeather" class="shrink-0 leading-none" :style="{ color: 'currentColor' }" v-html="featherSvg"></span>
  <i v-else-if="isBx" :class="value" class="shrink-0 leading-none" :style="{ fontSize: px }"></i>
  <i v-else-if="isFa" :class="value" class="shrink-0 leading-none" :style="{ fontSize: px }"></i>
  <span v-else-if="isEmoji" class="shrink-0 leading-none" :style="{ fontSize: px }">{{ value }}</span>
  <span
    v-else
    class="material-symbols-outlined shrink-0 leading-none"
    :style="{ fontSize: px }"
  >{{ symbolName }}</span>
</template>
