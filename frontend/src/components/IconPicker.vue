<script setup>
import { ref, computed } from 'vue'
import { showToast } from '../store'
import { api } from '../api/client'
import EntityIcon from './EntityIcon.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '选择图标' },
})
const emit = defineEmits(['update:open', 'pick'])

// 图标来源：系统图标（Material Symbols）/ Feather / Boxicons / FontAwesome / Flaticon（自定义）
const TABS = [
  { key: 'symbol', label: '系统图标' },
  { key: 'feather', label: 'Feather' },
  { key: 'boxicons', label: 'Boxicons' },
  { key: 'fontawesome', label: 'FontAwesome' },
  { key: 'flaticon', label: 'Flaticon' },
]
const activeTab = ref('symbol')

// 系统图标（Material Symbols）
const SYMBOL = [
  'home', 'home_work', 'apartment', 'business', 'work', 'school', 'menu_book', 'book', 'article',
  'description', 'folder', 'folder_open', 'folder_shared', 'category', 'label', 'bookmark', 'star',
  'favorite', 'schedule', 'event', 'calendar_today', 'alarm', 'notifications', 'mail', 'chat', 'forum',
  'group', 'person', 'person_add', 'account_circle', 'admin_panel_settings', 'settings', 'settings_applications',
  'build', 'construction', 'handyman', 'hardware', 'palette', 'brush', 'image', 'photo',
  'camera', 'videocam', 'movie', 'theaters', 'music_note', 'audiotrack', 'podcasts', 'library_music',
  'play_circle', 'pause_circle', 'live_tv', 'smart_display', 'slideshow', 'collections',
  'auto_awesome', 'dashboard', 'insights', 'analytics', 'bar_chart', 'pie_chart', 'show_chart', 'monitoring',
  'bolt', 'lightbulb', 'psychology', 'touch_app', 'extension', 'widgets', 'apps', 'grid_view', 'view_list',
  'check_circle', 'cancel', 'block', 'report', 'flag', 'warning', 'error', 'help', 'help_outline', 'info',
  'search', 'language', 'translate', 'public', 'travel_explore', 'map', 'place',
  'location_on', 'navigation', 'directions', 'directions_car', 'local_shipping', 'flight', 'train',
  'directions_bike', 'restaurant', 'local_cafe', 'local_bar', 'local_grocery_store', 'shopping_cart',
  'shopping_bag', 'store', 'credit_card', 'payments', 'account_balance', 'savings', 'attach_money',
  'receipt', 'calculate', 'science', 'biotech', 'medical_services', 'health_and_safety',
  'monitor_heart', 'fitness_center', 'sports_esports', 'sports_basketball', 'casino', 'celebration', 'cake',
  'emoji_events', 'workspace_premium', 'diamond',
  'code', 'terminal', 'javascript', 'html', 'css', 'php', 'database', 'storage', 'cloud', 'cloud_upload',
  'cloud_download', 'dns', 'hub', 'router', 'wifi', 'wifi_off', 'bluetooth', 'computer',
  'laptop', 'desktop_windows', 'tablet', 'smartphone', 'phone_android', 'print',
  'keyboard', 'mouse', 'tv', 'speaker', 'headphones', 'cast', 'link', 'link_off', 'share', 'content_copy',
  'file_download', 'file_upload', 'download', 'upload', 'save', 'edit',
  'delete', 'add', 'add_circle', 'remove', 'close', 'check', 'done',
  'reply', 'forward', 'send', 'shield', 'verified', 'lock',
  'lock_open', 'key', 'vpn_key', 'fingerprint', 'visibility', 'visibility_off', 'password', 'security',
  'bug_report', 'policy', 'campaign', 'announcement', 'microphone', 'volume_up',
  'tune', 'filter_alt', 'sort', 'dashboard_customize', 'rocket_launch',
  'model_training', 'inventory', 'shopping_bag', 'vaccines',
  'speed', 'solar_power', 'energy_savings_leaf', 'recycling', 'eco',
  'park', 'nature', 'water_drop', 'waves', 'wb_sunny', 'dark_mode', 'light_mode',
  'contrast', 'color_lens', 'format_paint', 'gesture', 'back_hand',
  'badge', 'verified_user', 'history_edu', 'menu', 'more_horiz',
  'more_vert', 'expand_more', 'chevron_right', 'arrow_back', 'arrow_upward', 'arrow_forward', 'open_in_new',
  'launch', 'preview', 'source', 'code_blocks', 'data_object',
  'api', 'webhook', 'web_asset', 'schema',
  'account_tree', 'globe', 'lan',
]
// Feather Icons（名称，存储为 feather:<name>）
const FEATHER = [
  'activity', 'alert-circle', 'alert-triangle', 'anchor', 'aperture', 'archive', 'arrow-down', 'arrow-left',
  'arrow-right', 'arrow-up', 'award', 'bar-chart', 'bar-chart-2', 'bell', 'bluetooth', 'book', 'bookmark',
  'box', 'briefcase', 'calendar', 'camera', 'cast', 'check', 'check-circle', 'check-square', 'chevron-down',
  'chevron-left', 'chevron-right', 'chevron-up', 'clipboard', 'clock', 'cloud', 'cloud-off', 'code', 'command',
  'compass', 'copy', 'cpu', 'credit-card', 'database', 'delete', 'download', 'droplet', 'edit', 'edit-2',
  'edit-3', 'external-link', 'eye', 'facebook', 'file', 'file-text', 'film', 'filter', 'flag', 'folder',
  'gift', 'github', 'globe', 'grid', 'hard-drive', 'hash', 'headphones', 'heart', 'help-circle', 'home',
  'image', 'inbox', 'info', 'instagram', 'layers', 'layout', 'link', 'link-2', 'list', 'lock', 'log-in',
  'log-out', 'mail', 'map', 'map-pin', 'menu', 'message-circle', 'mic', 'monitor', 'moon', 'more-horizontal',
  'more-vertical', 'music', 'navigation', 'package', 'paperclip', 'pause', 'phone', 'phone-call', 'pie-chart',
  'play', 'plus', 'plus-circle', 'power', 'printer', 'radio', 'refresh-cw', 'repeat', 'search', 'send',
  'settings', 'share-2', 'shield', 'shopping-bag', 'shopping-cart', 'shuffle', 'sidebar', 'sliders',
  'smartphone', 'star', 'sun', 'tablet', 'tag', 'terminal', 'trash', 'trash-2', 'trending-up', 'truck',
  'tv', 'twitter', 'umbrella', 'unlock', 'upload', 'user', 'users', 'video', 'volume', 'wifi', 'wind', 'x',
  'x-circle', 'zap', 'zoom-in',
]
// Boxicons（bx- 普通样式，存储为 bx <name>）
const BOXICONS = [
  'bx-home', 'bx-building', 'bx-buildings', 'bx-cog', 'bx-calendar', 'bx-calendar-event', 'bx-cart',
  'bx-chart', 'bx-cloud', 'bx-envelope', 'bx-folder', 'bx-heart', 'bx-image', 'bx-link', 'bx-map',
  'bx-movie', 'bx-music', 'bx-phone', 'bx-search', 'bx-star', 'bx-user', 'bx-group', 'bx-bell',
  'bx-bookmark', 'bx-camera', 'bx-message-rounded', 'bx-news', 'bx-wifi', 'bx-world', 'bx-data',
  'bx-server', 'bx-laptop', 'bx-mobile', 'bx-desktop', 'bx-printer', 'bx-globe', 'bx-package',
  'bx-shopping-bag', 'bx-tv', 'bx-video', 'bx-headphone', 'bx-pulse', 'bx-rocket', 'bx-atom', 'bx-cube',
  'bx-grid-alt', 'bx-bar-chart', 'bx-pie-chart', 'bx-tachometer', 'bx-shield', 'bx-lock', 'bx-lock-alt',
  'bx-key', 'bx-credit-card', 'bx-dollar', 'bx-money', 'bx-wallet', 'bx-coin', 'bx-briefcase', 'bx-id-card',
  'bx-award', 'bx-medal', 'bx-trophy', 'bx-target-lock', 'bx-bulb', 'bx-paint', 'bx-brush', 'bx-code',
  'bx-code-block', 'bx-terminal', 'bx-bug', 'bx-cpu', 'bx-chip', 'bx-hdd', 'bx-network-chart',
  'bx-fingerprint', 'bx-qr', 'bx-scan', 'bx-plus-circle', 'bx-edit', 'bx-trash', 'bx-check',
  'bx-check-circle', 'bx-x', 'bx-x-circle', 'bx-info-circle', 'bx-error', 'bx-help-circle', 'bx-book',
  'bx-calculator', 'bx-receipt', 'bx-stats', 'bx-time', 'bx-wrench', 'bx-first-aid', 'bx-health',
  'bx-traffic-cone', 'bx-bxs-bank', 'bx-bxs-store', 'bx-bxs-plane',
]
// FontAwesome（fa-solid，存储为 fa-solid fa-<name>）
const FONTAWESOME = [
  'house', 'building', 'building-columns', 'gear', 'calendar', 'calendar-days', 'cart-shopping', 'chart-line',
  'chart-bar', 'chart-pie', 'cloud', 'envelope', 'folder', 'folder-open', 'heart', 'image', 'link',
  'map-location-dot', 'film', 'music', 'phone', 'magnifying-glass', 'star', 'user', 'users', 'bell',
  'bookmark', 'camera', 'comment', 'comment-dots', 'newspaper', 'wifi', 'earth-americas', 'database',
  'server', 'laptop', 'mobile-screen-button', 'desktop', 'print', 'globe', 'box', 'shopping-bag', 'tv',
  'video', 'headphones', 'heart-pulse', 'rocket', 'atom', 'cube', 'network-wired', 'shield-halved', 'lock',
  'key', 'credit-card', 'dollar-sign', 'money-bill-wave', 'wallet', 'coins', 'briefcase', 'id-card',
  'certificate', 'award', 'medal', 'trophy', 'bullseye', 'lightbulb', 'paint-brush', 'brush', 'code',
  'code-branch', 'terminal', 'bug', 'microchip', 'hard-drive', 'fingerprint', 'qr-code', 'plus-circle',
  'pen-to-square', 'trash-can', 'check', 'circle-check', 'xmark', 'circle-xmark', 'circle-info',
  'triangle-exclamation', 'circle-question', 'bolt', 'fire', 'snowflake', 'sun', 'moon', 'cloud-sun',
  'diagram-project', 'gauge', 'route', 'location-dot', 'tag', 'stamp', 'gem', 'plane', 'car', 'train',
  'ship', 'bicycle', 'gamepad', 'puzzle-piece', 'book', 'book-open', 'graduation-cap', 'flask', 'microscope',
  'pill', 'hospital', 'ambulance', 'robot', 'brain', 'compass', 'signal', 'satellite', 'clock',
  'calendar-check', 'circle-play', 'display', 'tower-broadcast', 'wrench', 'screwdriver-wrench', 'gears',
  'shop', 'store', 'warehouse', 'truck-fast', 'file-lines', 'clipboard-list', 'bell-concierge', 'mug-hot',
]

const SOURCES = {
  symbol: SYMBOL,
  feather: FEATHER,
  boxicons: BOXICONS,
  fontawesome: FONTAWESOME,
}

function storeValue(tab, name) {
  if (tab === 'symbol') return name
  if (tab === 'feather') return 'feather:' + name
  if (tab === 'boxicons') return 'bx ' + name
  if (tab === 'fontawesome') return 'fa-solid fa-' + name
  return name
}

const search = ref('')
const items = computed(() => {
  const tab = activeTab.value
  if (tab === 'flaticon') return []
  const list = SOURCES[tab] || []
  const q = search.value.trim().toLowerCase()
  const filtered = q ? list.filter((n) => n.includes(q)) : list
  return filtered.map((n) => ({ name: n, value: storeValue(tab, n) }))
})

// Flaticon：付费图标库无免费 Web 字体，这里以「上传 / 粘贴地址」方式使用下载的图标
const customUrl = ref('')
const uploading = ref(false)

async function onUpload(e) {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  uploading.value = true
  try {
    const data = await api.uploadIcon(file)
    showToast('图标已上传并填入', 'success')
    emit('pick', data.path)
    emit('update:open', false)
  } catch (err) {
    showToast(err.message || '上传失败', 'error')
  } finally {
    uploading.value = false
    e.target.value = ''
  }
}
function applyCustomUrl() {
  const u = customUrl.value.trim()
  if (!u) {
    showToast('请先粘贴图标地址', 'info')
    return
  }
  emit('pick', u)
  emit('update:open', false)
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch (e) {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    let ok = false
    try {
      ok = document.execCommand('copy')
    } catch (_) {
      ok = false
    }
    document.body.removeChild(ta)
    return ok
  }
}

async function onPick(value) {
  emit('pick', value)
  showToast('已选择并填入图标', 'success')
  emit('update:open', false)
}

function close() {
  emit('update:open', false)
}
</script>

<template>
  <transition name="modal" appear>
  <div v-if="open" class="fixed inset-0 z-[80] flex items-center justify-center p-4">
    <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="close"></div>
    <div class="relative bg-bg-card modal-panel w-full max-w-3xl max-h-[85vh] rounded-[20px] shadow-2xl overflow-hidden flex flex-col border border-outline-variant/30">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-outline-variant/20 bg-surface-container-lowest flex justify-between items-center shrink-0">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-xl bg-primary-fixed text-primary flex items-center justify-center">
            <span class="material-symbols-outlined text-[20px]">emoji_emotions</span>
          </div>
          <div>
            <h2 class="font-headline-md text-headline-md text-on-surface">{{ title }}</h2>
            <p class="font-label-sm text-label-sm text-on-surface-variant">点击图标即可复制其代码并填入输入框</p>
          </div>
        </div>
        <button class="w-9 h-9 rounded-full hover:bg-surface-container transition-colors flex items-center justify-center text-on-surface-variant" @click="close">
          <span class="material-symbols-outlined">close</span>
        </button>
      </div>

      <!-- 图标来源切换 -->
      <div class="px-6 py-3 border-b border-outline-variant/20 shrink-0">
        <div class="flex items-center bg-surface-container-highest rounded-full p-1 gap-1 overflow-x-auto">
          <button type="button" v-for="t in TABS" :key="t.key"
            class="flex-none px-3 py-1.5 rounded-full text-sm font-medium transition-all"
            :class="activeTab === t.key ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'"
            @click="activeTab = t.key">
            {{ t.label }}
          </button>
        </div>
      </div>

      <!-- 搜索（Flaticon 不需要） -->
      <div v-if="activeTab !== 'flaticon'" class="px-6 py-3 border-b border-outline-variant/20 shrink-0">
        <div class="relative">
          <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline">search</span>
          <input
            v-model="search"
            class="w-full pl-10 pr-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-full font-body-sm text-body-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all"
            placeholder="搜索图标名称，如 home、cloud、settings…"
            type="text"
            autofocus
          />
        </div>
      </div>

      <!-- 图标网格 -->
      <div class="flex-1 overflow-y-auto p-4">
        <!-- 系统图标 / Feather / Boxicons / FontAwesome -->
        <template v-if="activeTab !== 'flaticon'">
          <div v-if="!items.length" class="text-center py-16 text-on-surface-variant">
            <span class="material-symbols-outlined text-4xl">search_off</span>
            <p class="mt-2 font-body-sm text-body-sm">没有匹配的图标</p>
          </div>
          <div v-else class="grid grid-cols-5 sm:grid-cols-8 md:grid-cols-10 gap-2">
            <button
              v-for="it in items"
              :key="it.value"
              class="flex flex-col items-center justify-center gap-1 py-3 rounded-xl border border-transparent hover:border-primary/40 hover:bg-primary-fixed/30 transition-[transform,background-color,border-color] active:scale-95 group"
              :title="`点击选用：${it.name}`"
              @click="onPick(it.value)"
            >
              <EntityIcon :icon="it.value" :size="26" class="text-on-surface group-hover:text-primary" />
              <span class="font-label-sm text-label-sm text-on-surface-variant truncate max-w-full px-1 group-hover:text-primary">{{ it.name }}</span>
            </button>
          </div>
        </template>

        <!-- Flaticon：上传 / 粘贴地址 -->
        <template v-else>
          <div class="max-w-md mx-auto py-6 space-y-5">
            <p class="font-body-sm text-body-sm text-on-surface-variant leading-relaxed">
              Flaticon 为付费图标库，无免费 Web 字体，故以「上传 / 粘贴图标地址」方式使用。
              可前往 Flaticon 下载 SVG/PNG 后上传，或粘贴图标直链（http(s) / data:），与站内其它图片图标一致。
            </p>
            <div>
              <label class="font-label-md text-label-md text-on-surface">上传图标文件</label>
              <button type="button" :disabled="uploading"
                class="mt-2 w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-primary text-on-primary font-label-md text-label-md disabled:opacity-50">
                <span class="material-symbols-outlined text-[18px]">upload</span>
                {{ uploading ? '上传中…' : '选择并上传图标' }}
                <input type="file" accept="image/*" class="hidden" :disabled="uploading" @change="onUpload" />
              </button>
            </div>
            <div>
              <label class="font-label-md text-label-md text-on-surface">或粘贴图标地址</label>
              <div class="mt-2 flex gap-2">
                <input v-model="customUrl" type="text" placeholder="https://… 或 /uploads/… 或 data:image/…"
                  class="flex-1 px-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-full font-body-sm text-body-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary" />
                <button type="button" @click="applyCustomUrl"
                  class="px-4 py-2.5 rounded-full bg-primary text-on-primary font-label-md text-label-md">填入</button>
              </div>
            </div>
          </div>
        </template>
      </div>

      <div v-if="activeTab !== 'flaticon'" class="px-6 py-2.5 border-t border-outline-variant/20 text-center shrink-0">
        <span class="font-label-sm text-label-sm text-on-surface-variant">共 {{ items.length }} 个图标 · 点击下方任意图标即可选用</span>
      </div>
    </div>
  </div>
  </transition>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.28s cubic-bezier(0.32, 0.72, 0, 1);
}
.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}
.modal-enter-active .modal-panel {
  transition: transform 0.42s cubic-bezier(0.32, 0.72, 0, 1), opacity 0.42s cubic-bezier(0.32, 0.72, 0, 1);
}
.modal-leave-active .modal-panel {
  transition: transform 0.22s cubic-bezier(0.32, 0.72, 0, 0, 1), opacity 0.22s cubic-bezier(0.32, 0.72, 0, 1);
}
.modal-enter-from .modal-panel,
.modal-leave-to .modal-panel {
  transform: scale(0.96) translateY(14px);
  opacity: 0;
}
</style>
