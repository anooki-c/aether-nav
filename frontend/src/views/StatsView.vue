<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { api } from '../api/client'

const Chart = window.Chart

/* ── 控制项（全局筛选器） ───────────────────────────── */
const days = ref(30)
const customDays = ref(30)
const topN = ref(10)
const dim = ref('link') // link / parent / child
const compare = ref(true)
const drillParent = ref(null)
const userSort = ref('total')
const userId = ref(null) // TOP 排行按人员筛选（局部，不影响其他区块）

/* ── 状态 ───────────────────────────────────────────── */
const loading = ref(true)
const error = ref('')
const data = ref({})

/* 热力图：选中日期 + 单日明细 */
const selectedDate = ref(null)
const dayDetail = ref(null)
const dayLoading = ref(false)

/* ── 设计 token ─────────────────────────────────────── */
const PALETTE = ['#5341CD', '#10B981', '#3B82F6', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4', '#EC4899', '#84CC16', '#F97316']
const CLICK_COLOR = '#5341CD'
const LOGIN_COLOR = '#10B981'
const GRID_COLOR = 'rgba(71,69,84,0.08)'
const TEXT_MUTED = '#474554'
const TEXT_PRIMARY = '#1c1b23'

/* ── 画布 ref ───────────────────────────────────────── */
const trendCanvas = ref(null)
const topCanvas = ref(null)
const permCanvas = ref(null)
const catCanvas = ref(null)
const memberCanvas = ref(null)
const newUsersCanvas = ref(null)
const charts = {}

/* ── 计算属性 ───────────────────────────────────────── */
const kpis = computed(() => data.value.kpis || {})
const kpisPrev = computed(() => data.value.kpis_prev || {})
const trend = computed(() => data.value.trend || { labels: [], clicks: [], logins: [] })
const top = computed(() => data.value.top || { dim: 'link', items: [] })
const permission = computed(() => data.value.permission || { link_states: [], roles: [], denied_rules: 0 })
const categoryShare = computed(() => data.value.category_share || [])
const members = computed(() => data.value.members || [])
const users = computed(() => data.value.users || [])
const userOptions = computed(() => data.value.user_options || [])
const health = computed(() => data.value.health || {})
const linkPing = computed(() => data.value.link_ping || { unreachable: 0, reachable: 0, unchecked: 0, last_ping_at: null })
const retention = computed(() => data.value.retention || {})
const newUsers = computed(() => data.value.new_users || { labels: [], count: [] })

const dayHourly = computed(() => dayDetail.value?.hourly || Array(24).fill(0))
const dayHourlyMax = computed(() => Math.max(1, ...dayHourly.value))
const dayMax = computed(() => Math.max(1, ...(trend.value.clicks || [0])))

const weekly = computed(() => data.value.weekly || Array(7).fill(0))
const weekLabels = ['一', '二', '三', '四', '五', '六', '日']
const selectedUserName = computed(() => {
  if (!userId.value) return ''
  const u = userOptions.value.find((x) => x.id === userId.value)
  return u ? (u.display_name || u.username) : ''
})

const sortedUsers = computed(() => {
  const arr = [...users.value]
  arr.sort((a, b) => (b[userSort.value] || 0) - (a[userSort.value] || 0))
  return arr
})

function pctDelta(cur, prev) {
  if (!prev || prev <= 0) return null
  return Math.round(((cur - prev) / prev) * 1000) / 10
}

const colorMap = {
  primary: { bg: 'bg-primary/10', fg: 'text-primary' },
  success: { bg: 'bg-success/10', fg: 'text-success' },
  info:    { bg: 'bg-info/10',    fg: 'text-info' },
  warning: { bg: 'bg-warning/10', fg: 'text-warning' },
}

/* 一行 3 个合并 KPI 卡片 */
const kpiList = computed(() => {
  const k = kpis.value
  const p = kpisPrev.value
  const mk = (primaryLabel, primaryValue, secondaryLabel, secondaryValue, delta, icon, color) =>
    ({ primaryLabel, primaryValue, secondaryLabel, secondaryValue, delta, icon, color, bg: colorMap[color].bg, fg: colorMap[color].fg })
  return [
    mk('总用户数', k.total_users, '活跃用户', k.active_users, pctDelta(k.active_users, p.active_users), 'group', 'primary'),
    mk('链接总数', k.links, '活跃链接', k.active_links, pctDelta(k.active_links, p.active_links), 'link', 'info'),
    mk('总点击量', k.total_clicks, '人均点击', k.avg_clicks_per_user, pctDelta(k.total_clicks, p.total_clicks), 'touch_app', 'success'),
    mk('父分类数', k.parent_categories, '子分类', k.child_categories, null, 'category', 'warning'),
  ]
})

function deltaChip(d) {
  if (d == null) return { cls: 'text-text-secondary', arrow: '—', txt: '无对比' }
  if (d > 0) return { cls: 'text-success', arrow: '▲', txt: `+${d}%` }
  if (d < 0) return { cls: 'text-error', arrow: '▼', txt: `${d}%` }
  return { cls: 'text-text-secondary', arrow: '—', txt: '0%' }
}

function topDelta(cur, prev) {
  if (!prev || prev <= 0) return cur > 0 ? { cls: 'text-success', txt: '新增' } : { cls: 'text-text-secondary', txt: '—' }
  const d = Math.round(((cur - prev) / prev) * 1000) / 10
  if (d > 0) return { cls: 'text-success', arrow: '▲', txt: `+${d}%` }
  if (d < 0) return { cls: 'text-error', arrow: '▼', txt: `${d}%` }
  return { cls: 'text-text-secondary', txt: '0%' }
}

/* ── Chart.js 默认 ──────────────────────────────────── */
function applyDefaults() {
  Chart.defaults.font.family = "'Inter', sans-serif"
  Chart.defaults.color = TEXT_MUTED
  Chart.defaults.plugins.legend.labels.usePointStyle = true
  Chart.defaults.plugins.legend.labels.padding = 16
  Chart.defaults.plugins.legend.labels.boxWidth = 8
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}
function shadeColor(color, percent) {
  const num = parseInt(color.replace('#', ''), 16)
  const amt = Math.round(2.55 * percent)
  const R = Math.min(255, Math.max(0, (num >> 16) + amt))
  const G = Math.min(255, Math.max(0, ((num >> 8) & 0x00FF) + amt))
  const B = Math.min(255, Math.max(0, (num & 0x0000FF) + amt))
  return `#${(1 << 24 | R << 16 | G << 8 | B).toString(16).slice(1)}`
}

function destroyCharts() {
  Object.keys(charts).forEach((k) => {
    if (charts[k]) { charts[k].destroy(); charts[k] = null }
  })
}

/* ── 图表构建 ───────────────────────────────────────── */
function buildTrend() {
  if (!trendCanvas.value) return
  const ctx = trendCanvas.value.getContext('2d')
  const ds = [
    { label: '点击', data: trend.value.clicks, borderColor: CLICK_COLOR, backgroundColor: hexToRgba(CLICK_COLOR, 0.10), fill: true, tension: 0.4, borderWidth: 2.5, pointRadius: 2, pointHoverRadius: 5, pointBackgroundColor: '#fff', pointBorderColor: CLICK_COLOR, pointBorderWidth: 2 },
    { label: '登录', data: trend.value.logins, borderColor: LOGIN_COLOR, backgroundColor: hexToRgba(LOGIN_COLOR, 0.06), fill: false, tension: 0.4, borderWidth: 2.5, pointRadius: 2, pointHoverRadius: 5, pointBackgroundColor: '#fff', pointBorderColor: LOGIN_COLOR, pointBorderWidth: 2 },
  ]
  if (compare.value && trend.value.prev_clicks) {
    ds.push({ label: '上期对比', data: trend.value.prev_clicks, borderColor: 'rgba(120,120,140,0.55)', backgroundColor: 'transparent', borderDash: [6, 5], fill: false, tension: 0.4, borderWidth: 1.5, pointRadius: 0, pointHoverRadius: 4 })
  }
  charts.trend = new Chart(ctx, {
    type: 'line',
    data: { labels: trend.value.labels.map((l) => l.slice(5)), datasets: ds },
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      plugins: { legend: { position: 'top', align: 'end' }, tooltip: { backgroundColor: '#1c1b23', padding: 12, cornerRadius: 10 } },
      scales: {
        x: { grid: { display: false, drawBorder: false }, ticks: { color: TEXT_MUTED, font: { size: 11 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 14 } },
        y: { grid: { color: GRID_COLOR, drawBorder: false }, ticks: { color: TEXT_MUTED, font: { size: 11 }, stepSize: 1 }, beginAtZero: true },
      },
    },
  })
}

function buildTop() {
  if (!topCanvas.value) return
  const items = top.value.items.slice(0, 10)
  const color = dim.value === 'link' ? CLICK_COLOR : dim.value === 'parent' ? '#3B82F6' : '#8B5CF6'
  charts.top = new Chart(topCanvas.value.getContext('2d'), {
    type: 'bar',
    data: {
      labels: items.map((i) => (i.title || '未命名').slice(0, 18)),
      datasets: [{ label: '点击量', data: items.map((i) => i.clicks), backgroundColor: color, borderRadius: 6, barThickness: 18, hoverBackgroundColor: shadeColor(color, -10) }],
    },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { backgroundColor: '#1c1b23', padding: 10, cornerRadius: 8, callbacks: { label: (c) => `点击: ${c.parsed.x}` } } },
      scales: { x: { grid: { color: GRID_COLOR, drawBorder: false }, ticks: { display: false } }, y: { grid: { display: false, drawBorder: false }, ticks: { color: TEXT_PRIMARY, font: { size: 12 }, padding: 8 } } },
    },
  })
}

function buildPerm() {
  if (!permCanvas.value) return
  const roles = permission.value.roles || []
  charts.perm = new Chart(permCanvas.value.getContext('2d'), {
    type: 'bar',
    data: {
      labels: roles.map((r) => r.role),
      datasets: [{ label: '点击量', data: roles.map((r) => r.clicks), backgroundColor: PALETTE.slice(0, roles.length), borderRadius: 6, hoverBackgroundColor: PALETTE.slice(0, roles.length).map((c) => shadeColor(c, -10)) }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { backgroundColor: '#1c1b23', padding: 10, cornerRadius: 8, callbacks: { label: (c) => `点击: ${c.parsed.y}` } } },
      scales: {
        x: { grid: { display: false, drawBorder: false }, ticks: { color: TEXT_PRIMARY, font: { size: 12 } } },
        y: { grid: { color: GRID_COLOR, drawBorder: false }, ticks: { color: TEXT_MUTED, font: { size: 11 }, stepSize: 1 }, beginAtZero: true },
      },
    },
  })
}

function buildCat() {
  if (!catCanvas.value) return
  const cs = categoryShare.value.slice(0, 8)
  charts.cat = new Chart(catCanvas.value.getContext('2d'), {
    type: 'doughnut',
    data: { labels: cs.map((c) => c.name), datasets: [{ data: cs.map((c) => c.clicks), backgroundColor: PALETTE.slice(0, cs.length), borderColor: '#fff', borderWidth: 3, hoverOffset: 6 }] },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '62%',
      plugins: {
        legend: { position: 'right', labels: { padding: 10, font: { size: 11 } } },
        tooltip: { backgroundColor: '#1c1b23', padding: 10, cornerRadius: 8, callbacks: { label: (c) => `${c.label}: ${c.parsed} (${c.raw != null && cs.length ? Math.round(c.parsed / (cs.reduce((s, x) => s + x.clicks, 0) || 1) * 100) : 0}%)` } },
      },
    },
  })
}

function buildMember() {
  if (!memberCanvas.value) return
  const m = members.value.slice(0, 10)
  charts.member = new Chart(memberCanvas.value.getContext('2d'), {
    type: 'bar',
    data: { labels: m.map((x) => (x.display_name || x.username).slice(0, 14)), datasets: [{ label: '累计添加链接', data: m.map((x) => x.added_links), backgroundColor: '#10B981', borderRadius: 6, barThickness: 18 }] },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { backgroundColor: '#1c1b23', padding: 10, cornerRadius: 8, callbacks: { label: (c) => `链接: ${c.parsed.x}` } } },
      scales: { x: { grid: { color: GRID_COLOR, drawBorder: false }, ticks: { display: false } }, y: { grid: { display: false, drawBorder: false }, ticks: { color: TEXT_PRIMARY, font: { size: 12 }, padding: 8 } } },
    },
  })
}

function buildNewUsers() {
  if (!newUsersCanvas.value) return
  charts.newUsers = new Chart(newUsersCanvas.value.getContext('2d'), {
    type: 'line',
    data: {
      labels: newUsers.value.labels.map((l) => l.slice(5)),
      datasets: [{ label: '新增用户', data: newUsers.value.count, borderColor: '#F59E0B', backgroundColor: hexToRgba('#F59E0B', 0.12), fill: true, tension: 0.4, borderWidth: 2.5, pointRadius: 2, pointHoverRadius: 5 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      plugins: { legend: { position: 'top', align: 'end' }, tooltip: { backgroundColor: '#1c1b23', padding: 12, cornerRadius: 10 } },
      scales: {
        x: { grid: { display: false, drawBorder: false }, ticks: { color: TEXT_MUTED, font: { size: 11 }, maxRotation: 0, autoSkip: true, maxTicksLimit: 14 } },
        y: { grid: { color: GRID_COLOR, drawBorder: false }, ticks: { color: TEXT_MUTED, font: { size: 11 }, stepSize: 1 }, beginAtZero: true },
      },
    },
  })
}

function renderCharts() {
  nextTick(() => {
    destroyCharts()
    buildTrend()
    buildTop()
    buildPerm()
    buildCat()
    buildMember()
    buildNewUsers()
  })
}

/* ── 数据加载 ───────────────────────────────────────── */
async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.statsDashboard({ days: days.value, topN: topN.value, dim: dim.value, compare: compare.value, userId: userId.value })
    data.value = res
    const labels = (res.trend && res.trend.labels) || []
    selectedDate.value = labels.length ? labels[labels.length - 1] : null
    loading.value = false
    renderCharts()
    if (selectedDate.value) await loadDayDetail(selectedDate.value)
  } catch (e) {
    error.value = e.message || '加载失败'
    loading.value = false
  }
}

async function loadDayDetail(date) {
  dayLoading.value = true
  try {
    dayDetail.value = await api.statsDayDetail(date)
  } catch (e) {
    dayDetail.value = null
  } finally {
    dayLoading.value = false
  }
}

function selectDate(d) {
  selectedDate.value = d
  loadDayDetail(d)
}

function setRange(d) { days.value = d; customDays.value = d; loadData() }
function setDim(d) { dim.value = d; drillParent.value = null; loadData() }
function onTopN(e) { topN.value = parseInt(e.target.value) || 10; loadData() }
function onCompare() { compare.value = !compare.value; loadData() }
function onUserFilter(e) {
  const v = e.target.value
  userId.value = v ? parseInt(v) : null
  loadData()
}
function onCustomDays(e) {
  const v = parseInt(e.target.value)
  if (v >= 1 && v <= 365) { days.value = v; loadData() }
}
function toggleDrill(id) { drillParent.value = drillParent.value === id ? null : id }
function setUserSort(s) { userSort.value = s }

/* 手动触发链接可达性探测（系统也会定时自动 ping） */
const pinging = ref(false)
async function recheckLinks() {
  pinging.value = true
  try {
    await api.pingLinks()
    await loadData()
  } catch (e) {
    // 忽略错误，保持页面可用
  } finally {
    pinging.value = false
  }
}

/* ── CSV 导出 ───────────────────────────────────────── */
function exportCsv() {
  const lines = []
  lines.push('导航站统计分析报表')
  lines.push(`时间范围,${data.value.range ? data.value.range.start + ' ~ ' + data.value.range.end : ''}`)
  lines.push('')
  lines.push('指标,数值')
  for (const c of kpiList.value) lines.push(`${c.primaryLabel},${c.primaryValue}`)
  lines.push('')
  lines.push(`TOP排行(${top.value.dim}${selectedUserName.value ? ' · ' + selectedUserName.value : ''}),点击量,占比%,上期`)
  for (const it of top.value.items) lines.push(`${it.title},${it.clicks},${it.ratio},${it.prev_clicks}`)
  lines.push('')
  lines.push('活跃用户,角色,点击,登录,总操作,最后活跃')
  for (const u of users.value) lines.push(`${u.display_name || u.username},${u.role},${u.clicks},${u.logins},${u.total},${u.last_seen || ''}`)
  lines.push('')
  lines.push('成员贡献,角色,累计添加链接,期内新增,添加分类,编辑次数')
  for (const m of members.value) lines.push(`${m.display_name || m.username},${m.role},${m.added_links},${m.new_links_period},${m.added_categories},${m.edits}`)
  const csv = '﻿' + lines.join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `stats_${days.value}days.csv`
  a.click()
  URL.revokeObjectURL(url)
}

/* ── 生命周期 ───────────────────────────────────────── */
onMounted(() => {
  applyDefaults()
  loadData()
})
onBeforeUnmount(() => { destroyCharts() })
</script>

<template>
  <div>
    <!-- 标题 + 全局筛选条 -->
    <div class="mb-6 flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
      <div>
        <h1 class="font-headline-lg text-headline-lg text-text-primary tracking-tight">数据统计</h1>
        <p class="font-body-md text-body-md text-text-secondary mt-1">站点访问、内容热度、用户活跃与权限分布总览（仅管理员可见）</p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <div class="flex gap-1 bg-surface-container rounded-xl p-1">
          <button v-for="d in [7, 30, 90]" :key="d" @click="setRange(d)"
            class="px-3 py-1.5 rounded-lg text-sm font-semibold transition-all"
            :class="days === d ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-surface-container-high'">
            {{ d }}天
          </button>
          <input :value="customDays" @change="onCustomDays" type="number" min="1" max="365"
            class="w-16 px-2 py-1.5 rounded-lg text-sm text-text-primary bg-surface-container-highest focus:outline-none focus:ring-2 focus:ring-primary/40"
            title="自定义天数" />
        </div>
        <select :value="topN" @change="onTopN" class="px-3 py-2 rounded-xl text-sm bg-surface-container text-text-primary border border-outline-variant/40 focus:outline-none focus:ring-2 focus:ring-primary/40">
          <option :value="10">TOP 10</option>
          <option :value="20">TOP 20</option>
          <option :value="50">TOP 50</option>
        </select>
        <button @click="onCompare"
          class="px-3 py-2 rounded-xl text-sm font-semibold border transition-all"
          :class="compare ? 'bg-primary/10 text-primary border-primary/40' : 'bg-surface-container text-on-surface-variant border-outline-variant/40'">
          {{ compare ? '环比对比 开' : '环比对比 关' }}
        </button>
        <button @click="exportCsv" class="px-3 py-2 rounded-xl text-sm font-semibold bg-surface-container text-on-surface-variant border border-outline-variant/40 hover:bg-surface-container-high transition-all flex items-center gap-1">
          <span class="material-symbols-outlined text-[18px]">download</span>导出CSV
        </button>
      </div>
    </div>

    <!-- 加载 / 错误 -->
    <div v-if="loading" class="text-center text-text-secondary py-24 flex flex-col items-center gap-3">
      <svg class="animate-spin h-8 w-8 text-primary" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" fill="none" opacity="0.25"/><path d="M4 12a8 8 0 018-8" stroke="currentColor" stroke-width="3" fill="none" stroke-linecap="round"/></svg>
      <span class="text-label-sm">加载数据中...</span>
    </div>
    <div v-else-if="error" class="text-center text-error py-24">⚠️ {{ error }}</div>

    <div v-else>
      <!-- F1 KPI 卡片（一行合并指标） -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-grid-gutter mb-6">
        <div v-for="c in kpiList" :key="c.primaryLabel" class="bg-bg-card rounded-2xl p-card-padding shadow-glass hover:shadow-glass-hover transition-shadow duration-300 border border-surface-variant/50">
          <div class="flex items-center justify-between mb-3">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center" :class="c.bg">
              <span class="material-symbols-outlined text-[20px]" :class="c.fg">{{ c.icon }}</span>
            </div>
            <span v-if="c.delta != null" class="text-xs font-semibold flex items-center gap-0.5" :class="deltaChip(c.delta).cls">
              {{ deltaChip(c.delta).arrow }} {{ deltaChip(c.delta).txt }}
            </span>
          </div>
          <div class="font-headline-lg text-headline-lg text-text-primary leading-none">{{ typeof c.primaryValue === 'number' ? c.primaryValue.toLocaleString() : c.primaryValue }}</div>
          <div class="text-label-sm text-text-secondary mt-2">{{ c.primaryLabel }}</div>
          <div class="mt-3 pt-3 border-t border-surface-variant/40 flex items-center justify-between">
            <span class="text-label-sm text-text-secondary">{{ c.secondaryLabel }}</span>
            <span class="font-headline-sm text-headline-sm text-text-primary">{{ typeof c.secondaryValue === 'number' ? c.secondaryValue.toLocaleString() : c.secondaryValue }}</span>
          </div>
        </div>
      </div>

      <!-- F4 趋势 + F3 权限（宽度 7:5） -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-grid-gutter mb-6">
        <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 lg:col-span-7">
          <div class="flex items-center justify-between mb-1">
            <h2 class="font-headline-sm text-headline-sm text-text-primary">访问趋势</h2>
            <span class="text-label-sm text-text-secondary">点击 / 登录{{ compare ? ' · 上期对比' : '' }}</span>
          </div>
          <div style="height: 260px; position: relative;"><canvas ref="trendCanvas"></canvas></div>
        </div>
        <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 lg:col-span-5">
          <h2 class="font-headline-sm text-headline-sm text-text-primary mb-1">角色点击分布</h2>
          <p class="text-label-sm text-text-secondary mb-2">按角色统计点击量（F3，柱状图）</p>
          <div style="height: 240px; position: relative;"><canvas ref="permCanvas"></canvas></div>
          <div class="mt-3 pt-3 border-t border-surface-variant/40 text-label-sm text-text-secondary space-y-1">
            <div>链接权限状态：
              <span v-for="s in permission.link_states" :key="s.state" class="inline-block mr-2">{{ s.state }} {{ s.count }}</span>
            </div>
            <div>显式拒绝规则：<span class="text-error font-semibold">{{ permission.denied_rules }}</span> 条</div>
          </div>
        </div>
      </div>

      <!-- F2 TOP 排行（含局部人员筛选） -->
      <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 mb-6">
        <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div>
            <h2 class="font-headline-sm text-headline-sm text-text-primary">
              TOP 点击排行
              <span v-if="selectedUserName" class="ml-2 text-sm font-medium px-2 py-0.5 rounded-full bg-primary/10 text-primary align-middle">{{ selectedUserName }}</span>
            </h2>
            <p class="text-label-sm text-text-secondary">维度可切换，父分类可下钻子分类{{ selectedUserName ? '（仅该人员点击）' : '' }}</p>
          </div>
          <div class="flex gap-2 flex-wrap">
            <select :value="userId || ''" @change="onUserFilter"
              class="px-3 py-1.5 rounded-lg text-sm bg-surface-container text-text-primary border border-outline-variant/40 focus:outline-none focus:ring-2 focus:ring-primary/40">
              <option value="">全部人员</option>
              <option v-for="u in userOptions" :key="u.id" :value="u.id">{{ u.display_name || u.username }}（{{ u.role }}）</option>
            </select>
            <div class="flex gap-1 bg-surface-container rounded-xl p-1">
              <button v-for="o in [{k:'link',l:'链接'},{k:'parent',l:'父分类'},{k:'child',l:'子分类'}]" :key="o.k" @click="setDim(o.k)"
                class="px-3 py-1.5 rounded-lg text-sm font-semibold transition-all"
                :class="dim === o.k ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-surface-container-high'">
                {{ o.l }}
              </button>
            </div>
          </div>
        </div>
        <div v-if="!top.items.length" class="text-center text-text-secondary py-10 text-sm">
          {{ selectedUserName ? selectedUserName + ' 在统计周期内暂无点击记录' : '统计周期内暂无点击数据' }}
        </div>
        <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div style="height: 300px; position: relative;"><canvas ref="topCanvas"></canvas></div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-label-sm text-text-secondary border-b border-surface-variant/40">
                  <th class="text-left py-2 pr-2 font-medium">名称</th>
                  <th class="text-left py-2 pr-2 font-medium">路径 / 分类</th>
                  <th class="text-right py-2 pr-2 font-medium">点击</th>
                  <th class="text-right py-2 pr-2 font-medium">占比</th>
                  <th class="text-right py-2 font-medium">环比</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="it in top.items" :key="it.id">
                  <tr class="border-b border-surface-variant/30 hover:bg-surface-container/40" :class="dim === 'parent' ? 'cursor-pointer' : ''" @click="dim === 'parent' && toggleDrill(it.id)">
                    <td class="py-2 pr-2 text-text-primary font-medium">
                      {{ it.title }}
                      <span v-if="dim === 'parent'" class="material-symbols-outlined text-[16px] align-middle text-text-secondary">{{ drillParent === it.id ? 'expand_less' : 'expand_more' }}</span>
                    </td>
                    <td class="py-2 pr-2 text-text-secondary">{{ (it.path && it.path.join(' / ')) || (dim === 'child' ? '子分类' : '—') }}</td>
                    <td class="py-2 pr-2 text-right text-text-primary">{{ it.clicks.toLocaleString() }}</td>
                    <td class="py-2 pr-2 text-right text-text-secondary">{{ it.ratio }}%</td>
                    <td class="py-2 text-right" :class="topDelta(it.clicks, it.prev_clicks).cls">{{ topDelta(it.clicks, it.prev_clicks).txt }}</td>
                  </tr>
                  <template v-if="dim === 'parent' && drillParent === it.id">
                    <tr v-for="ch in it.children" :key="ch.id" class="bg-surface-container/50">
                      <td class="py-1.5 pl-8 pr-2 text-text-secondary text-sm">{{ ch.title }}</td>
                      <td class="py-1.5 pr-2 text-text-secondary text-sm">子分类</td>
                      <td class="py-1.5 pr-2 text-right text-text-secondary text-sm">{{ ch.clicks.toLocaleString() }}</td>
                      <td class="py-1.5 pr-2 text-right text-text-secondary text-sm">—</td>
                      <td class="py-1.5 text-right text-text-secondary text-sm">—</td>
                    </tr>
                  </template>
                </template>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- F10 分类占比 + F6 成员贡献 -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-grid-gutter mb-6">
        <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50">
          <h2 class="font-headline-sm text-headline-sm text-text-primary mb-1">分类点击占比</h2>
          <p class="text-label-sm text-text-secondary mb-2">各父分类点击量分布（F10，看结构是否均衡）</p>
          <div style="height: 260px; position: relative;"><canvas ref="catCanvas"></canvas></div>
        </div>
        <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50">
          <h2 class="font-headline-sm text-headline-sm text-text-primary mb-1">成员贡献</h2>
          <p class="text-label-sm text-text-secondary mb-2">各成员累计添加链接数（F6）</p>
          <div style="height: 260px; position: relative;"><canvas ref="memberCanvas"></canvas></div>
          <div class="mt-3 pt-3 border-t border-surface-variant/40 overflow-x-auto">
            <table class="w-full text-sm">
              <thead><tr class="text-label-sm text-text-secondary"><th class="text-left py-1 font-medium">成员</th><th class="text-right py-1 font-medium">累计</th><th class="text-right py-1 font-medium">期内新增</th><th class="text-right py-1 font-medium">分类</th><th class="text-right py-1 font-medium">编辑</th></tr></thead>
              <tbody>
                <tr v-for="m in members.slice(0, 6)" :key="m.id" class="border-t border-surface-variant/30">
                  <td class="py-1 text-text-primary">{{ m.display_name || m.username }}</td>
                  <td class="py-1 text-right text-text-primary">{{ m.added_links }}</td>
                  <td class="py-1 text-right text-text-secondary">+{{ m.new_links_period }}</td>
                  <td class="py-1 text-right text-text-secondary">{{ m.added_categories }}</td>
                  <td class="py-1 text-right text-text-secondary">{{ m.edits }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- F5 用户行为 -->
      <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 mb-6">
        <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
          <div>
            <h2 class="font-headline-sm text-headline-sm text-text-primary">用户行为</h2>
            <p class="text-label-sm text-text-secondary">统计周期内活跃用户（F5，含脱敏聚合）</p>
          </div>
          <div class="flex gap-1 bg-surface-container rounded-xl p-1">
            <button v-for="o in [{k:'total',l:'总操作'},{k:'clicks',l:'点击'},{k:'logins',l:'登录'}]" :key="o.k" @click="setUserSort(o.k)"
              class="px-3 py-1.5 rounded-lg text-sm font-semibold transition-all"
              :class="userSort === o.k ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-surface-container-high'">
              {{ o.l }}
            </button>
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead><tr class="text-label-sm text-text-secondary border-b border-surface-variant/40">
              <th class="text-left py-2 font-medium">用户</th><th class="text-left py-2 font-medium">角色</th>
              <th class="text-right py-2 font-medium">点击</th><th class="text-right py-2 font-medium">登录</th>
              <th class="text-right py-2 font-medium">总操作</th><th class="text-right py-2 font-medium">最后活跃</th><th class="text-right py-2 font-medium">注册时间</th>
            </tr></thead>
            <tbody>
              <tr v-for="u in sortedUsers" :key="u.id" class="border-b border-surface-variant/30 hover:bg-surface-container/40">
                <td class="py-2 text-text-primary font-medium">{{ u.display_name || u.username }}</td>
                <td class="py-2 text-text-secondary">{{ u.role }}</td>
                <td class="py-2 text-right text-text-primary">{{ u.clicks.toLocaleString() }}</td>
                <td class="py-2 text-right text-text-secondary">{{ u.logins.toLocaleString() }}</td>
                <td class="py-2 text-right text-text-primary">{{ u.total.toLocaleString() }}</td>
                <td class="py-2 text-right text-text-secondary">{{ u.last_seen ? u.last_seen.slice(0, 10) : '—' }}</td>
                <td class="py-2 text-right text-text-secondary">{{ u.created_at ? u.created_at.slice(0, 10) : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- F8 新增用户 + 留存 -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-grid-gutter mb-6">
        <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 lg:col-span-2">
          <h2 class="font-headline-sm text-headline-sm text-text-primary mb-1">新增用户趋势</h2>
          <p class="text-label-sm text-text-secondary mb-2">按日统计新注册用户（F8）</p>
          <div style="height: 220px; position: relative;"><canvas ref="newUsersCanvas"></canvas></div>
        </div>
        <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50">
          <h2 class="font-headline-sm text-headline-sm text-text-primary mb-1">用户留存</h2>
          <p class="text-label-sm text-text-secondary mb-3">同期新增用户 cohort（F8）· n={{ retention.cohort || 0 }}</p>
          <div class="space-y-3">
            <div v-for="r in [{k:'d1',l:'次日留存'},{k:'d7',l:'7日留存'},{k:'d30',l:'30日留存'}]" :key="r.k" class="flex items-center gap-3">
              <span class="text-sm text-text-secondary w-20">{{ r.l }}</span>
              <div class="flex-1 h-3 rounded-full bg-surface-container overflow-hidden">
                <div class="h-full rounded-full bg-success" :style="{ width: (retention[r.k] != null ? retention[r.k] : 0) + '%' }"></div>
              </div>
              <span class="text-sm font-semibold text-text-primary w-12 text-right">{{ retention[r.k] != null ? retention[r.k] + '%' : '—' }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- F9 活跃时段（可点击日期切换的日历热力图 + 选中日 24h 分布） -->
      <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 mb-6">
        <div class="flex items-center justify-between mb-1 flex-wrap gap-2">
          <h2 class="font-headline-sm text-headline-sm text-text-primary">活跃日期热力图</h2>
          <span class="text-label-sm text-text-secondary">点击任意日期，查看当日 24 小时分布</span>
        </div>
        <p class="text-label-sm text-text-secondary mb-3">统计周期内每日点击量（颜色越深越多），日期范围随上方时间筛选变化</p>
        <div class="flex flex-wrap gap-1.5 max-h-[150px] overflow-y-auto pr-1">
          <button v-for="(d, i) in trend.labels" :key="d"
            class="w-5 h-5 rounded-[4px] transition-all hover:opacity-80"
            :style="{ background: `rgba(83,65,205,${0.08 + 0.92 * (trend.clicks[i] / dayMax)})`, outline: selectedDate === d ? '2px solid #5341CD' : 'none', outlineOffset: '1px' }"
            :title="`${d}：${trend.clicks[i]} 次点击`"
            @click="selectDate(d)"></button>
        </div>
        <div class="mt-6 border-t border-surface-variant/40 pt-5">
          <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
            <h3 class="font-headline-sm text-headline-sm text-text-primary">
              {{ selectedDate || '—' }} 当日 24 小时分布
            </h3>
            <span v-if="dayDetail" class="text-label-sm text-text-secondary">点击 {{ dayDetail.total_clicks }} · 登录 {{ dayDetail.total_logins }}</span>
            <span v-else-if="dayLoading" class="text-label-sm text-text-secondary">加载中…</span>
          </div>
          <div class="grid grid-cols-12 gap-1.5">
            <div v-for="(h, i) in dayHourly" :key="i" class="relative rounded-md flex items-center justify-center text-[10px] font-medium text-white/90"
              :style="{ height: '28px', background: `rgba(83,65,205,${0.12 + 0.88 * (h / dayHourlyMax)})` }" :title="`${i}:00 - ${h} 次`">
              <span v-if="h / dayHourlyMax > 0.45">{{ h }}</span>
            </div>
          </div>
          <div class="flex justify-between text-label-sm text-text-secondary mt-1 px-0.5">
            <span>0:00</span><span>6:00</span><span>12:00</span><span>18:00</span><span>23:00</span>
          </div>
        </div>
        <div class="mt-5 grid grid-cols-7 gap-2">
          <div v-for="(w, i) in weekly" :key="i" class="rounded-xl p-3 text-center"
            :style="{ background: `rgba(16,185,129,${0.1 + 0.9 * (w / Math.max(1, ...weekly))})` }">
            <div class="text-label-sm text-text-secondary">周{{ weekLabels[i] }}</div>
            <div class="font-headline-sm text-headline-sm text-text-primary mt-1">{{ w.toLocaleString() }}</div>
          </div>
        </div>
      </div>

      <!-- F7 链接健康 -->
      <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 mb-6">
        <div class="flex items-start justify-between mb-1 flex-wrap gap-2">
          <div>
            <h2 class="font-headline-sm text-headline-sm text-text-primary">链接健康度</h2>
            <p class="text-label-sm text-text-secondary">长尾、空壳与可达性（系统每 10 分钟自动 ping 探测）</p>
          </div>
          <button @click="recheckLinks" :disabled="pinging"
            class="px-3 py-1.5 rounded-lg text-sm font-semibold bg-surface-container text-on-surface-variant border border-outline-variant/40 hover:bg-surface-container-high transition-all flex items-center gap-1 disabled:opacity-60">
            <span class="material-symbols-outlined text-[18px]" :class="pinging ? 'animate-spin' : ''">refresh</span>
            {{ pinging ? '检测中…' : '重新检测' }}
          </button>
        </div>
        <p class="text-label-sm text-text-secondary mb-4">
          最近探测：{{ linkPing.last_ping_at ? linkPing.last_ping_at.slice(0, 16).replace('T', ' ') : '尚未探测' }}
          <span class="ml-2">已探测 {{ linkPing.reachable + linkPing.unreachable }} · 未探测 {{ linkPing.unchecked }}</span>
        </p>
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          <div class="rounded-xl bg-surface-container p-4">
            <div class="text-label-sm text-text-secondary">零点击链接</div>
            <div class="font-headline-md text-headline-md text-warning mt-1">{{ health.zero_click_links }}</div>
            <div class="text-label-sm text-text-secondary mt-1">占比 {{ health.zero_click_ratio }}%</div>
          </div>
          <div class="rounded-xl bg-surface-container p-4">
            <div class="text-label-sm text-text-secondary">链接总数</div>
            <div class="font-headline-md text-headline-md text-text-primary mt-1">{{ health.links_total }}</div>
            <div class="text-label-sm text-text-secondary mt-1">活跃 {{ health.links_total - health.zero_click_links }}</div>
          </div>
          <div class="rounded-xl bg-surface-container p-4">
            <div class="text-label-sm text-text-secondary">空壳子分类</div>
            <div class="font-headline-md text-headline-md text-warning mt-1">{{ health.empty_categories }}</div>
            <div class="text-label-sm text-text-secondary mt-1">占比 {{ health.empty_ratio }}%</div>
          </div>
          <div class="rounded-xl bg-surface-container p-4">
            <div class="text-label-sm text-text-secondary">子分类总数</div>
            <div class="font-headline-md text-headline-md text-text-primary mt-1">{{ health.categories_total }}</div>
            <div class="text-label-sm text-text-secondary mt-1">含链接 {{ health.categories_total - health.empty_categories }}</div>
          </div>
          <div class="rounded-xl bg-surface-container p-4 border border-error/30">
            <div class="text-label-sm text-text-secondary">无法访问</div>
            <div class="font-headline-md text-headline-md mt-1" :class="linkPing.unreachable > 0 ? 'text-error' : 'text-success'">{{ linkPing.unreachable }}</div>
            <div class="text-label-sm text-text-secondary mt-1">可达 {{ linkPing.reachable }}</div>
          </div>
        </div>
      </div>

      <p class="text-center text-label-sm text-text-secondary py-4">
        数据口径：点击 / 登录事件来自 AccessLog（UTC）；留存为同期新增用户 cohort 近似；死链探测（F7）与站内搜索词（F11）本期未接入。
      </p>
    </div>
  </div>
</template>
