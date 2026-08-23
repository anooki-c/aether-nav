<template>
  <div class="mx-auto max-w-6xl px-4 py-6">
    <header class="mb-6 flex items-start justify-between gap-4">
      <div>
        <h1 class="text-headline-lg font-bold text-on-surface">数据异常概览</h1>
        <p class="mt-1 text-body-md text-on-surface-variant">点击下方任意卡片，查看对应的异常链接或分类明细。</p>
      </div>
      <button
        class="flex items-center gap-2 rounded-lg bg-primary-container px-3 py-2 text-label-sm text-on-primary-container transition-colors hover:bg-primary-fixed/60"
        @click="load"
        :disabled="loading"
      >
        <span class="material-symbols-outlined text-[20px]" :class="loading ? 'animate-spin' : ''">refresh</span>
        <span>{{ loading ? '加载中' : '刷新' }}</span>
      </button>
    </header>

    <p v-if="error" class="mb-4 rounded-lg bg-error-container px-4 py-3 text-body-md text-on-error-container">{{ error }}</p>
    <p v-if="notice" class="mb-4 rounded-lg bg-primary-container px-4 py-3 text-body-md text-on-primary-container">{{ notice }}</p>

    <!-- 三个可点击卡片 -->
    <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
      <button
        v-for="p in panels"
        :key="p.key"
        class="group flex flex-col items-start gap-3 rounded-xl border bg-surface p-5 text-left transition-all"
        :class="[
          selected === p.key
            ? p.activeClass + ' ' + p.activeBorder
            : 'border-outline-variant ' + p.hoverBorder + ' hover:bg-surface-container',
        ]"
        @click="toggle(p.key)"
      >
        <div class="flex w-full items-center justify-between">
          <span class="material-symbols-outlined text-[28px]" :class="p.iconClass">{{ p.icon }}</span>
          <span
            class="rounded-full px-2 py-0.5 text-label-sm font-bold"
            :class="p.badgeClass"
          >{{ countOf(p.key) }}</span>
        </div>
        <div>
          <div class="text-headline-md font-bold text-on-surface">{{ p.title }}</div>
          <div class="mt-0.5 text-body-sm text-on-surface-variant">{{ p.desc }}</div>
        </div>
        <div class="text-label-sm" :class="selected === p.key ? 'text-primary' : 'text-on-surface-variant'">
          {{ selected === p.key ? '收起明细 ▲' : '点击查看明细 ▼' }}
        </div>
      </button>
    </div>

    <!-- 明细面板 -->
    <section
      v-if="selected && !loading"
      class="mt-6 rounded-xl border border-outline-variant bg-surface p-5"
    >
      <!-- 零点击链接 -->
      <div v-if="selected === 'zero_click'">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-headline-md font-bold text-on-surface">
            零点击连接 <span class="text-on-surface-variant">({{ data.zero_click_links.length }})</span>
          </h2>
        </div>
        <div v-if="!data.zero_click_links.length" class="py-8 text-center text-body-md text-on-surface-variant">暂无异常 🎉</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-left text-body-md">
            <thead>
              <tr class="border-b border-outline-variant text-on-surface-variant">
                <th class="py-2 pr-4 font-medium">标题</th>
                <th class="py-2 pr-4 font-medium">地址</th>
                <th class="py-2 pr-4 font-medium">分类</th>
                <th class="py-2 pr-4 font-medium">权限</th>
                <th class="py-2 pr-4 font-medium">创建时间</th>
                <th class="py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="l in data.zero_click_links" :key="l.id" class="border-b border-outline-variant/60">
                <td class="py-2 pr-4 text-on-surface">{{ l.title }}</td>
                <td class="py-2 pr-4 max-w-[220px] truncate text-on-surface-variant"><a :href="l.url" target="_blank" class="hover:text-primary hover:underline">{{ l.url || '-' }}</a></td>
                <td class="py-2 pr-4 text-on-surface-variant">{{ l.category_name || '-' }}</td>
                <td class="py-2 pr-4 text-on-surface-variant">{{ permLabel(l.permission) }}</td>
                <td class="py-2 pr-4 text-on-surface-variant">{{ fmtDate(l.created_at) }}</td>
                <td class="py-2"><button class="text-label-sm text-primary hover:underline" @click="goAdmin('links')">去管理</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 空壳子分类 -->
      <div v-else-if="selected === 'empty_category'">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-headline-md font-bold text-on-surface">
            空壳子分类 <span class="text-on-surface-variant">({{ data.empty_categories.length }})</span>
          </h2>
        </div>
        <div v-if="!data.empty_categories.length" class="py-8 text-center text-body-md text-on-surface-variant">暂无异常 🎉</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-left text-body-md">
            <thead>
              <tr class="border-b border-outline-variant text-on-surface-variant">
                <th class="py-2 pr-4 font-medium">分类名</th>
                <th class="py-2 pr-4 font-medium">所属父分类</th>
                <th class="py-2 pr-4 font-medium">权限</th>
                <th class="py-2 pr-4 font-medium">主页显示</th>
                <th class="py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in data.empty_categories" :key="c.id" class="border-b border-outline-variant/60">
                <td class="py-2 pr-4 text-on-surface">
                  <span v-if="c.icon" class="mr-1">{{ c.icon }}</span>{{ c.name }}
                </td>
                <td class="py-2 pr-4 text-on-surface-variant">{{ c.parent_name || '-' }}</td>
                <td class="py-2 pr-4 text-on-surface-variant">{{ permLabel(c.permission) }}</td>
                <td class="py-2 pr-4 text-on-surface-variant">{{ c.visible ? '显示' : '隐藏' }}</td>
                <td class="py-2"><button class="text-label-sm text-primary hover:underline" @click="goAdmin('categories')">去管理</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 无法访问 -->
      <div v-else-if="selected === 'unreachable'">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-headline-md font-bold text-on-surface">
            无法访问 <span class="text-on-surface-variant">({{ data.unreachable_links.length }})</span>
          </h2>
          <button
            class="flex items-center gap-1 rounded-lg bg-surface-container px-3 py-1.5 text-label-sm text-on-surface hover:bg-surface-container-highest"
            @click="repPing"
            :disabled="pinging"
          >
            <span class="material-symbols-outlined text-[18px]" :class="pinging ? 'animate-spin' : ''">radar</span>
            <span>{{ pinging ? '探测中' + progressText : '重新探测' }}</span>
          </button>
        </div>
        <div v-if="!data.unreachable_links.length" class="py-8 text-center text-body-md text-on-surface-variant">暂无异常 🎉</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-left text-body-md">
            <thead>
              <tr class="border-b border-outline-variant text-on-surface-variant">
                <th class="py-2 pr-4 font-medium">标题</th>
                <th class="py-2 pr-4 font-medium">地址</th>
                <th class="py-2 pr-4 font-medium">分类</th>
                <th class="py-2 pr-4 font-medium">最近探测</th>
                <th class="py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="l in data.unreachable_links" :key="l.id" class="border-b border-outline-variant/60">
                <td class="py-2 pr-4 text-on-surface">{{ l.title }}</td>
                <td class="py-2 pr-4 max-w-[220px] truncate text-on-surface-variant"><a :href="l.url" target="_blank" class="hover:text-primary hover:underline">{{ l.url || '-' }}</a></td>
                <td class="py-2 pr-4 text-on-surface-variant">{{ l.category_name || '-' }}</td>
                <td class="py-2 pr-4 text-on-surface-variant">{{ fmtDate(l.ping_at) }}</td>
                <td class="py-2"><button class="text-label-sm text-primary hover:underline" @click="goAdmin('links')">去管理</button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { api } from '../api/client'

const emit = defineEmits(['gotoManage'])
const loading = ref(false)
const pinging = ref(false)
const error = ref('')
const notice = ref('')
const progress = ref(null) // 探测进度 { done, total }，null 表示无进行中探测
const selected = ref(null)
const data = ref({ zero_click_links: [], empty_categories: [], unreachable_links: [] })

const PERM = { all: '所有人', registered: '登录用户', admin: '仅管理员', self: '仅自己' }
function permLabel(p) { return PERM[p] || p || '所有人' }
function fmtDate(s) { return s ? s.slice(0, 10) : '-' }

const panels = computed(() => [
  {
    key: 'zero_click', title: '零点击连接', icon: 'link_off', desc: '从未被点击过的链接',
    iconClass: 'text-tertiary',
    badgeClass: 'bg-tertiary-container text-on-tertiary-container',
    activeClass: 'bg-tertiary-container/40', activeBorder: 'border-tertiary', hoverBorder: 'hover:border-tertiary',
  },
  {
    key: 'empty_category', title: '空壳子分类', icon: 'folder_off', desc: '没有任何链接的子分类',
    iconClass: 'text-secondary',
    badgeClass: 'bg-secondary-container text-on-secondary-container',
    activeClass: 'bg-secondary-container/40', activeBorder: 'border-secondary', hoverBorder: 'hover:border-secondary',
  },
  {
    key: 'unreachable', title: '无法访问', icon: 'wifi_off', desc: '连通性探测不可达的链接',
    iconClass: 'text-error',
    badgeClass: 'bg-error-container text-on-error-container',
    activeClass: 'bg-error-container/40', activeBorder: 'border-error', hoverBorder: 'hover:border-error',
  },
])

function countOf(key) {
  if (key === 'zero_click') return data.value.zero_click_links.length
  if (key === 'empty_category') return data.value.empty_categories.length
  return data.value.unreachable_links.length
}

const progressText = computed(() => {
  const p = progress.value
  if (!p) return ''
  if (!p.total) return ' …'
  return ` ${p.done}/${p.total}`
})

function toggle(key) {
  selected.value = selected.value === key ? null : key
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api.statsAnomalies()
  } catch (e) {
    error.value = '加载失败：' + (e && e.message ? e.message : e)
  } finally {
    loading.value = false
  }
}

async function repPing() {
  if (pinging.value) return
  pinging.value = true
  error.value = ''
  notice.value = ''
  progress.value = { done: 0, total: 0 }
  try {
    const res = await api.pingLinks()
    if (res && res.message) notice.value = res.message
    // 后端在后台线程异步探测（接口立即返回，避免 HTTP 长请求超时）；
    // 每秒轮询一次进度，探测完成后再刷新明细列表
    const timer = setInterval(async () => {
      try {
        const p = await api.pingProgress()
        progress.value = { done: p.done || 0, total: p.total || 0 }
        if (!p.running || (p.total && p.done >= p.total)) {
          clearInterval(timer)
          await load()
          progress.value = null
          notice.value = ''
          pinging.value = false
        }
      } catch (e) {
        clearInterval(timer)
        progress.value = null
        notice.value = ''
        pinging.value = false
      }
    }, 1000)
  } catch (e) {
    error.value = '探测失败：' + (e && e.message ? e.message : e)
    progress.value = null
    pinging.value = false
  }
}

// 通知管理后台切换 tab：链接类异常 → 链接管理；分类类异常 → 分类管理
function goAdmin(target) {
  emit('gotoManage', target)
}

onMounted(load)
</script>
