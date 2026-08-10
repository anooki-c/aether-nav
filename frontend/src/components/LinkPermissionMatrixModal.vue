<script setup>
import { ref, watch, computed } from 'vue'
import { api } from '../api/client'

const props = defineProps({
  open: { type: Boolean, default: false },
  link: { type: Object, default: null },
})
const emit = defineEmits(['update:open'])

const loading = ref(false)
const linkInfo = ref(null)
const users = ref([])
const summary = ref({ total: 0, visible: 0, hidden: 0, by_layer: {} })
const filterRole = ref('')

async function load() {
  if (!props.link) return
  loading.value = true
  try {
    const d = await api.linkPermissions(props.link.id)
    linkInfo.value = d.link
    users.value = d.users || []
    summary.value = d.summary || { total: 0, visible: 0, hidden: 0, by_layer: {} }
  } catch (e) {
    users.value = []
    linkInfo.value = null
  } finally {
    loading.value = false
  }
}

watch(
  () => props.open,
  (v) => {
    if (v && props.link) {
      filterRole.value = ''
      load()
    }
  }
)

const roles = computed(() => [...new Set(users.value.map((u) => u.role))])
const shown = computed(() => {
  if (!filterRole.value) return users.value
  return users.value.filter((u) => u.role === filterRole.value)
})

const layerMeta = {
  L0: { label: 'L0 账号墙', cls: 'bg-red-100 text-red-700' },
  L1a: { label: 'L1a 分类墙', cls: 'bg-orange-100 text-orange-700' },
  L1b: { label: 'L1b 角色', cls: 'bg-amber-100 text-amber-700' },
  L2: { label: 'L2 链接权限', cls: 'bg-sky-100 text-sky-700' },
  L3: { label: 'L3 显式拒绝', cls: 'bg-purple-100 text-purple-700' },
}
function layerBadge(layer) {
  return layerMeta[layer] || { label: layer || '?', cls: 'bg-gray-100 text-gray-700' }
}

function close() {
  emit('update:open', false)
}
</script>

<template>
  <div v-if="open && link" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
    <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="close"></div>

    <div class="relative w-full max-w-3xl max-h-[90vh] flex flex-col bg-surface-container-lowest rounded-xl shadow-2xl border border-outline-variant/30 overflow-hidden">
      <!-- Header -->
      <div class="flex items-start justify-between p-6 border-b border-outline-variant/30">
        <div>
          <h2 class="font-headline-lg text-headline-lg text-text-primary tracking-tight">权限矩阵：{{ link.title }}</h2>
          <p class="text-text-secondary mt-1 flex items-center gap-2 font-body-sm" v-if="linkInfo">
            <span class="material-symbols-outlined text-[16px]">folder</span>
            {{ (linkInfo.category_path || []).join(' / ') || '未分类' }}
            <span class="text-outline">·</span>
            <span>基础权限：{{ linkInfo.permission }}</span>
          </p>
        </div>
        <button class="text-outline hover:text-primary transition-colors" @click="close">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>

      <!-- Summary -->
      <div class="flex flex-wrap gap-3 px-6 py-3 border-b border-outline-variant/30 bg-surface/40">
        <span class="px-3 py-1.5 rounded-full text-label-sm bg-emerald-100 text-emerald-700">可见 {{ summary.visible }}</span>
        <span class="px-3 py-1.5 rounded-full text-label-sm bg-rose-100 text-rose-700">不可见 {{ summary.hidden }}</span>
        <span
          v-for="(cnt, layer) in summary.by_layer"
          :key="layer"
          class="px-3 py-1.5 rounded-full text-label-sm"
          :class="layerBadge(layer).cls"
        >{{ layerBadge(layer).label }} {{ cnt }}</span>
      </div>

      <!-- Body -->
      <div class="flex-1 overflow-hidden flex flex-col">
        <div class="p-4 border-b border-outline-variant/30 bg-surface/50 flex justify-between items-center">
          <div class="flex items-center gap-2 text-on-surface-variant text-label-sm bg-surface-container px-3 py-1.5 rounded-md">
            <span class="material-symbols-outlined text-[16px]">info</span>
            该链接对每个用户的可见性；隐藏者标注被哪一层拦截
          </div>
          <div class="relative" v-if="roles.length">
            <select v-model="filterRole" class="pl-3 pr-8 py-1.5 bg-surface-container-lowest border border-outline-variant rounded-lg text-body-sm focus:ring-2 focus:ring-primary/20 focus:border-primary appearance-none cursor-pointer">
              <option value="">全部角色</option>
              <option v-for="r in roles" :key="r" :value="r">{{ r }}</option>
            </select>
          </div>
        </div>

        <div class="overflow-y-auto">
          <table class="w-full text-left border-collapse">
            <thead>
              <tr class="border-b border-outline-variant/30 bg-surface-container-low/50 sticky top-0">
                <th class="py-3 px-4 font-headline-sm text-headline-sm text-on-surface-variant w-12 text-center">#</th>
                <th class="py-3 px-4 font-headline-sm text-headline-sm text-on-surface-variant">用户</th>
                <th class="py-3 px-4 font-headline-sm text-headline-sm text-on-surface-variant">角色</th>
                <th class="py-3 px-4 font-headline-sm text-headline-sm text-on-surface-variant w-24 text-center">可见</th>
                <th class="py-3 px-4 font-headline-sm text-headline-sm text-on-surface-variant">被拦截层级 / 原因</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-outline-variant/20">
              <tr v-if="loading" class="text-center text-on-surface-variant">
                <td colspan="5" class="py-10 font-body-md">加载中…</td>
              </tr>
              <tr v-else-if="shown.length === 0" class="text-center text-on-surface-variant">
                <td colspan="5" class="py-10 font-body-md">暂无用户</td>
              </tr>
              <tr v-for="(u, i) in shown" :key="u.id" class="hover:bg-surface-container-lowest transition-all">
                <td class="py-3 px-4 text-center text-outline font-label-sm">{{ i + 1 }}</td>
                <td class="py-3 px-4">
                  <div class="flex items-center gap-2">
                    <span class="font-headline-sm text-headline-sm text-text-primary">{{ u.display_name }}</span>
                    <span class="text-label-sm text-on-surface-variant">@{{ u.username }}</span>
                    <span v-if="!u.is_active" class="px-1.5 py-0.5 rounded text-label-xs bg-gray-200 text-gray-600">已禁用</span>
                  </div>
                </td>
                <td class="py-3 px-4 text-body-sm text-on-surface">{{ u.role }}</td>
                <td class="py-3 px-4 text-center">
                  <span
                    class="inline-flex px-2 py-1 rounded-full text-label-sm font-medium"
                    :class="u.visible ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'"
                  >{{ u.visible ? '可见' : '隐藏' }}</span>
                </td>
                <td class="py-3 px-4">
                  <template v-if="u.visible">
                    <span class="text-label-sm text-on-surface-variant">默认可见 / 已授权</span>
                  </template>
                  <template v-else>
                    <span class="px-2 py-1 rounded-md text-label-sm font-medium" :class="layerBadge(u.layer).cls">{{ layerBadge(u.layer).label }}</span>
                    <span class="block text-label-xs text-on-surface-variant mt-1">{{ u.reason }}</span>
                    <span v-if="u.fixable" class="block text-label-xs text-primary mt-1">可在该用户「编辑权限」页签开启</span>
                    <span v-else class="block text-label-xs text-on-surface-variant mt-1">需在分类 / 链接设置中调整</span>
                  </template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
