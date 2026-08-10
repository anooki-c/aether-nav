<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { store, bumpLinks, showToast } from '../store'
import { api } from '../api/client'
import EntityIcon from './EntityIcon.vue'
import LinkCard from './LinkCard.vue'
import IconPicker from './IconPicker.vue'
import { getLinkIcon } from '../utils/linkIcon'

const props = defineProps({
  open: { type: Boolean, default: false },
  // 由外部网页（书签小工具）带过来的预填：当前页 URL 与标题
  prefillUrl: { type: String, default: '' },
  prefillTitle: { type: String, default: '' },
})
const emit = defineEmits(['update:open', 'full-form'])

const mainUrl = ref('')        // 唯一的主 URL 输入框
const title = ref('')
const description = ref('')
const category_id = ref(null)
const icon = ref('')           // 自动识别填入，也可手动/图标库修改
const permission = ref('all')
const enablePwd = ref(false)
const pwdNew = ref('')
const pwdConfirm = ref('')
const manualOther = ref('')    // 折叠的「另一个 URL」，高级设置里展开

const detectedNetwork = ref('')   // 'lan' | 'wan' | ''
const detecting = ref(false)
const detectMsg = ref('')
const error = ref('')
const pwdError = ref('')
const saving = ref(false)

// 两级联动分类
const catParent = ref('')
const catChildren = computed(() => {
  if (!catParent.value) return []
  const p = store.tree.find((x) => x.id === Number(catParent.value))
  return p ? (p.children || []).map((c) => ({ id: c.id, name: c.name })) : []
})
watch(catParent, () => {
  if (catChildren.value.length > 0) category_id.value = null
})

// 高级设置折叠
const showAdvanced = ref(false)
const iconPickerOpen = ref(false)
function onPickIcon(name) {
  icon.value = name
}

// 书签小工具：在任意外部网页点击，自动打开本导航站并预填当前页地址
// 用当前站点 origin 动态生成，确保部署到任何域名都可用
const bookmarklet = computed(() => {
  const origin = (typeof window !== 'undefined' && window.location.origin) || ''
  const target = `${origin}/?quickadd=`
  return `javascript:(function(){var u=location.href,t=document.title;window.open('${target}'+encodeURIComponent(u)+'&title='+encodeURIComponent(t),'_blank');})();`
})
const bookmarkCopied = ref(false)
async function copyBookmarklet() {
  try {
    await navigator.clipboard.writeText(bookmarklet.value)
    bookmarkCopied.value = true
    setTimeout(() => (bookmarkCopied.value = false), 2000)
  } catch (e) {
    bookmarkCopied.value = false
  }
}

// 网络徽标文案
const networkLabel = computed(() =>
  detectedNetwork.value === 'lan' ? '局域网' : detectedNetwork.value === 'wan' ? '互联网' : ''
)
// 主 URL 应落入的字段；另一个 URL 折叠进高级设置
const primaryField = computed(() => (detectedNetwork.value === 'lan' ? '内网' : detectedNetwork.value === 'wan' ? '外网' : ''))
const otherField = computed(() => (detectedNetwork.value === 'lan' ? '外网' : detectedNetwork.value === 'wan' ? '内网' : ''))

// 实时预览（与主页 LinkCard 一致）
const cardPreview = computed(() => {
  const net = detectedNetwork.value === 'lan' ? 'internal' : 'external'
  return {
    title: title.value || mainUrl.value || '未命名链接',
    description: description.value || '暂无描述',
    icon: icon.value || '',
    has_password: !!enablePwd,
    network: net,
  }
})

watch(() => props.open, (v) => {
  if (v) {
    mainUrl.value = ''
    title.value = ''
    description.value = ''
    category_id.value = null
    icon.value = ''
    permission.value = 'all'
    enablePwd.value = false
    pwdNew.value = ''
    pwdConfirm.value = ''
    manualOther.value = ''
    detectedNetwork.value = ''
    detecting.value = false
    detectMsg.value = ''
    error.value = ''
    pwdError.value = ''
    saving.value = false
    catParent.value = ''
    showAdvanced.value = false
    iconPickerOpen.value = false
    // 从外部网页（书签小工具）带入当前页地址：预填并自动识别
    if (props.prefillUrl) {
      mainUrl.value = props.prefillUrl
      if (props.prefillTitle) title.value = props.prefillTitle
      nextTick(() => detect())
    }
  }
})

function close() {
  emit('update:open', false)
}

// 识别主 URL：判断局域网/互联网，并抓取标题与图标
async function detect() {
  const url = mainUrl.value.trim()
  if (!url) {
    detectMsg.value = '请先填写主 URL'
    return
  }
  detecting.value = true
  detectMsg.value = ''
  try {
    const data = await api.fetchLinkMeta(url)
    detectedNetwork.value = data.network === 'lan' ? 'lan' : 'wan'
    if (data.title && !title.value) title.value = data.title
    if (data.icon_url && !icon.value) icon.value = data.icon_url
    detectMsg.value = detectedNetwork.value === 'lan'
      ? '已识别为局域网地址，将填入内网 URL'
      : '已识别为互联网地址，将填入外网 URL'
  } catch (e) {
    // 识别失败不应阻断添加：默认按外网处理，并提示用户手动确认
    detectedNetwork.value = 'wan'
    detectMsg.value = (e.message || '识别失败') + '，已按外网处理，可手动修改'
  } finally {
    detecting.value = false
  }
}

async function save() {
  error.value = ''
  pwdError.value = ''
  const url = mainUrl.value.trim()
  if (!url) {
    error.value = '请填写主 URL'
    return
  }
  if (!title.value.trim()) {
    error.value = '请填写名称（可由识别结果自动带入）'
    return
  }
  if (!category_id.value) {
    error.value = '请选择分类'
    return
  }
  if (enablePwd.value) {
    if (!pwdNew.value) { pwdError.value = '请输入访问密码'; return }
    if (pwdNew.value !== pwdConfirm.value) { pwdError.value = '两次输入的密码不一致'; return }
    if (pwdNew.value.length < 4) { pwdError.value = '密码至少 4 位'; return }
  }
  saving.value = true
  try {
    // 主 URL 按其网络属性落入对应字段；另一个 URL 仅当用户在高级设置里填写时附带
    const url_internal = detectedNetwork.value === 'lan' ? url : (manualOther.value.trim() || null)
    const url_external = detectedNetwork.value === 'wan' ? url : (manualOther.value.trim() || null)
    const payload = {
      title: title.value.trim(),
      description: description.value.trim(),
      url_internal,
      url_external,
      category_id: category_id.value,
      icon: icon.value.trim() || '',
      permission: permission.value,
    }
    if (enablePwd.value) payload.password = pwdNew.value
    const res = await api.createLink(payload)
    bumpLinks()
    if (res && res.icon_error) showToast(res.icon_error, 'warn')
    else showToast('链接已添加', 'success')
    close()
  } catch (e) {
    error.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <transition name="modal">
    <div v-if="open" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="close"></div>
      <div class="modal-panel relative bg-bg-card w-full max-w-[640px] max-h-[90vh] rounded-[20px] shadow-2xl overflow-hidden flex flex-col border border-outline-variant/30">
      <!-- Header -->
      <div class="px-7 py-5 border-b border-outline-variant/20 bg-surface-container-lowest flex justify-between items-center shrink-0">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-xl bg-primary-fixed text-primary flex items-center justify-center">
            <span class="material-symbols-outlined text-[20px]">bolt</span>
          </div>
          <div>
            <h2 class="font-headline-md text-headline-md text-on-surface leading-tight">快速添加链接</h2>
            <p class="font-label-xs text-label-xs text-on-surface-variant">粘贴地址，或在任意网页用「书签小工具」一键带入当前页</p>
          </div>
        </div>
        <button class="w-9 h-9 rounded-full hover:bg-surface-container transition-colors flex items-center justify-center text-on-surface-variant" @click="close">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>

      <!-- Body -->
      <div class="flex-1 overflow-y-auto p-7 space-y-5">
        <!-- 主 URL -->
        <div class="flex flex-col gap-1.5">
          <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">页面主 URL <span class="text-error">*</span></label>
          <div class="flex gap-2">
            <input v-model="mainUrl" type="text" @keyup.enter="detect"
              class="flex-1 px-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40"
              placeholder="粘贴链接，如 https://example.com 或 http://192.168.1.100:8080" />
            <button type="button" class="px-4 h-[42px] rounded-xl bg-primary text-on-primary text-sm font-medium shrink-0 hover:brightness-105 disabled:opacity-50 flex items-center gap-1"
              :disabled="detecting" @click="detect">
              <span class="material-symbols-outlined text-[18px]" :class="{ 'animate-spin': detecting }">auto_awesome</span>
              {{ detecting ? '识别中' : '识别' }}
            </button>
          </div>
          <!-- 识别结果：网络徽标 + 提示 -->
          <div v-if="detectedNetwork" class="flex items-center gap-2 mt-0.5">
            <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium"
              :class="detectedNetwork === 'lan' ? 'bg-tertiary-container text-on-tertiary-container' : 'bg-secondary-container text-on-secondary-container'">
              <span class="material-symbols-outlined text-[14px]">{{ detectedNetwork === 'lan' ? 'home' : 'public' }}</span>
              {{ networkLabel }}（自动填入{{ primaryField }} URL）
            </span>
          </div>
          <span v-if="detectMsg" class="text-xs text-on-surface-variant/80">{{ detectMsg }}</span>
        </div>

        <!-- 名称（自动带入） -->
        <div class="flex flex-col gap-1.5">
          <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">名称 <span class="text-error">*</span></label>
          <input v-model="title" type="text"
            class="w-full px-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40"
            placeholder="识别后会自动带入页面标题，可修改" />
        </div>

        <!-- 分类（两级联动） -->
        <div class="flex flex-col gap-1.5">
          <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">选择分类 <span class="text-error">*</span></label>
          <div class="flex gap-2">
            <select v-model="catParent"
              class="flex-1 px-3 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all appearance-none cursor-pointer">
              <option value="">父分类</option>
              <option v-for="p in store.tree" :key="p.id" :value="p.id">{{ p.name }}</option>
            </select>
            <select v-model="category_id"
              class="flex-1 px-3 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all appearance-none cursor-pointer disabled:opacity-45 disabled:cursor-not-allowed"
              :disabled="!catParent && !category_id">
              <option :value="null">子分类</option>
              <template v-if="catParent">
                <option v-for="c in catChildren" :key="c.id" :value="c.id">{{ c.name }}</option>
              </template>
              <template v-else>
                <template v-for="p in store.tree" :key="'p-'+p.id">
                  <option v-for="c in (p.children||[])" :key="c.id" :value="c.id">{{ c.name }}</option>
                </template>
                <option v-for="p in store.tree" :key="'top-'+p.id" :value="p.id">{{ p.name }}（顶级）</option>
              </template>
            </select>
          </div>
        </div>

        <!-- 高级设置（可折叠） -->
        <div class="rounded-xl border border-outline-variant/40 overflow-hidden">
          <button type="button" class="w-full flex items-center justify-between px-4 py-3 bg-surface-container-lowest hover:bg-surface-container transition-colors"
            @click="showAdvanced = !showAdvanced">
            <span class="flex items-center gap-2 font-label-sm text-label-sm text-on-surface font-medium">
              <span class="material-symbols-outlined text-[18px] text-on-surface-variant">tune</span>
              高级设置
            </span>
            <span class="material-symbols-outlined text-[20px] text-on-surface-variant transition-transform" :class="showAdvanced ? 'rotate-180' : ''">expand_more</span>
          </button>
          <div v-if="showAdvanced" class="px-4 py-4 space-y-4 border-t border-outline-variant/30 bg-bg-card">
            <!-- 描述 -->
            <div class="flex flex-col gap-1.5">
              <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">描述内容</label>
              <textarea v-model="description" rows="2"
                class="w-full px-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm resize-none focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40"
                placeholder="添加描述信息…"></textarea>
            </div>

            <!-- 另一个 URL（自动折叠项，仅高级里展开） -->
            <div v-if="otherField" class="flex flex-col gap-1.5">
              <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">{{ otherField }} URL（可选）</label>
              <input v-model="manualOther" type="text"
                class="w-full px-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40"
                :placeholder="otherField === '内网' ? 'http://192.168.x.x:port' : 'https://example.com'" />
            </div>

            <!-- 图标 -->
            <div class="flex flex-col gap-1.5">
              <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">图标</label>
              <div class="flex items-center gap-3">
                <div class="w-14 h-14 rounded-xl bg-surface-container-high border border-outline-variant/50 flex items-center justify-center shrink-0 overflow-hidden">
                  <EntityIcon :icon="icon" :fallback="getLinkIcon(title)" :size="32" />
                </div>
                <input v-model="icon" type="text"
                  class="flex-1 px-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40"
                  placeholder="识别后自动填入，可手动替换" />
                <button type="button" class="px-3 h-[42px] rounded-xl bg-surface-container-high text-on-surface-variant hover:bg-surface-variant text-sm flex items-center gap-1 transition-colors" @click="iconPickerOpen = true">
                  <span class="material-symbols-outlined text-[18px]">emoji_emotions</span>
                  图标库
                </button>
              </div>
            </div>

            <!-- 权限 -->
            <div class="flex flex-col gap-1.5">
              <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">访问权限</label>
              <select v-model="permission"
                class="w-full px-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all appearance-none cursor-pointer">
                <option value="all">🌐 所有人 — 所有访客均可访问</option>
                <option value="registered">👤 注册用户 — 登录后可见</option>
                <option value="admin">🛡️ 管理员 — 仅管理员与所有者可见</option>
                <option value="self">🔒 仅自己 — 只有你能看到</option>
              </select>
            </div>

            <!-- 密码 -->
            <div class="flex flex-col gap-3">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span class="material-symbols-outlined text-lg" :class="enablePwd ? 'text-error' : 'text-on-surface-variant'">lock</span>
                  <span class="font-label-sm text-label-sm text-on-surface font-medium">开启访问密码</span>
                </div>
                <button @click="enablePwd = !enablePwd; pwdError=''"
                  class="relative w-11 h-6 rounded-full transition-colors duration-200"
                  :class="enablePwd ? 'bg-primary' : 'bg-surface-variant'">
                  <span class="absolute top-[2px] left-[2px] w-5 h-5 bg-white rounded-full shadow-sm transition-transform duration-200"
                    :class="enablePwd ? 'translate-x-5' : ''"></span>
                </button>
              </div>
              <div v-if="enablePwd" class="space-y-3 pl-1 pt-1">
                <input v-model="pwdNew" type="password"
                  class="w-full px-4 py-2 bg-bg-card border border-outline-variant rounded-lg font-body-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 transition-all"
                  placeholder="至少 4 位密码" />
                <input v-model="pwdConfirm" type="password"
                  class="w-full px-4 py-2 bg-bg-card border border-outline-variant rounded-lg font-body-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 transition-all"
                  placeholder="再次输入密码" />
                <p v-if="pwdError" class="text-error font-label-xs text-label-xs flex items-center gap-1">
                  <span class="material-symbols-outlined text-[14px]">error</span>{{ pwdError }}
                </p>
              </div>
            </div>

            <!-- 书签小工具 -->
            <div class="flex flex-col gap-2 rounded-xl bg-surface-container-lowest border border-outline-variant/40 p-3">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-[18px] text-on-surface-variant">bookmark_add</span>
                <span class="font-label-sm text-label-sm text-on-surface font-medium">书签小工具（任意网页一键添加）</span>
              </div>
              <p class="font-label-xs text-label-xs text-on-surface-variant">把下面的链接拖到浏览器书签栏。之后在任意网页点它，会自动打开本导航站并带出当前页面的地址与标题。</p>
              <div class="flex items-center gap-2">
                <a :href="bookmarklet"
                  class="flex-1 min-w-0 truncate px-3 py-2 rounded-lg bg-primary-fixed text-primary text-sm font-medium select-all"
                  title="拖到书签栏">
                  ⚡ 快速添加到导航
                </a>
                <button type="button" class="px-3 h-[38px] rounded-lg bg-surface-container-high text-on-surface-variant hover:bg-surface-variant text-sm shrink-0"
                  @click="copyBookmarklet">
                  {{ bookmarkCopied ? '已复制' : '复制代码' }}
                </button>
              </div>
            </div>

            <!-- 切换到完整表单 -->
            <button type="button" class="w-full px-4 py-2.5 rounded-xl border border-outline-variant text-on-surface-variant hover:bg-surface-container text-sm transition-colors"
              @click="emit('full-form')">
              需要填写两个 URL 或更多选项？切换到完整表单 →
            </button>
          </div>
        </div>

        <!-- 预览 -->
        <div class="flex flex-col gap-2">
          <span class="font-label-xs text-label-xs text-on-surface-variant uppercase tracking-wider font-semibold">实时预览</span>
          <LinkCard :link="cardPreview" />
        </div>

        <p v-if="error" class="text-error font-body-sm flex items-center gap-1">
          <span class="material-symbols-outlined text-[16px]">error</span>{{ error }}
        </p>
      </div>

      <!-- Footer -->
      <div class="px-7 py-5 border-t border-outline-variant/20 bg-surface-container-lowest flex justify-end gap-3 shrink-0">
        <button class="px-7 py-2.5 rounded-full text-secondary hover:bg-surface-container transition-colors font-headline-sm" @click="close">取消</button>
        <button class="px-7 py-2.5 rounded-full bg-primary text-on-primary shadow-md hover:shadow-lg hover:-translate-y-[1px] active:translate-y-0 transition-all font-headline-sm font-semibold disabled:opacity-50" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>
    </div>

    <IconPicker :open="iconPickerOpen" title="选择链接图标" @update:open="iconPickerOpen = $event" @pick="onPickIcon" />
      </div>
  </transition>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.22s cubic-bezier(0.32, 0.72, 0, 1);
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-active .modal-panel,
.modal-leave-active .modal-panel {
  transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1), opacity 0.3s cubic-bezier(0.32, 0.72, 0, 1);
}
.modal-enter-from .modal-panel,
.modal-leave-to .modal-panel {
  transform: scale(0.94) translateY(8px);
  opacity: 0;
}
</style>
