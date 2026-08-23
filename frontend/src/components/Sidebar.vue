<script setup>
import { ref, computed } from 'vue'
import { store, cycleTheme, logout, closeDrawer, scrollToCategory } from '../store'
import { useRouter } from 'vue-router'
import EntityIcon from './EntityIcon.vue'

const router = useRouter()

// 悬浮态：
//  - hoveredParentId：当前悬浮的"有子分类父分类"（悬浮即展开，移开即折叠）
//  - hoveredItemId：当前悬浮的具体项（仅用于规则4的高亮样式，不改变选中）
const hoveredParentId = ref(null)
const hoveredItemId = ref(null)

// 仅管理员可见"管理后台"
const isAdmin = computed(() => store.user && store.user.role === 'admin')
// 折叠 = 桌面端 144px 图标轨道；展开 = 240px 全宽
const collapsed = computed(() => store.sidebarCollapsed)

// 显隐 + 宽度：移动端抽屉「常驻渲染、离屏平移」而非 display:none，
// 这样开启/关闭时能真正滑动（Apple 抽屉应沿同一路径进出、可被手指抓取）。
// 关闭态加 pointer-events-none 防止离屏时误触；桌面端始终显示（lg:translate-x-0）。
const navClass = computed(() => {
  const mobile = store.drawerOpen
    ? 'translate-x-0 flex w-[280px] max-w-[85vw]'
    : 'flex -translate-x-full w-[280px] max-w-[85vw] pointer-events-none lg:pointer-events-auto'
  const desktop = store.sidebarCollapsed
    ? 'lg:translate-x-0 lg:flex lg:w-[144px]'
    : 'lg:translate-x-0 lg:flex lg:w-[240px]'
  return mobile + ' ' + desktop
})

// 分类名 → Material Symbols 图标映射（对齐原型 P1 风格）
const categoryIconMap = {
  '开发': 'code',
  '开发工具': 'terminal',
  '影音': 'movie',
  '娱乐': 'theaters',
  '网络': 'language',
  '服务': 'dns',
  '工具': 'build',
  '源码托管': 'folder_open',
  '源码': 'source',
  '视频': 'videocam',
  '音乐': 'music_note',
  '内网服务': 'home_work',
  'NAS': 'storage',
  '收藏': 'star',
  '常用': 'bookmark',
  '工作': 'work',
  '学习': 'school',
  '社交': 'groups',
  '设计': 'palette',
  '阅读': 'menu_book',
}

function getCategoryIcon(name) {
  return categoryIconMap[name] || 'folder'
}

// 侧边栏只展示「当前用户在该分类(或任一子分类)有可见链接」的分类，与主页显示规则①②③一致：
// 无权限 / 链接全无权限 / 空分类 均不显示。has_links 由后端 categories_tree 基于
// visible_links_for(user) 计算（已含 visible/archived/角色白名单/链接权限/空判定），无需前端重复过滤。
const visibleTree = computed(() =>
  store.tree
    .filter((cat) => cat.has_links || (cat.children || []).some((c) => c.has_links))
    .map((cat) => ({ ...cat, children: (cat.children || []).filter((c) => c.has_links) }))
)

// 找到包含某分类 id 的父分类
function findParent(id) {
  for (const cat of store.tree) {
    if (cat.children && cat.children.some((c) => c.id === id)) return cat
  }
  return null
}

// 当前选中分类的父分类（若选中的是子分类），否则 null
const selectedParentId = computed(() => {
  if (!store.activeCategoryId) return null
  const p = findParent(store.activeCategoryId)
  return p ? p.id : null
})

// 是否展开某父分类：选中子分类所属的父分类（始终展开） 或 当前悬浮的父分类（悬浮即展开）
function isExpanded(cat) {
  if (!cat.children || !cat.children.length) return false
  return cat.id === selectedParentId.value || cat.id === hoveredParentId.value
}

const selStyle = ' bg-brand/10 text-brand font-semibold translate-x-1'

// 选中样式：仅当该项确实为"选中项"或"悬浮项（规则4：无子父分类或子分类）"时应用
function applySel(base, id, isChildlessParent, isChild) {
  const selected = store.activeCategoryId === id
  const hovered = hoveredItemId.value === id && (isChildlessParent || isChild)
  return base + ((selected || hovered) ? selStyle : '')
}

// 父分类样式（折叠轨道 / 展开全宽）
function parentClass(cat) {
  const base =
    'nav-item relative flex items-center rounded-lg transition-all duration-150 cursor-pointer text-on-surface-variant hover:bg-surface-variant dark:hover:bg-surface-container-highest'
  const hasChildren = cat.children && cat.children.length
  if (collapsed.value) {
    return applySel(base + ' w-24 mx-auto justify-center py-3', cat.id, !hasChildren, false)
  }
  return applySel(base + ' justify-between px-3 py-2.5', cat.id, !hasChildren, false)
}

// 子分类样式（内联 / 折叠共用）：图标 + 标题（折叠态仅图标）
function childClass(child) {
  const base =
    'nav-item relative flex items-center gap-3 rounded-lg transition-all duration-150 cursor-pointer text-on-surface-variant hover:bg-surface-variant dark:hover:bg-surface-container-highest'
  if (collapsed.value) {
    return applySel(base + ' w-24 mx-auto justify-center py-2.5', child.id, false, true)
  }
  return applySel(base + ' px-3 py-2', child.id, false, true)
}

// 悬浮整棵分类子树（<li>）：若有子分类则悬浮即展开
function onTreeEnter(cat) {
  if (cat.children && cat.children.length) hoveredParentId.value = cat.id
}
function onTreeLeave(cat) {
  if (hoveredParentId.value === cat.id) hoveredParentId.value = null
}
// 悬浮具体项（用于规则4高亮，不改变选中）
function onItemEnter(id) {
  hoveredItemId.value = id
}
function onItemLeave() {
  hoveredItemId.value = null
}

// 父分类点击：有子分类 → 无需点击展开（悬浮即展开）；无子分类 → 选中（规则1）
function onParentClick(cat) {
  if (!(cat.children && cat.children.length)) {
    selectItem(cat.id)
  }
  closeDrawerIfMobile()
}
// 子分类点击 → 选中（规则1）
function onChildClick(child) {
  selectItem(child.id)
  closeDrawerIfMobile()
}
// 选中（子分类 / 无子父分类）：设置高亮 + 平滑滚动；选中父分类始终展开，其余自动折叠（规则5）
function selectItem(id) {
  scrollToCategory(id)
}

// 子分类列表：悬浮展开时返回子项，否则空列表，交给 transition-group 做逐项进入/退出
function childList(cat) {
  return isExpanded(cat) ? cat.children : []
}
// 逐项错峰：依次进入 / 退出（延迟随索引递增，形成级联）
function staggerDelay(el) {
  const i = Number(el.dataset.index || 0)
  el.style.animationDelay = i * 30 + 'ms'
}
function clearDelay(el) {
  el.style.animationDelay = ''
}

function closeDrawerIfMobile() {
  if (typeof window !== 'undefined' && window.innerWidth < 1024) closeDrawer()
}

function goFront() {
  router.push('/')
}

async function onDisplayMode() {
  cycleTheme()
}

// 显示模式按钮：随当前模式切换图标 / 文案 / 高亮
const themeMeta = computed(
  () =>
    ({
      light: { icon: 'light_mode', label: '浅色' },
      dark: { icon: 'dark_mode', label: '深色' },
      system: { icon: 'auto_mode', label: '跟随系统' },
    }[store.theme] || { icon: 'light_mode', label: '浅色' })
)
function onSettings() {
  router.push('/settings')
}
function onAdmin() {
  router.push('/admin')
}
function onAnomalies() {
  router.push('/anomalies')
}
function onSignOut() {
  logout()
  router.push('/login')
}
function onLogin() {
  router.push('/login')
}
</script>

<template>
  <div>
    <!-- 移动端抽屉遮罩（淡入淡出，与抽屉同步） -->
    <transition name="fade">
      <div
        v-if="store.drawerOpen"
        class="fixed inset-0 bg-black/40 z-20 lg:hidden"
        @click="closeDrawer"
      ></div>
    </transition>
    <nav
      class="app-sidebar border-r border-outline-variant shadow-sm fixed left-0 top-0 h-full z-30 transition-transform duration-300 ease-spring"
      :class="navClass"
    >
      <div class="flex flex-col h-full py-8 w-full">
        <!-- Brand（折叠态仅显示 Logo） -->
        <button
          class="mb-8 flex items-center gap-4 text-left hover:opacity-80 transition-opacity"
          :class="collapsed ? 'flex-col px-0 pt-1 mx-auto' : 'px-6'"
          @click="goFront"
        >
          <div class="w-10 h-10 rounded-lg flex items-center justify-center text-primary text-xl font-bold overflow-hidden">
            <img v-if="store.siteLogo" :src="store.siteLogo" alt="logo" class="w-full h-full object-contain" />
            <span v-else>云</span>
          </div>
          <div :class="collapsed ? 'hidden' : ''">
            <h1 class="font-headline-lg text-headline-lg font-bold text-primary dark:text-primary-fixed">{{ store.siteName }}</h1>
            <p class="font-label-sm text-label-sm text-on-surface-variant">{{ store.siteSubtitle || '个人导航主页' }}</p>
          </div>
        </button>

        <!-- Category tree（折叠 / 展开共用内联子分类；展开显示 icon+title，折叠只显示 icon） -->
        <div
          class="flex-1 min-h-0 overflow-y-auto relative"
          :class="collapsed ? 'px-2' : 'px-4'"
        >
          <ul class="space-y-1">
            <li
              v-for="cat in visibleTree"
              :key="cat.id"
              class="relative"
              @mouseenter="onTreeEnter(cat)"
              @mouseleave="onTreeLeave(cat)"
            >
              <a
                class="nav-item flex items-center rounded-lg transition-all duration-150 cursor-pointer text-on-surface-variant hover:bg-surface-variant dark:hover:bg-surface-container-highest"
                :class="parentClass(cat)"
                @mouseenter="onItemEnter(cat.id)"
                @mouseleave="onItemLeave"
                @click="onParentClick(cat)"
              >
                <div class="flex items-center" :class="collapsed ? 'justify-center' : 'gap-3'">
                  <EntityIcon :icon="cat.icon" :fallback="getCategoryIcon(cat.name)" :size="collapsed ? 28 : 20" :alt="cat.name" />
                  <span class="font-headline-sm text-headline-sm" :class="collapsed ? 'hidden' : ''">{{ cat.name }}</span>
                </div>
                <!-- 展开指示：仅展开态（240px）且有子分类时显示；折叠图标轨道模式不显示展开标志 -->
                <span
                  v-if="!collapsed && cat.children && cat.children.length"
                  class="material-symbols-outlined text-[16px] text-on-surface-variant/60 transition-transform duration-200"
                  :class="isExpanded(cat) ? 'rotate-180' : ''"
                  >expand_more</span
                >
              </a>
              <!-- 子分类（悬浮父分类即展开；折叠 / 展开均为内联列表，折叠态仅图标） -->
              <transition-group
                name="child"
                tag="ul"
                class="space-y-1"
                :class="[
                  isExpanded(cat) ? 'mt-1' : '',
                  collapsed ? 'pl-2 ml-3 border-l border-outline-variant/40' : 'ml-9 border-l border-outline-variant/50 pl-2'
                ]"
                @before-enter="staggerDelay"
                @after-enter="clearDelay"
                @before-leave="staggerDelay"
                @after-leave="clearDelay"
              >
                <li
                  v-for="(child, i) in childList(cat)"
                  :key="child.id"
                  :data-index="i"
                >
                  <a
                    class="nav-item flex items-center gap-3 rounded-lg transition-all duration-150 cursor-pointer text-on-surface-variant hover:bg-surface-variant dark:hover:bg-surface-container-highest"
                    :class="childClass(child)"
                    @mouseenter="onItemEnter(child.id)"
                    @mouseleave="onItemLeave"
                    @click="onChildClick(child)"
                  >
                    <EntityIcon :icon="child.icon" :fallback="getCategoryIcon(child.name)" :size="collapsed ? 24 : 18" :alt="child.name" />
                    <span v-if="!collapsed" class="font-body-sm text-body-sm">{{ child.name }}</span>
                  </a>
                </li>
              </transition-group>
            </li>
          </ul>
        </div>

        <!-- Bottom fixed items（折叠态仅图标居中）。移动端抽屉底部加留白，避免被底部导航栏遮挡 -->
        <div class="mt-auto pb-20 lg:pb-0" :class="collapsed ? 'px-2' : 'px-4'">
          <ul class="space-y-1" :class="collapsed ? 'border-t-0 pt-2' : 'border-t border-outline-variant pt-4'">
            <li>
              <button
                class="nav-item flex w-full items-center rounded-lg transition-colors"
                :class="[
                  collapsed ? 'justify-center px-0 py-3' : 'gap-3 px-3 py-2',
                  store.theme !== 'light'
                    ? 'text-primary bg-primary-fixed/40 hover:bg-primary-fixed/60'
                    : 'text-on-surface-variant hover:bg-surface-variant dark:hover:bg-surface-container-highest',
                ]"
                @click="onDisplayMode"
              >
                <span class="material-symbols-outlined text-[20px]">{{ themeMeta.icon }}</span>
                <span class="font-body-md text-body-md" :class="collapsed ? 'hidden' : ''">{{ themeMeta.label }}</span>
              </button>
            </li>
            <li v-if="isAdmin && store.showAdminConsole">
              <a
                class="nav-item flex items-center rounded-lg hover:bg-surface-variant dark:hover:bg-surface-container-highest cursor-pointer transition-colors text-on-surface-variant"
                :class="collapsed ? 'justify-center px-0 py-3' : 'gap-3 px-3 py-2'"
                @click="onAdmin"
              >
                <span class="material-symbols-outlined text-[20px]">admin_panel_settings</span>
                <span class="font-body-md text-body-md" :class="collapsed ? 'hidden' : ''">管理后台</span>
              </a>
            </li>
            <li v-if="isAdmin && store.showAdminConsole">
              <a
                class="nav-item flex items-center rounded-lg hover:bg-surface-variant dark:hover:bg-surface-container-highest cursor-pointer transition-colors text-on-surface-variant"
                :class="collapsed ? 'justify-center px-0 py-3' : 'gap-3 px-3 py-2'"
                @click="onAnomalies"
              >
                <span class="material-symbols-outlined text-[20px]">monitor_heart</span>
                <span class="font-body-md text-body-md" :class="collapsed ? 'hidden' : ''">异常数据</span>
              </a>
            </li>
            <li v-if="store.user && store.showPersonalSettings">
              <a
                class="nav-item flex items-center rounded-lg hover:bg-surface-variant dark:hover:bg-surface-container-highest cursor-pointer transition-colors text-on-surface-variant"
                :class="collapsed ? 'justify-center px-0 py-3' : 'gap-3 px-3 py-2'"
                @click="onSettings"
              >
                <span class="material-symbols-outlined text-[20px]">settings</span>
                <span class="font-body-md text-body-md" :class="collapsed ? 'hidden' : ''">个人设置</span>
              </a>
            </li>
            <li v-if="store.user">
              <a
                class="nav-item flex items-center rounded-lg hover:bg-error-container/30 cursor-pointer transition-colors text-error"
                :class="collapsed ? 'justify-center px-0 py-3' : 'gap-3 px-3 py-2'"
                @click="onSignOut"
              >
                <span class="material-symbols-outlined text-[20px]">logout</span>
                <span class="font-body-md text-body-sm" :class="collapsed ? 'hidden' : ''">退出登录</span>
              </a>
            </li>
            <li v-else>
              <a
                class="nav-item flex items-center rounded-lg hover:bg-surface-variant dark:hover:bg-surface-container-highest cursor-pointer transition-colors text-on-surface-variant"
                :class="collapsed ? 'justify-center px-0 py-3' : 'gap-3 px-3 py-2'"
                @click="onLogin"
              >
                <span class="material-symbols-outlined text-[20px]">login</span>
                <span class="font-body-md text-body-sm" :class="collapsed ? 'hidden' : ''">登录</span>
              </a>
            </li>
          </ul>
        </div>
      </div>
    </nav>
  </div>
</template>

<style scoped>
/* 子分类展开/折叠动画（Vue <transition name="child">）：
   - 展开（进入）：位移 + 透明度，缓动用弹簧曲线（平滑无回弹），营造"内容被推出来"的层次感
   - 折叠（离开）：位移归位 + 透明度缓出，避免硬切
   遮罩淡入淡出（name="fade"）同步抽屉。 */
@keyframes childInMove {
  from { transform: translateX(-40px) scale(0.96); }
  to { transform: translateX(0) scale(1); }
}
@keyframes childInMoveRev {
  from { transform: translateX(0); }
  to { transform: translateX(16px); }
}
@keyframes childFade {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes childFadeOut {
  from { opacity: 1; }
  to { opacity: 0; }
}
.child-enter-active {
  animation: childInMove 0.3s cubic-bezier(0.16, 1, 0.3, 1), childFade 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  animation-fill-mode: backwards;
}
.child-leave-active {
  animation: childInMoveRev 0.2s cubic-bezier(0.32, 0.72, 0, 1), childFadeOut 0.2s ease-out;
  animation-fill-mode: both;
}
/* 遮罩淡入淡出 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s cubic-bezier(0.32, 0.72, 0, 1);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
/* 尊重系统"减少动效"偏好（全局已降级为瞬时，这里直接关闭位移动画） */
@media (prefers-reduced-motion: reduce) {
  .child-enter-active,
  .child-leave-active {
    animation: none;
  }
  .fade-enter-active,
  .fade-leave-active {
    transition: none;
  }
}
</style>
