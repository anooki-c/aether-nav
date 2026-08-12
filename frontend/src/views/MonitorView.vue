<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api/client'

/* ── 连接配置 ─────────────────────────────────────── */
const config = reactive({ host: '', port: '', user: '', password: '', https: false })
const savingConfig = ref(false)
const configMsg = ref('')
const needConfig = ref(false)

/* ── 监控数据 ─────────────────────────────────────── */
const loading = ref(false)
const error = ref('')
const snap = ref(null)
const actingId = ref(null)
let timer = null
const AUTO_INTERVAL = 10000

const system = computed(() => snap.value?.system || {})
const network = computed(() => snap.value?.network || {})
const volumes = computed(() => snap.value?.storage?.volumes || [])
const containers = computed(() => snap.value?.containers || [])

/* ── 拉取与操作 ───────────────────────────────────── */
async function loadConfig() {
  try {
    const d = await api.monitorConfig()
    config.host = d.host || ''
    config.port = d.port || ''
    config.user = d.user || ''
    config.https = !!d.https
    needConfig.value = !d.configured
  } catch (e) { /* 配置接口失败不阻塞 */ }
}

async function saveConfig() {
  savingConfig.value = true
  configMsg.value = ''
  try {
    await api.monitorConfigSave({
      host: config.host, port: config.port, user: config.user,
      password: config.password, https: config.https,
    })
    configMsg.value = '已保存，正在拉取监控数据…'
    config.password = ''
    needConfig.value = false
    await loadSnapshot()
  } catch (e) {
    configMsg.value = '保存失败：' + e.message
  } finally {
    savingConfig.value = false
  }
}

async function loadSnapshot() {
  loading.value = true
  error.value = ''
  try {
    const d = await api.monitorSnapshot()
    snap.value = d
    const diags = d.diagnostics || {}
    const failed = Object.entries(diags)
      .filter(([, v]) => v && !v.ok)
      .map(([k, v]) => `${k}: ${v.error || '未知错误'}`)
    if (failed.length) error.value = '以下模块获取数据失败：' + failed.join('；')
  } catch (e) {
    error.value = e.message || '加载失败'
    if (e.message && e.message.includes('配置')) needConfig.value = true
  } finally {
    loading.value = false
  }
}

async function act(cid, action) {
  actingId.value = cid + ':' + action
  try {
    await api.monitorContainerAction(cid, action)
    await loadSnapshot()
  } catch (e) {
    error.value = e.message
  } finally {
    actingId.value = null
  }
}

/* ── 格式化 ───────────────────────────────────────── */
function fmtBytes(b) {
  if (b == null) return '—'
  const u = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0, n = Number(b)
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++ }
  return (i ? n.toFixed(1) : n) + ' ' + u[i]
}
function fmtUptime(s) {
  if (s == null) return '—'
  s = Number(s)
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  return (d ? d + ' 天 ' : '') + h + ' 小时 ' + m + ' 分'
}
function fmtPorts(ports) {
  if (!ports) return '—'
  if (Array.isArray(ports)) {
    const s = ports.map((p) => {
      if (p.host && p.container) return `${p.host}:${p.container}`
      if (p.container) return String(p.container)
      if (p.port) return `${p.bind ? p.bind + ':' : ''}${p.port}`
      return String(p)
    }).join('，')
    return s || '—'
  }
  return String(ports)
}
function barColor(p) {
  if (p == null) return 'bg-text-secondary'
  if (p < 60) return 'bg-success'
  if (p < 85) return 'bg-warning'
  return 'bg-error'
}
function stateDot(state) {
  if (state === 'running') return 'bg-success'
  if (state === 'paused') return 'bg-warning'
  return 'bg-text-secondary'
}
function stateText(state) {
  if (state === 'running') return '运行中'
  if (state === 'paused') return '已暂停'
  if (state === 'stopped') return '已停止'
  return state || '—'
}

/* ── 生命周期 ─────────────────────────────────────── */
onMounted(async () => {
  await loadConfig()
  if (!needConfig.value) loadSnapshot()
  timer = setInterval(() => { if (!needConfig.value) loadSnapshot() }, AUTO_INTERVAL)
})
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div>
    <!-- 标题 + 刷新 -->
    <div class="mb-6 flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
      <div>
        <h1 class="font-headline-lg text-headline-lg text-text-primary tracking-tight">群晖监控</h1>
        <p class="font-body-md text-body-md text-text-secondary mt-1">通过 DSM API 实时查看 NAS 系统状态与 Docker 容器（仅管理员可见）</p>
      </div>
      <button v-if="!needConfig" @click="loadSnapshot" :disabled="loading"
        class="px-3 py-2 rounded-xl text-sm font-semibold bg-surface-container text-on-surface-variant border border-outline-variant/40 hover:bg-surface-container-high transition-all flex items-center gap-1 disabled:opacity-60">
        <span class="material-symbols-outlined text-[18px]" :class="loading ? 'animate-spin' : ''">refresh</span>
        {{ loading ? '刷新中…' : '刷新' }}
      </button>
    </div>

    <!-- 连接配置（未配置或想修改时显示） -->
    <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 mb-6">
      <div class="flex items-center gap-2 mb-4">
        <span class="material-symbols-outlined text-[20px] text-primary">router</span>
        <h2 class="font-headline-sm text-headline-sm text-text-primary">群晖连接配置</h2>
        <span v-if="!needConfig" class="text-label-sm text-success ml-2">● 已连接</span>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <label class="block">
          <span class="text-label-sm text-text-secondary">主机地址 / IP</span>
          <input v-model="config.host" type="text" placeholder="如 192.168.1.10"
            class="mt-1 w-full px-3 py-2 rounded-xl text-sm bg-surface-container text-text-primary border border-outline-variant/40 focus:outline-none focus:ring-2 focus:ring-primary/40" />
        </label>
        <label class="block">
          <span class="text-label-sm text-text-secondary">端口（留空用默认）</span>
          <input v-model="config.port" type="number" placeholder="5000 / 5001"
            class="mt-1 w-full px-3 py-2 rounded-xl text-sm bg-surface-container text-text-primary border border-outline-variant/40 focus:outline-none focus:ring-2 focus:ring-primary/40" />
        </label>
        <label class="flex items-end gap-3 pb-1">
          <input v-model="config.https" type="checkbox" class="w-4 h-4 rounded accent-primary" />
          <span class="text-sm text-text-primary">使用 HTTPS（默认 5001 端口）</span>
        </label>
        <label class="block">
          <span class="text-label-sm text-text-secondary">账号</span>
          <input v-model="config.user" type="text" placeholder="admin"
            class="mt-1 w-full px-3 py-2 rounded-xl text-sm bg-surface-container text-text-primary border border-outline-variant/40 focus:outline-none focus:ring-2 focus:ring-primary/40" />
        </label>
        <label class="block">
          <span class="text-label-sm text-text-secondary">密码（留空则不修改）</span>
          <input v-model="config.password" type="password" placeholder="••••••••"
            class="mt-1 w-full px-3 py-2 rounded-xl text-sm bg-surface-container text-text-primary border border-outline-variant/40 focus:outline-none focus:ring-2 focus:ring-primary/40" />
        </label>
      </div>
      <div class="mt-4 flex items-center gap-3">
        <button @click="saveConfig" :disabled="savingConfig"
          class="px-4 py-2 rounded-xl text-sm font-semibold bg-primary text-on-primary hover:opacity-90 transition-all disabled:opacity-60">
          {{ savingConfig ? '保存中…' : '保存并连接' }}
        </button>
        <span v-if="configMsg" class="text-label-sm text-text-secondary">{{ configMsg }}</span>
      </div>
      <p class="text-label-sm text-text-secondary mt-3">
        凭据存储于站点数据库（或环境变量 SYNO_*）。群晖需在「控制面板 → 终端机和 SNMP」开启，并确保账号拥有访问权限。
      </p>
    </div>

    <!-- 未配置 / 错误 -->
    <div v-if="needConfig" class="text-center text-text-secondary py-16">
      ⚠️ 请先在上方填写群晖连接信息并保存
    </div>
    <div v-else-if="error && !snap" class="text-center text-error py-16">⚠️ {{ error }}</div>

    <div v-else-if="snap">
      <!-- 错误提示（部分失败） -->
      <div v-if="error" class="mb-4 px-4 py-3 rounded-xl bg-warning/10 text-warning text-sm">
        ⚠️ {{ error }}
        <details class="mt-2 text-text-secondary">
          <summary class="cursor-pointer select-none">查看诊断详情</summary>
          <pre class="mt-2 text-xs whitespace-pre-wrap break-all">{{ JSON.stringify(snap && snap.diagnostics, null, 2) }}</pre>
        </details>
      </div>

      <!-- 系统概览卡片 -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-grid-gutter mb-6">
        <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50">
          <div class="flex items-center justify-between mb-2">
            <span class="text-label-sm text-text-secondary">CPU 使用率</span>
            <span class="material-symbols-outlined text-[18px] text-primary">memory</span>
          </div>
          <div class="font-headline-md text-headline-md text-text-primary">{{ snap.cpu != null ? snap.cpu + '%' : '—' }}</div>
          <div class="mt-3 h-2 rounded-full bg-surface-container overflow-hidden">
            <div class="h-full rounded-full transition-all" :class="barColor(snap.cpu)" :style="{ width: (snap.cpu || 0) + '%' }"></div>
          </div>
        </div>
        <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50">
          <div class="flex items-center justify-between mb-2">
            <span class="text-label-sm text-text-secondary">内存使用率</span>
            <span class="material-symbols-outlined text-[18px] text-info">developer_board</span>
          </div>
          <div class="font-headline-md text-headline-md text-text-primary">{{ snap.memory != null ? snap.memory + '%' : '—' }}</div>
          <div class="mt-3 h-2 rounded-full bg-surface-container overflow-hidden">
            <div class="h-full rounded-full transition-all" :class="barColor(snap.memory)" :style="{ width: (snap.memory || 0) + '%' }"></div>
          </div>
        </div>
        <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50">
          <div class="flex items-center justify-between mb-2">
            <span class="text-label-sm text-text-secondary">磁盘利用率</span>
            <span class="material-symbols-outlined text-[18px] text-warning">storage</span>
          </div>
          <div class="font-headline-md text-headline-md text-text-primary">{{ snap.disk_util != null ? snap.disk_util + '%' : '—' }}</div>
          <div class="mt-3 h-2 rounded-full bg-surface-container overflow-hidden">
            <div class="h-full rounded-full transition-all" :class="barColor(snap.disk_util)" :style="{ width: (snap.disk_util || 0) + '%' }"></div>
          </div>
        </div>
        <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50">
          <div class="flex items-center justify-between mb-2">
            <span class="text-label-sm text-text-secondary">系统温度</span>
            <span class="material-symbols-outlined text-[18px] text-error">thermostat</span>
          </div>
          <div class="font-headline-md text-headline-md text-text-primary">{{ system.temperature != null ? system.temperature + '°C' : '—' }}</div>
          <div class="text-label-sm text-text-secondary mt-2">运行时长</div>
          <div class="font-headline-sm text-headline-sm text-text-primary">{{ fmtUptime(system.uptime_seconds) }}</div>
        </div>
      </div>

      <!-- 系统信息 + 网络 -->
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-grid-gutter mb-6">
        <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 lg:col-span-2">
          <h2 class="font-headline-sm text-headline-sm text-text-primary mb-3">系统信息</h2>
          <div class="grid grid-cols-2 gap-y-3 text-sm">
            <div class="text-text-secondary">型号</div><div class="text-text-primary font-medium">{{ system.model || '—' }}</div>
            <div class="text-text-secondary">DSM 版本</div><div class="text-text-primary font-medium">{{ system.version || '—' }}</div>
            <div class="text-text-secondary">监控地址</div><div class="text-text-primary font-medium">{{ snap.host }}</div>
            <div class="text-text-secondary">运行时长</div><div class="text-text-primary font-medium">{{ fmtUptime(system.uptime_seconds) }}</div>
          </div>
        </div>
        <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50">
          <h2 class="font-headline-sm text-headline-sm text-text-primary mb-3">网络流量（累计）</h2>
          <div class="space-y-3 text-sm">
            <div>
              <div class="text-text-secondary">接收 ↓</div>
              <div class="font-headline-sm text-headline-sm text-text-primary">{{ fmtBytes(network.rx_bytes) }}</div>
            </div>
            <div>
              <div class="text-text-secondary">发送 ↑</div>
              <div class="font-headline-sm text-headline-sm text-text-primary">{{ fmtBytes(network.tx_bytes) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 存储卷 -->
      <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 mb-6">
        <h2 class="font-headline-sm text-headline-sm text-text-primary mb-3">存储卷</h2>
        <div v-if="!volumes.length" class="text-text-secondary text-sm py-4">无数据</div>
        <div v-for="v in volumes" :key="v.name" class="mb-4 last:mb-0">
          <div class="flex items-center justify-between mb-1 text-sm">
            <span class="text-text-primary font-medium">{{ v.name || '卷' }}</span>
            <span class="text-text-secondary">{{ fmtBytes(v.used_bytes) }} / {{ fmtBytes(v.total_bytes) }}（{{ v.usage_pct != null ? v.usage_pct + '%' : '—' }}）</span>
          </div>
          <div class="h-2 rounded-full bg-surface-container overflow-hidden">
            <div class="h-full rounded-full transition-all" :class="barColor(v.usage_pct)" :style="{ width: (v.usage_pct || 0) + '%' }"></div>
          </div>
        </div>
      </div>

      <!-- Docker 容器 -->
      <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50">
        <div class="flex items-center justify-between mb-3">
          <h2 class="font-headline-sm text-headline-sm text-text-primary">Docker 容器</h2>
          <span class="text-label-sm text-text-secondary">{{ containers.length }} 个</span>
        </div>
        <div v-if="!containers.length" class="text-text-secondary text-sm py-4">未获取到容器（或群晖未安装 Container Manager）</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-label-sm text-text-secondary border-b border-surface-variant/40">
                <th class="text-left py-2 pr-2 font-medium">名称</th>
                <th class="text-left py-2 pr-2 font-medium">状态</th>
                <th class="text-right py-2 pr-2 font-medium">CPU</th>
                <th class="text-right py-2 pr-2 font-medium">内存</th>
                <th class="text-left py-2 pr-2 font-medium">镜像</th>
                <th class="text-left py-2 pr-2 font-medium">IP</th>
                <th class="text-left py-2 pr-2 font-medium">端口</th>
                <th class="text-right py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in containers" :key="c.id" class="border-b border-surface-variant/30 hover:bg-surface-container/40">
                <td class="py-2 pr-2 text-text-primary font-medium">{{ c.name }}</td>
                <td class="py-2 pr-2">
                  <span class="inline-flex items-center gap-1.5">
                    <span class="w-2 h-2 rounded-full" :class="stateDot(c.state)"></span>
                    <span class="text-text-secondary">{{ stateText(c.state) }}</span>
                  </span>
                </td>
                <td class="py-2 pr-2 text-right text-text-primary">{{ c.cpu_pct != null ? c.cpu_pct + '%' : '—' }}</td>
                <td class="py-2 pr-2 text-right text-text-primary">{{ fmtBytes(c.mem_bytes) }}</td>
                <td class="py-2 pr-2 text-text-secondary max-w-[200px] truncate">{{ c.image || '—' }}</td>
                <td class="py-2 pr-2 text-text-primary font-mono text-xs">{{ c.container_ip || '—' }}</td>
                <td class="py-2 pr-2 text-text-secondary">{{ fmtPorts(c.ports) }}</td>
                <td class="py-2 text-right whitespace-nowrap">
                  <button v-if="c.state !== 'running'" @click="act(c.id, 'start')" :disabled="actingId === c.id + ':start'"
                    class="px-2 py-1 rounded-lg text-xs font-semibold bg-success/10 text-success hover:bg-success/20 transition-all disabled:opacity-60">启动</button>
                  <button v-if="c.state === 'running'" @click="act(c.id, 'stop')" :disabled="actingId === c.id + ':stop'"
                    class="px-2 py-1 rounded-lg text-xs font-semibold bg-error/10 text-error hover:bg-error/20 transition-all disabled:opacity-60">停止</button>
                  <button @click="act(c.id, 'restart')" :disabled="actingId === c.id + ':restart'"
                    class="px-2 py-1 rounded-lg text-xs font-semibold bg-surface-container text-on-surface-variant border border-outline-variant/40 hover:bg-surface-container-high transition-all disabled:opacity-60 ml-1">重启</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <p class="text-center text-label-sm text-text-secondary py-4">
        每 {{ AUTO_INTERVAL / 1000 }} 秒自动刷新；容器启停操作即时生效并重新拉取状态。
      </p>
    </div>
  </div>
</template>
