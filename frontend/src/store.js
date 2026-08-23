import { reactive, computed, watch } from 'vue'
import { api } from './api/client'

const LS = {
  token: 'zn_token',
  tokenExpiry: 'zn_token_expiry',
  theme: 'zn_theme',
  network: 'zn_network',
}

// 可切换配色方案（accent palette）。default=沿用 :root 默认紫；
// 其余 5 套来自设计稿配色库，仅改变强调色（按钮/激活态/聚焦环），中性表面保持不变。
// colors 仅用于设置页色板预览。
export const COLOR_SCHEMES = [
  { id: 'default', label: '默认紫', colors: ['#6C5CE7'] },
  { id: 'macaron', label: '棉花糖', colors: ['#E36D9A', '#FFC3A0'] },
  { id: 'sunset', label: '落日', colors: ['#F2762E', '#FFB26B'] },
  { id: 'mint', label: '薄荷海', colors: ['#12A98A', '#5FD0D6'] },
  { id: 'cosmic', label: '星河', colors: ['#5B5BE0', '#C3B1E1'] },
  { id: 'berry', label: '莓果', colors: ['#C13C8A', '#FF8FB1'] },
]

const SEARCH_ENGINE_DEFAULTS = [
  { id: 'local', label: '站内', url: '', enabled: true },
  { id: 'google', label: 'Google', url: 'https://www.google.com/search?q={q}', enabled: true },
  { id: 'baidu', label: '百度', url: 'https://www.baidu.com/s?wd={q}', enabled: true },
  { id: 'bing', label: '必应', url: 'https://www.bing.com/search?q={q}', enabled: true },
  { id: 'ddg', label: 'DuckDuckGo', url: 'https://duckduckgo.com/?q={q}', enabled: true },
  { id: 'brave', label: 'Brave', url: 'https://search.brave.com/search?q={q}', enabled: true },
]

function readToken() {
  const token = sessionStorage.getItem(LS.token) || localStorage.getItem(LS.token)
  if (!token) return ''
  const expiry = localStorage.getItem(LS.tokenExpiry)
  if (expiry && Date.now() > Number(expiry)) {
    sessionStorage.removeItem(LS.token)
    localStorage.removeItem(LS.token)
    localStorage.removeItem(LS.tokenExpiry)
    return ''
  }
  return token
}

export const store = reactive({
  token: readToken(),
  user: null,
  theme: localStorage.getItem(LS.theme) || 'light',
  network: localStorage.getItem(LS.network) || 'auto', // external | internal | auto（auto=按访问者网络自动判断）
  drawerOpen: false, // 移动端侧边栏抽屉
  tree: [], // 分类树（全局）
  linksVersion: 0, // 链接列表变更计数（创建链接后自增，首页监听刷新）
  dragSortEnabled: true, // 站点设置：主页拖拽排序是否开启（PRD item 6）
  searchBoxPos: 'fixed', // 站点设置：搜索框位置 fixed=固定顶部 / scrolling=随内容滚动
  searchEngines: [
    ...SEARCH_ENGINE_DEFAULTS,
  ],
  defaultSearchEngine: 'local',
  searchQuery: '',
  // 站点「显示设置」默认值（作用于首页卡片布局）
  columns: 4, // 桌面端每行列数 2~8
  compactMode: false, // 紧凑模式
  density: 'comfortable', // comfortable | compact 卡片密度
  // 站点级默认值（系统设置中配置），作为无个人偏好的新用户/访客的兜底
  siteNetwork: 'auto', // 默认网络：external | internal | auto（auto=按访问者网络自动判断）
  // 实际生效网络（external | internal）：network='auto' 时由后端按访问者 IP 判断后回填，供 UI 高亮展示
  effectiveNetwork: 'external',
  siteTheme: 'light', // 默认主题：light | dark | system
  // 站点默认配色方案（accent palette）：default=当前紫，其余见 COLOR_SCHEMES
  siteColorScheme: 'default',
  // 当前生效的配色方案（个人覆盖 > 站点默认 > default）。initialize 时由 applyColorScheme 赋值
  colorScheme: 'default',
  // 站点级开关：是否将分类颜色应用到首页图标（分类图标 + 其下链接卡片图标背景）
  showCategoryColors: false,
  allowHomeEdit: true, // 站点设置：是否允许用户自定义主页（添加/拖拽排序）
  lanCidrs: '', // 站点设置：管理员补充的自定义局域网网段（换行/逗号分隔）
  // 首页是否可编辑：派生自「登录 + 站点允许主页编辑(allowHomeEdit)」，见 canEditHome，不再单独维护编辑模式开关

  // 全局链接弹窗（新增/编辑共用 AddLinkModal）：editLink 非空=编辑，null/空=新增
  linkModalOpen: false,
  linkModalEditLink: null,
  // 卡片图标刷新中（按图标获取接口异步拉取时锁定单卡片，避免重复点击）
  iconBusyId: null,
  // 主页侧边栏 / 头像菜单是否显示「个人设置 / 管理后台」入口（系统设置开关）
  showPersonalSettings: true,
  showAdminConsole: true,
  showPasswordLock: true, // 站点设置：是否显示密码锁标识（仅影响显示）
  // 站点品牌（系统设置「站点品牌」自定义）：logo 图片路径 / 名称 / 副标题
  siteName: '云航导航',
  siteSubtitle: '',
  siteLogo: '',
  sidebarCollapsed: false, // 桌面端侧边栏是否折叠
  activeCategoryId: null, // 侧边栏高亮（点击分类跳转后）
  scrollTargetId: null, // 需要滚动到的分类 id
  scrollNonce: 0, // 触发主页滚动到分类区域
  weatherCity: localStorage.getItem('zn_weather_city') || '北京', // 天气城市（个人偏好）
  searchNonce: 0, // 触发搜索框聚焦（移动端底栏"搜索"按钮）
  toast: { text: '', type: 'info', nonce: 0, duration: 0 }, // 全局轻提示
})

export function bumpLinks() {
  store.linksVersion++
}

let toastTimer = null
// 全局轻提示：type = info | success | warn | error
export function showToast(text, type = 'info', duration = 3200) {
  if (!text) return
  store.toast = { text, type, nonce: store.toast.nonce + 1, duration }
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    store.toast = { text: '', type: 'info', nonce: store.toast.nonce, duration: 0 }
  }, duration)
}

export async function loadTree() {
  try {
    const data = await api.categoryTree()
    store.tree = data.tree || []
    // 页面始终有一个选中的分类：默认选中第一个分类的首个子分类（若子分类为空则选中该父分类）
    if (!store.activeCategoryId && store.tree.length) {
      const first = store.tree[0]
      if (first.children && first.children.length) store.activeCategoryId = first.children[0].id
      else store.activeCategoryId = first.id
    }
  } catch (e) {
    store.tree = []
  }
}

export async function loadSettings() {
  try {
    const data = await api.getSettings()
    store.dragSortEnabled = !!data.drag_sort_enabled
    store.searchBoxPos = data.search_box_pos || 'fixed'
    const configuredEngines = Array.isArray(data.search_engines) && data.search_engines.length
      ? data.search_engines.filter((item) => item && item.id)
      : SEARCH_ENGINE_DEFAULTS
    const configuredIds = new Set(configuredEngines.map((item) => item.id))
    // 保留后台返回的自定义项和排序，同时兼容旧后端只返回前三个内置引擎的情况。
    const mergedEngines = [
      ...configuredEngines,
      ...SEARCH_ENGINE_DEFAULTS.filter((item) => !configuredIds.has(item.id)),
    ]
    store.searchEngines = mergedEngines.filter((item) => item.enabled !== false)
    const configuredDefault = String(data.default_engine || 'local').toLowerCase()
    store.defaultSearchEngine = store.searchEngines.some((item) => item.id === configuredDefault && item.id !== 'local')
      ? configuredDefault
      : (store.searchEngines.find((item) => item.id !== 'local')?.id || 'google')
    // 显示设置（首页卡片布局）
    if (typeof data.columns === 'number') store.columns = data.columns
    else if (data.columns) store.columns = Number(data.columns) || 4
    store.compactMode = !!data.compact_mode
    store.density = data.density || 'comfortable'
    // 站点级默认值（无个人偏好时使用）
    store.siteNetwork = data.network || 'auto'
    store.siteTheme = data.theme || 'light'
    store.siteColorScheme = data.color_scheme || 'default'
    store.showCategoryColors = data.show_category_colors === true
    store.allowHomeEdit = data.allow_home_edit !== false
    store.showPersonalSettings = data.show_personal_settings !== false
    store.showAdminConsole = data.show_admin_console !== false
    store.showPasswordLock = data.show_password_lock !== false
    store.lanCidrs = data.lan_cidrs || ''
    // 站点品牌（自定义 logo / 名称 / 副标题）
    store.siteName = data.site_name || '云航导航'
    store.siteSubtitle = data.site_subtitle || ''
    store.siteLogo = data.site_logo || ''
    // 站点 Logo 同步为浏览器标签页图标
    applyFavicon(store.siteLogo)
    // 应用站点默认配色方案（登录用户若设置了个人配色，会在 loadMe→applyUserPrefs 中覆盖）
    applyColorScheme(store.siteColorScheme, false)
    // 同步浏览器标签标题为站点名称
    if (typeof document !== 'undefined') document.title = store.siteName
  } catch (e) {
    store.dragSortEnabled = true
    store.searchBoxPos = 'fixed'
  }
}

export async function loadMe() {
  if (!store.token) return
  try {
    const data = await api.me()
    store.user = data.user
    applyUserPrefs(data.user?.preferences || {})
  } catch (e) {
    // token 失效
    setAuth('', null)
  }
}

// 将后端下发的个人偏好应用到前端运行态（登录/加载时调用，不回写后端）
export function applyUserPrefs(prefs) {
  if (!prefs || typeof prefs !== 'object') return
  // 个人未选择网络时，回退到站点默认网络（系统设置中配置）
  if (prefs.network) setNetwork(prefs.network, false)
  else if (store.siteNetwork) store.network = store.siteNetwork
  if (prefs.theme) applyTheme(prefs.theme, false)
  if (prefs.color_scheme) applyColorScheme(prefs.color_scheme, false)
  else applyColorScheme(store.siteColorScheme, false)
  if (prefs.weather_city) {
    store.weatherCity = prefs.weather_city
    localStorage.setItem('zn_weather_city', prefs.weather_city)
  }
}

// 个人偏好回写后端（fire-and-forget，不阻塞交互）
function persistPref(key, value) {
  if (!store.token) return
  api.updateProfile({ preferences: { [key]: value } }).catch(() => {})
}

export function toggleDrawer() {
  store.drawerOpen = !store.drawerOpen
}
export function closeDrawer() {
  store.drawerOpen = false
}
export function openDrawer() {
  store.drawerOpen = true
}
// 侧边栏折叠（桌面端）/ 抽屉（移动端）切换
export function toggleSidebar() {
  if (typeof window !== 'undefined' && window.innerWidth < 1024) {
    toggleDrawer()
  } else {
    store.sidebarCollapsed = !store.sidebarCollapsed
  }
}

// 点击侧边栏分类：主页始终显示全部卡片，仅滚动跳转到对应分类区域
// 若选中的是子分类，滚动目标取其父分类所在区域（父分类区域包含子分类的链接）
export function scrollToCategory(id) {
  store.activeCategoryId = id
  let target = id
  for (const cat of store.tree) {
    if (cat.children && cat.children.some((c) => c.id === id)) {
      target = cat.id
      break
    }
  }
  store.scrollTargetId = target
  store.scrollNonce++
}

// 天气城市（个人偏好，localStorage 持久化）
export function setWeatherCity(city) {
  store.weatherCity = city
  localStorage.setItem('zn_weather_city', city)
}
export function focusSearch() {
  store.searchNonce++
}

// 跟随系统：监听系统配色偏好变化
let systemMedia = null
let systemHandler = null
function applySystemTheme() {
  if (store.theme !== 'system') return
  const dark = !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches)
  const html = document.documentElement
  if (dark) html.classList.add('dark')
  else html.classList.remove('dark')
}

export function applyTheme(theme, persist = true) {
  store.theme = theme
  localStorage.setItem(LS.theme, theme)
  if (theme === 'system') {
    applySystemTheme()
    if (!systemMedia && typeof window !== 'undefined' && window.matchMedia) {
      systemMedia = window.matchMedia('(prefers-color-scheme: dark)')
      systemHandler = () => applySystemTheme()
      systemMedia.addEventListener('change', systemHandler)
    }
  } else {
    const html = document.documentElement
    if (theme === 'dark') html.classList.add('dark')
    else html.classList.remove('dark')
  }
  if (persist) persistPref('theme', theme)
}

export function toggleTheme() {
  applyTheme(store.theme === 'dark' ? 'light' : 'dark', true)
}

// 配色方案（accent palette）：default 不设置属性，沿用 :root 默认紫；
// 其余通过 <html data-palette="x"> 覆写强调色令牌（style.css 中定义）。
export function applyColorScheme(scheme, persist = true) {
  if (!scheme || scheme === 'default') {
    document.documentElement.removeAttribute('data-palette')
    store.colorScheme = 'default'
  } else {
    document.documentElement.setAttribute('data-palette', scheme)
    store.colorScheme = scheme
  }
  if (persist) persistPref('color_scheme', store.colorScheme)
}

export function setColorScheme(scheme, persist = true) {
  applyColorScheme(scheme, persist)
}

// 站点 Logo 同步为浏览器标签页图标（favicon）：
//  - 图片路径（/uploads、http(s):、data:）→ 直接作为图标
//  - 纯 emoji / 文本 → 生成 SVG data-url favicon（透明底居中显示）
//  - 空 → 移除自定义图标，回退浏览器默认
export function applyFavicon(logo) {
  if (typeof document === 'undefined') return
  let href = ''
  const v = (logo || '').trim()
  if (v) {
    if (/^(\/|https?:\/\/|data:)/.test(v)) {
      href = v
    } else {
      // emoji / 文本：SVG 图标，避免把文字塞进 <img> 破图
      const svg =
        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">` +
        `<text y=".9em" font-size="56" text-anchor="middle" x="50%">${v}</text></svg>`
      href = 'data:image/svg+xml,' + encodeURIComponent(svg)
    }
  }
  let link = document.querySelector('link[rel="icon"]')
  if (!href) {
    if (link) link.remove()
    return
  }
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.appendChild(link)
  }
  link.href = href
}

// 显示模式三态循环：浅色 → 深色 → 跟随系统 → 浅色
const THEME_CYCLE = ['light', 'dark', 'system']
export function cycleTheme() {
  const idx = THEME_CYCLE.indexOf(store.theme)
  const next = THEME_CYCLE[(idx + 1) % THEME_CYCLE.length] || 'light'
  applyTheme(next, true)
}

export function setNetwork(network, persist = true) {
  store.network = network
  localStorage.setItem(LS.network, network)
  if (persist) persistPref('network', network)
}

export function setAuth(token, user, remember = false) {
  store.token = token
  store.user = user
  if (token) {
    sessionStorage.removeItem(LS.token)
    localStorage.removeItem(LS.token)
    ;(remember ? localStorage : sessionStorage).setItem(LS.token, token)
    if (remember) {
      // 记住我：30 天免登录
      localStorage.setItem(LS.tokenExpiry, String(Date.now() + 30 * 24 * 3600 * 1000))
    } else {
      localStorage.removeItem(LS.tokenExpiry)
    }
  } else {
    sessionStorage.removeItem(LS.token)
    localStorage.removeItem(LS.token)
    localStorage.removeItem(LS.tokenExpiry)
  }
}

export function logout() {
  setAuth('', null)
  store.theme = 'light'
  store.network = 'auto'
  store.effectiveNetwork = 'external'
  store.weatherCity = '北京'
  localStorage.removeItem(LS.theme)
  localStorage.removeItem(LS.network)
  localStorage.removeItem('zn_weather_city')
}

// ---------- 首页可编辑状态 + 全局链接弹窗 ----------
// 首页是否可编辑：登录且站点允许主页编辑（后台系统设置「主页是否可以编辑」）时为真。
// 编辑按钮 / 图标刷新 / 拖拽排序均以此为门控，与后台设置合并，不再有独立的编辑模式开关。
export const canEditHome = computed(() => !!store.token && store.allowHomeEdit)
// 打开「新增链接」弹窗（清空编辑目标）
export function openAddLink() {
  store.linkModalEditLink = null
  store.linkModalOpen = true
}
// 打开「编辑链接」弹窗，预填指定链接
export function openEditLink(link) {
  store.linkModalEditLink = link
  store.linkModalOpen = true
}
export function closeLinkModal() {
  store.linkModalOpen = false
  store.linkModalEditLink = null
}

// 模块加载时根据已恢复的主题（含 system）立即应用，避免首屏闪烁
if (typeof window !== 'undefined') {
  applyTheme(store.theme, false)
  applyColorScheme(store.siteColorScheme || 'default', false)
}

// store.theme 变化时实时应用（深浅色/跟随系统），无需刷新
watch(
  () => store.theme,
  (t) => applyTheme(t, false)
)

// store.colorScheme 变化时实时应用配色方案（如设置页直接修改 store）
watch(
  () => store.colorScheme,
  (s) => applyColorScheme(s, false)
)
