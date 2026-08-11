<script setup>
import { ref, computed } from 'vue'
import { showToast } from '../store'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '选择图标' },
})
const emit = defineEmits(['update:open', 'pick'])

// 图标来源切换：系统图标（Material Symbols）/ 表情符号（emoji）
const activeTab = ref('symbol')

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

// 表情符号（新增图标源）：每项 [emoji, 关键字(中/英，用于搜索)]
const EMOJI = [
  ['🚀', 'rocket 火箭 发射 启动'], ['🌐', 'globe 地球 网络 全球'], ['💡', 'idea 灯泡 点子 灵感'],
  ['🔧', 'wrench 扳手 工具 设置'], ['⚙️', 'gear 齿轮 设置 配置'], ['📊', 'chart 图表 统计 数据'],
  ['📈', 'trend 上涨 增长 曲线'], ['📉', 'down 下跌 下降'], ['📁', 'folder 文件夹 文件'],
  ['📂', 'folder 打开 文件夹'], ['📄', 'doc 文档 文件'], ['📝', 'edit 笔记 编辑 记录'],
  ['📌', 'pin 图钉 置顶 标记'], ['🔖', 'bookmark 书签 收藏'], ['🏠', 'home 家 主页 首页'],
  ['🏢', 'building 公司 企业 办公'], ['🏬', 'shop 商场 门店'], ['🏭', 'factory 工厂 生产'],
  ['💻', 'computer 电脑 笔记本'], ['🖥️', 'desktop 台式机 显示器'], ['💾', 'save 保存 软盘 存储'],
  ['💽', 'disk 磁盘 存储'], ['🖱️', 'mouse 鼠标'], ['⌨️', 'keyboard 键盘'],
  ['📱', 'phone 手机 移动'], ['📞', 'call 电话 联系'], ['📧', 'mail 邮件 邮箱'],
  ['✉️', 'envelope 信 邮件'], ['📨', 'inbox 收件 消息'], ['🔔', 'bell 铃铛 通知 提醒'],
  ['🔍', 'search 搜索 查找'], ['🔎', 'search 放大镜 查找'], ['🌟', 'star 星 收藏 推荐'],
  ['⭐', 'star 星标 收藏'], ['✨', 'sparkle 闪光 亮点'], ['🎯', 'target 目标 靶心'],
  ['🔒', 'lock 锁 安全 加密'], ['🔓', 'unlock 解锁 打开'], ['🔑', 'key 钥匙 权限 密码'],
  ['🛡️', 'shield 盾 安全 保护'], ['🔐', 'secure 安全 锁'], ['👤', 'user 用户 人 账户'],
  ['👥', 'users 团队 群组 多用户'], ['👑', 'crown 皇冠 管理员 特权'], ['🧑‍💻', 'developer 开发 程序员'],
  ['🧠', 'brain 大脑 智能 ai'], ['🤖', 'robot 机器人 ai 自动化'], ['⚡', 'bolt 闪电 快 能量'],
  ['🔥', 'fire 火 热门 活跃'], ['❄️', 'snow 雪 冷 冰冻'], ['🌈', 'rainbow 彩虹 色彩'],
  ['🌙', 'moon 月亮 夜间 暗'], ['☀️', 'sun 太阳 白天 亮'], ['🌤️', 'weather 天气 晴'],
  ['☁️', 'cloud 云 天气'], ['🌧️', 'rain 雨 天气'], ['⛅', 'partly 多云 天气'],
  ['💧', 'water 水 水滴'], ['🌊', 'wave 海浪 水'], ['🌱', 'plant 植物 成长 绿'],
  ['🌳', 'tree 树 森林'], ['🌸', 'flower 花 樱花'], ['🍀', 'clover 幸运 四叶草'],
  ['🐱', 'cat 猫 宠物'], ['🐶', 'dog 狗 宠物'], ['🦊', 'fox 狐狸'],
  ['🐳', 'whale 鲸鱼'], ['🐝', 'bee 蜜蜂'], ['🦋', 'butterfly 蝴蝶'],
  ['🍎', 'apple 苹果 水果'], ['☕', 'coffee 咖啡 饮品'], ['🍵', 'tea 茶'],
  ['🍔', 'burger 汉堡 食物'], ['🍕', 'pizza 披萨'], ['🎮', 'game 游戏 手柄'],
  ['🎲', 'dice 骰子 随机'], ['🎨', 'art 画 艺术 设计'], ['🎵', 'music 音乐 音符'],
  ['🎬', 'movie 电影 视频'], ['📺', 'tv 电视'], ['📷', 'camera 相机 拍照'],
  ['💰', 'money 钱 财富 金币'], ['💎', 'gem 钻石 宝石 珍贵'], ['🏆', 'trophy 奖杯 冠军 成就'],
  ['🥇', 'gold 金牌 第一'], ['❤️', 'heart 心 喜欢 爱'], ['💬', 'chat 聊天 对话 评论'],
  ['💡', 'bulb 灯泡 提示'], ['🧩', 'puzzle 拼图 模块'], ['🔗', 'link 链接 连接 链'],
  ['📦', 'box 包裹 容器 部署'], ['🚚', 'truck 货车 物流'], ['🛒', 'cart 购物车 购物'],
  ['🔭', 'telescope 望远镜 观察'], ['🧭', 'compass 指南针 导航 方向'], ['🗺️', 'map 地图 导航'],
  ['📍', 'pin 定位 位置'], ['🏷️', 'tag 标签 价格'], ['🧱', 'brick 砖 模块 组件'],
  ['🔌', 'plug 插头 电源 连接'], ['📡', 'satellite 信号 天线 网络'], ['🛰️', 'satellite 卫星'],
  ['⏰', 'clock 时钟 时间 提醒'], ['📅', 'calendar 日历 日期'], ['🗓️', 'calendar 日程'],
  ['✅', 'check 完成 对勾 通过'], ['❌', 'cross 错误 关闭'], ['⚠️', 'warning 警告 注意'],
  ['🚨', 'alert 警报 紧急'], ['🆘', 'help 求助 急救'], ['📢', 'megaphone 广播 通知 公告'],
  ['🧪', 'test 实验 测试 试管'], ['🔬', 'microscope 显微镜 研究'], ['🧬', 'dna 基因 生物'],
  ['💊', 'pill 药 医疗'], ['🏥', 'hospital 医院 医疗'], ['🚑', 'ambulance 救护车'],
]
const filteredEmoji = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return EMOJI
  return EMOJI.filter(([e, k]) => k.toLowerCase().includes(q) || e.includes(q))
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
        <div class="flex items-center bg-surface-container-highest rounded-full p-1 gap-1">
          <button type="button" class="flex-1 px-3 py-1.5 rounded-full text-sm font-medium transition-all flex items-center justify-center gap-1.5"
            :class="activeTab === 'symbol' ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'"
            @click="activeTab = 'symbol'">
            <span class="material-symbols-outlined text-[18px]">text_decorated</span>系统图标
          </button>
          <button type="button" class="flex-1 px-3 py-1.5 rounded-full text-sm font-medium transition-all flex items-center justify-center gap-1.5"
            :class="activeTab === 'emoji' ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'"
            @click="activeTab = 'emoji'">
            <span class="material-symbols-outlined text-[18px]">mood</span>表情符号
          </button>
        </div>
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
        <!-- 系统图标（Material Symbols） -->
        <template v-if="activeTab === 'symbol'">
          <div v-if="!filtered.length" class="text-center py-16 text-on-surface-variant">
            <span class="material-symbols-outlined text-4xl">search_off</span>
            <p class="mt-2 font-body-sm text-body-sm">没有匹配的图标</p>
          </div>
          <div v-else class="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 gap-2">
            <button
              v-for="n in filtered"
              :key="n"
              class="flex flex-col items-center justify-center gap-1 py-3 rounded-xl border border-transparent hover:border-primary/40 hover:bg-primary-fixed/30 transition-[transform,background-color,border-color] active:scale-95 group"
              :title="`点击复制：${n}`"
              @click="onPick(n)"
            >
              <span class="material-symbols-outlined text-[26px] text-on-surface group-hover:text-primary">{{ n }}</span>
              <span class="font-label-sm text-label-sm text-on-surface-variant truncate max-w-full px-1 group-hover:text-primary">{{ n }}</span>
            </button>
          </div>
        </template>
        <!-- 表情符号（emoji） -->
        <template v-else>
          <div v-if="!filteredEmoji.length" class="text-center py-16 text-on-surface-variant">
            <span class="material-symbols-outlined text-4xl">search_off</span>
            <p class="mt-2 font-body-sm text-body-sm">没有匹配的符号</p>
          </div>
          <div v-else class="grid grid-cols-5 sm:grid-cols-8 md:grid-cols-10 gap-2">
            <button
              v-for="[e] in filteredEmoji"
              :key="e"
              class="flex items-center justify-center py-2.5 rounded-xl border border-transparent hover:border-primary/40 hover:bg-primary-fixed/30 transition-[transform,background-color,border-color] active:scale-95 text-[26px] leading-none"
              :title="`点击选用：${e}`"
              @click="onPick(e)"
            >{{ e }}</button>
          </div>
        </template>
      </div>

      <div class="px-6 py-2.5 border-t border-outline-variant/20 text-center shrink-0">
        <span class="font-label-sm text-label-sm text-on-surface-variant" v-if="activeTab === 'symbol'">共 {{ filtered.length }} 个图标 · 点击下方任意图标即可选用</span>
        <span class="font-label-sm text-label-sm text-on-surface-variant" v-else>共 {{ filteredEmoji.length }} 个表情符号 · 点击下方任意表情即可选用</span>
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
  transition: transform 0.22s cubic-bezier(0.32, 0.72, 0, 1), opacity 0.22s cubic-bezier(0.32, 0.72, 0, 1);
}
.modal-enter-from .modal-panel,
.modal-leave-to .modal-panel {
  transform: scale(0.96) translateY(14px);
  opacity: 0;
}
</style>
