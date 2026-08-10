<script setup>
import { ref, computed } from 'vue'
import { showToast } from '../store'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '选择图标' },
})
const emit = defineEmits(['update:open', 'pick'])

// 常用 Material Symbols 图标（可按需继续扩充）；点击即复制其代码
const ICONS = [
  // 通用 / 界面
  'home', 'home_work', 'apartment', 'business', 'work', 'school', 'menu_book', 'book', 'article',
  'description', 'folder', 'folder_open', 'folder_shared', 'category', 'label', 'bookmark', 'star',
  'favorite', 'schedule', 'event', 'calendar_today', 'alarm', 'notifications', 'mail', 'chat', 'forum',
  'group', 'person', 'person_add', 'account_circle', 'admin_panel_settings', 'settings', 'settings_applications',
  'build', 'construction', 'handyman', 'hardware', 'palette', 'brush', 'emoji_emotions', 'image', 'photo',
  // 影音 / 媒体
  'camera', 'videocam', 'movie', 'theaters', 'music_note', 'audiotrack', 'podcasts', 'library_music',
  'play_circle', 'pause_circle', 'live_tv', 'smart_display', 'slideshow', 'gallery_thumbnail', 'collections',
  'auto_awesome', 'dashboard', 'insights', 'analytics', 'bar_chart', 'pie_chart', 'show_chart', 'monitoring',
  'bolt', 'lightbulb', 'psychology', 'touch_app', 'extension', 'widgets', 'apps', 'grid_view', 'view_list',
  'check_circle', 'cancel', 'block', 'report', 'flag', 'warning', 'error', 'help', 'help_outline', 'info',
  // 搜索 / 语言 / 出行
  'search', 'search_insights', 'language', 'translate', 'public', 'travel_explore', 'map', 'place',
  'location_on', 'navigation', 'directions', 'directions_car', 'local_shipping', 'flight', 'train',
  'directions_bike', 'restaurant', 'local_cafe', 'local_bar', 'local_grocery_store', 'shopping_cart',
  'shopping_bag', 'store', 'credit_card', 'payments', 'account_balance', 'savings', 'attach_money',
  'request_quote', 'receipt', 'calculate', 'science', 'biotech', 'medical_services', 'health_and_safety',
  'monitor_heart', 'fitness_center', 'sports_esports', 'sports_basketball', 'casino', 'celebration', 'cake',
  'emoji_events', 'workspace_premium', 'diamond',
  // 开发 / 设备
  'code', 'terminal', 'javascript', 'html', 'css', 'php', 'database', 'storage', 'cloud', 'cloud_upload',
  'cloud_download', 'cloud_done', 'dns', 'hub', 'router', 'wifi', 'wifi_off', 'bluetooth', 'computer',
  'laptop', 'laptop_chromebook', 'desktop_windows', 'tablet', 'smartphone', 'phone_android', 'print',
  'keyboard', 'mouse', 'tv', 'speaker', 'headphones', 'cast', 'link', 'link_off', 'share', 'content_copy',
  'content_paste', 'file_copy', 'file_download', 'file_upload', 'download', 'upload', 'save', 'edit',
  'edit_note', 'draw', 'delete', 'add', 'add_circle', 'add_link', 'remove', 'close', 'check', 'done',
  'done_all', 'reply', 'forward', 'send', 'mark_email_read', 'shield', 'shield_moon', 'verified', 'lock',
  'lock_open', 'key', 'vpn_key', 'fingerprint', 'visibility', 'visibility_off', 'password', 'security',
  'bug_report', 'policy', 'balance', 'gavel', 'campaign', 'announcement', 'microphone', 'mic', 'volume_up',
  'graphic_eq', 'tune', 'filter_alt', 'sort', 'view_agenda', 'dashboard_customize', 'rocket_launch',
  'model_training', 'dataset', 'integration_instructions', 'api', 'webhook', 'web_asset', 'schema',
  'inventory', 'inventory_2', 'shopping_bag', 'checkroom', 'medical_services', 'vaccines',
  'monitoring', 'speed', 'electric_bolt', 'solar_power', 'energy_savings_leaf', 'recycling', 'eco',
  'park', 'nature', 'grass', 'forest', 'water_drop', 'waves', 'wb_sunny', 'dark_mode', 'light_mode',
  'auto_mode', 'contrast', 'brightness_6', 'color_lens', 'format_paint', 'gesture', 'touch_app', 'back_hand',
  'badge', 'badge_important', 'verified_user', 'gpp_maybe', 'history_edu', 'menu', 'menu_open', 'more_horiz',
  'more_vert', 'expand_more', 'chevron_right', 'arrow_back', 'arrow_upward', 'arrow_forward', 'open_in_new',
  'launch', 'visibility', 'preview', 'visibility_off', 'hide_source', 'source', 'code_blocks', 'data_object',
  'api', 'dns', 'lan', 'public', 'language', 'translate', 'globe', 'forum', 'hub', 'account_tree', 'schema',
]

const search = ref('')
const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return ICONS
  return ICONS.filter((n) => n.includes(q))
})

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

async function onPick(name) {
  const ok = await copyText(name)
  showToast(ok ? `已复制并填入：${name}` : `已选择：${name}`, ok ? 'success' : 'info')
  emit('pick', name)
  emit('update:open', false)
}

function close() {
  emit('update:open', false)
}
</script>

<template>
  <div v-if="open" class="fixed inset-0 z-[80] flex items-center justify-center p-4">
    <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="close"></div>
    <div class="relative bg-bg-card w-full max-w-3xl max-h-[85vh] rounded-[20px] shadow-2xl overflow-hidden flex flex-col border border-outline-variant/30">
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

      <!-- 搜索 -->
      <div class="px-6 py-3 border-b border-outline-variant/20 shrink-0">
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
        <div v-if="!filtered.length" class="text-center py-16 text-on-surface-variant">
          <span class="material-symbols-outlined text-4xl">search_off</span>
          <p class="mt-2 font-body-sm text-body-sm">没有匹配的图标</p>
        </div>
        <div v-else class="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-2">
          <button
            v-for="n in filtered"
            :key="n"
            class="flex flex-col items-center justify-center gap-1 py-3 rounded-xl border border-transparent hover:border-primary/40 hover:bg-primary-fixed/30 transition-colors group"
            :title="`点击复制：${n}`"
            @click="onPick(n)"
          >
            <span class="material-symbols-outlined text-[26px] text-on-surface group-hover:text-primary">{{ n }}</span>
            <span class="font-label-sm text-label-sm text-on-surface-variant truncate max-w-full px-1 group-hover:text-primary">{{ n }}</span>
          </button>
        </div>
      </div>

      <div class="px-6 py-2.5 border-t border-outline-variant/20 text-center shrink-0">
        <span class="font-label-sm text-label-sm text-on-surface-variant">共 {{ filtered.length }} 个图标 · 点击下方任意图标即可选用</span>
      </div>
    </div>
  </div>
</template>
