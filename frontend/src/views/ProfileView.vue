<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { store, showToast, applyUserPrefs } from '../store'
import { api } from '../api/client'
import EntityIcon from '../components/EntityIcon.vue'

const router = useRouter()

// 本地表单副本（初始值来自 store.user）
const form = reactive({
  username: '',
  display_name: '',
  avatar: '',
  weather_city: '',
  network: 'external',
  theme: 'light',
})
const pwd = reactive({ current: '', next: '', confirm: '' })
const showEmoji = ref(false)

const avatarInput = ref(null)
const EMOJIS = ['😀', '😎', '🚀', '🌟', '🔥', '🌈', '🐱', '🐶', '🍀', '☕', '🎯', '💡', '🌙', '⚡', '🍎', '🐼']
const savingProfile = ref(false)
const savingPwd = ref(false)

// 侧边栏导航 + 当前高亮区块（点击平滑滚动到对应 section）
const sections = [
  { k: 'profile', icon: 'badge', label: '基本资料' },
  { k: 'prefs', icon: 'tune', label: '个人偏好' },
  { k: 'security', icon: 'lock', label: '安全' },
  { k: 'info', icon: 'info', label: '账号信息' },
]
const activeSection = ref('profile')
function scrollTo(id) {
  activeSection.value = id
  const el = document.getElementById('sec-' + id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
function goFront() {
  router.push('/')
}

// 头像预览值：优先本地表单，其次 store
const avatarPreview = computed(() => form.avatar || store.user?.avatar || '')

onMounted(() => {
  resetForm()
})

function resetForm() {
  const u = store.user || {}
  const p = u.preferences || {}
  form.username = u.username || ''
  form.display_name = u.display_name || ''
  form.avatar = u.avatar || ''
  form.weather_city = p.weather_city || store.weatherCity || ''
  form.network = p.network || store.network || 'external'
  form.theme = p.theme || store.theme || 'light'
}

/* ── 头像上传 / emoji ─────────────────────────────── */
function triggerAvatar() {
  avatarInput.value?.click()
}
async function onAvatarFile(e) {
  const f = e.target.files && e.target.files[0]
  if (!f) return
  try {
    const res = await api.uploadIcon(f)
    form.avatar = res.path
    showToast('头像已上传', 'success')
  } catch (err) {
    showToast(err.message || '头像上传失败', 'error')
  } finally {
    e.target.value = ''
  }
}
function pickEmoji(em) {
  form.avatar = em
}

/* ── 保存基本资料 + 偏好 ──────────────────────────── */
async function saveProfile() {
  savingProfile.value = true
  try {
    const payload = {
      username: form.username,
      display_name: form.display_name,
      avatar: form.avatar,
      preferences: {
        network: form.network,
        theme: form.theme,
        weather_city: form.weather_city,
      },
    }
    const res = await api.updateProfile(payload)
    store.user = res.user
    applyUserPrefs(res.user.preferences || {})
    showToast('资料已保存', 'success')
  } catch (err) {
    showToast(err.message || '保存失败', 'error')
  } finally {
    savingProfile.value = false
  }
}

/* ── 修改密码 ───────────────────────────────────── */
async function savePassword() {
  if (pwd.next.length < 6) {
    showToast('新密码至少 6 位', 'warn')
    return
  }
  if (pwd.next !== pwd.confirm) {
    showToast('两次输入的密码不一致', 'warn')
    return
  }
  savingPwd.value = true
  try {
    await api.updateProfile({
      current_password: pwd.current,
      new_password: pwd.next,
    })
    pwd.current = pwd.next = pwd.confirm = ''
    showToast('密码已更新', 'success')
  } catch (err) {
    showToast(err.message || '修改失败', 'error')
  } finally {
    savingPwd.value = false
  }
}
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-bg-page text-on-background font-body-md">
    <!-- 个人设置 侧边栏（与后台同款独立控制台） -->
    <aside class="hidden md:flex flex-col bg-surface shadow-md w-[240px] shrink-0">
      <button class="px-6 pt-6 pb-6 border-b border-outline-variant/30 flex items-center gap-3 text-left hover:opacity-80 transition-opacity" @click="goFront">
        <div class="w-10 h-10 rounded-xl bg-primary-container text-on-primary-container flex items-center justify-center font-bold text-lg shadow-sm">云</div>
        <div>
          <div class="font-headline-sm text-headline-sm font-bold text-primary">云航导航</div>
          <div class="font-label-sm text-label-sm text-secondary">个人设置</div>
        </div>
      </button>
      <nav class="flex-1 px-4 py-4 flex flex-col gap-1">
        <button
          v-for="s in sections"
          :key="s.k"
          class="flex items-center gap-3 px-4 py-3 rounded-lg text-left font-body-md transition-all active:opacity-80"
          :class="activeSection === s.k ? 'bg-primary-fixed text-primary border-l-4 border-primary rounded-r-lg font-bold' : 'text-secondary hover:bg-surface-container'"
          @click="scrollTo(s.k)"
        >
          <span class="material-symbols-outlined">{{ s.icon }}</span>
          {{ s.label }}
        </button>
      </nav>
      <div class="p-4 border-t border-outline-variant/30">
        <button class="flex items-center gap-3 px-4 py-3 w-full rounded-lg text-secondary hover:bg-surface-container transition-all" @click="goFront">
          <span class="material-symbols-outlined">arrow_back</span>
          <span class="font-body-md">返回前台</span>
        </button>
      </div>
    </aside>

    <!-- 主列 -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- 顶栏 -->
      <header class="flex justify-between items-center px-grid-gutter py-3 bg-surface shadow-sm z-30">
        <div class="font-headline-md text-headline-md font-bold text-primary">个人设置</div>
        <div class="flex items-center gap-2">
          <span class="text-body-sm text-on-surface-variant hidden sm:block">{{ store.user?.display_name || store.user?.username }}</span>
          <button
            class="w-9 h-9 rounded-full bg-surface-container flex items-center justify-center text-on-surface-variant hover:bg-surface-container-high transition-colors"
            title="后台设置"
            @click="router.push('/admin')"
          >
            <span class="material-symbols-outlined text-[20px]">settings</span>
          </button>
          <div class="w-9 h-9 rounded-full bg-surface-container flex items-center justify-center overflow-hidden border border-surface-container-highest">
            <EntityIcon v-if="avatarPreview" :icon="avatarPreview" fallback="person" :size="28" alt="头像" />
            <span v-else class="material-symbols-outlined text-[20px] text-on-surface-variant">person</span>
          </div>
        </div>
      </header>

      <!-- 内容区 -->
      <main class="flex-1 overflow-y-auto p-4 md:p-8">
        <div class="max-w-3xl mx-auto space-y-6">
          <!-- 基本资料 -->
          <section id="sec-profile" class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 scroll-mt-24">
            <h2 class="font-headline-sm text-headline-sm text-text-primary mb-5">基本资料</h2>

            <!-- 头像 -->
            <div class="flex items-center gap-5 mb-6">
              <div class="w-20 h-20 rounded-full bg-surface-container flex items-center justify-center overflow-hidden border-2 border-surface-container-highest shrink-0">
                <EntityIcon v-if="avatarPreview" :icon="avatarPreview" fallback="person" :size="56" alt="头像" />
                <span v-else class="material-symbols-outlined text-[40px] text-on-surface-variant">person</span>
              </div>
              <div class="space-y-2">
                <div class="flex gap-2">
                  <button @click="triggerAvatar" class="px-4 py-2 rounded-xl bg-primary text-on-primary text-sm font-semibold hover:bg-primary/90 transition-colors">上传图片</button>
                  <button @click="form.avatar = ''" class="px-4 py-2 rounded-xl bg-surface-container text-on-surface-variant text-sm font-semibold hover:bg-surface-container-high transition-colors">清除头像</button>
                  <button @click="showEmoji = !showEmoji" class="px-4 py-2 rounded-xl bg-surface-container text-on-surface-variant text-sm font-semibold hover:bg-surface-container-high transition-colors">
                    {{ showEmoji ? '收起 emoji' : '选择 emoji' }}
                  </button>
                </div>
                <input ref="avatarInput" type="file" accept="image/*" class="hidden" @change="onAvatarFile" />
              </div>
            </div>
            <!-- emoji 选择（可折叠） -->
            <div v-if="showEmoji" class="flex flex-wrap gap-2 mb-6">
              <button v-for="em in EMOJIS" :key="em" @click="pickEmoji(em)"
                class="w-10 h-10 rounded-xl text-xl flex items-center justify-center transition-all"
                :class="form.avatar === em ? 'bg-primary/10 ring-2 ring-primary' : 'bg-surface-container hover:bg-surface-container-high'">
                {{ em }}
              </button>
            </div>

            <!-- 用户名 / 昵称 -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label class="block text-label-sm text-text-secondary mb-1.5">用户名（登录账号）</label>
                <input v-model="form.username" type="text" class="w-full px-4 py-2.5 rounded-xl bg-surface-container border border-outline-variant/60 text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-primary/40" placeholder="登录用户名" />
              </div>
              <div>
                <label class="block text-label-sm text-text-secondary mb-1.5">昵称 / 显示名</label>
                <input v-model="form.display_name" type="text" class="w-full px-4 py-2.5 rounded-xl bg-surface-container border border-outline-variant/60 text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-primary/40" placeholder="展示名称" />
              </div>
            </div>

            <div class="flex justify-end mt-5">
              <button @click="saveProfile" :disabled="savingProfile"
                class="px-6 py-2.5 rounded-xl bg-primary text-on-primary text-sm font-semibold shadow-sm hover:bg-primary/90 transition-all disabled:opacity-50">
                {{ savingProfile ? '保存中…' : '保存资料' }}
              </button>
            </div>
          </section>

          <!-- 个人偏好 -->
          <section id="sec-prefs" class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 scroll-mt-24">
            <h2 class="font-headline-sm text-headline-sm text-text-primary mb-5">个人偏好</h2>

            <!-- 默认网络模式 -->
            <div class="flex items-center justify-between py-3 border-b border-surface-variant/40">
              <div>
                <div class="text-body-md text-text-primary">默认网络模式</div>
                <div class="text-label-sm text-text-secondary">首页与链接默认展示外网还是内网地址</div>
              </div>
              <div class="flex items-center bg-surface-container-highest rounded-full p-1 gap-1 shrink-0">
                <button class="px-4 py-1.5 rounded-full text-sm font-semibold transition-all"
                  :class="form.network === 'external' ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'"
                  @click="form.network = 'external'">
                  <span class="inline-flex items-center gap-1"><span class="material-symbols-outlined text-[16px]">public</span>外网</span>
                </button>
                <button class="px-4 py-1.5 rounded-full text-sm font-semibold transition-all"
                  :class="form.network === 'internal' ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'"
                  @click="form.network = 'internal'">
                  <span class="inline-flex items-center gap-1"><span class="material-symbols-outlined text-[16px]">home</span>内网</span>
                </button>
              </div>
            </div>

            <!-- 界面主题 -->
            <div class="flex items-center justify-between py-3 border-b border-surface-variant/40">
              <div>
                <div class="text-body-md text-text-primary">界面主题</div>
                <div class="text-label-sm text-text-secondary">浅色 / 深色 / 跟随系统</div>
              </div>
              <div class="flex items-center bg-surface-container-highest rounded-full p-1 gap-1 shrink-0">
                <button v-for="t in [{k:'light',l:'浅色',i:'light_mode'},{k:'dark',l:'深色',i:'dark_mode'},{k:'system',l:'跟随系统',i:'auto_mode'}]"
                  :key="t.k" class="px-4 py-1.5 rounded-full text-sm font-semibold transition-all"
                  :class="form.theme === t.k ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'"
                  @click="form.theme = t.k">
                  <span class="inline-flex items-center gap-1"><span class="material-symbols-outlined text-[16px]">{{ t.i }}</span>{{ t.l }}</span>
                </button>
              </div>
            </div>

            <!-- 天气城市 -->
            <div class="flex items-center justify-between py-3">
              <div>
                <div class="text-body-md text-text-primary">天气城市</div>
                <div class="text-label-sm text-text-secondary">首页天气小组件展示的城市</div>
              </div>
              <input v-model="form.weather_city" type="text" class="w-40 px-4 py-2 rounded-xl bg-surface-container border border-outline-variant/60 text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-primary/40" placeholder="如：北京" />
            </div>

            <div class="flex justify-end mt-5">
              <button @click="saveProfile" :disabled="savingProfile"
                class="px-6 py-2.5 rounded-xl bg-primary text-on-primary text-sm font-semibold shadow-sm hover:bg-primary/90 transition-all disabled:opacity-50">
                {{ savingProfile ? '保存中…' : '保存偏好' }}
              </button>
            </div>
          </section>

          <!-- 安全 -->
          <section id="sec-security" class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 scroll-mt-24">
            <h2 class="font-headline-sm text-headline-sm text-text-primary mb-5">安全</h2>
            <div class="space-y-4 max-w-sm">
              <div>
                <label class="block text-label-sm text-text-secondary mb-1.5">当前密码</label>
                <input v-model="pwd.current" type="password" class="w-full px-4 py-2.5 rounded-xl bg-surface-container border border-outline-variant/60 text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-primary/40" />
              </div>
              <div>
                <label class="block text-label-sm text-text-secondary mb-1.5">新密码</label>
                <input v-model="pwd.next" type="password" class="w-full px-4 py-2.5 rounded-xl bg-surface-container border border-outline-variant/60 text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-primary/40" placeholder="至少 6 位" />
              </div>
              <div>
                <label class="block text-label-sm text-text-secondary mb-1.5">确认新密码</label>
                <input v-model="pwd.confirm" type="password" class="w-full px-4 py-2.5 rounded-xl bg-surface-container border border-outline-variant/60 text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-primary/40" />
              </div>
            </div>
            <div class="flex justify-end mt-5">
              <button @click="savePassword" :disabled="savingPwd"
                class="px-6 py-2.5 rounded-xl bg-primary text-on-primary text-sm font-semibold shadow-sm hover:bg-primary/90 transition-all disabled:opacity-50">
                {{ savingPwd ? '更新中…' : '更新密码' }}
              </button>
            </div>
          </section>

          <!-- 账号信息（只读） -->
          <section id="sec-info" class="bg-bg-card rounded-2xl p-card-padding shadow-glass border border-surface-variant/50 scroll-mt-24">
            <h2 class="font-headline-sm text-headline-sm text-text-primary mb-4">账号信息</h2>
            <div class="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
              <div>
                <div class="text-label-sm text-text-secondary">角色</div>
                <div class="text-text-primary font-medium mt-1">{{ store.user?.role || '—' }}</div>
              </div>
              <div>
                <div class="text-label-sm text-text-secondary">注册时间</div>
                <div class="text-text-primary font-medium mt-1">{{ store.user?.created_at ? store.user.created_at.slice(0, 10) : '—' }}</div>
              </div>
              <div>
                <div class="text-label-sm text-text-secondary">最后活跃</div>
                <div class="text-text-primary font-medium mt-1">{{ store.user?.last_seen ? store.user.last_seen.slice(0, 10) : '—' }}</div>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>

    <!-- 右下角：返回前台（移动端也始终可见） -->
    <button
      class="fixed bottom-20 lg:bottom-8 right-6 lg:right-8 z-40 flex items-center gap-2 px-4 py-3 rounded-full bg-primary text-on-primary shadow-[0_10px_25px_-5px_rgba(108,92,231,0.5)] hover:scale-105 hover:bg-primary/90 transition-[transform,background-color] active:scale-95"
      @click="goFront"
      aria-label="返回前台"
    >
      <span class="material-symbols-outlined text-[20px]">arrow_back</span>
      <span class="font-body-sm font-semibold">返回前台</span>
    </button>
  </div>
</template>
