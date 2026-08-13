<script setup>
import { ref, computed, watch } from 'vue'
import { api } from '../api/client'

const props = defineProps({ open: Boolean })
const emit = defineEmits(['update:open'])
function close() { emit('update:open', false) }

/* ── 数据拉取（自包含，不依赖监控页状态） ───────────── */
const loading = ref(false)
const loadError = ref('')
const containers = ref([])

async function ensureData() {
  if (containers.value.length || loading.value) return
  loading.value = true
  loadError.value = ''
  try {
    const d = await api.monitorSnapshot()
    containers.value = d.containers || []
  } catch (e) {
    loadError.value = e.message || '加载群晖数据失败'
  } finally {
    loading.value = false
  }
}
watch(() => props.open, (v) => { if (v) ensureData() })

function stateCardClass(state) {
  if (state === 'running') return 'bg-success/10 border-success/30'
  if (state === 'paused') return 'bg-warning/10 border-warning/30'
  return 'bg-error/10 border-error/30'
}

/* ── 端口重复性检测 ───────────────────────────────── */
const portValue = ref('')
const portMatches = ref([])
const portConflict = ref([])
const portBusy = ref(false)
async function checkPort() {
  const q = String(portValue.value).trim()
  if (!q || portBusy.value) return
  portBusy.value = true
  try {
    await ensureData()
    // 强制刷新全部容器端口后再查
    const results = await Promise.all(
      containers.value.map((c) =>
        api.monitorContainerDetail({ name: c.name || '', id: c.id || '' })
          .then((d) => ({ c, ports: d.ports || [] }))
          .catch(() => ({ c, ports: [] }))
      )
    )
    const byContainer = {}
    const hostOwners = {}
    for (const { c, ports } of results) {
      let hostHit = false, contHit = false
      const ps = []
      for (const p of ports) {
        const hostMatch = !!p.host && p.host !== 'None' && String(p.host) === q
        const contMatch = !!p.container && String(p.container) === q
        if (!hostMatch && !contMatch) continue
        if (hostMatch) hostHit = true
        if (contMatch) contHit = true
        ps.push({ host: p.host, container: p.container, type: p.type, hostMatch, contMatch })
        if (hostMatch && p.host && p.host !== 'None') {
          ;(hostOwners[p.host] = hostOwners[p.host] || new Set()).add(c.name)
        }
      }
      if (!ps.length) continue
      byContainer[c.name] = {
        name: c.name,
        state: c.state,
        networks: (c.networks || []).map((n) => n.name).join(', ') || '—',
        ports: ps, hostHit, contHit,
      }
    }
    portMatches.value = Object.values(byContainer)
    portConflict.value = Object.entries(hostOwners)
      .filter(([, owners]) => owners.size > 1)
      .map(([h]) => h)
  } finally {
    portBusy.value = false
  }
}

/* ── IP 重复性检测 ────────────────────────────────── */
const networkOptions = computed(() => {
  const map = {}
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
const ipNetwork = ref('')
const ipOctet = ref('')
const ipTarget = ref('')
const ipMatches = ref([])
const ipPrefix = computed(() => {
  const opt = networkOptions.value.find((o) => o.name === ipNetwork.value)
  return opt ? opt.prefix : ''
})
watch(networkOptions, (opts) => {
  if (!ipNetwork.value && opts.length) ipNetwork.value = opts[0].name
})
function checkIp() {
  const net = ipNetwork.value
  const octet = String(ipOctet.value).trim()
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
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
    <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="close"></div>
    <div class="relative bg-bg-card w-full max-w-[680px] max-h-[88vh] rounded-[20px] shadow-2xl overflow-hidden flex flex-col border border-outline-variant/30">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-outline-variant/20 flex justify-between items-center shrink-0">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-xl bg-primary-fixed text-primary flex items-center justify-center">
            <span class="material-symbols-outlined text-[20px]">hub</span>
          </div>
          <h2 class="font-headline-md text-headline-md text-text-primary">网络检测</h2>
        </div>
        <button @click="close" class="text-text-secondary hover:text-text-primary transition-all">
          <span class="material-symbols-outlined text-[22px]">close</span>
        </button>
      </div>

      <div class="p-6 overflow-y-auto space-y-8">
        <p v-if="loadError" class="text-error text-sm">{{ loadError }}</p>
        <p v-else-if="loading" class="text-text-secondary text-sm py-2">加载群晖数据…</p>

        <!-- 端口重复性检测 -->
        <section>
          <div class="flex items-center gap-2 mb-3">
            <span class="material-symbols-outlined text-[18px] text-primary">find_in_page</span>
            <h3 class="font-headline-sm text-headline-sm text-text-primary">端口重复性检测</h3>
          </div>
          <div class="flex items-center gap-2">
            <input v-model="portValue" @keyup.enter="checkPort" :disabled="portBusy" type="text"
              placeholder="输入端口号，如 3000" class="flex-1 px-3 py-2 rounded-xl text-sm bg-surface-container text-text-primary border border-outline-variant/40 focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-60" />
            <button @click="checkPort" :disabled="portBusy"
              class="px-4 py-2 rounded-xl text-sm font-semibold bg-primary text-on-primary hover:opacity-90 transition-all disabled:opacity-60">
              {{ portBusy ? '检测中…' : '检测' }}
            </button>
          </div>
          <div v-if="!portMatches.length && portValue" class="text-text-secondary text-sm py-3 text-center">
            未检测到端口 {{ portValue }} 被任何容器占用 ✓
          </div>
          <div v-else-if="portMatches.length" class="mt-3 space-y-3">
            <div v-for="(m, i) in portMatches" :key="i" class="rounded-xl border p-3" :class="stateCardClass(m.state)">
              <div class="flex items-center gap-2 mb-1.5 flex-wrap">
                <span class="material-symbols-outlined text-[18px] text-primary">label</span>
                <span class="font-medium text-text-primary">{{ m.name }}</span>
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
        </section>

        <div class="border-t border-outline-variant/20"></div>

        <!-- IP 重复性检测 -->
        <section>
          <div class="flex items-center gap-2 mb-3">
            <span class="material-symbols-outlined text-[18px] text-primary">pin</span>
            <h3 class="font-headline-sm text-headline-sm text-text-primary">IP 重复性检测</h3>
          </div>
          <div class="flex flex-col sm:flex-row sm:items-end gap-3">
            <label class="flex flex-col gap-1">
              <span class="text-label-sm text-text-secondary">网络类型</span>
              <select v-model="ipNetwork"
                class="px-3 py-2 rounded-xl text-sm bg-surface-container text-text-primary border border-outline-variant/40 focus:outline-none focus:ring-2 focus:ring-primary/40">
                <option v-for="o in networkOptions" :key="o.name" :value="o.name">{{ o.name }}</option>
              </select>
            </label>
            <label class="flex flex-col gap-1 flex-1">
              <span class="text-label-sm text-text-secondary">IP 地址（前 24 位 + 末位）</span>
              <div class="flex items-center gap-0 rounded-xl border border-outline-variant/40 overflow-hidden bg-surface-container focus-within:ring-2 focus-within:ring-primary/40">
                <span class="px-3 py-2 font-mono text-sm text-text-secondary whitespace-nowrap">{{ ipPrefix }}.</span>
                <input v-model="ipOctet" @keyup.enter="checkIp" type="number" min="0" max="255" placeholder="末位，如 10"
                  class="flex-1 px-2 py-2 text-sm bg-transparent text-text-primary font-mono focus:outline-none" />
              </div>
            </label>
            <button @click="checkIp"
              class="px-4 py-2 rounded-xl text-sm font-semibold bg-primary text-on-primary hover:opacity-90 transition-all">
              检测
            </button>
          </div>
          <div v-if="!networkOptions.length" class="text-label-sm text-text-secondary mt-3">
            暂无可用网络（容器未加载网络信息或未配置群晖连接）
          </div>
          <div v-else-if="!ipMatches.length && ipTarget" class="text-text-secondary text-sm py-3 text-center">
            未检测到 IP {{ ipTarget }} 被任何容器占用 ✓
          </div>
          <div v-else-if="ipMatches.length" class="mt-3 space-y-3">
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
        </section>
      </div>
    </div>
  </div>
</template>
