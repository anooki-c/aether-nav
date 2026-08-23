<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { api } from '../api/client'
import { showToast } from '../store'
import QuickAddLink from '../components/QuickAddLink.vue'

/* ── 连接配置 ─────────────────────────────────────── */
const config = reactive({ host: '', port: '', user: '', password: '', https: false })
const savingConfig = ref(false)
const testingConfig = ref(false)
const configMsg = ref('')
const needConfig = ref(false)
const showConfig = ref(false)

/* ── 监控数据 ─────────────────────────────────────── */
const loading = ref(false)
const error = ref('')
const snap = ref(null)
const actingId = ref(null)
let timer = null
const AUTO_INTERVAL = 15000

const util = computed(() => snap.value?.utilization || {})
const containers = computed(() => snap.value?.containers || [])
const systemHealth = computed(() => snap.value?.system_health || null)

/* ── 磁盘容量（空间用量）────────────────────────── */
// 每个物理硬盘：合并容量（storage）与 I/O（volumes），用于在顶部一行内逐盘展示。
// 容量接口不可用时退化为仅 I/O 卷；两者皆空则列表为空（模板显示占位）。
// 容量（storage）与 I/O（volumes）均按归一化卷名（如 volume3）对齐合并。
const diskVolumes = computed(() => {
  const caps = (util.value.storage || []).filter((v) => v && v.name)
  const ios = util.value.volumes || []
  const ioByName = {}
  for (const v of ios) {
    if (v && v.name) ioByName[v.name] = v
  }
  if (caps.length) {
    return caps.map((c) => ({
      name: c.name,
      display_name: c.display_name || c.name,
      used: c.used, total: c.total, usage_pct: c.usage_pct,
      io: ioByName[c.name] || null,
    }))
  }
  if (ios.length) {
    return ios.map((v) => ({
      name: v.name,
      display_name: v.name,
      used: null, total: null, usage_pct: null, io: v,
    }))
  }
  return []
})

/* ── Docker 容器「快速添加为导航链接」────────────── */
// 仅内网：URL = 群晖宿主机 IP + docker 宿主机端口；复用快速添加弹窗（自动识别网络 + 自动获取图标）。
const quickAddOpen = ref(false)
const quickPrefill = ref({ url: '', title: '' })

// 取群晖宿主机 IP：优先 SystemHealth 接口 IP，回退快照 host
function synologyHostIp() {
  const itfs = (systemHealth.value && systemHealth.value.interfaces) || []
  const ip = itfs.length ? itfs[0].ip : (snap.value && snap.value.host) || ''
  return ip || ''
}

// 构造内网 URL（群晖宿主 IP + docker 已发布到宿主机的端口）
function containerAddUrl(c) {
  const ip = synologyHostIp()
  if (!ip) return ''
  const ports = filteredPorts(c.id)
  const pub = ports.find((p) => p.host && p.host !== 'None')
  const port = pub ? pub.host : (ports[0] && ports[0].container) || ''
  if (!port) return ''
  return `http://${ip}:${port}`
}

async function openAddConnection(c) {
  if (c.state !== 'running') return
  // 端口未加载则先拉取，确保能算出正确的内网 URL（去重判定依赖它）
  if (!portCache[c.id]) {
    await fetchPorts(c, true).catch(() => {})
  }
  // 每次点击都重新拉取最新链接列表，确保去重数据是最新的（不依赖 onMounted 缓存）
  await loadExistingLinks()
  const url = containerAddUrl(c)
  // 打开前检测链接是否已存在（精确 host:port + 同端口兜底，兼容多 IP）
  if (addUrlExists(c)) {
    showToast('该内网地址已存在链接，无需重复添加', 'warn')
    return
  }
  if (!url) {
    const isHostNet = (c.networks || []).some((n) => n.name === 'host')
    showToast(isHostNet ? '该容器使用宿主机网络模式(host)，无端口映射，请手动添加' : '该容器暂无可用的宿主机端口', 'warn')
    return
  }
  quickPrefill.value = { url, title: c.name }
  quickAddOpen.value = true
}

/* ── 已有链接（一次拉取，用于「快速添加地址是否已存在」判定 → 已存在则禁用按钮）── */
const existingLinks = ref([])
async function loadExistingLinks() {
  try {
    // 用 internal 模式，使返回 url 优先反映内网地址（与容器内网添加 URL 可比）
    const data = await api.links('internal')
    const groups = (data && data.groups) || []
    const flat = []
    for (const g of groups) {
      const ls = (g && g.links) || []
      for (const l of ls) flat.push(l)
    }
    existingLinks.value = flat
  } catch (e) {
    existingLinks.value = []
  }
}

// 归一化 URL → host:port（含默认端口），用于「域名+端口」去重比较
function hostPortKey(url) {
  if (!url) return ''
  try {
    const u = new URL(url)
    let port = u.port
    if (!port) port = u.protocol === 'https:' ? '443' : '80'
    return (u.hostname || '').toLowerCase() + ':' + port
  } catch (e) { return '' }
}
function linkExistsByUrl(url) {
  const key = hostPortKey(url)
  if (!key) return false
  // 精确匹配：url / url_internal / url_external
  if (existingLinks.value.some((l) =>
    hostPortKey(l.url) === key ||
    hostPortKey(l.url_internal) === key ||
    hostPortKey(l.url_external) === key
  )) return true
  // 兜底：同端口匹配（同一台 NAS 可能有多个 IP，如 10.x vs 192.168.x，
  // 容器端口在宿主机上是唯一的，任一 IP + 同端口 = 同一个服务）
  const targetPort = key.split(':')[1]
  if (targetPort) {
    return existingLinks.value.some((l) => {
      for (const field of [l.url, l.url_internal, l.url_external]) {
        const k = hostPortKey(field)
        if (k && k.endsWith(':' + targetPort)) return true
      }
      return false
    })
  }
  return false
}
// 容器内网添加 URL 是否已存在于导航链接（按域名+端口判定）
function addUrlExists(c) {
  return linkExistsByUrl(containerAddUrl(c))
}

/* ── 容器视图：Tab / 搜索 / 列表卡片切换 ────────────── */
const viewMode = ref('list')        // 'list' | 'card'
const activeTab = ref('all')        // all | running | stopped | paused
const searchText = ref('')

const tabCounts = computed(() => {
  const cs = containers.value
  return {
    all: cs.length,
    running: cs.filter((c) => c.state === 'running').length,
    stopped: cs.filter((c) => c.state === 'stopped' || c.state === 'exited').length,
    paused: cs.filter((c) => c.state === 'paused').length,
  }
})

const filteredContainers = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  return containers.value.filter((c) => {
    if (activeTab.value === 'running' && c.state !== 'running') return false
    if (activeTab.value === 'stopped' && !(c.state === 'stopped' || c.state === 'exited')) return false
    if (activeTab.value === 'paused' && c.state !== 'paused') return false
    if (q && !((c.name || '').toLowerCase().includes(q) || (c.image || '').toLowerCase().includes(q))) return false
    return true
  })
})

/* ── 利用率历史（折线图）─────────────────────────── */
const history = ref([])   // { cpu, mem, disk, net } 最近 30 次采样
let lastRx = null
let lastT = 0
function pushHistory() {
  const u = util.value
  const now = Date.now()
  let net = null
  const rx = (u.network || {}).rx_bytes
  // rx_bytes 是各接口自开机累计字节之和。NAS 重启复位、或容器 veth 接口随启停
  // 增减都会使该总和回退变小，此时 (rx-lastRx) 为负。仅在「严格递增」时才求差，
  // 否则丢弃该样本并重置基线，避免负速率与折线图尖刺。
  if (lastRx != null && lastT && rx != null && rx >= lastRx) {
    const dt = (now - lastT) / 1000
    if (dt > 0) net = (rx - lastRx) / dt
  }
  lastRx = rx
  lastT = now
  history.value.push({
    cpu: u.cpu_usage ?? 0,
    mem: u.memory ?? 0,
    disk: u.disk_io ?? 0,
    net: net,
  })
  if (history.value.length > 30) history.value.shift()
}
function smoothPath(vals, w = 120, h = 32) {
  if (!vals || vals.length < 2) return ''
  // Y 轴自动留边距（上下各 pad 比例），避免贝塞尔控制点把线条推出图表区
  const rawMax = Math.max(...vals)
  const rawMin = Math.min(...vals)
  const rawRange = rawMax - rawMin || 1
  const pad = 0.15          // 上下各留 15% 边距
  const yMin = rawMin - rawRange * pad
  const yMax = rawMax + rawRange * pad
  const range = yMax - yMin
  const step = w / (vals.length - 1)
  const pts = vals.map((v, i) => [i * step, h - ((v - yMin) / range) * h])
  if (pts.length === 2) return `M ${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)} L ${pts[1][0].toFixed(1)} ${pts[1][1].toFixed(1)}`
  let d = `M ${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[i + 2] || p2
    const cp1x = p1[0] + (p2[0] - p0[0]) / 6
    const cp1y = p1[1] + (p2[1] - p0[1]) / 6
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6
    const cp2y = p2[1] - (p3[1] - p1[1]) / 6
    d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`
  }
  return d
}

/* ── 端口：本地缓存 + 被动更新 ───────────────────── */
const portCache = reactive({})       // containerId -> { loading, ports, error }
let prevStates = {}
let portsPrimed = false

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
    showConfig.value = false
    await loadSnapshot()
  } catch (e) {
    configMsg.value = '保存失败：' + e.message
  } finally {
    savingConfig.value = false
  }
}

async function testConfig() {
  testingConfig.value = true
  configMsg.value = ''
  try {
    const d = await api.monitorConfigTest({
      host: config.host, port: config.port, user: config.user,
      password: config.password, https: config.https,
    })
    configMsg.value = `连接成功：${d.hostname || 'DSM'}，发现 ${d.container_count || 0} 个容器`
  } catch (e) {
    configMsg.value = `连接失败：${e.message}`
  } finally {
    testingConfig.value = false
  }
}

async function loadSnapshot(force = false) {
  if (loading.value) return  // 防止慢响应期间自动刷新叠加请求
  loading.value = true
  error.value = ''
  try {
    const d = await api.monitorSnapshot(force)
    snap.value = d
    pushHistory()
    // 端口被动更新：首次拉取运行容器，之后仅状态变化的容器重拉
    await syncPorts()
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
    // 操作后清除该容器端口缓存，被动更新会重新拉取
    delete portCache[cid]
    await loadSnapshot()
  } catch (e) {
    error.value = e.message
  } finally {
    actingId.value = null
  }
}

async function fetchPorts(c, force = false) {
  // 首次展开或强制刷新时才请求；保留旧数据避免闪烁
  if (!force && portCache[c.id]) return
  portCache[c.id] = portCache[c.id] || { loading: false, ports: [], error: '' }
  portCache[c.id].loading = true
  portCache[c.id].error = ''
  try {
    const d = await api.monitorContainerDetail({ name: c.name || '', id: c.id || '' })
    portCache[c.id].ports = d.ports || []
  } catch (e) {
    portCache[c.id].error = e.message || '加载失败'
  } finally {
    portCache[c.id].loading = false
  }
}

// 手动刷新单个容器端口
function refreshContainerPorts(c) {
  return fetchPorts(c, true)
}

// 被动更新：首次拉取运行容器的端口；之后仅当容器状态变化时重拉该容器
async function syncPorts() {
  const cs = containers.value
  const changed = cs.filter((c) => prevStates[c.id] !== undefined && prevStates[c.id] !== c.state)
  if (!portsPrimed) {
    const toFetch = cs.filter((c) => c.state === 'running')
    await Promise.all(toFetch.map((c) => fetchPorts(c, true).catch(() => {})))
    portsPrimed = true
  } else if (changed.length) {
    await Promise.all(changed.map((c) => fetchPorts(c, true).catch(() => {})))
  }
  prevStates = {}
  cs.forEach((c) => { prevStates[c.id] = c.state })
}

function filteredPorts(cid) {
  const pc = portCache[cid]
  if (!pc || !pc.ports) return []
  return pc.ports.filter((p) => p.ip !== '::')
}

/* ── 端口重复性检测 ──────────────────────────────── */
const portCheckValue = ref('')
const showPortModal = ref(false)
const portCheckLoading = ref(false)
const portCheckErrors = ref([])
const portMatches = ref([])      // [{ name, networks, ports:[{map,host,container}] }]
const portConflict = ref([])     // 被多个容器占用的外部端口列表
async function checkPort() {
  const q = String(portCheckValue.value).trim()
  if (!q) return
  const cs = containers.value
  // 端口已随运行容器在快照时被动缓存（首次加载 + 状态变化更新）。
  // 检测前仅补充「尚未加载」的容器端口，已有缓存一律复用，不强制全量重抓
  // （容器端口配置极少变动，避免每次查询都重新抓取所有容器）。
  await Promise.all(cs
    .filter((c) => !portCache[c.id])
    .map((c) => fetchPorts(c, true).catch(() => {})))
  // 按容器聚合，避免同一容器多个映射重复出现
  const byContainer = {}
  const hostOwners = {}   // 外部端口 -> 占用它的容器名集合（用于冲突检测）
  for (const c of cs) {
    const pc = portCache[c.id]
    if (!pc || !pc.ports) continue
    let hostHit = false, contHit = false
    const ports = []
    for (const p of pc.ports) {
      const hostMatch = !!p.host && p.host !== 'None' && String(p.host) === q
      const contMatch = !!p.container && String(p.container) === q
      if (!hostMatch && !contMatch) continue
      if (hostMatch) hostHit = true
      if (contMatch) contHit = true
      ports.push({ host: p.host, container: p.container, type: p.type, hostMatch, contMatch })
      if (hostMatch && p.host && p.host !== 'None') {
        ;(hostOwners[p.host] = hostOwners[p.host] || new Set()).add(c.name)
      }
    }
    if (!ports.length) continue
    byContainer[c.name] = {
      name: c.name,
      state: c.state,
      networks: (c.networks || []).map((n) => n.name).join(', ') || '—',
      ports, hostHit, contHit,
    }
  }
  portMatches.value = Object.values(byContainer)
  portConflict.value = Object.entries(hostOwners)
    .filter(([, owners]) => owners.size > 1)
    .map(([h]) => h)
  showPortModal.value = true
}

/* ── IP 重复性检测 ───────────────────────────────── */
// 可选网络列表：从容器已加载的网络聚合，取 /24 前缀
const networkOptions = computed(() => {
  const map = {}   // name -> { name, prefix }
  for (const c of containers.value) {
    for (const n of (c.networks || [])) {
      if (!n.ip || n.ip === 'host') continue
      const parts = String(n.ip).split('.')
      if (parts.length !== 4) continue
      if (!map[n.name]) map[n.name] = { name: n.name, prefix: parts.slice(0, 3).join('.') }
    }
  }
  return Object.values(map).sort((a, b) => a.name.localeCompare(b.name))
})
const ipPrefix = computed(() => {
  const opt = networkOptions.value.find((o) => o.name === ipCheckNetwork.value)
  return opt ? opt.prefix : ''
})
const showIpModal = ref(false)
const ipCheckNetwork = ref('')
const ipCheckOctet = ref('')
const ipCheckValue = ref('')
const ipTarget = ref('')
const ipMatches = ref([])      // [{ name, state, networks:[{name, ip, matched}] }]
function openIpModal() {
  if (!ipCheckNetwork.value && networkOptions.value.length) {
    ipCheckNetwork.value = networkOptions.value[0].name
  }
  ipMatches.value = []
  ipTarget.value = ''
  showIpModal.value = true
}
function checkIp() {
  const net = ipCheckNetwork.value
  const octet = String(ipCheckOctet.value).trim()
  if (!net || !octet) return
  const target = `${ipPrefix.value}.${octet}`
  ipTarget.value = target
  const matches = []
  for (const c of containers.value) {
    const nets = (c.networks || []).map((n) => ({
      name: n.name,
      ip: n.ip || (n.name === 'host' ? 'host' : '—'),
      matched: !!n.ip && n.ip !== 'host' && n.name === net && n.ip === target,
    }))
    if (nets.some((n) => n.matched)) {
      matches.push({ name: c.name, state: c.state, networks: nets })
    }
  }
  ipMatches.value = matches
}

/* ── 格式化 ───────────────────────────────────────── */
function fmtBytes(b) {
  if (b == null) return '—'
  const u = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0, n = Number(b)
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++ }
  return (i ? n.toFixed(1) : n) + ' ' + u[i]
}
// 网络速率：输入字节/秒，按比特/秒（bps/Kbps/Mbps/Gbps）显示——网速业界用比特而非字节
function fmtNetRate(bps) {
  if (bps == null || bps < 0) return '—'
  const bits = bps * 8
  const u = ['bps', 'Kbps', 'Mbps', 'Gbps']
  let i = 0, n = bits
  while (n >= 1000 && i < u.length - 1) { n /= 1000; i++ }
  return (i ? n.toFixed(1) : Math.round(n)) + ' ' + u[i]
}
function fmtPort(p) {
  if (p.host && p.host !== 'None') return `${p.host} → ${p.container}/${p.type}`
  return `${p.container}/${p.type}（容器内）`
}
function fmtUptime(u) {
  if (!u) return '—'
  return String(u).split(':').map((p) => p.padStart(2, '0')).join(':')
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
  if (state === 'stopped' || state === 'exited') return '已停止'
  return state || '—'
}
// 容器信息卡背景：按状态整卡浅色填充（运行中绿 / 已停止红 / 已暂停黄）
function stateCardClass(state) {
  if (state === 'running') return 'bg-success/10 border-success/30'
  if (state === 'paused') return 'bg-warning/10 border-warning/30'
  return 'bg-error/10 border-error/30'
}

/* ── 生命周期 ─────────────────────────────────────── */
onMounted(async () => {
  await loadConfig()
  if (!needConfig.value) loadSnapshot()
  await loadExistingLinks()   // 必须等待：按钮 disabled / openAddConnection 去重都依赖 existingLinks
  timer = setInterval(() => {
    if (document.visibilityState === 'visible' && !needConfig.value && !loading.value) loadSnapshot()
  }, AUTO_INTERVAL)
  document.addEventListener('visibilitychange', onVisibilityChange)
})
function onVisibilityChange() {
  if (document.visibilityState === 'visible' && !needConfig.value && !loading.value) loadSnapshot()
}
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
  document.removeEventListener('visibilitychange', onVisibilityChange)
})

// 快速添加弹窗关闭后（无论保存或取消）刷新已有链接，及时更新按钮禁用态
watch(quickAddOpen, (v) => { if (!v) loadExistingLinks() })

async function runPortDiagnostic() {
  const query = String(portCheckValue.value).trim()
  if (!query || portCheckLoading.value) return
  portCheckLoading.value = true
  portCheckErrors.value = []
  try {
    const d = await api.monitorDiagnostics({ port: query })
    portMatches.value = (d.port_matches || []).map((m) => ({
      ...m,
      networks: (m.networks || []).map((n) => n.name).join(', ') || '—',
    }))
    portConflict.value = (d.port_conflicts || []).map((c) => `${c.ip}:${c.port}/${c.type}`)
    portCheckErrors.value = d.errors || []
    showPortModal.value = true
  } catch (e) {
    error.value = e.message || '端口检测失败'
  } finally {
    portCheckLoading.value = false
  }
}

async function runIpDiagnostic() {
  const target = String(ipCheckValue.value || (ipPrefix.value && ipCheckOctet.value ? `${ipPrefix.value}.${ipCheckOctet.value}` : '')).trim()
  if (!target) return
  ipTarget.value = target
  try {
    const d = await api.monitorDiagnostics({ ip: target })
    ipMatches.value = d.ip_matches || []
  } catch (e) {
    error.value = e.message || 'IP 检测失败'
  }
}
</script>

<template>
  <div>
    <!-- 标题 + 刷新 -->
    <div class="mb-6 flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
      <div>
        <h1 class="font-headline-lg text-headline-lg text-text-primary tracking-tight">群晖监控</h1>
        <p class="font-body-md text-body-md text-text-secondary mt-1">通过 DSM API 实时查看 NAS 利用率与 Docker 容器（仅管理员可见）</p>
      </div>
      <div class="flex items-center gap-2">
        <button v-if="!needConfig" @click="showConfig = !showConfig"
          class="px-3 py-2 rounded-xl text-sm font-semibold border transition-all flex items-center gap-1"
          :class="showConfig
            ? 'bg-primary text-on-primary hover:opacity-90'
            : 'bg-surface-container text-on-surface-variant border border-outline-variant/40 hover:bg-surface-container-high'">
          <span class="material-symbols-outlined text-[18px]">router</span>
          {{ showConfig ? '收起配置' : '连接配置' }}
        </button>
        <button v-if="!needConfig" @click="loadSnapshot(true)" :disabled="loading"
          class="px-3 py-2 rounded-xl text-sm font-semibold bg-surface-container text-on-surface-variant border border-outline-variant/40 hover:bg-surface-container-high transition-all flex items-center gap-1 disabled:opacity-60">
          <span class="material-symbols-outlined text-[18px]" :class="loading ? 'animate-spin' : ''">refresh</span>
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
      </div>
    </div>

    <!-- 群晖连接配置（内联卡片，不弹窗）。未配置时强制显示并高亮；已配置时由右上角按钮展开/收起 -->
    <div v-if="needConfig || showConfig"
      class="mb-6 rounded-[20px] border p-6 bg-surface-container-low"
      :class="needConfig ? 'border-warning/50' : 'border-outline-variant/30'">
      <div class="flex items-center gap-3 mb-4">
        <div class="w-9 h-9 rounded-xl bg-primary-fixed text-primary flex items-center justify-center shrink-0">
          <span class="material-symbols-outlined text-[20px]">router</span>
        </div>
        <div>
          <h2 class="font-headline-md text-headline-md text-text-primary">群晖连接配置</h2>
          <p v-if="needConfig" class="text-label-sm text-warning mt-0.5">尚未配置连接，请填写以下信息</p>
        </div>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
      </div>
      <label class="flex items-center gap-3 mt-4">
        <input v-model="config.https" type="checkbox" class="w-4 h-4 rounded accent-primary" />
        <span class="text-sm text-text-primary">使用 HTTPS（默认 5001 端口）</span>
      </label>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
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
      <p class="text-label-sm text-text-secondary mt-3">
        凭据存储于站点数据库（或环境变量 SYNO_*）。群晖账号需拥有 Container Manager / 系统监控权限。
      </p>
      <div class="flex items-center justify-end gap-3 mt-4">
        <span v-if="configMsg" class="text-label-sm text-text-secondary mr-auto">{{ configMsg }}</span>
        <button v-if="!needConfig" @click="showConfig = false"
          class="px-4 py-2 rounded-xl text-sm font-semibold bg-surface-container text-on-surface-variant border border-outline-variant/40 hover:bg-surface-container-high transition-all">
          收起
        </button>
        <button @click="testConfig" :disabled="testingConfig"
          class="px-4 py-2 rounded-xl text-sm font-semibold bg-surface-container text-on-surface-variant border border-outline-variant/40 hover:bg-surface-container-high transition-all disabled:opacity-60">
          {{ testingConfig ? '测试中…' : '测试连接' }}
        </button>
        <button @click="saveConfig" :disabled="savingConfig"
          class="px-4 py-2 rounded-xl text-sm font-semibold bg-primary text-on-primary hover:opacity-90 transition-all disabled:opacity-60">
          {{ savingConfig ? '保存中…' : '保存并连接' }}
        </button>
      </div>
    </div>

    <!-- 未配置 / 错误 -->
    <div v-if="needConfig" class="text-center text-text-secondary py-16">
      ⚠️ 尚未配置群晖连接，请填写上方配置表单
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

      <!-- 主机信息（SystemHealth） -->
      <div v-if="systemHealth" class="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-label-sm text-text-secondary mb-4">
        <span class="flex items-center gap-1.5">
          <span class="material-symbols-outlined text-[16px] text-primary">dns</span>
          {{ systemHealth.hostname || '—' }}
        </span>
        <span class="flex items-center gap-1.5">
          <span class="material-symbols-outlined text-[16px] text-info">schedule</span>
          已运行 {{ fmtUptime(systemHealth.uptime) }}
        </span>
        <span v-for="itf in (systemHealth.interfaces || [])" :key="itf.id" class="flex items-center gap-1.5">
          <span class="material-symbols-outlined text-[16px] text-success">lan</span>
          {{ itf.ip || '—' }}
        </span>
      </div>

      <!-- 利用率概览卡片：Grid stretch 保持四卡等高；含折线图的卡片用 flex 纵向布局，
           SVG flex-1 自动填满剩余空间，避免线条被遮挡 -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-grid-gutter mb-6">
        <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 flex flex-col min-h-0">
          <div class="flex items-center justify-between shrink-0">
            <span class="text-label-sm text-text-secondary">CPU 使用率</span>
            <span class="material-symbols-outlined text-[18px] text-primary">memory</span>
          </div>
          <div class="font-headline-md text-headline-md text-text-primary shrink-0">{{ util.cpu_usage != null ? util.cpu_usage + '%' : '—' }}</div>
          <svg viewBox="0 0 120 32" preserveAspectRatio="none" class="w-full flex-1 min-h-[40px] mt-1 text-primary">
            <path :d="smoothPath(history.map(h => h.cpu))" fill="none" stroke="currentColor" stroke-width="0.75" stroke-linejoin="round" stroke-linecap="round" />
          </svg>
          <div class="text-label-sm text-text-secondary shrink-0" v-if="util.cpu_1 != null">负载 {{ util.cpu_1 }}/{{ util.cpu_5 }}/{{ util.cpu_15 }}</div>
        </div>
        <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 flex flex-col min-h-0">
          <div class="flex items-center justify-between shrink-0">
            <span class="text-label-sm text-text-secondary">内存使用率</span>
            <span class="material-symbols-outlined text-[18px] text-info">developer_board</span>
          </div>
          <div class="font-headline-md text-headline-md text-text-primary shrink-0">{{ util.memory != null ? util.memory + '%' : '—' }}</div>
          <svg viewBox="0 0 120 32" preserveAspectRatio="none" class="w-full flex-1 min-h-[40px] mt-1 text-info">
            <path :d="smoothPath(history.map(h => h.mem))" fill="none" stroke="currentColor" stroke-width="0.75" stroke-linejoin="round" stroke-linecap="round" />
          </svg>
        </div>
        <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 flex flex-col min-h-0">
          <div class="flex items-center justify-between shrink-0">
            <span class="text-label-sm text-text-secondary">网络速率</span>
            <span class="material-symbols-outlined text-[18px] text-success">lan</span>
          </div>
          <div class="font-headline-md text-headline-md text-text-primary shrink-0">{{ history.length ? fmtNetRate(history[history.length - 1].net) : '—' }}</div>
          <svg viewBox="0 0 120 32" preserveAspectRatio="none" class="w-full flex-1 min-h-[40px] mt-1 text-success">
            <path :d="smoothPath(history.map(h => h.net))" fill="none" stroke="currentColor" stroke-width="0.75" stroke-linejoin="round" stroke-linecap="round" />
          </svg>
        </div>
        <!-- 硬盘（所有卷合并到一张卡片，每行一个卷：名称 + 容量 + IO + 进度条） -->
        <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50">
          <div class="flex items-center justify-between mb-2">
            <span class="text-label-sm text-text-secondary">硬盘</span>
            <span class="material-symbols-outlined text-[18px] text-warning">storage</span>
          </div>
          <div v-if="diskVolumes.length" class="space-y-2.5">
            <div v-for="(d, i) in diskVolumes" :key="'disk' + i" class="space-y-1">
              <div class="flex items-center gap-3 text-sm min-w-0">
                <span class="text-text-primary font-medium shrink-0 w-20 truncate" :title="d.display_name || d.name">{{ d.display_name || d.name }}</span>
                <span class="text-text-primary text-xs shrink-0">{{ d.used != null ? fmtBytes(d.used) + ' / ' + fmtBytes(d.total) : '—' }}</span>
                <span class="text-text-secondary text-xs shrink-0 ml-auto">
                  <template v-if="d.io">IO {{ fmtBytes(d.io.read_byte) }} / {{ fmtBytes(d.io.write_byte) }}</template>
                  <template v-else>IO —</template>
                </span>
              </div>
              <div v-if="d.usage_pct != null" class="flex items-center gap-2">
                <div class="flex-1 h-1.5 rounded-full bg-surface-container overflow-hidden">
                  <div class="h-full rounded-full transition-all" :class="barColor(d.usage_pct)" :style="{ width: (d.usage_pct || 0) + '%' }"></div>
                </div>
                <span class="text-label-sm text-text-secondary w-9 text-right shrink-0">{{ d.usage_pct }}%</span>
              </div>
            </div>
          </div>
          <div v-else class="text-label-sm text-text-secondary py-1">无存储卷数据</div>
        </div>
      </div>

      <!-- Docker 容器 -->
      <div class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50">
        <!-- 头部：标题 + 视图切换 -->
        <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 mb-4">
          <div class="flex items-center gap-2">
            <h2 class="font-headline-sm text-headline-sm text-text-primary">Docker 容器</h2>
            <span class="text-label-sm text-text-secondary">{{ filteredContainers.length }}/{{ containers.length }} 个</span>
          </div>
          <div class="flex items-center gap-2">
            <!-- 搜索 -->
            <div class="relative">
              <span class="material-symbols-outlined text-[18px] text-text-secondary absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none">search</span>
              <input v-model="searchText" type="text" placeholder="搜索名称 / 镜像"
                class="pl-9 pr-3 py-2 rounded-xl text-sm bg-surface-container text-text-primary border border-outline-variant/40 focus:outline-none focus:ring-2 focus:ring-primary/40 w-44" />
            </div>
            <!-- 视图切换 -->
            <div class="flex rounded-xl border border-outline-variant/40 overflow-hidden">
              <button @click="viewMode = 'list'" :class="viewMode === 'list' ? 'bg-primary/10 text-primary' : 'bg-surface-container text-text-secondary hover:bg-surface-container-high'"
                class="px-2.5 py-2 transition-all" title="列表视图">
                <span class="material-symbols-outlined text-[18px]">view_list</span>
              </button>
              <button @click="viewMode = 'card'" :class="viewMode === 'card' ? 'bg-primary/10 text-primary' : 'bg-surface-container text-text-secondary hover:bg-surface-container-high'"
                class="px-2.5 py-2 transition-all border-l border-outline-variant/40" title="卡片视图">
                <span class="material-symbols-outlined text-[18px]">view_module</span>
              </button>
            </div>
            <!-- 端口检测 -->
            <div class="flex items-center gap-1 rounded-xl border border-outline-variant/40 overflow-hidden bg-surface-container">
              <input v-model="portCheckValue" @keyup.enter="runPortDiagnostic" type="text" placeholder="端口检测"
                class="px-3 py-2 text-sm bg-transparent text-text-primary focus:outline-none w-24" />
              <button @click="runPortDiagnostic"
                class="px-2.5 py-2 text-text-secondary hover:bg-surface-container-high transition-all" title="检测端口是否被占用">
                <span class="material-symbols-outlined text-[18px]">find_in_page</span>
              </button>
            </div>
            <!-- IP 检测 -->
            <button @click="openIpModal"
              class="flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-semibold bg-surface-container text-on-surface-variant border border-outline-variant/40 hover:bg-surface-container-high transition-all" title="检测 IP 是否被占用">
              <span class="material-symbols-outlined text-[18px]">pin</span>
              IP 检测
            </button>
          </div>
        </div>

        <!-- 状态 Tab -->
        <div class="flex flex-wrap gap-2 mb-4">
          <button @click="activeTab = 'all'" :class="activeTab === 'all' ? 'bg-primary text-on-primary' : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high'"
            class="px-3 py-1.5 rounded-full text-xs font-semibold transition-all">{{ '全部' }} <span class="opacity-70">{{ tabCounts.all }}</span></button>
          <button @click="activeTab = 'running'" :class="activeTab === 'running' ? 'bg-success text-on-primary' : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high'"
            class="px-3 py-1.5 rounded-full text-xs font-semibold transition-all">运行中 <span class="opacity-70">{{ tabCounts.running }}</span></button>
          <button @click="activeTab = 'stopped'" :class="activeTab === 'stopped' ? 'bg-text-secondary text-on-primary' : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high'"
            class="px-3 py-1.5 rounded-full text-xs font-semibold transition-all">已停止 <span class="opacity-70">{{ tabCounts.stopped }}</span></button>
          <button @click="activeTab = 'paused'" :class="activeTab === 'paused' ? 'bg-warning text-on-primary' : 'bg-surface-container text-on-surface-variant hover:bg-surface-container-high'"
            class="px-3 py-1.5 rounded-full text-xs font-semibold transition-all">已暂停 <span class="opacity-70">{{ tabCounts.paused }}</span></button>
        </div>

        <div v-if="!containers.length" class="text-text-secondary text-sm py-4">未获取到容器（或群晖未安装 Container Manager）</div>
        <div v-else-if="!filteredContainers.length" class="text-text-secondary text-sm py-4">没有符合当前筛选条件的容器</div>

        <!-- 列表视图 -->
        <div v-else-if="viewMode === 'list'" class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-label-sm text-text-secondary border-b border-surface-variant/40">
                <th class="text-left py-2 pr-2 font-medium">名称</th>
                <th class="text-left py-2 pr-2 font-medium">状态</th>
                <th class="text-left py-2 pr-2 font-medium">镜像</th>
                <th class="text-left py-2 pr-2 font-medium">网络 / IP</th>
                <th class="text-left py-2 pr-2 font-medium">端口</th>
                <th class="text-right py-2 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="c in filteredContainers" :key="c.id">
                <tr class="border-b border-surface-variant/30 hover:bg-surface-container/40">
                  <td class="py-2 pr-2 text-text-primary font-medium">
                    <div class="flex items-center gap-2">
                      <span>{{ c.name }}</span>
                      <span v-if="c.project" class="text-[10px] px-1.5 py-0.5 rounded bg-surface-container text-text-secondary">{{ c.project }}</span>
                    </div>
                  </td>
                  <td class="py-2 pr-2">
                    <span class="inline-flex items-center gap-1.5">
                      <span class="w-2 h-2 rounded-full" :class="stateDot(c.state)"></span>
                      <span class="text-text-secondary">{{ stateText(c.state) }}</span>
                    </span>
                  </td>
                  <td class="py-2 pr-2 text-text-secondary max-w-[220px] truncate">{{ c.image || '—' }}</td>
                  <td class="py-2 pr-2 text-text-primary">
                    <div v-if="c.networks && c.networks.length" class="flex flex-col gap-0.5 font-mono text-xs">
                      <span v-for="n in c.networks" :key="n.name">
                        <span class="text-text-secondary">{{ n.name }}</span>:
                        <span>{{ n.ip || (n.name === 'host' ? 'host' : '—') }}</span>
                      </span>
                    </div>
                    <span v-else class="text-text-secondary">—</span>
                  </td>
                  <td class="py-2 pr-2">
                    <div v-if="!portCache[c.id]">
                      <button @click.stop="refreshContainerPorts(c)" class="text-label-sm text-primary hover:underline">加载端口</button>
                    </div>
                    <div v-else-if="portCache[c.id].loading" class="text-text-secondary text-xs">加载中…</div>
                    <div v-else-if="portCache[c.id].error" class="text-error text-xs">{{ portCache[c.id].error }}</div>
                    <div v-else-if="!filteredPorts(c.id).length" class="text-text-secondary text-xs">无</div>
                    <div v-else class="flex flex-wrap gap-1.5 items-center">
                      <span v-for="(p, i) in filteredPorts(c.id)" :key="i"
                        class="px-1.5 py-0.5 rounded-lg bg-surface-container text-text-primary font-mono text-[11px] border border-outline-variant/40">
                        {{ fmtPort(p) }}
                      </span>
                      <button @click.stop="refreshContainerPorts(c)" class="text-text-secondary hover:text-primary" title="刷新端口">
                        <span class="material-symbols-outlined text-[14px]" :class="portCache[c.id].loading ? 'animate-spin' : ''">refresh</span>
                      </button>
                    </div>
                  </td>
                  <td class="py-2 text-right whitespace-nowrap" @click.stop>
                    <button v-if="c.state !== 'running'" @click="act(c.name, 'start')" :disabled="actingId === c.name + ':start'"
                      class="px-2 py-1 rounded-lg text-xs font-semibold bg-success/10 text-success hover:bg-success/20 transition-all disabled:opacity-60">启动</button>
                    <button v-if="c.state === 'running'" @click="act(c.name, 'stop')" :disabled="actingId === c.name + ':stop'"
                      class="px-2 py-1 rounded-lg text-xs font-semibold bg-error/10 text-error hover:bg-error/20 transition-all disabled:opacity-60">停止</button>
                    <button @click="act(c.name, 'restart')" :disabled="actingId === c.name + ':restart'"
                      class="px-2 py-1 rounded-lg text-xs font-semibold bg-surface-container text-on-surface-variant border border-outline-variant/40 hover:bg-surface-container-high transition-all disabled:opacity-60 ml-1">重启</button>
                    <!-- 快速添加为导航链接：仅内网（群晖宿主 IP + docker 宿主机端口）；未运行或地址已存在则禁用 -->
                    <button v-if="c.state === 'running'" @click="openAddConnection(c)"
                      :disabled="addUrlExists(c)"
                      class="px-2 py-1 rounded-lg text-xs font-semibold transition-all ml-1"
                      :class="addUrlExists(c)
                        ? 'bg-surface-container text-on-surface-variant/40 border border-outline-variant/30 cursor-not-allowed'
                        : 'bg-primary/10 text-primary hover:bg-primary/20'"
                      :title="addUrlExists(c) ? '该内网地址已存在链接' : '快速添加为导航链接（内网地址）'">添加连接</button>
                    <button v-else disabled
                      class="px-2 py-1 rounded-lg text-xs font-semibold bg-surface-container text-on-surface-variant/40 border border-outline-variant/30 transition-all ml-1 cursor-not-allowed" title="容器未运行，暂不可用">添加连接</button>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>

        <!-- 卡片视图 -->
        <div v-else class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          <div v-for="c in filteredContainers" :key="c.id"
            class="rounded-2xl border border-surface-variant/40 bg-surface-container/30 p-3 flex flex-col gap-2">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <div class="flex items-center gap-1.5">
                  <span class="w-2 h-2 rounded-full shrink-0" :class="stateDot(c.state)"></span>
                  <span class="font-medium text-text-primary text-sm truncate">{{ c.name }}</span>
                </div>
                <div class="flex items-center gap-1.5 mt-0.5">
                  <span class="text-[11px] text-text-secondary">{{ stateText(c.state) }}</span>
                  <span v-if="c.project" class="text-[9px] px-1 py-0.5 rounded bg-surface-container text-text-secondary">{{ c.project }}</span>
                </div>
              </div>
              <div class="flex items-center gap-1 shrink-0" @click.stop>
                <button v-if="c.state !== 'running'" @click="act(c.name, 'start')" :disabled="actingId === c.name + ':start'"
                  class="px-1.5 py-0.5 rounded-md text-[11px] font-semibold bg-success/10 text-success hover:bg-success/20 transition-all disabled:opacity-60">启动</button>
                <button v-if="c.state === 'running'" @click="act(c.name, 'stop')" :disabled="actingId === c.name + ':stop'"
                  class="px-1.5 py-0.5 rounded-md text-[11px] font-semibold bg-error/10 text-error hover:bg-error/20 transition-all disabled:opacity-60">停止</button>
                <button @click="act(c.name, 'restart')" :disabled="actingId === c.name + ':restart'"
                  class="px-1.5 py-0.5 rounded-md text-[11px] font-semibold bg-surface-container text-on-surface-variant border border-outline-variant/40 hover:bg-surface-container-high transition-all disabled:opacity-60">重启</button>
                <button v-if="c.state === 'running'" @click="openAddConnection(c)"
                  :disabled="addUrlExists(c)"
                  class="px-1.5 py-0.5 rounded-md text-[11px] font-semibold transition-all"
                  :class="addUrlExists(c)
                    ? 'bg-surface-container text-on-surface-variant/40 border border-outline-variant/30 cursor-not-allowed'
                    : 'bg-primary/10 text-primary hover:bg-primary/20'"
                  :title="addUrlExists(c) ? '该内网地址已存在链接' : '快速添加为导航链接（内网地址）'">添加连接</button>
                <button v-else disabled title="容器未运行，暂不可用"
                  class="px-1.5 py-0.5 rounded-md text-[11px] font-semibold bg-surface-container text-on-surface-variant/40 border border-outline-variant/30 transition-all cursor-not-allowed">添加连接</button>
              </div>
            </div>
            <div class="text-[11px] text-text-secondary truncate">镜像：{{ c.image || '—' }}</div>
            <div v-if="c.networks && c.networks.length" class="flex flex-col gap-0.5 font-mono text-[11px] text-text-primary">
              <span v-for="n in c.networks" :key="n.name" class="truncate">
                <span class="text-text-secondary">{{ n.name }}</span>:
                <span>{{ n.ip || (n.name === 'host' ? 'host' : '—') }}</span>
              </span>
            </div>
            <div class="mt-auto">
              <div v-if="!portCache[c.id]">
                <button @click.stop="refreshContainerPorts(c)" class="text-[11px] text-primary hover:underline">加载端口</button>
              </div>
              <div v-else-if="portCache[c.id].loading" class="text-text-secondary text-[11px]">加载中…</div>
              <div v-else-if="portCache[c.id].error" class="text-error text-[11px]">{{ portCache[c.id].error }}</div>
              <div v-else-if="!filteredPorts(c.id).length" class="text-text-secondary text-[11px]">无端口</div>
              <div v-else class="flex flex-wrap gap-1">
                <span v-for="(p, i) in filteredPorts(c.id)" :key="i"
                  class="px-1.5 py-0.5 rounded bg-surface-container text-text-primary font-mono text-[10px] border border-outline-variant/40">
                  {{ fmtPort(p) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <p class="text-center text-label-sm text-text-secondary py-4">
        每 {{ AUTO_INTERVAL / 1000 }} 秒自动刷新容器与利用率；端口随运行容器自动加载，容器启停后被动更新；可在卡片右上「端口检测」查询某端口被哪个容器占用。
      </p>

      <!-- 端口重复性检测弹窗 -->
      <div v-if="showPortModal" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="showPortModal = false"></div>
        <div class="relative bg-bg-card w-full max-w-[520px] rounded-[20px] shadow-2xl overflow-hidden flex flex-col border border-outline-variant/30">
          <div class="px-6 py-4 border-b border-outline-variant/20 flex justify-between items-center shrink-0">
            <div class="flex items-center gap-3">
              <div class="w-9 h-9 rounded-xl bg-primary-fixed text-primary flex items-center justify-center">
                <span class="material-symbols-outlined text-[20px]">find_in_page</span>
              </div>
              <h2 class="font-headline-md text-headline-md text-text-primary">端口检测结果：{{ portCheckValue }}</h2>
            </div>
            <button class="w-9 h-9 rounded-full hover:bg-surface-container transition-colors flex items-center justify-center text-text-secondary" @click="showPortModal = false">
              <span class="material-symbols-outlined">close</span>
            </button>
          </div>
          <div class="p-6">
            <div v-if="!portMatches.length" class="text-text-secondary text-sm py-4 text-center">
              未检测到端口 {{ portCheckValue }} 被任何容器占用 ✓
            </div>
            <div v-if="portCheckErrors.length" class="mt-3 rounded-xl bg-warning/10 border border-warning/30 p-3 text-sm text-warning">
              部分容器端口详情获取失败，结果可能不完整：{{ portCheckErrors.length }} 个
            </div>
            <div v-else class="space-y-3">
              <div v-for="(m, i) in portMatches" :key="i" class="rounded-xl border p-3" :class="stateCardClass(m.state)">
                <div class="flex items-center gap-2 mb-1.5 flex-wrap">
                  <span class="material-symbols-outlined text-[18px] text-primary">label</span>
                  <span class="font-medium text-text-primary">{{ m.name }}</span>
                  <!-- 该容器查询端口的类型（宿主机端口 / 容器内部端口，可同时命中） -->
                  <span v-if="m.hostHit" class="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/15 text-primary">宿主机端口</span>
                  <span v-if="m.contHit" class="text-[10px] px-1.5 py-0.5 rounded-full bg-info/15 text-info">容器内部端口</span>
                </div>
                <div class="text-label-sm text-text-secondary">网络：{{ m.networks }}</div>
                <div class="mt-2 flex flex-wrap gap-1.5">
                  <span v-for="(p, j) in m.ports" :key="j"
                    class="px-2 py-1 rounded-lg font-mono text-xs border bg-primary/10 border-primary/40 text-text-primary flex items-center gap-1.5">
                    <template v-if="p.host && p.host !== 'None'">
                      <b :class="p.hostMatch ? 'text-primary font-bold' : ''">{{ p.host }}</b><span> → </span>
                    </template>
                    <b :class="p.contMatch ? 'text-primary font-bold' : ''">{{ p.container }}</b>/{{ p.type }}
                  </span>
                </div>
              </div>
              <p v-if="portConflict.length" class="text-label-sm text-warning">
                ⚠️ 外部端口 {{ portConflict.join('、') }} 被多个容器占用，存在端口冲突（仅宿主机发布端口计入，容器内部端口不计）。
              </p>
            </div>
          </div>
          <div class="px-6 py-4 border-t border-outline-variant/20 flex justify-end shrink-0">
            <button @click="showPortModal = false"
              class="px-4 py-2 rounded-xl text-sm font-semibold bg-surface-container text-on-surface-variant border border-outline-variant/40 hover:bg-surface-container-high transition-all">
              关闭
            </button>
          </div>
        </div>
      </div>

      <!-- IP 重复检测弹窗 -->
      <div v-if="showIpModal" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
        <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="showIpModal = false"></div>
        <div class="relative bg-bg-card w-full max-w-[640px] rounded-[20px] shadow-2xl overflow-hidden flex flex-col border border-outline-variant/30">
          <div class="px-6 py-4 border-b border-outline-variant/20 flex justify-between items-center shrink-0">
            <div class="flex items-center gap-3">
              <div class="w-9 h-9 rounded-xl bg-primary-fixed text-primary flex items-center justify-center">
                <span class="material-symbols-outlined text-[20px]">pin</span>
              </div>
              <h2 class="font-headline-md text-headline-md text-text-primary">IP 重复检测</h2>
            </div>
            <button @click="showIpModal = false" class="text-text-secondary hover:text-text-primary transition-all">
              <span class="material-symbols-outlined text-[22px]">close</span>
            </button>
          </div>
          <div class="p-6 space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center gap-3">
              <label class="flex flex-col gap-1">
                <span class="text-label-sm text-text-secondary">网络类型</span>
                <select v-model="ipCheckNetwork"
                  class="px-3 py-2 rounded-xl text-sm bg-surface-container text-text-primary border border-outline-variant/40 focus:outline-none focus:ring-2 focus:ring-primary/40">
                  <option v-for="o in networkOptions" :key="o.name" :value="o.name">{{ o.name }}</option>
                </select>
              </label>
              <label class="flex flex-col gap-1 flex-1">
                <span class="text-label-sm text-text-secondary">IP 地址（前 24 位 + 末位）</span>
                <div class="flex items-center gap-0 rounded-xl border border-outline-variant/40 overflow-hidden bg-surface-container focus-within:ring-2 focus-within:ring-primary/40">
                  <span class="px-3 py-2 font-mono text-sm text-text-secondary whitespace-nowrap">{{ ipPrefix }}.</span>
                  <input v-model="ipCheckOctet" @keyup.enter="checkIp" type="number" min="0" max="255" placeholder="末位，如 10"
                    class="flex-1 px-2 py-2 text-sm bg-transparent text-text-primary font-mono focus:outline-none" />
                </div>
              </label>
              <label class="flex flex-col gap-1 flex-1">
                <span class="text-label-sm text-text-secondary">或输入完整 IP</span>
                <input v-model="ipCheckValue" @keyup.enter="runIpDiagnostic" type="text" placeholder="例如 172.18.0.10"
                  class="px-3 py-2 rounded-xl text-sm bg-surface-container text-text-primary border border-outline-variant/40 focus:outline-none focus:ring-2 focus:ring-primary/40 font-mono" />
              </label>
            <button @click="runIpDiagnostic"
                class="sm:self-end px-4 py-2 rounded-xl text-sm font-semibold bg-primary text-on-primary hover:opacity-90 transition-all">
                检测
              </button>
            </div>
            <div v-if="!ipMatches.length && ipTarget" class="text-text-secondary text-sm py-4 text-center">
              未检测到 IP {{ ipTarget }} 被任何容器占用 ✓
            </div>
            <div v-else-if="ipMatches.length" class="space-y-3">
              <div v-for="(m, i) in ipMatches" :key="i" class="rounded-xl border p-3" :class="stateCardClass(m.state)">
                <div class="flex items-center gap-2 mb-1.5">
                  <span class="material-symbols-outlined text-[18px] text-primary">label</span>
                  <span class="font-medium text-text-primary">{{ m.name }}</span>
                </div>
                <div class="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs">
                  <span v-for="(n, j) in m.networks" :key="j" :class="n.matched ? 'text-primary font-bold' : 'text-text-secondary'">
                    {{ n.name }}: {{ n.ip }}
                  </span>
                </div>
              </div>
            </div>
            <p v-if="!networkOptions.length" class="text-label-sm text-text-secondary">
              暂无可用网络（容器未加载网络信息）
            </p>
          </div>
          <div class="px-6 py-4 border-t border-outline-variant/20 flex justify-end shrink-0">
            <button @click="showIpModal = false"
              class="px-4 py-2 rounded-xl text-sm font-semibold bg-surface-container text-on-surface-variant border border-outline-variant/40 hover:bg-surface-container-high transition-all">
              关闭
            </button>
          </div>
        </div>
      </div>

      <!-- 从 Docker 容器快速添加为导航链接（复用快速添加弹窗：自动识别内网 + 自动获取图标） -->
      <QuickAddLink :open="quickAddOpen" :prefill-url="quickPrefill.url" :prefill-title="quickPrefill.title" @update:open="quickAddOpen = $event" />
    </div>
  </div>
</template>
