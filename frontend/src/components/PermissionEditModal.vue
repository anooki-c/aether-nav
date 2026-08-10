<script setup>
import { ref, watch, computed } from 'vue'
import { api } from '../api/client'

const props = defineProps({
  open: { type: Boolean, default: false },
  user: { type: Object, default: null },
})
const emit = defineEmits(['update:open'])

const tab = ref('manage') // 'manage' | 'denied'
const links = ref([])
const denied = ref([])
const loading = ref(false)
const saving = ref(false)
const filterCat = ref('')

async function load() {
  if (!props.user) return
  loading.value = true
  try {
    const d = await api.userPermissions(props.user.id)
    // 可管理链接：每条带 visible(开关)
    links.value = (d.links || []).map((l) => ({ ...l, visible: l.visible !== false }))
    // 无权限链接：每条带 layer(拦截层级) + reason(原因)
    denied.value = d.denied || []
  } catch (e) {
    links.value = []
    denied.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => props.open,
  (v) => {
    if (v && props.user) {
      filterCat.value = ''
      tab.value = 'manage'
      load()
    }
  }
)

const categories = computed(() => [
  ...new Set([...links.value, ...denied.value].map((l) => (l.category_path || [])[0]).filter(Boolean)),
])
const manageShown = computed(() => {
  if (!filterCat.value) return links.value
  return links.value.filter((l) => (l.category_path || [])[0] === filterCat.value)
})
const deniedShown = computed(() => {
  if (!filterCat.value) return denied.value
  return denied.value.filter((l) => (l.category_path || [])[0] === filterCat.value)
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

function setVisible(l, v) {
  l.visible = v
}
function restoreAll() {
  links.value.forEach((l) => (l.visible = true))
}
async function save() {
  if (!props.user) return
  saving.value = true
  try {
    const denies = links.value.filter((l) => !l.visible).map((l) => l.id)
    await api.setUserPermissions(props.user.id, denies)
    emit('update:open', false)
  } finally {
    saving.value = false
  }
}
function close() {
  emit('update:open', false)
}
</script>

<template>
  <div v-if="open && user" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
    <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="close"></div>

    <div class="relative w-full max-w-4xl max-h-[90vh] flex flex-col bg-surface-container-lowest rounded-xl shadow-2xl border border-outline-variant/30 overflow-hidden">
      <!-- Header -->
      <div class="flex items-start justify-between p-6 border-b border-outline-variant/30">
        <div>
          <h2 class="font-headline-lg text-headline-lg text-text-primary tracking-tight">编辑权限：{{ user.display_name || user.username }}</h2>
          <p class="text-text-secondary mt-1 flex items-center gap-2 font-body-sm">
            <span class="material-symbols-outlined text-[16px]">mail</span>
            {{ user.username }}@本地
          </p>
        </div>
        <div class="flex gap-3" v-if="tab === 'manage'">
          <button class="px-4 py-2 bg-surface-container-lowest border border-outline-variant text-on-surface rounded-lg hover:bg-surface-container-high transition-colors font-headline-sm text-headline-sm shadow-sm" @click="restoreAll">恢复默认</button>
          <button class="px-4 py-2 bg-primary text-on-primary rounded-lg hover:bg-surface-tint transition-colors font-headline-sm text-headline-sm shadow-[0_4px_14px_rgba(108,92,231,0.15)] flex items-center gap-2 disabled:opacity-50" :disabled="saving" @click="save">
            <span class="material-symbols-outlined text-[18px]">save</span>
            {{ saving ? '保存中…' : '保存更改' }}
          </button>
        </div>
        <button v-else class="px-4 py-2 bg-surface-container-lowest border border-outline-variant text-on-surface rounded-lg hover:bg-surface-container-high transition-colors font-headline-sm text-headline-sm shadow-sm" @click="close">关闭</button>
      </div>

      <!-- Tabs -->
      <div class="flex gap-1 px-6 pt-3 border-b border-outline-variant/30 bg-surface/30">
        <button
          @click="tab = 'manage'"
          class="px-4 py-2 -mb-px border-b-2 font-headline-sm text-headline-sm transition-colors"
          :class="tab === 'manage' ? 'border-primary text-primary' : 'border-transparent text-on-surface-variant hover:text-on-surface'"
        >
          可管理链接 <span class="ml-1 px-1.5 py-0.5 rounded-full text-label-xs bg-surface-container text-on-surface-variant">{{ links.length }}</span>
        </button>
        <button
          @click="tab = 'denied'"
          class="px-4 py-2 -mb-px border-b-2 font-headline-sm text-headline-sm transition-colors"
          :class="tab === 'denied' ? 'border-primary text-primary' : 'border-transparent text-on-surface-variant hover:text-on-surface'"
        >
          无权限链接 <span class="ml-1 px-1.5 py-0.5 rounded-full text-label-xs bg-surface-container text-on-surface-variant">{{ denied.length }}</span>
        </button>
      </div>

      <!-- Body -->
      <div class="flex-1 overflow-hidden flex flex-col">
        <!-- ===== 可管理链接 ===== -->
        <template v-if="tab === 'manage'">
          <div class="p-4 border-b border-outline-variant/30 bg-surface/50 flex justify-between items-center">
            <div class="flex items-center gap-2 text-on-surface-variant text-label-sm bg-surface-container px-3 py-1.5 rounded-md">
              <span class="material-symbols-outlined text-[16px]">info</span>
              开关开启 = 该用户可见；关闭 = 对该用户隐藏。无权限的链接不显示在此
            </div>
            <div class="relative">
              <span class="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-[18px] text-outline">filter_list</span>
              <select v-model="filterCat" class="pl-9 pr-8 py-1.5 bg-surface-container-lowest border border-outline-variant rounded-lg text-body-sm focus:ring-2 focus:ring-primary/20 focus:border-primary appearance-none cursor-pointer">
                <option value="">全部分类</option>
                <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
              </select>
            </div>
          </div>

          <div class="overflow-y-auto">
            <table class="w-full text-left border-collapse">
              <thead>
                <tr class="border-b border-outline-variant/30 bg-surface-container-low/50 sticky top-0">
                  <th class="py-3 px-4 font-headline-sm text-headline-sm text-on-surface-variant w-16 text-center">序号</th>
                  <th class="py-3 px-4 font-headline-sm text-headline-sm text-on-surface-variant">链接资源</th>
                  <th class="py-3 px-4 font-headline-sm text-headline-sm text-on-surface-variant">添加者</th>
                  <th class="py-3 px-4 font-headline-sm text-headline-sm text-on-surface-variant">分类路径</th>
                  <th class="py-3 px-4 font-headline-sm text-headline-sm text-on-surface-variant w-28 text-center">可见</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-outline-variant/20">
                <tr v-if="loading" class="text-center text-on-surface-variant">
                  <td colspan="5" class="py-10 font-body-md">加载中…</td>
                </tr>
                <tr v-else-if="manageShown.length === 0" class="text-center text-on-surface-variant">
                  <td colspan="5" class="py-10 font-body-md">该用户暂无可管理的链接</td>
                </tr>
                <tr v-for="(l, i) in manageShown" :key="l.id" class="hover:bg-surface-container-lowest transition-all group">
                  <td class="py-4 px-4 text-center text-outline font-label-sm">{{ i + 1 }}</td>
                  <td class="py-4 px-4">
                    <div class="flex items-center gap-3">
                      <div class="w-10 h-10 rounded-lg bg-surface-container-high flex items-center justify-center shrink-0 group-hover:bg-primary/10 transition-colors">
                        <span class="material-symbols-outlined text-secondary group-hover:text-primary">link</span>
                      </div>
                      <div>
                        <p class="font-headline-sm text-headline-sm text-text-primary">{{ l.title }}</p>
                        <p class="text-label-sm text-text-secondary mt-0.5">{{ l.url }}</p>
                      </div>
                    </div>
                  </td>
                  <td class="py-4 px-4 text-body-sm text-on-surface">{{ l.owner_name }}</td>
                  <td class="py-4 px-4">
                    <div class="flex items-center text-label-sm text-text-secondary gap-1">
                      <template v-for="(c, ci) in l.category_path" :key="ci">
                        <span v-if="ci > 0" class="material-symbols-outlined text-[14px]">chevron_right</span>
                        <span class="bg-surface-container px-2 py-1 rounded">{{ c }}</span>
                      </template>
                    </div>
                  </td>
                  <td class="py-4 px-4 text-center">
                    <button
                      type="button"
                      role="switch"
                      :aria-checked="l.visible"
                      @click="setVisible(l, !l.visible)"
                      class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary/30"
                      :class="l.visible ? 'bg-primary' : 'bg-outline/40'"
                    >
                      <span
                        class="inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform"
                        :class="l.visible ? 'translate-x-[22px]' : 'translate-x-0.5'"
                      ></span>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="p-4 border-t border-outline-variant/30 bg-surface/50 flex justify-between items-center">
            <span class="text-label-sm text-on-surface-variant">{{ manageShown.length }} 个链接</span>
          </div>
        </template>

        <!-- ===== 无权限链接 ===== -->
        <template v-else>
          <div class="p-4 border-b border-outline-variant/30 bg-surface/50 flex justify-between items-center">
            <div class="flex items-center gap-2 text-on-surface-variant text-label-sm bg-surface-container px-3 py-1.5 rounded-md">
              <span class="material-symbols-outlined text-[16px]">lock</span>
              以下链接该用户最终不可见，并标注被哪一层权限拦截
            </div>
            <div class="relative">
              <span class="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-[18px] text-outline">filter_list</span>
              <select v-model="filterCat" class="pl-9 pr-8 py-1.5 bg-surface-container-lowest border border-outline-variant rounded-lg text-body-sm focus:ring-2 focus:ring-primary/20 focus:border-primary appearance-none cursor-pointer">
                <option value="">全部分类</option>
                <option v-for="c in categories" :key="c" :value="c">{{ c }}</option>
              </select>
            </div>
          </div>

          <div class="overflow-y-auto">
            <table class="w-full text-left border-collapse">
              <thead>
                <tr class="border-b border-outline-variant/30 bg-surface-container-low/50 sticky top-0">
                  <th class="py-3 px-4 font-headline-sm text-headline-sm text-on-surface-variant w-16 text-center">序号</th>
                  <th class="py-3 px-4 font-headline-sm text-headline-sm text-on-surface-variant">链接资源</th>
                  <th class="py-3 px-4 font-headline-sm text-headline-sm text-on-surface-variant">分类路径</th>
                  <th class="py-3 px-4 font-headline-sm text-headline-sm text-on-surface-variant w-40">被拦截层级</th>
                  <th class="py-3 px-4 font-headline-sm text-headline-sm text-on-surface-variant">原因</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-outline-variant/20">
                <tr v-if="loading" class="text-center text-on-surface-variant">
                  <td colspan="5" class="py-10 font-body-md">加载中…</td>
                </tr>
                <tr v-else-if="deniedShown.length === 0" class="text-center text-on-surface-variant">
                  <td colspan="5" class="py-10 font-body-md">该用户对所有链接都有访问权限 🎉</td>
                </tr>
                <tr v-for="(l, i) in deniedShown" :key="l.id" class="hover:bg-surface-container-lowest transition-all group">
                  <td class="py-4 px-4 text-center text-outline font-label-sm">{{ i + 1 }}</td>
                  <td class="py-4 px-4">
                    <div class="flex items-center gap-3">
                      <div class="w-10 h-10 rounded-lg bg-surface-container-high flex items-center justify-center shrink-0">
                        <span class="material-symbols-outlined text-on-surface-variant">link_off</span>
                      </div>
                      <div>
                        <p class="font-headline-sm text-headline-sm text-text-primary">{{ l.title }}</p>
                        <p class="text-label-sm text-text-secondary mt-0.5">{{ l.url }}</p>
                      </div>
                    </div>
                  </td>
                  <td class="py-4 px-4">
                    <div class="flex items-center text-label-sm text-text-secondary gap-1">
                      <template v-for="(c, ci) in l.category_path" :key="ci">
                        <span v-if="ci > 0" class="material-symbols-outlined text-[14px]">chevron_right</span>
                        <span class="bg-surface-container px-2 py-1 rounded">{{ c }}</span>
                      </template>
                    </div>
                  </td>
                  <td class="py-4 px-4">
                    <span class="px-2 py-1 rounded-md text-label-sm font-medium" :class="layerBadge(l.layer).cls">{{ layerBadge(l.layer).label }}</span>
                  </td>
                  <td class="py-4 px-4 text-body-sm text-on-surface">
                    {{ l.reason }}
                    <span v-if="l.fixable_here" class="block text-label-xs text-primary mt-1">可在「可管理链接」页签开启</span>
                    <span v-else class="block text-label-xs text-on-surface-variant mt-1">需在分类 / 链接设置中调整</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="p-4 border-t border-outline-variant/30 bg-surface/50 flex justify-between items-center">
            <span class="text-label-sm text-on-surface-variant">{{ deniedShown.length }} 个不可见链接</span>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>
