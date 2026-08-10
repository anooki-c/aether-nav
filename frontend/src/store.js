import { reactive, watch } from 'vue'
import { api } from './api/client'

const LS = {
  token: 'zn_token',
  tokenExpiry: 'zn_token_expiry',
  theme: 'zn_theme',
  network: 'zn_network',
}

function readToken() {
  const token = localStorage.getItem(LS.token)
  if (!token) return ''
  const expiry = localStorage.getItem(LS.tokenExpiry)
  if (expiry && Date.now() > Number(expiry)) {
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
  network: localStorage.getItem(LS.network) || 'external', // external | internal
  drawerOpen: false, // 移动端侧边栏抽屉
  tree: [], // 分类树（全局）
  linksVersion: 0, // 链接列表变更计数（创建链接后自增，首页监听刷新）
  dragSortEnabled: true, // 站点设置：主页拖拽排序是否开启（PRD item 6）
  searchBoxPos: 'fixed', // 站点设置：搜索框位置 fixed=固定顶部 / scrolling=随内容滚动
  // 站点「显示设置」默认值（作用于首页卡片布局）
  columns: 4, // 桌面端每行列数 2~8
  compactMode: false, // 紧凑模式
  density: 'comfortable', // comfortable | compact 卡片密度
  // 站点级默认值（系统设置中配置），作为无个人偏好的新用户/访客的兜底
  siteNetwork: 'external', // 默认网络：external | internal
  siteTheme: 'light', // 默认主题：light | dark | system
  allowHomeEdit: true, // 站点设置：是否允许用户自定义主页（添加/拖拽排序）
  lanCidrs: '', // 站点设置：管理员补充的自定义局域网网段（换行/逗号分隔）
  // 主页侧边栏 / 头像菜单是否显示「个人设置 / 管理后台」入口（系统设置开关）
  showPersonalSettings: true,
  showAdminConsole: true,
  showPasswordLock: true, // 站点设置：是否显示密码锁标识（仅影响显示）
  sidebarCollapsed: false, // 桌面端侧边栏是否折叠
  activeCategoryId: null, // 侧边栏高亮（点击分类跳转后）
  scrollTargetId: null, // 需要滚动到的分类 id
  scrollNonce: 0, // 触发主页滚动到分类区域
  weatherCity: localStorage.getItem('zn_weather_city') || '北京', // 天气城市（个人偏好）
  searchNonce: 0, // 触发搜索框聚焦（移动端底栏"搜索"按钮）
  toast: { text: '', type: 'info', nonce: 0 }, // 全局轻提示
})

export function bumpLinks() {
  store.linksVersion++
}

let toastTimer = null
// 全局轻提示：type = info | success | warn | error
export function showToast(text, type = 'info', duration = 3200) {
  if (!text) return
  store.toast = { text, type, nonce: store.toast.nonce + 1 }
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    store.toast = { text: '', type: 'info', nonce: store.toast.nonce }
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
    // 显示设置（首页卡片布局）
    if (typeof data.columns === 'number') store.columns = data.columns
    else if (data.columns) store.columns = Number(data.columns) || 4
    store.compactMode = !!data.compact_mode
    store.density = data.density || 'comfortable'
    // 站点级默认值（无个人偏好时使用）
    store.siteNetwork = data.network || 'external'
    store.siteTheme = data.theme || 'light'
    store.allowHomeEdit = data.allow_home_edit !== false
    store.showPersonalSettings = data.show_personal_settings !== false
    store.showAdminConsole = data.show_admin_console !== false
    store.showPasswordLock = data.show_password_lock !== false
    store.lanCidrs = data.lan_cidrs || ''
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
    localStorage.setItem(LS.token, token)
    if (remember) {
      // 记住我：30 天免登录
      localStorage.setItem(LS.tokenExpiry, String(Date.now() + 30 * 24 * 3600 * 1000))
    } else {
      localStorage.removeItem(LS.tokenExpiry)
    }
  } else {
    localStorage.removeItem(LS.token)
    localStorage.removeItem(LS.tokenExpiry)
  }
}

export function logout() {
  setAuth('', null)
}

// 模块加载时根据已恢复的主题（含 system）立即应用，避免首屏闪烁
if (typeof window !== 'undefined') {
  applyTheme(store.theme, false)
}

// store.theme 变化时实时应用（深浅色/跟随系统），无需刷新
watch(
  () => store.theme,
  (t) => applyTheme(t, false)
)
