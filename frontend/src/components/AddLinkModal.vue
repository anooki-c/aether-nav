<script setup>
import { computed, ref, watch } from 'vue'
import { store, bumpLinks, showToast } from '../store'
import { api } from '../api/client'
import EntityIcon from './EntityIcon.vue'
import LinkCard from './LinkCard.vue'
import IconPicker from './IconPicker.vue'
import { getLinkIcon } from '../utils/linkIcon'
import { parseUrlScheme, buildUrl } from '../utils/urlScheme'

const props = defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['update:open'])

const form = ref({
  title: '',
  description: '',
  url_external: '',
  url_internal: '',
  category_id: null,
  icon: '',
  permission: 'all',
  enablePwd: false,
  pwdNew: '',
  pwdConfirm: '',
})
const error = ref('')
const pwdError = ref('')
const saving = ref(false)
const iconBusy = ref(false)
const iconMsg = ref('')
const iconWarn = ref(false)
// 图标获取接口（弹窗内下拉切换）：清单 + 当前选中 + 自定义模板
const iconProviders = ref([])
const selectedProvider = ref('direct')
const faviconCustomUrl = ref('')
// 图标库弹窗：点击图标后填入 icon 字段
const iconPickerOpen = ref(false)
function onPickIcon(name) {
  form.value.icon = name
}

// URL scheme：输入框只填 host/path（body），SSL 勾选控制 http/https（默认 http）
const sslExternal = ref(false)
const extBody = ref('')
const sslInternal = ref(false)
const intBody = ref('')
// body / ssl 变化时拼回完整 URL，保持 form 与预览同步
watch([extBody, sslExternal], () => {
  form.value.url_external = buildUrl(sslExternal.value, extBody.value)
  iconMsg.value = ''
})
watch([intBody, sslInternal], () => {
  form.value.url_internal = buildUrl(sslInternal.value, intBody.value)
  iconMsg.value = ''
})

// 两级联动分类
const catParent = ref('')
const catChildren = computed(() => {
  if (!catParent.value) return []
  const p = store.tree.find((x) => x.id === Number(catParent.value))
  return p ? (p.children || []).map((c) => ({ id: c.id, name: c.name })) : []
})
watch(catParent, () => {
  // 切换父分类后清空已选子分类，避免选到不存在的归属
  if (catChildren.value.length > 0) form.value.category_id = null
})
watch(() => props.open, (v) => {
  if (v) {
    // 每次打开重置表单
    form.value = {
      title: '', description: '', url_external: '', url_internal: '',
      category_id: null, icon: '', permission: 'all', enablePwd: false, pwdNew: '', pwdConfirm: '',
    }
    catParent.value = ''
    error.value = ''
    pwdError.value = ''
    iconMsg.value = ''
    iconWarn.value = false
    iconProviders.value = []
    selectedProvider.value = 'direct'
    faviconCustomUrl.value = ''
    // 默认 http；把完整 URL 拆成 {ssl, body} 供输入框使用
    const e = parseUrlScheme(form.value.url_external)
    const i = parseUrlScheme(form.value.url_internal)
    sslExternal.value = e.ssl
    extBody.value = e.body
    sslInternal.value = i.ssl
    intBody.value = i.body
    loadIconProviders()
  }
})

function close() {
  emit('update:open', false)
}

// 实时预览（与主页 LinkCard 一致）
const cardPreview = computed(() => {
  const f = form.value
  const hasInt = !!f.url_internal.trim()
  const hasExt = !!f.url_external.trim()
  let net = 'internal'
  if (hasInt && hasExt) net = store.network === 'internal' ? 'internal' : 'external'
  else if (hasInt) net = 'internal'
  else if (hasExt) net = 'external'
  return {
    title: f.title || '未命名链接',
    description: f.description || '暂无描述',
    icon: f.icon || '',
    has_password: !!f.enablePwd,
    network: net,
  }
})

async function save() {
  error.value = ''
  pwdError.value = ''
  if (!form.value.title.trim()) {
    error.value = '请填写标题'
    return
  }
  if (!form.value.url_external.trim() && !form.value.url_internal.trim()) {
    error.value = '至少填写一个 URL（内网或外网）'
    return
  }
  if (!form.value.category_id) {
    error.value = '请选择分类'
    return
  }
  // 每用户独立密码校验
  if (form.value.enablePwd) {
    if (!form.value.pwdNew) {
      pwdError.value = '请输入访问密码'
      return
    }
    if (form.value.pwdNew !== form.value.pwdConfirm) {
      pwdError.value = '两次输入的密码不一致'
      return
    }
    if (form.value.pwdNew.length < 4) {
      pwdError.value = '密码至少 4 位'
      return
    }
  }
  saving.value = true
  try {
    const payload = {
      title: form.value.title.trim(),
      description: form.value.description.trim(),
      url_external: form.value.url_external.trim() || null,
      url_internal: form.value.url_internal.trim() || null,
      category_id: form.value.category_id,
      // 不写入 emoji 占位；留空由展示层按标题推断 Material Symbols 默认图标
      icon: form.value.icon.trim() || '',
      permission: form.value.permission,
    }
    if (form.value.enablePwd) payload.password = form.value.pwdNew
    const res = await api.createLink(payload)
    bumpLinks()
    // 图标落地失败：链接已创建，仅图标回退为默认，提示用户
    if (res && res.icon_error) showToast(res.icon_error, 'warn')
    else showToast('链接已添加', 'success')
    close()
  } catch (e) {
    error.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

// 拉取图标接口清单，填充弹窗里的下拉框（默认选中站点当前接口）
async function loadIconProviders() {
  try {
    const data = await api.getIconProviders()
    iconProviders.value = data.providers || []
    if (data.current) selectedProvider.value = data.current
  } catch (e) { /* 清单拉取失败不阻塞弹窗，下拉为空时用默认 direct */ }
}

// 自动获取图标地址（PRD item 10）：优先内网 URL，内外部都有时默认用内部 URL 解析
// 只把解析出的地址填进输入框，真正下载保存在「保存」时由后端完成
async function autoFetchIcon() {
  const url = form.value.url_internal.trim() || form.value.url_external.trim()
  if (!url) {
    iconMsg.value = '请先填写 URL 再自动获取'
    return
  }
  iconBusy.value = true
  iconMsg.value = ''
  iconWarn.value = false
  try {
    const data = await api.resolveIcon(
      url,
      selectedProvider.value,
      selectedProvider.value === 'custom' ? faviconCustomUrl.value : ''
    )
    form.value.icon = data.icon_url
    if (data.warning) { iconWarn.value = true; iconMsg.value = data.warning }
    else iconMsg.value = '已填入图标地址，保存时下载到本地'
  } catch (e) {
    iconMsg.value = e.message || '解析失败'
  } finally {
    iconBusy.value = false
  }
}

// 选择本地图片：浏览器拿不到真实磁盘路径，先上传取得可用路径再填进输入框
async function onUpload(e) {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  iconBusy.value = true
  iconMsg.value = ''
  try {
    const data = await api.uploadIcon(file)
    form.value.icon = data.path
    iconMsg.value = '已选择文件，路径已填入输入框'
  } catch (err) {
    iconMsg.value = err.message || '上传失败'
  } finally {
    iconBusy.value = false
    e.target.value = ''
  }
}
</script>

<template>
  <transition name="modal">
    <div v-if="open" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="close"></div>
      <div class="modal-panel relative bg-bg-card w-full max-w-[880px] rounded-[20px] shadow-2xl overflow-hidden flex flex-col border border-outline-variant/30">
      <!-- Header -->
      <div class="px-8 py-5 border-b border-outline-variant/20 bg-surface-container-lowest flex justify-between items-center shrink-0">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-xl bg-primary-fixed text-primary flex items-center justify-center">
            <span class="material-symbols-outlined text-[20px]">add_link</span>
          </div>
          <h2 class="font-headline-md text-headline-md text-on-surface">快速添加链接</h2>
        </div>
        <button class="w-9 h-9 rounded-full hover:bg-surface-container transition-colors flex items-center justify-center text-on-surface-variant" @click="close">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>

      <!-- Body: left-right split -->
      <div class="flex-1 flex min-h-0 overflow-hidden">
        <!-- ===== 左侧：表单区域 ===== -->
        <div class="w-[52%] p-8 overflow-y-auto space-y-5 border-r border-outline-variant/15">
          <!-- 名称 -->
          <div class="flex flex-col gap-1.5">
            <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">名称 <span class="text-error">*</span></label>
            <input v-model="form.title" type="text"
              class="w-full px-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-md focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40"
              placeholder="输入链接名称…" />
          </div>

          <!-- 外网 URL -->
          <div class="flex flex-col gap-1.5">
            <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">外网 URL</label>
            <div class="flex gap-2">
              <span class="flex items-center px-3 py-2.5 rounded-xl border border-outline-variant bg-surface-container-high text-on-surface-variant font-body-sm shrink-0 select-none cursor-pointer hover:bg-surface-container transition-colors"
                @click="sslExternal = !sslExternal" :title="sslExternal ? '当前 https，点击切换为 http' : '当前 http，点击切换为 https'">
                {{ sslExternal ? 'https://' : 'http://' }}
              </span>
              <input v-model="extBody" type="text"
                class="flex-1 min-w-0 px-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40"
                placeholder="example.com" />
              <label class="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-outline-variant bg-surface-container-low cursor-pointer shrink-0 select-none hover:bg-surface-container transition-colors">
                <input type="checkbox" v-model="sslExternal" class="w-4 h-4 accent-primary" />
                <span class="font-label-sm text-label-sm text-on-surface-variant">SSL</span>
              </label>
            </div>
            <span class="text-xs text-on-surface-variant/70">默认 http，勾选 SSL 自动切换为 https</span>
          </div>

          <!-- 内网 URL -->
          <div class="flex flex-col gap-1.5">
            <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">内网 URL</label>
            <div class="flex gap-2">
              <span class="flex items-center px-3 py-2.5 rounded-xl border border-outline-variant bg-surface-container-high text-on-surface-variant font-body-sm shrink-0 select-none cursor-pointer hover:bg-surface-container transition-colors"
                @click="sslInternal = !sslInternal" :title="sslInternal ? '当前 https，点击切换为 http' : '当前 http，点击切换为 https'">
                {{ sslInternal ? 'https://' : 'http://' }}
              </span>
              <input v-model="intBody" type="text"
                class="flex-1 min-w-0 px-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40"
                placeholder="192.168.x.x:port" />
              <label class="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-outline-variant bg-surface-container-low cursor-pointer shrink-0 select-none hover:bg-surface-container transition-colors">
                <input type="checkbox" v-model="sslInternal" class="w-4 h-4 accent-primary" />
                <span class="font-label-sm text-label-sm text-on-surface-variant">SSL</span>
              </label>
            </div>
            <span class="text-xs text-on-surface-variant/70">默认 http，勾选 SSL 自动切换为 https</span>
          </div>

          <!-- 描述 -->
          <div class="flex flex-col gap-1.5">
            <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">描述内容</label>
            <textarea v-model="form.description" rows="3"
              class="w-full px-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm resize-none focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40"
              placeholder="添加描述信息…"></textarea>
          </div>

          <!-- 图标 -->
          <div class="flex flex-col gap-1.5">
            <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">图标</label>
            <div class="flex items-stretch gap-3">
              <!-- 左侧：预览框，正方形（边长 = 右侧两行总高 36+8+42=86px） -->
              <div class="w-[86px] h-[86px] rounded-xl bg-surface-container-high border border-outline-variant/50 flex items-center justify-center shrink-0 overflow-hidden">
                <EntityIcon :icon="form.icon" :fallback="getLinkIcon(form.title)" :size="40" />
              </div>
                <!-- 右侧：上=接口下拉 + 获取(占满剩余宽度) + 上传(更窄)，下=地址输入 -->
                <div class="flex-1 min-w-0 flex flex-col gap-2">
                  <div class="flex gap-2 h-9">
                    <select v-model="selectedProvider"
                      class="h-9 w-[150px] shrink-0 px-2 py-2 rounded-lg text-sm bg-surface-variant text-on-surface-variant border border-outline-variant/60 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 appearance-none cursor-pointer">
                      <option v-for="p in iconProviders" :key="p.key" :value="p.key">{{ p.label }}{{ p.network === 'proxy' ? '（需代理）' : '' }}{{ p.network === 'cn' ? '（国内）' : '' }}{{ p.network === 'direct' ? '（直连）' : '' }}</option>
                    </select>
                    <!-- 获取图标：柔和卡片色（淡紫罗兰） -->
                    <button type="button" title="获取图标"
                      class="flex-1 min-w-0 h-9 rounded-xl text-sm bg-[#E2D4F5] text-[#43358F] hover:brightness-95 disabled:opacity-50 flex items-center justify-center overflow-hidden shadow-sm"
                      :disabled="iconBusy" @click="autoFetchIcon">
                      <span class="material-symbols-outlined text-[18px]" :class="{ 'animate-spin': iconBusy }">auto_awesome</span>
                    </button>
                    <!-- 上传：柔和卡片色（淡桃粉） -->
                    <label title="上传图标"
                      class="w-10 h-9 shrink-0 rounded-xl text-sm bg-[#FCDFD0] text-[#A8513F] hover:brightness-95 cursor-pointer flex items-center justify-center disabled:opacity-50 shadow-sm">
                      <span class="material-symbols-outlined text-[18px]">upload</span>
                      <input type="file" accept="image/*" class="hidden" :disabled="iconBusy" @change="onUpload" />
                    </label>
                  </div>
                  <input v-if="selectedProvider === 'custom'" v-model="faviconCustomUrl" type="text"
                    class="w-full h-[38px] px-3 bg-surface-container-low border border-outline-variant rounded-lg font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40"
                    placeholder="自定义接口模板：{scheme}://{host}/favicon.ico" />
                  <input v-model="form.icon" type="text"
                    class="w-full h-[42px] px-4 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40"
                    placeholder="图片网址 / 本地文件路径 / Material Symbols 名称" />
                  <button type="button" class="w-full h-9 shrink-0 rounded-lg bg-surface-container-high text-on-surface-variant hover:bg-surface-variant text-sm flex items-center justify-center gap-1 transition-colors" @click="iconPickerOpen = true">
                    <span class="material-symbols-outlined text-[18px]">emoji_emotions</span>
                    从系统图标库中选择
                  </button>
                </div>
            </div>
            <span class="text-xs text-on-surface-variant/70">保存时按此地址把图标下载并存到本地；失败则回退为按标题匹配的默认图标</span>
            <span v-if="iconMsg" class="text-xs" :class="iconWarn ? 'text-error' : 'text-on-surface-variant'">{{ iconMsg }}</span>
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
              <select v-model="form.category_id"
                class="flex-1 px-3 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all appearance-none cursor-pointer disabled:opacity-45 disabled:cursor-not-allowed"
                :disabled="!catParent && !form.category_id">
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
        </div>

        <!-- ===== 右侧：预览 + 权限 + 密码 ===== -->
        <div class="w-[48%] p-8 flex flex-col gap-6 bg-surface-container-lowest/60">
          <!-- 预览卡片（与主页 LinkCard 一致样式） -->
          <div class="flex flex-col gap-2">
            <span class="font-label-xs text-label-xs text-on-surface-variant uppercase tracking-wider font-semibold">实时预览</span>
            <LinkCard :link="cardPreview" />
          </div>

          <!-- 分隔线 -->
          <div class="border-t border-outline-variant/15"></div>

          <!-- 权限配置 -->
          <div class="flex flex-col gap-2">
            <span class="font-label-xs text-label-xs text-on-surface-variant uppercase tracking-wider font-semibold">权限配置</span>
            <select v-model="form.permission"
              class="w-full px-4 py-2.5 bg-bg-card border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all appearance-none cursor-pointer">
              <option value="all">🌐 所有人 — 所有访客均可访问</option>
              <option value="registered">👤 注册用户 — 登录后可见</option>
              <option value="admin">🛡️ 管理员 — 仅管理员与所有者可见</option>
              <option value="self">🔒 仅自己 — 只有你能看到</option>
            </select>
          </div>

          <!-- 密码设置（每用户独立） -->
          <div class="flex flex-col gap-3">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-lg" :class="form.enablePwd ? 'text-error' : 'text-on-surface-variant'">lock</span>
                <span class="font-label-sm text-label-sm text-on-surface font-medium">开启访问密码</span>
              </div>
              <button @click="form.enablePwd = !form.enablePwd; pwdError=''"
                class="relative w-11 h-6 rounded-full transition-colors duration-200"
                :class="form.enablePwd ? 'bg-primary' : 'bg-surface-variant'">
                <span class="absolute top-[2px] left-[2px] w-5 h-5 bg-white rounded-full shadow-sm transition-transform duration-200"
                  :class="form.enablePwd ? 'translate-x-5' : ''"></span>
              </button>
            </div>
            <p class="font-label-xs text-label-xs text-on-surface-variant pl-1 -mt-1">密码为每个用户独立管理，仅影响你自己的访问验证</p>

            <!-- 密码输入（展开时显示） -->
            <div v-if="form.enablePwd" class="space-y-3 pl-1 pt-1">
              <div class="flex flex-col gap-1">
                <label class="font-label-xs text-label-xs text-on-surface-variant">新密码</label>
                <input v-model="form.pwdNew" type="password"
                  class="w-full px-4 py-2 bg-bg-card border border-outline-variant rounded-lg font-body-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 transition-all"
                  placeholder="至少 4 位密码" />
              </div>
              <div class="flex flex-col gap-1">
                <label class="font-label-xs text-label-xs text-on-surface-variant">确认密码</label>
                <input v-model="form.pwdConfirm" type="password"
                  class="w-full px-4 py-2 bg-bg-card border border-outline-variant rounded-lg font-body-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 transition-all"
                  placeholder="再次输入密码" />
              </div>
              <p v-if="pwdError" class="text-error font-label-xs text-label-xs flex items-center gap-1">
                <span class="material-symbols-outlined text-[14px]">error</span>{{ pwdError }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-8 py-5 border-t border-outline-variant/20 bg-surface-container-lowest flex justify-end gap-3 shrink-0">
        <button class="px-7 py-2.5 rounded-full text-secondary hover:bg-surface-container transition-colors font-headline-sm" @click="close">取消</button>
        <button class="px-7 py-2.5 rounded-full bg-primary text-on-primary shadow-md hover:shadow-lg hover:-translate-y-[1px] active:translate-y-0 transition-all font-headline-sm font-semibold disabled:opacity-50" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>

      <p v-if="error" class="px-8 pb-5 -mt-3 text-error font-body-sm">{{ error }}</p>
    </div>

    <!-- 图标库弹窗 -->
    <IconPicker :open="iconPickerOpen" title="选择链接图标" @update:open="iconPickerOpen = $event" @pick="onPickIcon" />
      </div>
  </transition>
</template>

<style scoped>
/* 弹窗材质化入场：遮罩淡入 + 面板 scale 弹入（弹簧曲线，平滑无回弹）。
   Apple：玻璃/模糊面板的入场应是"真实材质抵达"，而非单纯透明度淡入。 */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.22s cubic-bezier(0.32, 0.72, 0, 1);
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-active .modal-panel {
  transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1), opacity 0.3s cubic-bezier(0.32, 0.72, 0, 1);
}
/* 出口比入口快：关闭是系统响应，应更利落 */
.modal-leave-active .modal-panel {
  transition: transform 0.2s cubic-bezier(0.32, 0.72, 0, 1), opacity 0.2s cubic-bezier(0.32, 0.72, 0, 1);
}
.modal-enter-from .modal-panel,
.modal-leave-to .modal-panel {
  transform: scale(0.94) translateY(8px);
  opacity: 0;
}
</style>
