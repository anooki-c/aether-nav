<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { store, bumpLinks, loadSettings, showToast, COLOR_SCHEMES } from '../store'
import { api } from '../api/client'
import AddLinkModal from '../components/AddLinkModal.vue'
import PermissionEditModal from '../components/PermissionEditModal.vue'
import LinkPermissionMatrixModal from '../components/LinkPermissionMatrixModal.vue'
import StatsView from './StatsView.vue'
import MonitorView from './MonitorView.vue'
import EntityIcon from '../components/EntityIcon.vue'
import LinkCard from '../components/LinkCard.vue'
import UserMenu from '../components/UserMenu.vue'
import IconPicker from '../components/IconPicker.vue'
import PasswordModal from '../components/PasswordModal.vue'
import { getLinkIcon } from '../utils/linkIcon'
import { parseUrlScheme, buildUrl } from '../utils/urlScheme'

const router = useRouter()
const tab = ref('links') // links | categories | users | settings
const msg = ref('')
// 移动端后台侧边导航抽屉（md 以下 aside 隐藏，改用抽屉）
const adminNavOpen = ref(false)
function switchTab(k) {
  tab.value = k
  adminNavOpen.value = false
}

const isAdmin = computed(() => store.user && store.user.role === 'admin')
// 鉴权是否已出结果：有 token 但 user 还没拉回来时视为「加载中」，
// 避免 F5 刷新瞬间闪现「仅管理员可访问」
const authPending = computed(() => !!store.token && !store.user)

// ---------- 版本与更新检测 ----------
const versionInfo = ref(null)
const checking = ref(false)
const updateStatus = ref(null) // { update_available, latest_commit, error, ... }
async function loadVersion() {
  try {
    versionInfo.value = await api.version()
  } catch (e) {
    versionInfo.value = { source: 'dev', commit: null }
  }
}
async function checkUpdate() {
  checking.value = true
  updateStatus.value = null
  try {
    updateStatus.value = await api.checkUpdate()
  } catch (e) {
    updateStatus.value = { error: (e && e.message) || '检测失败' }
  } finally {
    checking.value = false
  }
}

// ---------- 链接管理 ----------
const adminLinkList = ref([])
// 分类筛选：两级联动（父 → 子）
const filterParent = ref('')
const filterChild = ref('')
// 添加人筛选（原“网络”改为“添加人”）
const filterOwner = ref('')
// 是否设置密码筛选
const filterPwd = ref('') // '' | 'set' | 'unset'
// 权限筛选
const filterPerm = ref('') // '' | 'all' | 'registered' | 'admin' | 'self'
const linkSubTab = ref('all') // all | archived
const linksPage = ref(1)
const linksPageSize = ref(10)
const showAdd = ref(false)

// 密码设置/修改弹窗
const pwdModal = ref(null) // { mode: 'set' | 'update', link }
const pwdForm = ref({ oldPw: '', npw1: '', npw2: '' })
const pwdError = ref('')

// 编辑弹窗
const showEdit = ref(false)
const editTarget = ref(null)
// 编辑弹窗是否「只读模式」：非链接添加人（且非管理员）仅可设访问密码与是否在主页显示
const editReadonly = computed(() => !!editTarget.value && !editTarget.value.can_edit)
const editForm = ref({ title: '', url_external: '', url_internal: '', category_id: null, icon: '', description: '', permission: 'public', enablePwd: false, pwdNew: '', pwdConfirm: '' })
const editPwdError = ref('')
const editIconBusy = ref(false)
const editIconMsg = ref('')
const editIconWarn = ref(false)

// 编辑弹窗：URL scheme（默认 http，SSL 勾选切换 https；输入框只填 host/path）
const editSslExternal = ref(false)
const editExtBody = ref('')
const editSslInternal = ref(false)
const editIntBody = ref('')
watch([editExtBody, editSslExternal], () => {
  if (editForm.value) editForm.value.url_external = buildUrl(editSslExternal.value, editExtBody.value)
})
watch([editIntBody, editSslInternal], () => {
  if (editForm.value) editForm.value.url_internal = buildUrl(editSslInternal.value, editIntBody.value)
})

// 编辑弹窗：两级联动分类
const editCatParent = ref('')
const editCatChildren = computed(() => {
  if (!editCatParent.value) return []
  const p = store.tree.find((x) => x.id === Number(editCatParent.value))
  return p ? (p.children || []).map((c) => ({ id: c.id, name: c.name })) : []
})
watch(editCatParent, () => {
  if (editForm.value && editCatChildren.value.length > 0 && !editCatChildren.value.some(c => c.id === editForm.value.category_id)) {
    // 父切换后子不在列表中，清空子选择
  }
})

// 编辑弹窗：预览数据（直接复用主页 LinkCard 的样式）
const editCardPreview = computed(() => {
  const f = editForm.value
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

// ---------- 用户权限编辑弹窗 (edit_permissions) ----------
const permOpen = ref(false)
const permUser = ref(null)
function openPerm(u) {
  permUser.value = u
  permOpen.value = true
}

// ---------- 链接维度权限矩阵弹窗 ----------
const matrixOpen = ref(false)
const matrixLink = ref(null)
function openMatrix(l) {
  matrixLink.value = l
  matrixOpen.value = true
}

async function loadLinks() {
  try {
    const d = await api.adminLinks()
    adminLinkList.value = d.links.map((l) => ({ ...l, busy: false }))
  } catch (e) {
    msg.value = e.message
  }
}
const filteredLinks = computed(() => {
  return adminLinkList.value.filter((l) => {
    const isArchived = !l.is_active
    if (linkSubTab.value === 'archived' && !isArchived) return false
    if (linkSubTab.value === 'all' && isArchived) return false
    // 两级联动分类筛选
    if (filterParent.value) {
      if (filterChild.value) {
        if (l.category_id !== Number(filterChild.value)) return false
      } else if (l.category_id !== Number(filterParent.value) && catParentMap.value.get(l.category_id) !== Number(filterParent.value)) {
        return false
      }
    }
    // 添加人筛选
    if (filterOwner.value && l.owner_id !== Number(filterOwner.value)) return false
    // 是否设置密码筛选
    if (filterPwd.value === 'set' && !l.has_password) return false
    if (filterPwd.value === 'unset' && l.has_password) return false
    // 权限筛选
    if (filterPerm.value && l.permission !== filterPerm.value) return false
    return true
  })
})

// 父分类 → 子分类 映射（用于两级联动筛选）
const catParentMap = computed(() => {
  const m = new Map()
  for (const p of store.tree) {
    for (const c of (p.children || [])) m.set(c.id, p.id)
  }
  return m
})
const categoryParents = computed(() => store.tree.map((p) => ({ id: p.id, name: p.name })))
const categoryChildren = computed(() => {
  if (!filterParent.value) return []
  const p = store.tree.find((x) => x.id === Number(filterParent.value))
  return p ? (p.children || []).map((c) => ({ id: c.id, name: c.name })) : []
})
// 添加人列表（去重）
const linkOwners = computed(() => {
  const m = new Map()
  for (const l of adminLinkList.value) {
    if (l.owner_id != null) m.set(l.owner_id, l.owner_name)
  }
  return [...m.entries()].map(([id, name]) => ({ id, name }))
})
// 编辑弹窗用的扁平分类列表
const allCategoriesFlat = computed(() => {
  const out = []
  for (const p of store.tree) {
    out.push({ id: p.id, name: p.name, indent: 0 })
    for (const c of (p.children || [])) out.push({ id: c.id, name: c.name, indent: 1 })
  }
  return out
})

// ---------- 密码设置 / 修改 ----------
function openSetPwd(l) {
  pwdModal.value = { mode: 'set', link: l }
  pwdForm.value = { oldPw: '', npw1: '', npw2: '' }
  pwdError.value = ''
}
function openUpdatePwd(l) {
  pwdModal.value = { mode: 'update', link: l }
  pwdForm.value = { oldPw: '', npw1: '', npw2: '' }
  pwdError.value = ''
}
async function confirmPwd() {
  const { mode, link } = pwdModal.value
  const { oldPw, npw1, npw2 } = pwdForm.value
  try {
    if (mode === 'set') {
      if (!npw1) { pwdError.value = '请输入密码'; return }
      if (npw1 !== npw2) { pwdError.value = '两次输入的密码不一致'; return }
      await api.updateLink(link.id, { password: npw1 })
    } else {
      // 修改：需先验证旧密码
      if (!oldPw) { pwdError.value = '请输入旧密码'; return }
      const r = await api.unlock(link.id, oldPw)
      if (!r.ok) { pwdError.value = '旧密码错误'; return }
      if (!npw1) {
        // 新密码留空 = 取消（移除）密码
        await api.updateLink(link.id, { password: '' })
      } else {
        if (npw1 !== npw2) { pwdError.value = '两次输入的密码不一致'; return }
        await api.updateLink(link.id, { password: npw1 })
      }
    }
    pwdModal.value = null
    await loadLinks()
    bumpLinks()
    msg.value = '密码已更新'
  } catch (e) {
    pwdError.value = e.message
  }
}

// ---------- 链接管理：点击外/内网 URL 打开 ----------
// 有密码的链接先弹密码框验证，再新标签页打开；无密码直接打开（带点击埋点）。
const adminPwdOpen = ref(false)
const adminPwdLink = ref(null)
function openLinkUrl(l, which) {
  const url = which === 'external' ? (l.url_external || '') : (l.url_internal || '')
  if (!url) return
  if (l.has_password) {
    adminPwdLink.value = { ...l, url }
    adminPwdOpen.value = true
  } else {
    if (l.id) api.trackClick(l.id).catch(() => {})
    window.open(url, '_blank')
  }
}

// ---------- 权限修改（仅自己添加的链接） ----------
async function changePerm(l, val) {
  try {
    await api.updateLink(l.id, { permission: val })
    await loadLinks()
    bumpLinks()
    msg.value = '权限已更新'
  } catch (e) { msg.value = e.message }
}

// 主页显示开关：控制该链接是否显示在当前登录用户自己的主页（默认显示）
async function toggleHome(l) {
  const next = !l.show_on_home
  l.show_on_home = next // 乐观更新
  try {
    await api.setVisibility(l.id, next)
  } catch (e) {
    l.show_on_home = !next // 失败回滚
    msg.value = e.message
  }
}

// ---------- 编辑链接 ----------
function openEdit(l) {
  editTarget.value = l
  // 确定分类的父级
  let parentId = ''
  for (const p of store.tree) {
    if (p.id === l.category_id) { parentId = String(p.id); break }
    for (const c of (p.children || [])) { if (c.id === l.category_id) { parentId = String(p.id); break } }
    if (parentId) break
  }
  editCatParent.value = parentId
  editForm.value = {
    title: l.title,
    url_external: l.url_external || '',
    url_internal: l.url_internal || '',
    category_id: l.category_id,
    icon: l.icon || '',
    description: l.description || '',
    permission: l.permission || 'admin',
    enablePwd: !!l.has_password,
    pwdNew: '',
    pwdConfirm: '',
  }
  editPwdError.value = ''
  editIconMsg.value = ''
  editIconProviders.value = []
  editSelectedProvider.value = 'direct'
  editFaviconCustomUrl.value = ''
  // 默认 http；把完整 URL 拆成 {ssl, body} 供输入框使用
  const e = parseUrlScheme(l.url_external || '')
  const i = parseUrlScheme(l.url_internal || '')
  editSslExternal.value = e.ssl
  editExtBody.value = e.body
  editSslInternal.value = i.ssl
  editIntBody.value = i.body
  loadEditIconProviders()
  showEdit.value = true
}

// 编辑弹窗：自动解析图标地址（优先内网 URL）；只填入输入框，保存时才下载落地
async function editAutoFetchIcon() {
  const url = editForm.value.url_internal.trim() || editForm.value.url_external.trim()
  if (!url) { editIconMsg.value = '请先填写 URL 再自动获取'; return }
  editIconBusy.value = true; editIconMsg.value = ''; editIconWarn.value = false
  try {
    const data = await api.resolveIcon(
      url,
      editSelectedProvider.value,
      editSelectedProvider.value === 'custom' ? editFaviconCustomUrl.value : ''
    )
    editForm.value.icon = data.icon_url
    if (data.warning) { editIconWarn.value = true; editIconMsg.value = data.warning }
    else editIconMsg.value = '已填入图标地址，保存时下载到本地'
  } catch (e) { editIconMsg.value = e.message || '解析失败' }
  finally { editIconBusy.value = false }
}

// 编辑弹窗：选择本地图片（浏览器拿不到真实磁盘路径，先上传取得可用路径再填入输入框）
async function editOnUpload(e) {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  editIconBusy.value = true; editIconMsg.value = ''
  try {
    const data = await api.uploadIcon(file)
    editForm.value.icon = data.path
    editIconMsg.value = '已选择文件，路径已填入输入框'
  } catch (err) { editIconMsg.value = err.message || '上传失败' }
  finally { editIconBusy.value = false; e.target.value = '' }
}
async function saveEdit() {
  const f = editForm.value
  if (!f.title.trim()) { msg.value = '请填写链接名称'; return }
  // 每用户独立密码：仅当开启且填写新密码时才设置；关闭且原先有密码时清除
  let payloadPassword = undefined
  if (f.enablePwd) {
    if (f.pwdNew) {
      if (f.pwdNew !== f.pwdConfirm) { editPwdError.value = '两次输入的密码不一致'; return }
      if (f.pwdNew.length < 4) { editPwdError.value = '密码至少 4 位'; return }
      payloadPassword = f.pwdNew
    }
    // 开启但留空新密码 → 保留原有密码（不传 password）
  } else if (editTarget.value && editTarget.value.has_password) {
    payloadPassword = '' // 关闭 → 清除当前用户的密码
  }
  try {
    const payload = {
      title: f.title,
      url_external: f.url_external || null,
      url_internal: f.url_internal || null,
      category_id: f.category_id,
      icon: f.icon || '',
      description: f.description || '',
      permission: f.permission,
    }
    if (payloadPassword !== undefined) payload.password = payloadPassword
    const res = await api.updateLink(editTarget.value.id, payload)
    showEdit.value = false
    await loadLinks()
    bumpLinks()
    // 图标落地失败：链接已更新，仅图标回退为默认
    if (res && res.icon_error) { msg.value = res.icon_error; showToast(res.icon_error, 'warn') }
    else msg.value = '链接已更新'
  } catch (e) { msg.value = e.message }
}
const linksTotalPages = computed(() => Math.max(1, Math.ceil(filteredLinks.value.length / linksPageSize.value)))
const pagedLinks = computed(() => {
  const start = (linksPage.value - 1) * linksPageSize.value
  return filteredLinks.value.slice(start, start + linksPageSize.value)
})
function pageList(current, total) {
  const pages = []
  if (total <= 5) {
    for (let i = 1; i <= total; i++) pages.push(i)
    return pages
  }
  pages.push(1)
  const start = Math.max(2, current - 1)
  const end = Math.min(total - 1, current + 1)
  if (start > 2) pages.push('...')
  for (let i = start; i <= end; i++) pages.push(i)
  if (end < total - 1) pages.push('...')
  pages.push(total)
  return pages
}
const linksPages = computed(() => pageList(linksPage.value, linksTotalPages.value))
function goLinksPage(p) {
  if (p === '...' || p < 1 || p > linksTotalPages.value) return
  linksPage.value = p
}
async function delLink(l) {
  if (!confirm(`确定删除链接「${l.title}」？`)) return
  await api.deleteLink(l.id)
  await loadLinks()
  bumpLinks()
  msg.value = '链接已删除'
}

// ---------- 分类管理 ----------
const expanded = ref({})
const selectedCat = ref(null)
// 当前选中的分类节点（在树中定位，含 owner_id / archived 等字段），用于权限判断
const selectedCatNode = computed(() => {
  if (!selectedCat.value) return null
  for (const p of store.tree) {
    if (p.id === selectedCat.value) return p
    const c = (p.children || []).find((x) => x.id === selectedCat.value)
    if (c) return c
  }
  return null
})
// 编辑分类时，上级分类下拉排除自身（防止把自己设为自己的父级）
const roleOptions = [
  { value: 'admin', label: '管理员' },
  { value: 'member', label: '成员' },
  { value: 'guest', label: '访客' },
]
// 分类权限（与链接权限一致：all/registered/admin/self）
const PERM_OPTIONS = [
  { value: 'all', label: '🌐 所有人 — 所有访客均可访问' },
  { value: 'registered', label: '👤 注册用户 — 登录后可见' },
  { value: 'admin', label: '🛡️ 管理员 — 仅管理员与所有者可见' },
  { value: 'self', label: '🔒 仅自己 — 只有你能看到' },
]
function parseRoles(s) {
  return (s || '').split(',').map((x) => x.trim()).filter(Boolean)
}
// 父分类权限变更级联确认（item 8）
const showPermCascade = ref(false)
const permCascadeCount = ref(0)
const catFormOrigPerm = ref(null)

const catParentOptions = computed(() =>
  store.tree.filter((p) => p.id !== selectedCat.value)
)
const catForm = ref({ id: null, name: '', parent_id: null, icon: '', color: '#6C5CE7', visible: true, archived: false, description: '', permission: 'registered', allowed_roles: [] })

// 当前用户能否编辑某个分类：仅管理员可编辑/删除；普通成员只能「添加」分类，不能修改（含自己创建的）
function canEditCat(c) {
  return isAdmin.value
}
function selectCat(c) {
  if (!canEditCat(c)) return
  selectedCat.value = c.id
  catForm.value = { id: c.id, name: c.name, parent_id: c.parent_id || null, icon: c.icon || '', color: c.color || '#6C5CE7', visible: c.visible !== false, archived: c.archived === true, description: c.description || '', permission: c.permission || 'all', allowed_roles: parseRoles(c.allowed_roles) }
  catFormOrigPerm.value = c.permission || 'all'
}
function newCatMode() {
  selectedCat.value = null
  catForm.value = { id: null, name: '', parent_id: null, icon: '', color: '#6C5CE7', visible: true, archived: false, description: '', permission: 'registered', allowed_roles: [] }
  catFormOrigPerm.value = null
}
// 新建子分类时，若未手动改过权限，则继承父分类权限（item 8：子分类没有设置则继承父分类）
watch(
  () => catForm.value.parent_id,
  (pid) => {
    if (!selectedCat.value && pid) {
      const p = store.tree.find((x) => x.id === Number(pid))
      if (p && p.permission) catForm.value.permission = p.permission
    }
  }
)
async function restoreCat(c) {
  if (!canEditCat(c)) return
  try {
    await api.updateCategory(c.id, { archived: false })
    const { loadTree } = await import('../store')
    await loadTree()
    showToast('已移出回收站（恢复）', 'success')
  } catch (e) { msg.value = e.message }
}
async function restoreCurrent() {
  if (!selectedCat.value) return
  let node = store.tree.find((p) => p.id === selectedCat.value)
  if (!node) return
  if (!node.children) node = (node.children || []).find((c) => c.id === selectedCat.value) || node
  await restoreCat(node)
  catForm.value.archived = false
}
async function saveCat() {
  if (!catForm.value.name.trim()) { msg.value = '请填写分类名称'; return }
  // 编辑态 + 管理员 + 父分类存在子分类：若权限被改动且子分类权限与拟设值不同，
  // 需用户确认「保持子分类现状」还是「同时应用到所有子分类」（item 8）
  if (selectedCat.value && isAdmin.value) {
    const node = selectedCatNode.value
    const children = (node && node.children) || []
    const newPerm = catForm.value.permission || 'registered'
    const permChanged = (catFormOrigPerm.value || 'all') !== newPerm
    const childDiffers = children.some((c) => (c.permission || 'all') !== newPerm)
    if (children.length && permChanged && childDiffers) {
      permCascadeCount.value = children.length
      showPermCascade.value = true
      return
    }
  }
  await doSaveCat(false)
}

// cascade=true 时，父分类权限变更同步应用到全部子分类
async function doSaveCat(cascade) {
  const payload = {
    name: catForm.value.name,
    icon: catForm.value.icon,
    color: catForm.value.color || '#6C5CE7',
    parent_id: catForm.value.parent_id || null,
    description: catForm.value.description,
    archived: catForm.value.archived === true,
  }
  // 「主页显示」与「分类权限」仅管理员可设置；非管理员不提交（后端也强制忽略）
  if (isAdmin.value) {
    payload.visible = catForm.value.visible !== false
    payload.permission = catForm.value.permission || 'registered'
  }
  if (selectedCat.value) {
    await api.updateCategory(catForm.value.id, payload)
    if (cascade) {
      const node = selectedCatNode.value
      const children = (node && node.children) || []
      for (const c of children) {
        await api.updateCategory(c.id, { permission: catForm.value.permission || 'registered' })
      }
    }
    msg.value = '分类已保存'
  } else {
    await api.createCategory(payload)
    msg.value = '分类已创建'
  }
  const { loadTree } = await import('../store')
  await loadTree()
  await loadLinks()
}
// 主页显示开关：切换为「不显示」时提醒用户（对所有用户生效）
function toggleCatVisible(next) {
  if (next === false && catForm.value.visible !== false) {
    if (!confirm('设为不显示后，所有用户的首页与侧边栏都将看不到该分类及其下的全部链接，确定隐藏？')) {
      return // 用户取消，保持显示
    }
    showToast('该分类已设为不在主页显示（对所有用户生效），保存后即时生效', 'warn')
  }
  catForm.value.visible = next
}
// ---------- 删除分类：处理旗下链接与子分类 ----------
const showCatDel = ref(false)
const catDelStats = ref({ link_count: 0, child_count: 0 })
const catDelMode = ref('archive') // archive（默认：移到回收站）| move | delete
const catDelMoveTo = ref(null)
// 可作为「移动目标」的分类（排除自身及其直接子分类）
const catDelMoveOptions = computed(() => {
  const self = selectedCat.value
  const node = store.tree.find((p) => p.id === self)
  const childIds = new Set(((node && node.children) || []).map((c) => c.id))
  const out = []
  for (const p of store.tree) {
    if (p.id === self) continue
    if (childIds.has(p.id)) continue
    out.push({ id: p.id, name: p.name, indent: 0 })
    for (const c of (p.children || [])) {
      if (c.id === self) continue
      if (childIds.has(c.id)) continue
      out.push({ id: c.id, name: '　└ ' + c.name, indent: 1 })
    }
  }
  return out
})
function openCatDel() {
  if (!selectedCat.value) return
  const node = store.tree.find((p) => p.id === selectedCat.value)
  catDelStats.value = {
    link_count: (node && node.link_count) || 0,
    child_count: (node && node.children ? node.children.length : 0),
  }
  // 默认选中「移动到回收站（归档）」
  catDelMode.value = 'archive'
  catDelMoveTo.value = catDelMoveOptions.value[0] ? catDelMoveOptions.value[0].id : null
  showCatDel.value = true
}
async function confirmCatDel() {
  const id = selectedCat.value
  try {
    if (catDelMode.value === 'archive') {
      await api.deleteCategory(id, { archive: true })
      showToast('已移动到回收站（归档），可在分类目录中恢复', 'success')
    } else if (catDelMode.value === 'move') {
      const r = await api.deleteCategory(id, { move_to: catDelMoveTo.value })
      const moved = (r && r.moved_links) || 0
      showToast(`已删除分类，旗下 ${moved} 个链接已移动到目标分类`, 'success')
    } else {
      const r = await api.deleteCategory(id, { delete_links: true })
      const del = (r && r.deleted_links) || 0
      showToast(`已彻底删除分类及其 ${del} 个链接`, 'success')
    }
    showCatDel.value = false
    const { loadTree } = await import('../store')
    await loadTree()
    newCatMode()
  } catch (e) { msg.value = e.message }
}

// ---------- 用户管理 ----------
const users = ref([])
const userSubTab = ref('all') // all | admin | online | banned
const usersPage = ref(1)
const usersPageSize = ref(9)
const showUserModal = ref(false)
const userForm = ref({ display_name: '', username: '', email: '', password: '', role: 'member' })
async function loadUsers() {
  try {
    const d = await api.adminUsers()
    users.value = d.users
  } catch (e) { msg.value = e.message }
}
async function changeRole(u, role) {
  await api.updateUser(u.id, { role })
  msg.value = `已更新 ${u.username} 的角色`
}
function openUserModal() {
  userForm.value = { display_name: '', username: '', email: '', password: '', role: 'member' }
  showUserModal.value = true
}
async function saveUser() {
  try {
    await api.createUser({
      username: userForm.value.username,
      password: userForm.value.password,
      display_name: userForm.value.display_name,
      role: userForm.value.role,
    })
    showUserModal.value = false
    await loadUsers()
    msg.value = '用户已创建'
  } catch (e) { msg.value = e.message }
}

const filteredUsers = computed(() => {
  return users.value.filter((u) => {
    if (userSubTab.value === 'admin') return u.role === 'admin'
    if (userSubTab.value === 'online') return !!u.online
    if (userSubTab.value === 'banned') return !!u.banned
    return true
  })
})
const userCounts = computed(() => ({
  all: users.value.length,
  admin: users.value.filter((u) => u.role === 'admin').length,
  online: users.value.filter((u) => u.online).length,
  banned: users.value.filter((u) => u.banned).length,
}))
const usersTotalPages = computed(() => Math.max(1, Math.ceil(filteredUsers.value.length / usersPageSize.value)))
const pagedUsers = computed(() => {
  const start = (usersPage.value - 1) * usersPageSize.value
  return filteredUsers.value.slice(start, start + usersPageSize.value)
})
const usersPages = computed(() => pageList(usersPage.value, usersTotalPages.value))
function goUsersPage(p) {
  if (p === '...' || p < 1 || p > usersTotalPages.value) return
  usersPage.value = p
}

// 真实时间格式化（created_at / last_seen）
function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// ---------- 重设密码（管理员） ----------
const showResetPwd = ref(false)
const resetPwdUser = ref(null)
const resetPwdForm = ref({ new_password: '' })
const resetPwdResult = ref('')
function openResetPwd(u) {
  resetPwdUser.value = u
  resetPwdForm.value = { new_password: '' }
  resetPwdResult.value = ''
  showResetPwd.value = true
}
function genRandomPwd() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789'
  let s = ''
  for (let i = 0; i < 12; i++) s += chars[Math.floor(Math.random() * chars.length)]
  resetPwdForm.value.new_password = s
}
async function confirmResetPwd() {
  if (!resetPwdUser.value) return
  try {
    const r = await api.resetUserPassword(resetPwdUser.value.id, resetPwdForm.value.new_password)
    resetPwdResult.value = r.new_password || '(已重置)'
    showToast(`已重设 ${resetPwdUser.value.username} 的密码`, 'success')
    await loadUsers()
  } catch (e) { msg.value = e.message }
}

// ---------- 禁用 / 启用用户 ----------
const banConfirmUser = ref(null)
function toggleBan(u) {
  if (u.username === 'admin') { showToast('不能禁用管理员账号', 'warn'); return }
  if (u.is_active !== false) {
    banConfirmUser.value = u // 打开应用内确认弹窗（避免原生 confirm 在预览环境被拦截）
  } else {
    enableUser(u)
  }
}
async function enableUser(u) {
  try {
    await api.updateUser(u.id, { is_active: true })
    await loadUsers()
    showToast(`已启用 ${u.username}`, 'success')
  } catch (e) { msg.value = e.message }
}
async function confirmBan() {
  const u = banConfirmUser.value
  banConfirmUser.value = null
  if (!u) return
  try {
    await api.updateUser(u.id, { is_active: false })
    await loadUsers()
    showToast(`已禁用 ${u.username}`, 'success')
  } catch (e) { msg.value = e.message }
}

// ---------- 系统设置 ----------
const defaultEngine = ref('Google')
const openNewTab = ref(true)
const density = ref('comfortable')
const searchBoxPos = ref('fixed') // fixed | scrolling
const columns = ref(4)
const compactMode = ref(false)
const allowHomeEdit = ref(true)

// 账号与安全
const allowRegister = ref(true)
const defaultRole = ref('member')
const tokenMaxAgeHours = ref(168)
const logRetentionDays = ref(90)

// 站点默认网络（系统设置中配置，作为新用户/未选择用户的默认）
const defaultNetwork = ref('external')

// 主页侧边栏 / 头像菜单入口开关
const showPersonalSettings = ref(true)
const showAdminConsole = ref(true)
const showPasswordLock = ref(true)
// 站点默认配色方案 + 分类颜色开关
const siteColorScheme = ref('default')
const colorSchemeOpen = ref(false)
const showCategoryColors = ref(false)

// 局域网网段（快速添加时用于识别内网地址，缺省走 RFC1918 私有段）
const lanCidrs = ref('')
// 站点品牌（第三列「站点品牌」分组）：logo / 名称 / 副标题
const siteName = ref('云航导航')
const siteSubtitle = ref('')
const siteLogo = ref('')
const logoUploading = ref(false)

// ---------- 编辑链接弹窗：图标接口选择（下拉 + 获取） ----------
const editIconProviders = ref([])        // /api/icon/providers 返回的清单
const editSelectedProvider = ref('direct')
const editFaviconCustomUrl = ref('')      // 自定义接口模板（仅 custom 时）

// 拉取图标接口清单，填充编辑弹窗下拉框
async function loadEditIconProviders() {
  try {
    const data = await api.getIconProviders()
    editIconProviders.value = data.providers || []
    if (data.current) editSelectedProvider.value = data.current
  } catch (e) { /* 清单拉取失败不阻塞弹窗 */ }
}

// 图标选择弹窗（分类 / 链接）：点击图标后填入对应字段
const catIconPickerOpen = ref(false)
const editIconPickerOpen = ref(false)
// 分类颜色预设色板
const catColorPresets = ['#6C5CE7', '#E36D9A', '#F2762E', '#12A98A', '#5B5BE0', '#C13C8A', '#0EA5E9', '#F59E0B', '#22C55E', '#EF4444']
function onPickCatIcon(name) {
  catForm.value.icon = name
}
function onPickEditIcon(name) {
  editForm.value.icon = name
}

// 进入设置页时回填已保存的站点设置（否则永远显示默认值）
async function fetchSettings() {
  try {
    const data = await api.getSettings()
    defaultEngine.value = data.default_engine || 'Google'
    openNewTab.value = data.open_new_tab !== false
    density.value = data.density || 'comfortable'
    searchBoxPos.value = data.search_box_pos || 'fixed'
    columns.value = Number(data.columns) || 4
    compactMode.value = !!data.compact_mode
    allowHomeEdit.value = data.allow_home_edit !== false
    allowRegister.value = data.allow_register !== false
    defaultRole.value = data.default_role || 'member'
    tokenMaxAgeHours.value = Number(data.token_max_age_hours) || 168
    logRetentionDays.value = Number(data.log_retention_days) || 90
    defaultNetwork.value = data.network || 'external'
    showPersonalSettings.value = data.show_personal_settings !== false
    showAdminConsole.value = data.show_admin_console !== false
    showPasswordLock.value = data.show_password_lock !== false
    siteColorScheme.value = data.color_scheme || 'default'
    showCategoryColors.value = data.show_category_colors === true
    lanCidrs.value = data.lan_cidrs || ''
    siteName.value = data.site_name || '云航导航'
    siteSubtitle.value = data.site_subtitle || ''
    siteLogo.value = data.site_logo || ''
  } catch (e) {
    // 读取失败时保留默认值
  }
}

async function saveSettings() {
  try {
    await api.updateSettings({
      default_engine: defaultEngine.value,
      open_new_tab: openNewTab.value,
      theme: store.theme,
      density: density.value,
      search_box_pos: searchBoxPos.value,
      columns: columns.value,
      compact_mode: compactMode.value,
      allow_home_edit: allowHomeEdit.value,
      allow_register: allowRegister.value,
      default_role: defaultRole.value,
      token_max_age_hours: Number(tokenMaxAgeHours.value) || 168,
      log_retention_days: Number(logRetentionDays.value) || 90,
      network: defaultNetwork.value,
      show_personal_settings: showPersonalSettings.value,
      show_admin_console: showAdminConsole.value,
      show_password_lock: showPasswordLock.value,
      color_scheme: siteColorScheme.value,
      show_category_colors: showCategoryColors.value,
      lan_cidrs: lanCidrs.value,
      site_name: siteName.value,
      site_subtitle: siteSubtitle.value,
      site_logo: siteLogo.value,
    })
    // 同步到全局 store，前台无需刷新即可生效（如搜索框位置）
    await loadSettings()
    msg.value = '设置已保存'
  } catch (e) { msg.value = e.message }
}

// 站点 logo 上传：复用 /api/upload/icon，返回本地路径写回 site_logo
async function onLogoUpload(e) {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  logoUploading.value = true
  try {
    const data = await api.uploadIcon(file)
    siteLogo.value = data.path
    msg.value = 'Logo 已上传，记得点「保存更改」生效'
  } catch (err) {
    msg.value = err.message || 'Logo 上传失败'
  } finally {
    logoUploading.value = false
    e.target.value = ''
  }
}

// ---------- 权限审计日志 ----------
const auditLogs = ref([])
const auditTotal = ref(0)
const auditPage = ref(1)
const auditPer = ref(50)
const auditLoading = ref(false)
const auditFilter = ref('') // '' 全部
const auditActions = [
  { k: '', label: '全部' },
  { k: 'perm_deny', label: '拒绝链接' },
  { k: 'perm_restore', label: '恢复链接' },
  { k: 'link_permission', label: '链接权限' },
  { k: 'category_update', label: '分类变更' },
  { k: 'user_role', label: '角色变更' },
  { k: 'user_ban', label: '禁用账号' },
  { k: 'user_unban', label: '启用账号' },
  { k: 'user_register', label: '自助注册' },
  { k: 'setting_update', label: '安全设置' },
]
const auditActionMeta = {
  perm_deny: { label: '拒绝链接', cls: 'bg-purple-100 text-purple-700' },
  perm_restore: { label: '恢复链接', cls: 'bg-emerald-100 text-emerald-700' },
  link_permission: { label: '链接权限', cls: 'bg-sky-100 text-sky-700' },
  category_update: { label: '分类变更', cls: 'bg-amber-100 text-amber-700' },
  user_role: { label: '角色变更', cls: 'bg-indigo-100 text-indigo-700' },
  user_ban: { label: '禁用账号', cls: 'bg-red-100 text-red-700' },
  user_unban: { label: '启用账号', cls: 'bg-emerald-100 text-emerald-700' },
  user_register: { label: '自助注册', cls: 'bg-teal-100 text-teal-700' },
  setting_update: { label: '安全设置', cls: 'bg-orange-100 text-orange-700' },
}
function auditBadge(action) {
  return auditActionMeta[action] || { label: action, cls: 'bg-gray-100 text-gray-700' }
}
function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
const auditTotalPages = computed(() => Math.max(1, Math.ceil(auditTotal.value / auditPer.value)))
async function loadAudit() {
  if (!isAdmin.value) return
  auditLoading.value = true
  try {
    const d = await api.adminAudit(auditPage.value, auditPer.value)
    auditLogs.value = (d.logs || []).filter((l) => !auditFilter.value || l.action === auditFilter.value)
    auditTotal.value = d.total || 0
  } catch (e) {
    msg.value = e.message
  } finally {
    auditLoading.value = false
  }
}
watch([auditPage, auditFilter], loadAudit)
watch(() => tab.value, (v) => { if (v === 'audit') loadAudit() })

const navItems = [
  { k: 'links', label: '链接管理', icon: 'link' },
  { k: 'categories', label: '分类管理', icon: 'folder_shared' },
  { k: 'users', label: '用户管理', icon: 'group' },
  { k: 'audit', label: '权限审计', icon: 'history_edu' },
  { k: 'settings', label: '系统设置', icon: 'settings_applications' },
  { k: 'stats', label: '数据统计', icon: 'insights' },
  { k: 'monitor', label: '群晖监控', icon: 'monitoring' },
]
// 普通用户仅可见「链接管理」「分类管理」；其余页面（用户/审计/设置/统计）仅管理员
const visibleNav = computed(() =>
  navItems.filter((n) => isAdmin.value || n.k === 'links' || n.k === 'categories')
)

watch([filterParent, filterChild, filterOwner, filterPwd, filterPerm, linkSubTab], () => { linksPage.value = 1 })
watch(filterParent, () => { filterChild.value = '' })
watch([userSubTab], () => { usersPage.value = 1 })

// 管理端数据统一加载入口
async function loadAdminData() {
  await fetchSettings()
  await loadUsers()
  await loadLinks()
}

// F5 直接刷新后台页时：子组件 onMounted 早于父组件 App.vue 的 onMounted，
// 此刻 loadMe() 尚未完成、store.user 为 null → isAdmin=false 会跳过加载。
// 因此监听 isAdmin 由 false→true 时补一次加载（分类管理用的是 store.tree，
// 由 App.vue 异步填充且响应式生效，所以刷新后一直正常）。
watch(isAdmin, (ok) => {
  if (ok) loadAdminData()
})
// 普通用户只能停留在 links / categories；若 tab 指向无权限页面则回退
watch(tab, (v) => {
  if (!isAdmin.value && v !== 'links' && v !== 'categories') tab.value = 'links'
})

onMounted(async () => {
  // 普通用户即可查看「链接管理」「分类管理」，因此始终加载链接；
  // 管理员额外加载用户/设置等管理数据
  loadVersion()
  await loadLinks()
  if (isAdmin.value) await loadAdminData()
})
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-bg-page text-on-background font-body-md">
    <!-- Admin Sidebar -->
    <aside class="hidden md:flex flex-col bg-surface shadow-md w-[240px] shrink-0">
      <button class="px-6 pt-6 pb-6 border-b border-outline-variant/30 flex items-center gap-3 text-left hover:opacity-80 transition-opacity" @click="router.push('/')">
        <div class="w-10 h-10 rounded-xl bg-primary-container text-on-primary-container flex items-center justify-center font-bold text-lg shadow-sm">云</div>
        <div>
          <div class="font-headline-sm text-headline-sm font-bold text-primary">{{ siteName }}</div>
          <div class="font-label-sm text-label-sm text-secondary">管理控制台</div>
        </div>
      </button>
      <nav class="flex-1 px-4 py-4 flex flex-col gap-1">
        <button
          v-for="n in visibleNav"
          :key="n.k"
          class="flex items-center gap-3 px-4 py-3 rounded-lg text-left font-body-md transition-all active:opacity-80"
          :class="tab === n.k ? 'bg-primary-fixed text-primary border-l-4 border-primary rounded-r-lg font-bold' : 'text-secondary hover:bg-surface-container'"
          @click="tab = n.k"
        >
          <span class="material-symbols-outlined">{{ n.icon }}</span>
          {{ n.label }}
        </button>
      </nav>
      <div class="p-4 border-t border-outline-variant/30">
        <button class="flex items-center gap-3 px-4 py-3 w-full rounded-lg text-secondary hover:bg-surface-container transition-all" @click="router.push('/')">
          <span class="material-symbols-outlined">arrow_back</span>
          <span class="font-body-md">返回前台</span>
        </button>
      </div>
    </aside>

    <!-- 移动端后台侧边导航抽屉（md 以下显示） -->
    <transition name="fade">
      <div v-if="adminNavOpen" class="fixed inset-0 bg-black/40 z-40 md:hidden" @click="adminNavOpen = false"></div>
    </transition>
    <transition name="drawer">
      <aside v-if="adminNavOpen" class="fixed left-0 top-0 h-full w-[260px] max-w-[85vw] bg-surface shadow-xl z-50 flex flex-col md:hidden">
        <div class="px-6 pt-6 pb-6 border-b border-outline-variant/30 flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-primary-container text-on-primary-container flex items-center justify-center font-bold text-lg shadow-sm overflow-hidden">
            <img v-if="store.siteLogo" :src="store.siteLogo" alt="logo" class="w-full h-full object-contain" />
            <span v-else>云</span>
          </div>
          <div>
            <div class="font-headline-sm text-headline-sm font-bold text-primary">{{ siteName }}</div>
            <div class="font-label-sm text-label-sm text-secondary">管理控制台</div>
          </div>
        </div>
        <nav class="flex-1 px-4 py-4 flex flex-col gap-1 overflow-y-auto">
          <button
            v-for="n in visibleNav"
            :key="n.k"
            class="flex items-center gap-3 px-4 py-3 rounded-lg text-left font-body-md transition-all"
            :class="tab === n.k ? 'bg-primary-fixed text-primary font-bold' : 'text-secondary hover:bg-surface-container'"
            @click="switchTab(n.k)"
          >
            <span class="material-symbols-outlined">{{ n.icon }}</span>
            {{ n.label }}
          </button>
        </nav>
        <div class="p-4 border-t border-outline-variant/30">
          <button class="flex items-center gap-3 px-4 py-3 w-full rounded-lg text-secondary hover:bg-surface-container transition-all" @click="router.push('/'); adminNavOpen = false">
            <span class="material-symbols-outlined">arrow_back</span>
            <span class="font-body-md">返回前台</span>
          </button>
        </div>
      </aside>
    </transition>

    <!-- Main column -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- Top bar -->
      <header class="flex justify-between items-center px-grid-gutter py-3 bg-surface shadow-sm z-30">
        <div class="flex items-center gap-2">
          <button class="md:hidden flex items-center justify-center w-9 h-9 rounded-lg text-primary hover:bg-surface-container transition-colors" @click="adminNavOpen = true" title="菜单">
            <span class="material-symbols-outlined">menu</span>
          </button>
          <button class="flex items-center gap-2 font-headline-md text-headline-md font-bold text-primary hidden md:block hover:opacity-80 transition-opacity" @click="router.push('/')">
            <img v-if="store.siteLogo" :src="store.siteLogo" alt="logo" class="w-6 h-6 object-contain" />
            <span v-else class="material-symbols-outlined text-primary">cloud</span>
            {{ siteName }}
          </button>
        </div>
        <div class="flex items-center gap-2">
          <UserMenu />
        </div>
      </header>

      <p v-if="msg" class="mx-6 mt-3 text-sm text-primary-container bg-primary-fixed/40 px-3 py-2 rounded-lg">{{ msg }}</p>

      <main class="flex-1 overflow-y-auto p-4 md:p-6">
        <div v-if="authPending" class="text-center py-20 text-on-surface-variant">
          <span class="material-symbols-outlined text-5xl animate-spin">progress_activity</span>
          <p class="mt-3">加载中…</p>
        </div>

        <div v-else>
          <!-- ===================== LINK MANAGEMENT ===================== -->
          <section v-if="tab === 'links'">
            <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
              <div>
                <h2 class="font-headline-lg text-headline-lg text-text-primary">链接管理</h2>
                <p class="font-body-md text-body-md text-text-secondary mt-1">管理并整理你的导航链接。</p>
              </div>
              <button class="flex items-center gap-2 bg-primary text-on-primary px-4 py-2 rounded-lg shadow-sm hover:shadow-md transition-shadow font-body-md active:scale-95" @click="showAdd = true">
                <span class="material-symbols-outlined text-sm">add</span>
                <span>新建链接</span>
              </button>
            </div>

            <div class="flex gap-6 border-b border-outline-variant mb-4">
              <button
                class="pb-3 border-b-2 font-headline-sm text-headline-sm transition-colors"
                :class="linkSubTab === 'all' ? 'border-primary text-primary' : 'border-transparent text-secondary hover:text-on-surface'"
                @click="linkSubTab = 'all'">全部链接</button>
              <button
                class="pb-3 border-b-2 font-headline-sm text-headline-sm transition-colors"
                :class="linkSubTab === 'archived' ? 'border-primary text-primary' : 'border-transparent text-secondary hover:text-on-surface'"
                @click="linkSubTab = 'archived'">已归档</button>
            </div>

            <div class="flex flex-wrap items-center gap-4 py-2 mb-4">
              <div class="flex items-center gap-2">
                <label class="font-label-sm text-label-sm text-text-secondary">分类:</label>
                <select v-model="filterParent" class="bg-bg-card border border-outline-variant rounded-lg px-3 py-1.5 font-body-sm text-body-sm focus:outline-none focus:border-primary">
                  <option value="">全部</option>
                  <option v-for="p in categoryParents" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
                <select v-model="filterChild" class="bg-bg-card border border-outline-variant rounded-lg px-3 py-1.5 font-body-sm text-body-sm focus:outline-none focus:border-primary disabled:opacity-50" :disabled="!filterParent">
                  <option value="">全部子分类</option>
                  <option v-for="c in categoryChildren" :key="c.id" :value="c.id">{{ c.name }}</option>
                </select>
              </div>
              <div class="flex items-center gap-2">
                <label class="font-label-sm text-label-sm text-text-secondary">添加人:</label>
                <select v-model="filterOwner" class="bg-bg-card border border-outline-variant rounded-lg px-3 py-1.5 font-body-sm text-body-sm focus:outline-none focus:border-primary">
                  <option value="">全部</option>
                  <option v-for="o in linkOwners" :key="o.id" :value="o.id">{{ o.name }}</option>
                </select>
              </div>
              <div class="flex items-center gap-2">
                <label class="font-label-sm text-label-sm text-text-secondary">密码:</label>
                <select v-model="filterPwd" class="bg-bg-card border border-outline-variant rounded-lg px-3 py-1.5 font-body-sm text-body-sm focus:outline-none focus:border-primary">
                  <option value="">全部</option>
                  <option value="set">已设密码</option>
                  <option value="unset">未设密码</option>
                </select>
              </div>
              <div class="flex items-center gap-2">
                <label class="font-label-sm text-label-sm text-text-secondary">权限:</label>
                <select v-model="filterPerm" class="bg-bg-card border border-outline-variant rounded-lg px-3 py-1.5 font-body-sm text-body-sm focus:outline-none focus:border-primary">
                  <option value="">全部</option>
                  <option value="all">所有人</option>
                  <option value="registered">注册用户</option>
                  <option value="admin">管理员</option>
                  <option value="self">仅自己</option>
                </select>
              </div>
            </div>

            <div class="bg-bg-card rounded-[16px] shadow-sm overflow-hidden border border-outline-variant/30">
              <div class="overflow-x-auto">
                <table class="w-full text-left border-collapse">
                  <thead>
                    <tr class="border-b border-outline-variant/50 bg-surface-container-lowest">
                      <th class="py-4 px-6 font-headline-sm text-headline-sm text-on-surface-variant font-semibold">图标</th>
                      <th class="py-4 px-6 font-headline-sm text-headline-sm text-on-surface-variant font-semibold">名称</th>
                      <th class="py-4 px-6 font-headline-sm text-headline-sm text-on-surface-variant font-semibold">外网URL</th>
                      <th class="py-4 px-6 font-headline-sm text-headline-sm text-on-surface-variant font-semibold">内网URL</th>
                      <th class="py-4 px-6 font-headline-sm text-headline-sm text-on-surface-variant font-semibold">分类</th>
                      <th class="py-4 px-6 font-headline-sm text-headline-sm text-on-surface-variant font-semibold">添加人</th>
                      <th class="py-4 px-6 font-headline-sm text-headline-sm text-on-surface-variant font-semibold">密码</th>
                      <th class="py-4 px-6 font-headline-sm text-headline-sm text-on-surface-variant font-semibold">权限</th>
                      <th class="py-4 px-6 font-headline-sm text-headline-sm text-on-surface-variant font-semibold">是否主页显示</th>
                      <th class="py-4 px-6 font-headline-sm text-headline-sm text-on-surface-variant font-semibold text-right">操作</th>
                    </tr>
                  </thead>
                  <tbody class="font-body-md text-body-md">
                    <tr v-for="l in pagedLinks" :key="l.id" class="border-b border-outline-variant/20 hover:bg-surface-container-low transition-colors group">
                      <td class="py-4 px-6">
                        <div class="w-10 h-10 rounded-lg bg-surface-container flex items-center justify-center text-primary group-hover:bg-primary-fixed transition-colors overflow-hidden">
                          <EntityIcon :icon="l.icon" :fallback="getLinkIcon(l.title)" :size="24" :alt="l.title" />
                        </div>
                      </td>
                      <td class="py-4 px-6 font-semibold text-on-surface">{{ l.title }}</td>
                      <td class="py-4 px-6 text-text-secondary max-w-[260px]">
                        <button v-if="l.url_external" type="button" class="block w-full truncate text-left text-primary hover:underline" :title="'打开外网链接：' + l.url_external" @click="openLinkUrl(l, 'external')">{{ l.url_external }}</button>
                        <span v-else class="text-text-secondary/60">—</span>
                      </td>
                      <td class="py-4 px-6 text-text-secondary max-w-[260px]">
                        <button v-if="l.url_internal" type="button" class="block w-full truncate text-left text-primary hover:underline" :title="'打开内网链接：' + l.url_internal" @click="openLinkUrl(l, 'internal')">{{ l.url_internal }}</button>
                        <span v-else class="text-text-secondary/60">—</span>
                      </td>
                      <td class="py-4 px-6">
                        <div class="flex items-center gap-1 flex-wrap">
                          <template v-if="l.parent_category_name">
                            <span class="px-2 py-1 bg-surface-variant text-on-surface-variant rounded text-xs">{{ l.parent_category_name }}</span>
                            <span class="text-text-secondary text-xs">&gt;</span>
                            <span class="px-2 py-1 bg-primary-fixed text-on-primary-fixed rounded text-xs">{{ l.category_name }}</span>
                          </template>
                          <span v-else class="px-2 py-1 bg-surface-variant text-on-surface-variant rounded text-xs">{{ l.category_name }}</span>
                        </div>
                      </td>
                      <td class="py-4 px-6">
                        <span class="px-2 py-1 bg-primary-fixed text-on-primary-fixed rounded-full text-xs font-medium flex items-center gap-1 w-max">
                          <span class="w-2 h-2 rounded-full bg-primary inline-block"></span>{{ l.owner_name }}
                        </span>
                      </td>
                      <td class="py-4 px-6">
                        <button v-if="!l.has_password" class="flex items-center gap-1 text-success hover:opacity-80 transition-opacity" title="未设密码，点击设置" @click="openSetPwd(l)">
                          <span class="material-symbols-outlined text-sm">lock_open</span><span class="text-xs">未设</span>
                        </button>
                        <button v-else class="flex items-center gap-1 text-error hover:opacity-80 transition-opacity" title="已设密码，点击修改/取消" @click="openUpdatePwd(l)">
                          <span class="material-symbols-outlined text-sm">lock</span><span class="text-xs">已设</span>
                        </button>
                      </td>
                      <td class="py-4 px-6">
                        <select
                          :value="l.permission || 'all'"
                          class="bg-bg-card border border-outline-variant rounded-lg px-2 py-1 font-body-sm text-body-sm focus:outline-none focus:border-primary disabled:opacity-50 disabled:cursor-not-allowed"
                          :disabled="l.owner_id !== store.user.id"
                          :title="l.owner_id === store.user.id ? '修改此链接的可见权限' : '仅添加人可修改权限'"
                          @change="changePerm(l, $event.target.value)"
                        >
                          <option value="all">所有人</option>
                          <option value="registered">注册用户</option>
                          <option value="admin">管理员</option>
                          <option value="self">仅自己</option>
                        </select>
                      </td>
                      <td class="py-4 px-6">
                        <button type="button" @click="toggleHome(l)" :title="l.show_on_home ? '在主页显示' : '已隐藏，点击在主页显示'"
                          class="relative w-11 h-6 rounded-full transition-colors duration-200"
                          :class="l.show_on_home ? 'bg-primary' : 'bg-surface-variant'">
                          <span class="absolute top-[2px] left-[2px] w-5 h-5 bg-white rounded-full shadow-sm transition-transform duration-200"
                            :class="l.show_on_home ? 'translate-x-5' : ''"></span>
                        </button>
                      </td>
                      <td class="py-4 px-6 text-right">
                        <div class="flex justify-end gap-2">
                          <button v-if="isAdmin" class="p-2 bg-success/10 text-success rounded-md hover:bg-success/20 transition-colors" title="权限矩阵：查看哪些用户能看此链接" @click="openMatrix(l)">
                            <span class="material-symbols-outlined text-[20px]">grid_view</span>
                          </button>
                          <button class="p-2 bg-secondary-container text-primary rounded-md hover:bg-primary-fixed transition-colors" title="编辑" @click="openEdit(l)">
                            <span class="material-symbols-outlined text-[20px]">edit</span>
                          </button>
                          <button v-if="l.can_edit" class="p-2 bg-error-container text-error rounded-md hover:opacity-80 transition-opacity" title="删除" @click="delLink(l)">
                            <span class="material-symbols-outlined text-[20px]">delete</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                    <tr v-if="!pagedLinks.length">
                      <td colspan="8" class="py-10 text-center text-on-surface-variant">无内容</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="border-t border-outline-variant/50 p-4 flex items-center justify-between bg-surface-container-lowest rounded-b-[16px]">
                <span class="font-body-sm text-body-sm text-on-surface-variant">共 {{ filteredLinks.length }} 条记录 · 第 {{ linksPage }} / {{ linksTotalPages }} 页</span>
                <div class="flex items-center gap-1">
                  <button class="w-8 h-8 flex items-center justify-center rounded border border-outline-variant text-on-surface-variant hover:bg-surface-container transition-colors disabled:opacity-40" :disabled="linksPage <= 1" @click="goLinksPage(linksPage - 1)">‹</button>
                  <button v-for="p in linksPages" :key="p"
                    class="w-8 h-8 flex items-center justify-center rounded border font-body-sm transition-colors"
                    :class="p === '...' ? 'border-transparent cursor-default text-on-surface-variant' : (p === linksPage ? 'border-primary bg-primary-container text-on-primary-container font-semibold' : 'border-outline-variant text-on-surface-variant hover:bg-surface-container')"
                    :disabled="p === '...'" @click="goLinksPage(p)">{{ p }}</button>
                  <button class="w-8 h-8 flex items-center justify-center rounded border border-outline-variant text-on-surface-variant hover:bg-surface-container transition-colors disabled:opacity-40" :disabled="linksPage >= linksTotalPages" @click="goLinksPage(linksPage + 1)">›</button>
                </div>
              </div>
            </div>
          </section>

          <!-- ===================== CATEGORY MANAGEMENT ===================== -->
          <section v-else-if="tab === 'categories'">
            <div class="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
              <div>
                <h1 class="font-headline-lg text-headline-lg text-primary-container mb-2">分类管理</h1>
                <p class="font-body-sm text-body-sm text-on-surface-variant">管理系统中的所有导航分类，调整层级结构与显示状态。</p>
              </div>
              <div class="flex items-center gap-3">
                <button class="bg-primary-container text-on-primary-container px-4 py-2 rounded-lg font-body-md hover:bg-surface-tint transition-colors shadow-md flex items-center gap-2" @click="newCatMode">
                  <span class="material-symbols-outlined text-sm">add</span> 新建分类
                </button>
              </div>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <!-- Tree -->
              <div class="lg:col-span-1 flex flex-col gap-4">
                <div class="bg-surface rounded-2xl p-6 border border-surface-variant shadow-sm">
                  <div class="flex items-center justify-between mb-6">
                    <h2 class="font-headline-sm text-primary-container">分类目录</h2>
                    <button class="text-primary flex items-center gap-1 hover:bg-surface-container-low px-2 py-1 rounded-lg transition-colors" @click="newCatMode">
                      <span class="material-symbols-outlined text-sm">add</span>
                      <span class="font-label-sm font-bold">新建</span>
                    </button>
                  </div>
                  <div class="flex flex-col gap-1">
                    <template v-for="p in store.tree" :key="p.id">
                      <div class="flex flex-col">
                        <div class="flex items-center gap-2 p-2 rounded-lg transition-colors"
                             :class="[
                               selectedCat === p.id ? 'bg-primary-fixed text-primary' : 'text-secondary',
                               canEditCat(p) ? 'cursor-pointer hover:bg-surface-container-low' : 'opacity-50 cursor-not-allowed'
                             ]"
                             :title="canEditCat(p) ? '' : '无权限：仅可编辑自己创建的分类'"
                             @click="canEditCat(p) && selectCat(p)">
                          <span class="material-symbols-outlined text-sm" @click.stop="expanded[p.id] = !expanded[p.id]">{{ expanded[p.id] ? 'expand_more' : 'chevron_right' }}</span>
                          <EntityIcon :icon="p.icon" fallback="folder" :size="20" :alt="p.name" />
                          <span class="font-body-md font-bold">{{ p.name }}</span>
                          <span v-if="p.visible === false" class="text-label-sm opacity-80 text-error">已隐藏</span>
                          <span v-if="p.archived" class="text-label-sm opacity-80 text-tertiary">已归档</span>
                          <span v-if="!canEditCat(p)" class="material-symbols-outlined text-label-sm opacity-70" title="无权限编辑">lock</span>
                          <span v-if="p.archived && canEditCat(p)" class="ml-1 text-label-sm text-primary hover:underline" @click.stop="restoreCat(p)">恢复</span>
                          <span class="ml-auto text-label-sm opacity-70">{{ (p.children || []).length }}</span>
                        </div>
                        <div v-if="expanded[p.id]" class="ml-6 mt-1 flex flex-col gap-1">
                          <div v-for="c in [...(p.children||[])].sort((a,b)=>a.position-b.position)" :key="c.id"
                               class="flex items-center gap-2 p-2 rounded-lg transition-colors"
                               :class="[
                                 selectedCat === c.id ? 'bg-primary-fixed text-primary' : 'text-secondary',
                                 canEditCat(c) ? 'cursor-pointer hover:bg-surface-container-low' : 'opacity-50 cursor-not-allowed'
                               ]"
                               :title="canEditCat(c) ? '' : '无权限：仅可编辑自己创建的分类'"
                               @click="canEditCat(c) && selectCat(c)">
                            <EntityIcon :icon="c.icon" fallback="folder" :size="20" :alt="c.name" />
                            <span class="font-body-md">{{ c.name }}</span>
                            <span v-if="c.visible === false" class="ml-1 text-label-sm opacity-80 text-error">已隐藏</span>
                            <span v-if="c.archived" class="text-label-sm opacity-80 text-tertiary">已归档</span>
                            <span v-if="!canEditCat(c)" class="material-symbols-outlined text-label-sm opacity-70" title="无权限编辑">lock</span>
                            <span v-if="c.archived && canEditCat(c)" class="ml-1 text-label-sm text-primary hover:underline" @click.stop="restoreCat(c)">恢复</span>
                          </div>
                        </div>
                      </div>
                    </template>
                  </div>
                </div>
              </div>

              <!-- Edit form -->
              <div class="lg:col-span-2 flex flex-col gap-4">
                <div class="bg-surface rounded-2xl border border-surface-variant shadow-sm overflow-hidden">
                  <div class="px-6 py-4 border-b border-surface-variant flex items-center justify-between bg-surface-container-lowest">
                    <h2 class="font-headline-sm text-on-surface">{{ selectedCat ? '编辑分类' : '新建分类' }}</h2>
                    <div class="flex items-center gap-3">
                      <button class="px-4 py-2 rounded-lg font-body-sm text-secondary hover:bg-surface-container transition-colors" @click="newCatMode">取消</button>
                      <button class="px-4 py-2 rounded-lg font-body-sm bg-primary-container text-on-primary-container hover:bg-surface-tint transition-colors shadow-sm" @click="saveCat">保存更改</button>
                    </div>
                  </div>
                  <div class="p-6 flex flex-col gap-6">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div class="flex flex-col gap-2">
                        <label class="font-label-sm text-secondary">分类名称 <span class="text-error">*</span></label>
                        <input v-model="catForm.name" class="bg-surface-container-low border-none rounded-lg text-body-md focus:ring-2 focus:ring-primary p-3" type="text" placeholder="分类名称" />
                      </div>
                      <div class="flex flex-col gap-2">
                        <label class="font-label-sm text-secondary">上级分类</label>
                        <select v-model="catForm.parent_id" class="bg-surface-container-low border-none rounded-lg text-body-md focus:ring-2 focus:ring-primary p-3">
                          <option :value="null">无 (作为顶级分类)</option>
                          <option v-for="p in catParentOptions" :key="p.id" :value="p.id">{{ p.name }}</option>
                        </select>
                      </div>
                    </div>
                    <div class="flex flex-col gap-2">
                      <label class="font-label-sm text-secondary">图标选择</label>
                      <div class="flex items-center gap-4">
                        <div class="w-12 h-12 rounded-xl bg-primary-fixed flex items-center justify-center text-primary overflow-hidden">
                          <EntityIcon :icon="catForm.icon" fallback="folder" :size="28" :alt="catForm.name" />
                        </div>
                        <input v-model="catForm.icon" class="px-3 py-1.5 rounded-lg border border-outline-variant text-label-sm w-28 focus:outline-none focus:border-primary" placeholder="图标名/emoji" />
                        <button type="button" class="px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface-variant hover:bg-surface-variant text-label-sm transition-colors flex items-center gap-1" @click="catIconPickerOpen = true">
                          <span class="material-symbols-outlined text-[18px]">emoji_emotions</span>
                          选择图标
                        </button>
                        <span class="font-label-sm text-secondary opacity-70">（分类无 URL，无需抓取图标）</span>
                      </div>
                    </div>
                    <div class="flex flex-col gap-2">
                      <label class="font-label-sm text-secondary">分类颜色</label>
                      <div class="flex items-center gap-3">
                        <input type="color" v-model="catForm.color" class="w-10 h-10 rounded-lg border border-outline-variant bg-transparent cursor-pointer p-0.5" />
                        <div class="flex items-center gap-2 flex-wrap">
                          <button v-for="c in catColorPresets" :key="c" type="button" class="w-6 h-6 rounded-full border border-outline-variant/60 transition-transform hover:scale-110" :class="catForm.color?.toLowerCase() === c.toLowerCase() ? 'ring-2 ring-offset-1 ring-primary' : ''" :style="{ background: c }" :title="c" @click="catForm.color = c"></button>
                        </div>
                        <span class="font-label-sm text-on-surface-variant">{{ catForm.color }}</span>
                      </div>
                      <span class="font-label-sm text-secondary opacity-70">开启「分类颜色」开关后，首页该分类图标及其下链接卡片图标将填充此颜色</span>
                    </div>
                    <div class="flex items-center justify-between rounded-xl bg-surface-container-low px-4 py-3">
                      <div class="flex flex-col">
                        <span class="font-body-md text-on-surface">主页显示</span>
                        <span class="font-label-sm text-on-surface-variant">关闭后所有用户的首页与侧边栏都不再显示该分类及其下的链接</span>
                      </div>
                      <!-- 仅管理员可设置「主页显示」开关 -->
                      <button v-if="isAdmin" type="button" role="switch" :aria-checked="catForm.visible !== false"
                        class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors shrink-0"
                        :class="catForm.visible !== false ? 'bg-primary' : 'bg-outline-variant'"
                        @click="toggleCatVisible(catForm.visible === false)">
                        <span class="inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform"
                          :class="catForm.visible !== false ? 'translate-x-5' : 'translate-x-1'"></span>
                      </button>
                      <div v-else class="flex items-center gap-1 text-label-sm text-on-surface-variant opacity-70" title="仅管理员可设置主页显示">
                        <span class="material-symbols-outlined text-[16px]">lock</span>
                        <span>{{ catForm.visible !== false ? '显示中（仅管理员可改）' : '已隐藏（仅管理员可改）' }}</span>
                      </div>
                    </div>
                    <!-- 分类权限（与链接权限一致：all/registered/admin/self），仅管理员可设置 -->
                    <div class="flex items-center justify-between rounded-xl bg-surface-container-low px-4 py-3">
                      <div class="flex flex-col">
                        <span class="font-body-md text-on-surface">分类权限</span>
                        <span class="font-label-sm text-on-surface-variant">控制谁能在前台看到该分类及其下的链接</span>
                      </div>
                      <div v-if="isAdmin" class="flex items-center gap-3 flex-wrap justify-end w-[55%]">
                        <select v-model="catForm.permission"
                          class="w-full px-3 py-2 bg-bg-card border border-outline-variant rounded-lg font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all appearance-none cursor-pointer">
                          <option v-for="p in PERM_OPTIONS" :key="p.value" :value="p.value">{{ p.label }}</option>
                        </select>
                      </div>
                      <div v-else class="flex items-center gap-1 text-label-sm text-on-surface-variant opacity-70" title="仅管理员可设置分类权限">
                        <span class="material-symbols-outlined text-[16px]">lock</span>
                        <span>仅管理员可设置</span>
                      </div>
                    </div>
                    <div v-if="catForm.archived" class="flex items-center justify-between rounded-xl bg-tertiary-container/40 px-4 py-3">
                      <div class="flex items-center gap-2">
                        <span class="material-symbols-outlined text-tertiary">inventory_2</span>
                        <span class="font-body-md text-on-surface">该分类已在回收站（归档）</span>
                      </div>
                      <button type="button" class="px-3 py-1.5 rounded-lg font-body-sm bg-primary-container text-on-primary-container hover:bg-surface-tint transition-colors" @click="restoreCurrent">移出回收站</button>
                    </div>
                    <div class="flex flex-col gap-2">
                      <label class="font-label-sm text-secondary">描述内容</label>
                      <textarea v-model="catForm.description" class="bg-surface-container-low border-none rounded-lg text-body-md focus:ring-2 focus:ring-primary p-3" rows="3" placeholder="输入分类描述..."></textarea>
                    </div>
                    <div class="pt-4 border-t border-surface-variant" v-if="selectedCat">
                      <button class="flex items-center gap-2 text-error bg-error-container/50 border border-error/25 hover:bg-error-container hover:border-error/40 px-4 py-2 rounded-lg transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
                        :disabled="!canEditCat(selectedCatNode)"
                        :title="canEditCat(selectedCatNode) ? '删除 / 移入回收站' : '无权限：仅可删除自己创建的分类'"
                        @click="openCatDel">
                        <span class="material-symbols-outlined">warning</span>
                        <span class="font-body-md font-bold">删除该分类</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <!-- 删除分类弹窗：处理旗下链接与子分类 -->
          <div v-if="showCatDel" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" @click.self="showCatDel = false">
            <div class="bg-surface rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
              <div class="px-6 py-4 border-b border-surface-variant flex items-center gap-2">
                <span class="material-symbols-outlined text-error">warning</span>
                <h3 class="font-headline-sm text-on-surface">删除分类</h3>
              </div>
              <div class="p-6 flex flex-col gap-5">
                <p class="font-body-sm text-on-surface-variant">
                  该分类下共有
                  <span class="font-bold text-on-surface">{{ catDelStats.link_count }}</span> 个链接、
                  <span class="font-bold text-on-surface">{{ catDelStats.child_count }}</span> 个子分类，请选择处理方式：
                </p>
                <div class="flex flex-col gap-3">
                  <label class="flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all"
                    :class="catDelMode === 'archive' ? 'border-amber-400 bg-amber-100 shadow-sm' : 'border-amber-200 bg-amber-50 hover:bg-amber-100'">
                    <input type="radio" value="archive" v-model="catDelMode" class="mt-1 accent-amber-500" />
                    <div class="flex flex-col">
                      <span class="font-body-md text-on-surface">移动到回收站（归档）<span class="ml-1 text-label-sm text-amber-600">默认</span></span>
                      <span class="font-label-sm text-on-surface-variant">保留分类与链接数据，前台不再显示，可随时恢复</span>
                    </div>
                  </label>
                  <label class="flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all"
                    :class="catDelMode === 'move' ? 'border-emerald-400 bg-emerald-100 shadow-sm' : 'border-emerald-200 bg-emerald-50 hover:bg-emerald-100'">
                    <input type="radio" value="move" v-model="catDelMode" class="mt-1 accent-emerald-500" />
                    <div class="flex flex-col gap-2 w-full">
                      <span class="font-body-md text-on-surface">移动到其他分类</span>
                      <select v-model="catDelMoveTo" class="bg-surface-container-low border-none rounded-lg text-body-sm focus:ring-2 focus:ring-emerald-400 p-2"
                        :disabled="catDelMode !== 'move'">
                        <option v-for="o in catDelMoveOptions" :key="o.id" :value="o.id">{{ o.name }}</option>
                      </select>
                    </div>
                  </label>
                  <label class="flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all"
                    :class="catDelMode === 'delete' ? 'border-red-400 bg-red-100 shadow-sm' : 'border-red-200 bg-red-50 hover:bg-red-100'">
                    <input type="radio" value="delete" v-model="catDelMode" class="mt-1 accent-red-500" />
                    <div class="flex flex-col">
                      <span class="font-body-md text-on-surface">同时删除链接与子分类</span>
                      <span class="font-label-sm text-on-surface-variant">该分类及其下所有链接、子分类将被永久删除</span>
                    </div>
                  </label>
                </div>
              </div>
              <div class="px-6 py-4 border-t border-surface-variant flex items-center justify-end gap-3 bg-surface-container-lowest">
                <button class="px-4 py-2 rounded-lg font-body-sm text-secondary hover:bg-surface-container transition-colors" @click="showCatDel = false">取消</button>
                <button class="px-4 py-2 rounded-lg font-body-sm bg-error text-on-error hover:opacity-90 transition-colors" @click="confirmCatDel">确认删除</button>
              </div>
            </div>
          </div>

          <!-- 父分类权限变更 → 子分类级联确认（item 8） -->
          <div v-if="showPermCascade" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" @click.self="showPermCascade = false">
            <div class="bg-surface rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
              <div class="px-6 py-4 border-b border-surface-variant flex items-center gap-2">
                <span class="material-symbols-outlined text-primary">account_tree</span>
                <h3 class="font-headline-sm text-on-surface">同步子分类权限</h3>
              </div>
              <div class="p-6 flex flex-col gap-4">
                <p class="font-body-sm text-on-surface-variant">
                  该父分类下共有 <b>{{ permCascadeCount }}</b> 个子分类，且权限与拟设值不同。是否同时将新权限应用到这些子分类？
                </p>
                <p class="font-label-sm text-on-surface-variant opacity-80">选择「保持现状」则仅修改父分类，子分类权限不变。</p>
                <div class="flex justify-end gap-3 pt-2">
                  <button class="px-4 py-2 rounded-lg font-body-sm text-secondary hover:bg-surface-container transition-colors" @click="showPermCascade = false">取消</button>
                  <button class="px-4 py-2 rounded-lg font-body-sm bg-surface-container-high text-on-surface hover:bg-surface-variant transition-colors" @click="showPermCascade = false; doSaveCat(false)">保持现状（仅父分类）</button>
                  <button class="px-4 py-2 rounded-lg font-body-sm bg-primary text-on-primary hover:opacity-90 transition-colors" @click="showPermCascade = false; doSaveCat(true)">同时应用到子分类</button>
                </div>
              </div>
            </div>
          </div>

          <!-- ===================== USER MANAGEMENT ===================== -->
          <section v-else-if="isAdmin && tab === 'users'">
            <div class="mb-8 flex justify-between items-end flex-wrap gap-4">
              <div>
                <h2 class="font-headline-lg text-headline-lg text-on-surface mb-1">用户管理</h2>
                <p class="font-body-sm text-body-sm text-text-secondary">管理平台用户及其访问权限。</p>
              </div>
              <button class="bg-primary text-on-primary font-headline-sm text-headline-sm px-6 py-2.5 rounded-full shadow-sm hover:-translate-y-[1px] hover:shadow-md transition-[transform,background-color,box-shadow] flex items-center gap-2" @click="openUserModal">
                <span class="material-symbols-outlined text-[18px]">add</span>
                添加用户
              </button>
            </div>

            <div class="flex gap-2 mb-6 border-b border-outline-variant/30 pb-2 overflow-x-auto">
              <button v-for="t in [{k:'all',label:'全部用户'},{k:'admin',label:'管理员'},{k:'online',label:'在线用户'},{k:'banned',label:'封禁名单'}]" :key="t.k"
                class="px-4 py-2 rounded-full font-headline-sm text-headline-sm whitespace-nowrap transition-colors"
                :class="userSubTab === t.k ? 'bg-primary-container text-on-primary-container' : 'text-secondary hover:bg-surface-container'"
                @click="userSubTab = t.k">{{ t.label }} ({{ userCounts[t.k] }})</button>
            </div>

            <div v-if="pagedUsers.length" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 mb-8">
              <div v-for="u in pagedUsers" :key="u.id" class="bg-bg-card rounded-card p-6 shadow-sm hover:shadow-md hover:-translate-y-[1px] transition-[transform,background-color,box-shadow,border-color] border border-transparent hover:border-primary-fixed-dim group flex flex-col relative overflow-hidden">
                <div class="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-primary-fixed/20 to-transparent rounded-bl-full pointer-events-none"></div>
                <div class="flex justify-between items-start mb-4 relative z-10">
                  <div class="flex items-center gap-4">
                    <div class="relative">
                      <div class="w-12 h-12 rounded-full border-2 border-surface bg-surface-container-high flex items-center justify-center text-primary font-headline-md text-headline-md">{{ (u.display_name || u.username)[0] }}</div>
                      <span class="absolute bottom-0 right-0 w-3.5 h-3.5 border-2 border-bg-card rounded-full" :class="u.online ? 'bg-success' : 'bg-outline-variant'"></span>
                    </div>
                    <div>
                      <div class="flex items-center gap-2">
                        <h3 class="font-headline-sm text-headline-sm text-on-surface">{{ u.display_name }}</h3>
                        <span v-if="u.banned" class="px-1.5 py-0.5 rounded text-[11px] font-medium bg-error-container text-error">已禁用</span>
                      </div>
                      <p class="font-label-sm text-label-sm text-text-secondary">@{{ u.username }}</p>
                    </div>
                  </div>
                </div>
                <div class="flex gap-2 mb-3">
                  <span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium"
                        :class="u.role === 'admin' ? 'bg-primary-fixed text-on-primary-fixed' : u.role === 'guest' ? 'bg-surface-container text-on-surface' : 'bg-surface-container-high text-on-surface-variant'">
                    {{ u.role === 'admin' ? '管理员' : u.role === 'guest' ? '访客' : '成员' }}
                  </span>
                </div>
                <div class="mb-4 space-y-1 font-label-sm text-label-sm text-on-surface-variant">
                  <div class="flex items-center gap-1.5">
                    <span class="material-symbols-outlined text-[14px]">event</span>
                    <span>注册：{{ fmtTime(u.created_at) }}</span>
                  </div>
                  <div class="flex items-center gap-1.5">
                    <span class="material-symbols-outlined text-[14px]">history</span>
                    <span>活跃：{{ u.online ? '当前在线' : fmtTime(u.last_seen) }}</span>
                  </div>
                </div>
                <div class="mt-auto pt-4 border-t border-outline-variant/30 flex items-center justify-between">
                  <span class="font-label-sm text-label-sm" :class="u.online ? 'text-success font-medium' : 'text-on-surface-variant'">
                    {{ u.online ? '在线' : '离线' }}
                  </span>
                  <div class="flex items-center gap-1.5">
                    <button class="w-8 h-8 flex items-center justify-center rounded-lg text-indigo-600 hover:bg-indigo-50 transition-colors" title="编辑权限" @click="openPerm(u)">
                      <span class="material-symbols-outlined text-[20px]">shield_person</span>
                    </button>
                    <button class="w-8 h-8 flex items-center justify-center rounded-lg text-amber-600 hover:bg-amber-50 transition-colors" title="重设密码" @click="openResetPwd(u)">
                      <span class="material-symbols-outlined text-[20px]">key</span>
                    </button>
                    <button class="w-8 h-8 flex items-center justify-center rounded-lg transition-colors"
                      :class="u.is_active === false ? 'text-success hover:bg-emerald-50' : 'text-error hover:bg-red-50'"
                      :title="u.is_active === false ? '启用用户' : '禁用用户'"
                      :disabled="u.username === 'admin'"
                      @click="toggleBan(u)">
                      <span class="material-symbols-outlined text-[20px]">{{ u.is_active === false ? 'person_add' : 'person_off' }}</span>
                    </button>
                    <select :value="u.role" class="text-xs bg-surface-container border border-outline-variant rounded px-2 py-1 focus:outline-none focus:border-primary" :disabled="u.username === 'admin'" @change="changeRole(u, $event.target.value)">
                      <option value="admin">admin</option>
                      <option value="member">member</option>
                      <option value="guest">guest</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="flex flex-col items-center justify-center py-20 text-on-surface-variant">
              <span class="material-symbols-outlined text-5xl mb-3">inbox</span>
              <p>无内容</p>
            </div>

            <div class="bg-surface rounded-card p-4 flex items-center justify-between border border-outline-variant shadow-sm">
              <span class="font-body-sm text-body-sm text-secondary">共 {{ filteredUsers.length }} 位用户 · 第 {{ usersPage }} / {{ usersTotalPages }} 页</span>
              <div class="flex items-center gap-1">
                <button class="w-8 h-8 flex items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container transition-colors disabled:opacity-40" :disabled="usersPage <= 1" @click="goUsersPage(usersPage - 1)">‹</button>
                <button v-for="p in usersPages" :key="p"
                  class="w-8 h-8 flex items-center justify-center rounded-lg font-body-sm transition-colors"
                  :class="p === '...' ? 'cursor-default text-on-surface-variant' : (p === usersPage ? 'bg-primary-container text-on-primary-container font-semibold' : 'hover:bg-surface-container text-on-surface-variant')"
                  :disabled="p === '...'" @click="goUsersPage(p)">{{ p }}</button>
                <button class="w-8 h-8 flex items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container transition-colors disabled:opacity-40" :disabled="usersPage >= usersTotalPages" @click="goUsersPage(usersPage + 1)">›</button>
              </div>
            </div>

            <!-- 重设密码弹窗 -->
            <div v-if="showResetPwd" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" @click.self="showResetPwd = false">
              <div class="bg-surface rounded-2xl shadow-xl w-full max-w-sm overflow-hidden">
                <div class="px-6 py-4 border-b border-surface-variant flex items-center gap-2">
                  <span class="material-symbols-outlined text-primary">key</span>
                  <h3 class="font-headline-sm text-on-surface">重设密码 · {{ resetPwdUser && resetPwdUser.username }}</h3>
                </div>
                <div class="p-6 flex flex-col gap-4">
                  <template v-if="!resetPwdResult">
                    <p class="font-body-sm text-on-surface-variant">为当前用户设置一个新密码（至少 6 位）。留空则自动生成 12 位随机密码。</p>
                    <div class="flex gap-2">
                      <input v-model="resetPwdForm.new_password" type="text" placeholder="留空则生成随机密码" minlength="6"
                        class="flex-1 px-3 py-2 rounded-lg bg-surface-container-low border border-outline-variant focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all font-body-sm" />
                      <button class="px-3 py-2 rounded-lg bg-surface-container text-on-surface hover:bg-surface-container-high transition-colors font-body-sm" title="生成随机密码" @click="genRandomPwd">
                        <span class="material-symbols-outlined text-[20px]">autorenew</span>
                      </button>
                    </div>
                    <div class="flex justify-end gap-3 pt-2">
                      <button class="px-4 py-2 rounded-lg font-body-sm text-secondary hover:bg-surface-container transition-colors" @click="showResetPwd = false">取消</button>
                      <button class="px-4 py-2 rounded-lg font-body-sm text-on-primary bg-primary hover:brightness-95 transition-colors" @click="confirmResetPwd">确定重设</button>
                    </div>
                  </template>
                  <template v-else>
                    <p class="font-body-sm text-on-surface-variant">密码已重设，请将以下新密码转交给用户：</p>
                    <div class="flex items-center gap-2 p-3 rounded-xl bg-surface-container-low border border-outline-variant">
                      <code class="flex-1 font-mono text-body-sm text-on-surface break-all">{{ resetPwdResult }}</code>
                      <button class="px-2 py-1 rounded-lg bg-surface-container text-on-surface hover:bg-surface-container-high transition-colors text-label-sm" @click="navigator.clipboard.writeText(resetPwdResult)">复制</button>
                    </div>
                    <div class="flex justify-end">
                      <button class="px-4 py-2 rounded-lg font-body-sm text-on-primary bg-primary hover:brightness-95 transition-colors" @click="showResetPwd = false">完成</button>
                    </div>
                  </template>
                </div>
              </div>
            </div>

            <!-- 禁用用户确认弹窗 -->
            <div v-if="banConfirmUser" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" @click.self="banConfirmUser = null">
              <div class="bg-surface rounded-2xl shadow-xl w-full max-w-sm overflow-hidden">
                <div class="px-6 py-4 border-b border-surface-variant flex items-center gap-2">
                  <span class="material-symbols-outlined text-error">person_off</span>
                  <h3 class="font-headline-sm text-on-surface">禁用用户</h3>
                </div>
                <div class="p-6">
                  <p class="font-body-sm text-on-surface-variant">确定禁用用户「<span class="font-medium text-on-surface">{{ banConfirmUser.username }}</span>」？禁用后该用户将无法登录，需由管理员重新启用。</p>
                </div>
                <div class="px-6 py-4 border-t border-surface-variant flex items-center justify-end gap-3 bg-surface-container-lowest">
                  <button class="px-4 py-2 rounded-lg font-body-sm text-secondary hover:bg-surface-container transition-colors" @click="banConfirmUser = null">取消</button>
                  <button class="px-4 py-2 rounded-lg font-body-sm text-on-error bg-error hover:opacity-90 transition-colors" @click="confirmBan">确认禁用</button>
                </div>
              </div>
            </div>
          </section>

          <!-- ===================== 权限审计 ===================== -->
          <section v-else-if="isAdmin && tab === 'audit'">
            <div class="mb-8">
              <h1 class="font-headline-lg text-headline-lg text-text-primary tracking-tight">权限审计日志</h1>
              <p class="font-body-md text-body-md text-text-secondary mt-1">记录权限与账号相关的关键操作，便于追溯「谁在何时改了什么」。</p>
            </div>

            <div class="flex flex-wrap gap-2 mb-4">
              <button
                v-for="a in auditActions"
                :key="a.k"
                @click="auditFilter = a.k; auditPage = 1"
                class="px-3 py-1.5 rounded-full font-label-sm text-label-sm border transition-colors"
                :class="auditFilter === a.k ? 'bg-primary text-on-primary border-primary' : 'bg-surface border-outline-variant text-on-surface-variant hover:bg-surface-container'"
              >{{ a.label }}</button>
            </div>

            <div class="bg-surface rounded-2xl border border-surface-variant shadow-sm overflow-hidden">
              <table class="w-full text-left border-collapse">
                <thead>
                  <tr class="border-b border-outline-variant/50 bg-surface-container-lowest">
                    <th class="py-3 px-5 font-headline-sm text-headline-sm text-on-surface-variant">时间</th>
                    <th class="py-3 px-5 font-headline-sm text-headline-sm text-on-surface-variant">操作人</th>
                    <th class="py-3 px-5 font-headline-sm text-headline-sm text-on-surface-variant">动作</th>
                    <th class="py-3 px-5 font-headline-sm text-headline-sm text-on-surface-variant">对象</th>
                    <th class="py-3 px-5 font-headline-sm text-headline-sm text-on-surface-variant">详情</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-outline-variant/20 font-body-md">
                  <tr v-if="auditLoading" class="text-center text-on-surface-variant">
                    <td colspan="5" class="py-10 font-body-md">加载中…</td>
                  </tr>
                  <tr v-else-if="!auditLogs.length" class="text-center text-on-surface-variant">
                    <td colspan="5" class="py-10 font-body-md">暂无审计记录</td>
                  </tr>
                  <tr v-for="l in auditLogs" :key="l.id" class="hover:bg-surface-container-lowest transition-colors">
                    <td class="py-3 px-5 text-label-sm text-on-surface-variant whitespace-nowrap">{{ formatTime(l.created_at) }}</td>
                    <td class="py-3 px-5 text-body-sm text-on-surface">{{ l.operator_name }}</td>
                    <td class="py-3 px-5">
                      <span class="px-2 py-1 rounded-md text-label-sm font-medium" :class="auditBadge(l.action).cls">{{ auditBadge(l.action).label }}</span>
                    </td>
                    <td class="py-3 px-5 text-body-sm text-on-surface">{{ l.target_type }}<span v-if="l.target_name" class="text-on-surface-variant"> · {{ l.target_name }}</span></td>
                    <td class="py-3 px-5 text-body-sm text-on-surface-variant">{{ l.detail }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="bg-surface rounded-card p-4 flex items-center justify-between border border-outline-variant shadow-sm mt-4" v-if="auditTotal > 0">
              <span class="font-body-sm text-body-sm text-secondary">共 {{ auditTotal }} 条 · 第 {{ auditPage }} / {{ auditTotalPages }} 页</span>
              <div class="flex items-center gap-1">
                <button class="w-8 h-8 flex items-center justify-center rounded-lg text-on-surface-variant hover:bg-surface-container transition-colors disabled:opacity-40" :disabled="auditPage <= 1" @click="auditPage = auditPage - 1">‹</button>
                <button class="w-8 h-8 flex items-center justify-center rounded-lg font-body-sm transition-colors" :class="auditPage === auditTotalPages ? 'bg-primary-container text-on-primary-container font-semibold' : 'hover:bg-surface-container text-on-surface-variant'" :disabled="auditPage >= auditTotalPages" @click="auditPage = auditPage + 1">›</button>
              </div>
            </div>
          </section>

          <!-- ===================== SYSTEM SETTINGS ===================== -->
          <section v-else-if="isAdmin && tab === 'settings'" class="max-w-none">
            <div class="mb-8">
              <h1 class="font-headline-lg text-headline-lg text-text-primary tracking-tight">系统设置</h1>
              <p class="font-body-md text-body-md text-text-secondary mt-1">配置全局首选项和仪表板行为。</p>
            </div>

            <!-- 版本与更新检测 -->
            <div class="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-surface-variant bg-surface px-4 py-3">
              <div class="flex flex-wrap items-center gap-x-5 gap-y-1 text-label-sm text-text-secondary">
                <span v-if="versionInfo">
                  当前版本：
                  <code class="rounded bg-surface-variant px-1.5 py-0.5 text-text-primary">{{ versionInfo.commit ? versionInfo.commit.slice(0, 7) : '开发版' }}</code>
                  <span v-if="versionInfo.build_time" class="text-text-secondary opacity-70">· 构建 {{ versionInfo.build_time }}</span>
                </span>
                <span v-else class="text-text-secondary opacity-70">版本信息加载中…</span>

                <span v-if="updateStatus && !updateStatus.error" class="inline-flex items-center gap-1.5">
                  <span class="material-symbols-outlined text-[16px]"
                        :class="updateStatus.update_available === false ? 'text-success' : (updateStatus.update_available === true ? 'text-warning' : 'text-text-secondary opacity-70')">
                    {{ updateStatus.update_available === false ? 'check_circle' : (updateStatus.update_available === true ? 'system_update' : 'help') }}
                  </span>
                  <span :class="updateStatus.update_available === false ? 'text-success' : (updateStatus.update_available === true ? 'text-warning' : 'text-text-secondary opacity-70')">
                    {{ updateStatus.update_available === false ? '已是最新' : (updateStatus.update_available === true ? '有更新可用（latest: ' + (updateStatus.latest_commit || '').slice(0, 7) + '）' : '更新状态未知') }}
                  </span>
                  <span v-if="updateStatus.cached" class="text-text-secondary opacity-70">（缓存 {{ updateStatus.checked_at ? updateStatus.checked_at.slice(11, 19) : '' }}）</span>
                </span>
                <span v-else-if="updateStatus && updateStatus.error" class="text-warning">检测失败：{{ updateStatus.error }}</span>
              </div>
              <button
                class="shrink-0 rounded-lg bg-primary px-3 py-1.5 text-label-sm font-medium text-on-primary transition-opacity hover:opacity-90 disabled:opacity-50"
                :disabled="checking"
                @click="checkUpdate"
              >{{ checking ? '检测中…' : '检查更新' }}</button>
            </div>

            <!-- 单卡片容器 + 三列分组（列间竖线分隔） -->
            <div class="bg-surface rounded-2xl p-6 shadow-sm border border-surface-variant">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-0 divide-y divide-outline-variant/50 md:divide-y-0 md:divide-x md:divide-outline-variant/50">

              <!-- 左列：账号安全 + 局域网 + 搜索偏好 -->
              <div class="flex flex-col gap-6 md:pr-6">

                <!-- 账号与安全 -->
                <div class="flex flex-col">
                  <div class="flex items-center gap-2.5 pb-3">
                    <span class="material-symbols-outlined text-primary text-[20px]">shield</span>
                    <h3 class="font-title-md text-[15px] font-semibold text-on-surface">账号与安全</h3>
                  </div>
                  <div class="flex items-center justify-between gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">开放注册</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">关闭后仅管理员可创建账号</div>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer shrink-0">
                      <input type="checkbox" v-model="allowRegister" class="sr-only peer">
                      <div class="w-9 h-5 bg-surface-variant peer-checked:bg-primary rounded-full peer-checked:after:translate-x-[18px] after:content-[''] after:absolute after:top-[1px] after:left-[1px] after:bg-white after:border-outline-variant after:border after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
                    </label>
                  </div>
                  <div class="flex items-center justify-between gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">新用户默认角色</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">自助注册用户自动获得的角色</div>
                    </div>
                    <div class="relative w-36 shrink-0">
                      <select v-model="defaultRole" class="block w-full pl-3 pr-9 py-2 text-sm border border-outline-variant rounded-lg bg-surface appearance-none focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer">
                        <option value="admin">管理员</option>
                        <option value="member">普通成员</option>
                        <option value="guest">访客</option>
                      </select>
                      <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-outline"><span class="material-symbols-outlined">expand_more</span></div>
                    </div>
                  </div>
                  <div class="flex items-center justify-between gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">登录有效期（小时）</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">令牌自动失效时间，默认 168（7 天）</div>
                    </div>
                    <input type="number" min="1" max="8760" v-model.number="tokenMaxAgeHours" class="block w-24 px-3 py-1.5 text-sm border border-outline-variant rounded-lg bg-surface shrink-0 focus:outline-none focus:ring-1 focus:ring-primary" />
                  </div>
                  <div class="flex items-center justify-between gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">访问日志保留天数</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">超过该天数的记录自动清理，默认 90 天</div>
                    </div>
                    <input type="number" min="1" max="3650" v-model.number="logRetentionDays" class="block w-24 px-3 py-1.5 text-sm border border-outline-variant rounded-lg bg-surface shrink-0 focus:outline-none focus:ring-1 focus:ring-primary" />
                  </div>
                </div>

                <!-- 局域网网段 -->
                <div class="flex flex-col pt-5 mt-5 border-t border-outline-variant/40">
                  <div class="flex items-center gap-2.5 pb-3">
                    <span class="material-symbols-outlined text-primary text-[20px]">lan</span>
                    <h3 class="font-title-md text-[15px] font-semibold text-on-surface">局域网网段</h3>
                  </div>
                  <label class="font-label-sm text-label-sm text-on-surface-variant font-medium mb-1.5">自定义局域网网段（可选）</label>
                  <textarea v-model="lanCidrs" rows="3"
                    class="w-full px-3 py-2 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm resize-none focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40"
                    placeholder="每行一个，如 192.168.1.0/24&#10;10.0.0.0/8&#10;172.16.0.0/12（留空则使用 RFC1918 私有段 + 本机 + 链路本地）"></textarea>
                  <p class="font-label-xs text-[11px] text-on-surface-variant mt-1.5 leading-tight">用于快速添加时判断粘贴的地址属于局域网还是互联网；命中即识别为内网并填入内网 URL。</p>
                </div>

                <!-- 搜索偏好 -->
                <div class="flex flex-col pt-5 mt-5 border-t border-outline-variant/40">
                  <div class="flex items-center gap-2.5 pb-3">
                    <span class="material-symbols-outlined text-primary text-[20px]">search_insights</span>
                    <h3 class="font-title-md text-[15px] font-semibold text-on-surface">搜索偏好</h3>
                  </div>
                  <div class="flex items-center justify-between gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">默认主引擎</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">首页搜索框使用的搜索引擎</div>
                    </div>
                    <div class="relative w-36 shrink-0">
                      <select v-model="defaultEngine" class="block w-full pl-3 pr-9 py-2 text-sm border border-outline-variant rounded-lg bg-surface appearance-none focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer">
                        <option>Google</option><option>DuckDuckGo</option><option>Bing</option><option>Brave</option><option>Baidu</option>
                      </select>
                      <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-outline"><span class="material-symbols-outlined">expand_more</span></div>
                    </div>
                  </div>
                  <div class="flex items-center justify-between gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">在新标签页中打开</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">在后台标签页中加载结果</div>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer shrink-0">
                      <input type="checkbox" v-model="openNewTab" class="sr-only peer">
                      <div class="w-9 h-5 bg-surface-variant peer-checked:bg-primary rounded-full peer-checked:after:translate-x-[18px] after:content-[''] after:absolute after:top-[1px] after:left-[1px] after:bg-white after:border-outline-variant after:border after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
                    </label>
                  </div>
                  <div class="flex items-center justify-between gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">搜索框位置</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">固定顶部或随内容滚动</div>
                    </div>
                    <div class="flex items-center bg-surface-container-highest rounded-full p-0.5 gap-1 shrink-0">
                      <button class="px-3 py-1 rounded-full text-xs font-medium transition-all" :class="searchBoxPos === 'fixed' ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'" @click="searchBoxPos = 'fixed'">固定</button>
                      <button class="px-3 py-1 rounded-full text-xs font-medium transition-all" :class="searchBoxPos === 'scrolling' ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'" @click="searchBoxPos = 'scrolling'">滚动</button>
                    </div>
                  </div>
                </div>

              </div>

              <!-- 中列：主页管理 + 主页入口 + 网络模式 -->
              <div class="flex flex-col gap-6 md:px-6">

                <!-- 主页管理 -->
                <div class="flex flex-col">
                  <div class="flex items-center gap-2.5 pb-3">
                    <span class="material-symbols-outlined text-primary text-[20px]">home_app_logo</span>
                    <h3 class="font-title-md text-[15px] font-semibold text-on-surface">主页管理</h3>
                  </div>
                  <div class="flex items-center justify-between gap-3 pt-2">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">允许主页内容编辑</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">允许用户自定义其主页导航链接</div>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer shrink-0">
                      <input type="checkbox" v-model="allowHomeEdit" class="sr-only peer">
                      <div class="w-9 h-5 bg-surface-variant peer-checked:bg-primary rounded-full peer-checked:after:translate-x-[18px] after:content-[''] after:absolute after:top-[1px] after:left-[1px] after:bg-white after:border-outline-variant after:border after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
                    </label>
                  </div>
                </div>

                <!-- 主页入口 -->
                <div class="flex flex-col pt-5 mt-5 border-t border-outline-variant/40">
                  <div class="flex items-center gap-2.5 pb-3">
                    <span class="material-symbols-outlined text-primary text-[20px]">menu_open</span>
                    <h3 class="font-title-md text-[15px] font-semibold text-on-surface">主页入口</h3>
                  </div>
                  <div class="flex items-center justify-between gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">显示「个人设置」</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">关闭后主页侧边栏与头像菜单均隐藏该入口</div>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer shrink-0">
                      <input type="checkbox" v-model="showPersonalSettings" class="sr-only peer">
                      <div class="w-9 h-5 bg-surface-variant peer-checked:bg-primary rounded-full peer-checked:after:translate-x-[18px] after:content-[''] after:absolute after:top-[1px] after:left-[1px] after:bg-white after:border-outline-variant after:border after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
                    </label>
                  </div>
                  <div class="flex items-center justify-between gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">显示「管理后台」</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">仅对管理员生效，关闭后入口隐藏</div>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer shrink-0">
                      <input type="checkbox" v-model="showAdminConsole" class="sr-only peer">
                      <div class="w-9 h-5 bg-surface-variant peer-checked:bg-primary rounded-full peer-checked:after:translate-x-[18px] after:content-[''] after:absolute after:top-[1px] after:left-[1px] after:bg-white after:border-outline-variant after:border after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
                    </label>
                  </div>
                </div>

                <!-- 网络模式 -->
                <div class="flex flex-col pt-5 mt-5 border-t border-outline-variant/40">
                  <div class="flex items-center gap-2.5 pb-3">
                    <span class="material-symbols-outlined text-primary text-[20px]">router</span>
                    <h3 class="font-title-md text-[15px] font-semibold text-on-surface">网络模式</h3>
                  </div>
                  <div class="flex items-center justify-between gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">默认网络</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">新用户与未单独设置的用户的默认展示网络</div>
                    </div>
                    <div class="flex items-center bg-surface-container-highest rounded-full p-0.5 gap-1 shrink-0">
                      <button class="px-3 py-1 rounded-full text-xs font-medium transition-all" :class="defaultNetwork === 'internal' ? 'bg-info text-white shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'" @click="defaultNetwork = 'internal'">内网</button>
                      <button class="px-3 py-1 rounded-full text-xs font-medium transition-all" :class="defaultNetwork === 'external' ? 'bg-success text-white shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'" @click="defaultNetwork = 'external'">外网</button>
                    </div>
                  </div>
                </div>

                <!-- 密码锁标识 -->
                <div class="flex flex-col pt-5 mt-5 border-t border-outline-variant/40">
                  <div class="flex items-center gap-2.5 pb-3">
                    <span class="material-symbols-outlined text-primary text-[20px]">lock</span>
                    <h3 class="font-title-md text-[15px] font-semibold text-on-surface">密码锁标识</h3>
                  </div>
                  <div class="flex items-center justify-between gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">显示密码锁标识</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">关闭后带密码的链接不再显示 lock 角标</div>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer shrink-0">
                      <input type="checkbox" v-model="showPasswordLock" class="sr-only peer">
                      <div class="w-9 h-5 bg-surface-variant peer-checked:bg-primary rounded-full peer-checked:after:translate-x-[18px] after:content-[''] after:absolute after:top-[1px] after:left-[1px] after:bg-white after:border-outline-variant after:border after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
                    </label>
                  </div>
                </div>

              </div>

              <!-- 右列：显示 / 外观 -->
              <div class="flex flex-col gap-6 md:pl-6">

                <!-- 站点品牌 -->
                <div class="flex flex-col">
                  <div class="flex items-center gap-2.5 pb-3">
                    <span class="material-symbols-outlined text-primary text-[20px]">badge</span>
                    <h3 class="font-title-md text-[15px] font-semibold text-on-surface">站点品牌</h3>
                  </div>
                  <!-- logo -->
                  <div class="flex items-center gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="w-14 h-14 rounded-xl bg-surface-container-high border border-outline-variant/50 flex items-center justify-center shrink-0 overflow-hidden">
                      <img v-if="siteLogo" :src="siteLogo" alt="logo" class="w-full h-full object-contain" />
                      <span v-else class="material-symbols-outlined text-[26px] text-on-surface-variant">image</span>
                    </div>
                    <div class="flex flex-col gap-2 min-w-0">
                      <label class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-container-high text-on-surface-variant hover:bg-surface-variant text-sm cursor-pointer transition-colors w-fit">
                        <span class="material-symbols-outlined text-[18px]">upload</span>
                        {{ logoUploading ? '上传中…' : '上传 Logo' }}
                        <input type="file" accept="image/*" class="hidden" :disabled="logoUploading" @change="onLogoUpload" />
                      </label>
                      <button type="button" v-if="siteLogo" class="text-xs text-error text-left hover:underline w-fit" @click="siteLogo = ''">移除 Logo</button>
                    </div>
                  </div>
                  <!-- logo 链接 / emoji -->
                  <div class="flex flex-col gap-1.5 pt-3">
                    <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">Logo 地址或 Emoji</label>
                    <input v-model="siteLogo" type="text"
                      class="w-full px-3 py-2 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40"
                      placeholder="留空则用默认；可填 /uploads/xxx.png 或 🚀 这类 emoji" />
                    <p class="font-label-xs text-[11px] text-on-surface-variant leading-tight">上传会自动填入此处；也可手动粘贴图片 URL 或 emoji 作为站点图标。</p>
                  </div>
                  <!-- 名称 -->
                  <div class="flex flex-col gap-1.5 pt-4">
                    <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">网站名称</label>
                    <input v-model="siteName" type="text"
                      class="w-full px-3 py-2 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40"
                      placeholder="云航导航" />
                  </div>
                  <!-- 副标题 -->
                  <div class="flex flex-col gap-1.5 pt-4">
                    <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">副标题</label>
                    <input v-model="siteSubtitle" type="text"
                      class="w-full px-3 py-2 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40"
                      placeholder="个人导航主页" />
                    <p class="font-label-xs text-[11px] text-on-surface-variant leading-tight">显示在名称下方；留空则不显示。</p>
                  </div>
                </div>

                <!-- 显示设置 -->
                <div class="flex flex-col">
                  <div class="flex items-center gap-2.5 pb-3">
                    <span class="material-symbols-outlined text-primary text-[20px]">grid_view</span>
                    <h3 class="font-title-md text-[15px] font-semibold text-on-surface">显示设置</h3>
                  </div>
                  <div class="py-2.5 border-t border-outline-variant/40">
                    <div class="flex items-center justify-between mb-2 gap-3">
                      <div class="font-body-sm text-body-sm text-on-surface">每行显示列数（桌面端）</div>
                      <span class="font-label-sm text-label-sm text-on-surface-variant bg-surface-container-highest rounded-full px-2.5 py-0.5">{{ columns }}</span>
                    </div>
                    <input type="range" min="2" max="8" step="1" v-model.number="columns" class="w-full h-2 bg-surface-variant rounded-lg appearance-none cursor-pointer accent-primary">
                  </div>
                  <div class="flex items-center justify-between gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">紧凑模式</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">更小的间距，显示更多卡片</div>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer shrink-0">
                      <input type="checkbox" v-model="compactMode" class="sr-only peer">
                      <div class="w-9 h-5 bg-surface-variant peer-checked:bg-primary rounded-full peer-checked:after:translate-x-[18px] after:content-[''] after:absolute after:top-[1px] after:left-[1px] after:bg-white after:border-outline-variant after:border after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
                    </label>
                  </div>
                  <div class="flex items-center justify-between gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">卡片密度</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">紧凑视图可显示更多内容</div>
                    </div>
                    <div class="flex items-center bg-surface-container-highest rounded-full p-0.5 gap-1 shrink-0">
                      <button class="px-3 py-1 rounded-full text-xs font-medium transition-all" :class="density === 'comfortable' ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'" @click="density = 'comfortable'">舒适</button>
                      <button class="px-3 py-1 rounded-full text-xs font-medium transition-all" :class="density === 'compact' ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'" @click="density = 'compact'">紧凑</button>
                    </div>
                  </div>
                </div>

                <!-- 外观设置 -->
                <div class="flex flex-col pt-5 mt-5 border-t border-outline-variant/40">
                  <div class="flex items-center gap-2.5 pb-3">
                    <span class="material-symbols-outlined text-primary text-[20px]">palette</span>
                    <h3 class="font-title-md text-[15px] font-semibold text-on-surface">外观设置</h3>
                  </div>
                  <div class="flex items-center justify-between gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">界面主题</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">浅色 / 深色 / 跟随系统</div>
                    </div>
                    <div class="flex items-center bg-surface-container-highest rounded-full p-0.5 gap-1 shrink-0">
                      <button v-for="t in [{k:'light',l:'浅色',i:'light_mode'},{k:'dark',l:'深色',i:'dark_mode'},{k:'system',l:'跟随系统',i:'auto_mode'}]" :key="t.k" class="px-3 py-1 rounded-full text-xs font-medium transition-all" :class="store.theme === t.k ? 'bg-primary text-on-primary shadow-sm' : 'text-on-surface-variant hover:bg-surface-variant'" @click="store.theme = t.k"><span class="inline-flex items-center gap-1"><span class="material-symbols-outlined text-[14px]">{{ t.i }}</span>{{ t.l }}</span></button>
                    </div>
                  </div>
                  <div class="flex items-center justify-between gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">默认配色方案</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">全站强调色（按钮 / 激活态），个人可在资料页覆盖</div>
                    </div>
                    <div class="relative shrink-0 w-48">
                      <button type="button" @click="colorSchemeOpen = !colorSchemeOpen" class="w-full flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-surface-container-highest text-on-surface border border-outline-variant/40 hover:border-primary/60 focus:border-primary focus:ring-2 focus:ring-primary/20 outline-none transition-colors cursor-pointer">
                        <span class="inline-flex items-center gap-1.5 min-w-0">
                          <span class="inline-flex gap-0.5 shrink-0">
                            <span v-for="(cc, ci) in (COLOR_SCHEMES.find(s => s.id === siteColorScheme)?.colors || ['#6C5CE7']).slice(0, 2)" :key="ci" class="w-2.5 h-2.5 rounded-full" :style="{ background: cc }"></span>
                          </span>
                          <span class="truncate">{{ COLOR_SCHEMES.find(s => s.id === siteColorScheme)?.label || '默认紫' }}</span>
                        </span>
                        <span class="material-symbols-outlined text-[16px] text-on-surface-variant shrink-0">expand_more</span>
                      </button>
                      <template v-if="colorSchemeOpen">
                        <div class="fixed inset-0 z-40" @click="colorSchemeOpen = false"></div>
                        <div class="absolute right-0 z-50 mt-1 w-52 rounded-xl border border-outline-variant/60 bg-surface shadow-lg p-1 max-h-72 overflow-auto">
                          <button v-for="s in COLOR_SCHEMES" :key="s.id" type="button" @click="siteColorScheme = s.id; colorSchemeOpen = false" class="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs font-medium transition-colors" :class="siteColorScheme === s.id ? 'bg-primary-container text-on-primary-container' : 'text-on-surface hover:bg-surface-container'">
                            <span class="inline-flex gap-0.5 shrink-0">
                              <span v-for="(cc, ci) in s.colors.slice(0, 2)" :key="ci" class="w-3 h-3 rounded-full" :style="{ background: cc }"></span>
                            </span>
                            <span class="truncate">{{ s.label }}</span>
                            <span v-if="siteColorScheme === s.id" class="material-symbols-outlined text-[16px] ml-auto">check</span>
                          </button>
                        </div>
                      </template>
                    </div>
                  </div>
                  <div class="flex items-center justify-between gap-3 py-2.5 border-t border-outline-variant/40">
                    <div class="min-w-0">
                      <div class="font-body-sm text-body-sm text-on-surface">分类颜色</div>
                      <div class="font-label-xs text-[11px] text-on-surface-variant leading-tight">开启后，首页分类图标及其下链接卡片图标背景填充分类颜色</div>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer shrink-0">
                      <input type="checkbox" v-model="showCategoryColors" class="sr-only peer">
                      <div class="w-9 h-5 bg-surface-variant peer-checked:bg-primary rounded-full peer-checked:after:translate-x-[18px] after:content-[''] after:absolute after:top-[1px] after:left-[1px] after:bg-white after:border-outline-variant after:border after:rounded-full after:h-4 after:w-4 after:transition-all"></div>
                    </label>
                  </div>
                </div>

              </div>
            </div>
            </div>

            <div class="mt-8 flex justify-end gap-4 border-t border-outline-variant/30 pt-6">
              <button class="px-6 py-2 rounded-lg font-body-sm text-body-sm font-semibold text-secondary hover:bg-surface-container transition-colors">取消</button>
              <button class="px-6 py-2 rounded-lg font-body-sm text-body-sm font-semibold bg-primary text-on-primary hover:bg-surface-tint shadow-sm transition-all" @click="saveSettings">保存更改</button>
            </div>
          </section>

          <section v-else-if="isAdmin && tab === 'stats'" class="px-2">
            <StatsView />
          </section>
          <section v-else-if="isAdmin && tab === 'monitor'">
            <MonitorView />
          </section>
        </div>
      </main>
    </div>

    <!-- Add user modal -->
    <div v-if="showUserModal" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="showUserModal = false"></div>
      <div class="relative bg-bg-card w-full max-w-md rounded-[16px] shadow-lg overflow-hidden flex flex-col">
        <div class="p-6 border-b border-outline-variant/30 flex justify-between items-center">
          <h2 class="font-headline-md text-headline-md text-on-surface">添加新用户</h2>
          <button class="text-outline hover:text-primary transition-colors" @click="showUserModal = false"><span class="material-symbols-outlined">close</span></button>
        </div>
        <div class="p-6 flex flex-col gap-4 overflow-y-auto max-h-[70vh]">
          <div class="flex flex-col gap-1">
            <label class="font-label-sm text-label-sm text-on-surface-variant">姓名</label>
            <input v-model="userForm.display_name" class="w-full px-4 py-2 bg-surface-container-low border border-outline-variant rounded font-body-sm focus:outline-none focus:border-primary" placeholder="请输入姓名" type="text" />
          </div>
          <div class="flex flex-col gap-1">
            <label class="font-label-sm text-label-sm text-on-surface-variant">用户名</label>
            <input v-model="userForm.username" class="w-full px-4 py-2 bg-surface-container-low border border-outline-variant rounded font-body-sm focus:outline-none focus:border-primary" placeholder="请输入用户名" type="text" />
          </div>
          <div class="flex flex-col gap-1">
            <label class="font-label-sm text-label-sm text-on-surface-variant">密码</label>
            <input v-model="userForm.password" class="w-full px-4 py-2 bg-surface-container-low border border-outline-variant rounded font-body-sm focus:outline-none focus:border-primary" placeholder="请输入密码" type="password" />
          </div>
          <div class="flex flex-col gap-1">
            <label class="font-label-sm text-label-sm text-on-surface-variant">角色</label>
            <select v-model="userForm.role" class="w-full px-4 py-2 bg-surface-container-low border border-outline-variant rounded font-body-sm focus:outline-none focus:border-primary">
              <option value="admin">管理员</option>
              <option value="member" selected>普通成员</option>
              <option value="guest">访客</option>
            </select>
          </div>
        </div>
        <div class="p-6 bg-surface-container-low flex justify-end gap-3">
          <button class="px-6 py-2 rounded-full text-secondary hover:bg-surface-container transition-colors font-headline-sm" @click="showUserModal = false">取消</button>
          <button class="px-6 py-2 rounded-full bg-primary text-on-primary shadow-sm hover:shadow-md hover:-translate-y-[1px] transition-[transform,background-color,box-shadow] font-headline-sm" @click="saveUser">保存用户</button>
        </div>
      </div>
    </div>

    <AddLinkModal v-model:open="showAdd" />
    <PermissionEditModal v-model:open="permOpen" :user="permUser" />
    <LinkPermissionMatrixModal v-model:open="matrixOpen" :link="matrixLink" />
    <!-- 点击加密链接时弹出的密码验证框（打开前已把目标 URL 写入 link.url） -->
    <PasswordModal v-model:open="adminPwdOpen" :link="adminPwdLink" />

    <!-- 密码设置 / 修改弹窗 -->
    <div v-if="pwdModal" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="pwdModal = null"></div>
      <div class="relative bg-bg-card w-full max-w-md rounded-[16px] shadow-lg overflow-hidden flex flex-col">
        <div class="px-6 py-4 border-b border-outline-variant/30 flex justify-between items-center">
          <h2 class="font-headline-md text-headline-md text-on-surface">{{ pwdModal.mode === 'set' ? '设置链接密码' : '修改链接密码' }}</h2>
          <button class="text-outline hover:text-primary transition-colors" @click="pwdModal = null"><span class="material-symbols-outlined">close</span></button>
        </div>
        <div class="p-6 flex flex-col gap-4">
          <p class="font-body-sm text-body-sm text-on-surface-variant">链接：<span class="font-semibold text-on-surface">{{ pwdModal.link.title }}</span></p>
          <template v-if="pwdModal.mode === 'update'">
            <div class="flex flex-col gap-1">
              <label class="font-label-sm text-label-sm text-on-surface-variant">旧密码</label>
              <input v-model="pwdForm.oldPw" type="password" class="w-full px-4 py-2 bg-surface-container-low border border-outline-variant rounded font-body-sm focus:outline-none focus:border-primary" placeholder="请输入旧密码" />
            </div>
          </template>
          <div class="flex flex-col gap-1">
            <label class="font-label-sm text-label-sm text-on-surface-variant">{{ pwdModal.mode === 'set' ? '新密码' : '新密码（留空则取消密码）' }}</label>
            <input v-model="pwdForm.npw1" type="password" class="w-full px-4 py-2 bg-surface-container-low border border-outline-variant rounded font-body-sm focus:outline-none focus:border-primary" placeholder="请输入新密码" />
          </div>
          <div class="flex flex-col gap-1">
            <label class="font-label-sm text-label-sm text-on-surface-variant">确认新密码</label>
            <input v-model="pwdForm.npw2" type="password" class="w-full px-4 py-2 bg-surface-container-low border border-outline-variant rounded font-body-sm focus:outline-none focus:border-primary" placeholder="再次输入新密码" />
          </div>
          <p v-if="pwdError" class="text-error font-body-sm">{{ pwdError }}</p>
        </div>
        <div class="p-6 bg-surface-container-low flex justify-end gap-3">
          <button class="px-6 py-2 rounded-full text-secondary hover:bg-surface-container transition-colors font-headline-sm" @click="pwdModal = null">取消</button>
          <button class="px-6 py-2 rounded-full bg-primary text-on-primary shadow-sm hover:shadow-md transition-all font-headline-sm" @click="confirmPwd">确定</button>
        </div>
      </div>
    </div>

    <!-- 编辑链接弹窗（左右分栏） -->
    <div v-if="showEdit" class="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="showEdit = false"></div>
      <div class="relative bg-bg-card w-full max-w-[880px] rounded-[20px] shadow-2xl overflow-hidden flex flex-col border border-outline-variant/30">
        <!-- Header -->
        <div class="px-8 py-5 border-b border-outline-variant/20 bg-surface-container-lowest flex justify-between items-center shrink-0">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-xl bg-primary-fixed text-primary flex items-center justify-center">
              <span class="material-symbols-outlined text-[20px]">edit</span>
            </div>
            <h2 class="font-headline-md text-headline-md text-on-surface">编辑链接</h2>
          </div>
          <button class="w-9 h-9 rounded-full hover:bg-surface-container transition-colors flex items-center justify-center text-on-surface-variant" @click="showEdit = false">
            <span class="material-symbols-outlined">close</span>
          </button>
        </div>

        <!-- Body: left-right split -->
        <div class="flex-1 flex min-h-0 overflow-hidden">
          <!-- ===== 左侧：表单区域 ===== -->
          <div class="w-[52%] p-8 overflow-y-auto space-y-5 border-r border-outline-variant/15">
            <!-- 只读提示（非链接添加人 / 非管理员） -->
            <div v-if="editReadonly" class="flex items-start gap-2 rounded-xl bg-tertiary-container/50 px-4 py-3 text-on-surface">
              <span class="material-symbols-outlined text-tertiary text-[18px] shrink-0">info</span>
              <p class="font-label-sm text-label-sm leading-snug">你不是该链接的添加人，仅可设置<b>访问密码</b>与<b>是否在主页显示</b>；其余字段不可修改。</p>
            </div>

            <!-- 名称 -->
            <div class="flex flex-col gap-1.5">
              <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">名称 <span class="text-error">*</span></label>
              <input v-model="editForm.title" type="text"
                class="w-full px-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-md focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="editReadonly"
                placeholder="输入链接名称…" />
            </div>

            <!-- 外网 URL -->
            <div class="flex flex-col gap-1.5">
              <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">外网 URL</label>
              <div class="flex gap-2">
                <span class="flex items-center px-3 py-2.5 rounded-xl border border-outline-variant bg-surface-container-high text-on-surface-variant font-body-sm shrink-0 select-none cursor-pointer hover:bg-surface-container transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  @click="!editReadonly && (editSslExternal = !editSslExternal)" :title="editSslExternal ? '当前 https，点击切换为 http' : '当前 http，点击切换为 https'">
                  {{ editSslExternal ? 'https://' : 'http://' }}
                </span>
                <input v-model="editExtBody" type="text"
                  class="flex-1 min-w-0 px-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40 disabled:opacity-50 disabled:cursor-not-allowed"
                  :disabled="editReadonly"
                  placeholder="example.com" />
                <label class="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-outline-variant bg-surface-container-low cursor-pointer shrink-0 select-none hover:bg-surface-container transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                  <input type="checkbox" v-model="editSslExternal" class="w-4 h-4 accent-primary" :disabled="editReadonly" />
                  <span class="font-label-sm text-label-sm text-on-surface-variant">SSL</span>
                </label>
              </div>
              <span class="text-xs text-on-surface-variant/70">默认 http，勾选 SSL 自动切换为 https</span>
            </div>

            <!-- 内网 URL -->
            <div class="flex flex-col gap-1.5">
              <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">内网 URL</label>
              <div class="flex gap-2">
                <span class="flex items-center px-3 py-2.5 rounded-xl border border-outline-variant bg-surface-container-high text-on-surface-variant font-body-sm shrink-0 select-none cursor-pointer hover:bg-surface-container transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  @click="!editReadonly && (editSslInternal = !editSslInternal)" :title="editSslInternal ? '当前 https，点击切换为 http' : '当前 http，点击切换为 https'">
                  {{ editSslInternal ? 'https://' : 'http://' }}
                </span>
                <input v-model="editIntBody" type="text"
                  class="flex-1 min-w-0 px-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40 disabled:opacity-50 disabled:cursor-not-allowed"
                  :disabled="editReadonly"
                  placeholder="192.168.x.x:port" />
                <label class="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-outline-variant bg-surface-container-low cursor-pointer shrink-0 select-none hover:bg-surface-container transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                  <input type="checkbox" v-model="editSslInternal" class="w-4 h-4 accent-primary" :disabled="editReadonly" />
                  <span class="font-label-sm text-label-sm text-on-surface-variant">SSL</span>
                </label>
              </div>
              <span class="text-xs text-on-surface-variant/70">默认 http，勾选 SSL 自动切换为 https</span>
            </div>

            <!-- 描述 -->
            <div class="flex flex-col gap-1.5">
              <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">描述内容</label>
              <textarea v-model="editForm.description" rows="3"
                class="w-full px-4 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm resize-none focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="editReadonly"
                placeholder="添加描述信息…"></textarea>
            </div>

            <!-- 图标 -->
            <div class="flex flex-col gap-1.5">
              <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">图标</label>
              <div class="flex items-stretch gap-3">
                <!-- 左侧：预览框，正方形（边长 = 右侧两行总高 36+8+42=86px） -->
                <div class="w-[86px] h-[86px] rounded-xl bg-surface-container-high border border-outline-variant/50 flex items-center justify-center shrink-0 overflow-hidden">
                  <EntityIcon :icon="editForm.icon" :fallback="getLinkIcon(editForm.title)" :size="40" />
                </div>
                <!-- 右侧：上=接口下拉 + 获取(占满剩余宽度) + 上传(更窄)，下=地址输入 -->
                <div class="flex-1 min-w-0 flex flex-col gap-2">
                  <div class="flex gap-2 h-9">
                    <select v-model="editSelectedProvider"
                      class="h-9 w-[150px] shrink-0 px-2 py-2 rounded-lg text-sm bg-surface-variant text-on-surface-variant border border-outline-variant/60 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 appearance-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                      :disabled="editReadonly">
                      <option v-for="p in editIconProviders" :key="p.key" :value="p.key">{{ p.label }}{{ p.network === 'proxy' ? '（需代理）' : '' }}{{ p.network === 'cn' ? '（国内）' : '' }}{{ p.network === 'direct' ? '（直连）' : '' }}</option>
                    </select>
                    <!-- 获取图标：柔和卡片色（淡紫罗兰） -->
                    <button type="button" title="获取图标"
                      class="flex-1 min-w-0 h-9 rounded-xl text-sm bg-[#E2D4F5] text-[#43358F] hover:brightness-95 disabled:opacity-50 flex items-center justify-center overflow-hidden shadow-sm"
                      :disabled="editIconBusy || editReadonly" @click="editAutoFetchIcon">
                      <span class="material-symbols-outlined text-[18px]" :class="{ 'animate-spin': editIconBusy }">auto_awesome</span>
                    </button>
                    <!-- 上传：柔和卡片色（淡桃粉） -->
                    <label title="上传图标"
                      class="w-10 h-9 shrink-0 rounded-xl text-sm bg-[#FCDFD0] text-[#A8513F] hover:brightness-95 cursor-pointer flex items-center justify-center disabled:opacity-50 shadow-sm">
                      <span class="material-symbols-outlined text-[18px]">upload</span>
                      <input type="file" accept="image/*" class="hidden" :disabled="editIconBusy || editReadonly" @change="editOnUpload" />
                    </label>
                  </div>
                  <input v-if="editSelectedProvider === 'custom'" v-model="editFaviconCustomUrl" type="text"
                    class="w-full h-[38px] px-3 bg-surface-container-low border border-outline-variant rounded-lg font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40 disabled:opacity-50 disabled:cursor-not-allowed"
                    :disabled="editReadonly"
                    placeholder="自定义接口模板：{scheme}://{host}/favicon.ico" />
                  <input v-model="editForm.icon" type="text"
                    class="w-full h-[42px] px-4 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all placeholder:text-on-surface-variant/40 disabled:opacity-50 disabled:cursor-not-allowed"
                    :disabled="editReadonly"
                    placeholder="图片网址 / 本地文件路径 / Material Symbols 名称" />
                  <button type="button" class="w-full h-9 shrink-0 rounded-lg bg-surface-container-high text-on-surface-variant hover:bg-surface-variant text-sm flex items-center justify-center gap-1 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" :disabled="editReadonly" @click="editIconPickerOpen = true">
                    <span class="material-symbols-outlined text-[18px]">emoji_emotions</span>
                    从系统图标库中选择
                  </button>
                </div>
              </div>
              <span class="text-xs text-on-surface-variant/70">保存时按此地址把图标下载并存到本地；失败则回退为按标题匹配的默认图标</span>
              <span v-if="editIconMsg" class="text-xs" :class="editIconWarn ? 'text-error' : 'text-on-surface-variant'">{{ editIconMsg }}</span>
            </div>

            <!-- 分类（两级联动） -->
            <div class="flex flex-col gap-1.5">
              <label class="font-label-sm text-label-sm text-on-surface-variant font-medium">选择分类</label>
              <div class="flex gap-2">
                <select v-model="editCatParent"
                  class="flex-1 px-3 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all appearance-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  :disabled="editReadonly">
                  <option value="">父分类</option>
                  <option v-for="p in store.tree" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
                <select v-model="editForm.category_id"
                  class="flex-1 px-3 py-2.5 bg-surface-container-low border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all appearance-none cursor-pointer disabled:opacity-45 disabled:cursor-not-allowed"
                  :disabled="editReadonly || (!editCatParent && !editForm.category_id)">
                  <option :value="null">子分类</option>
                  <template v-if="editCatParent">
                    <option v-for="c in editCatChildren" :key="c.id" :value="c.id">{{ c.name }}</option>
                  </template>
                  <template v-else>
                    <!-- 无父分类时显示全部子分类 -->
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
              <LinkCard :link="editCardPreview" />
            </div>

            <!-- 分隔线 -->
            <div class="border-t border-outline-variant/15"></div>

            <!-- 是否在主页显示（per-user，所有可见用户均可设置） -->
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-lg text-on-surface-variant">home</span>
                <span class="font-label-sm text-label-sm text-on-surface font-medium">在主页显示</span>
              </div>
              <button type="button" @click="toggleHome(editTarget)"
                class="relative w-11 h-6 rounded-full transition-colors duration-200"
                :class="editTarget && editTarget.show_on_home ? 'bg-primary' : 'bg-surface-variant'">
                <span class="absolute top-[2px] left-[2px] w-5 h-5 bg-white rounded-full shadow-sm transition-transform duration-200"
                  :class="editTarget && editTarget.show_on_home ? 'translate-x-5' : ''"></span>
              </button>
            </div>

            <!-- 权限配置 -->
            <div class="flex flex-col gap-2">
              <span class="font-label-xs text-label-xs text-on-surface-variant uppercase tracking-wider font-semibold">权限配置</span>
              <select v-model="editForm.permission"
                class="w-full px-4 py-2.5 bg-bg-card border border-outline-variant rounded-xl font-body-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all appearance-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="editReadonly">
                <option value="all">🌐 所有人 — 所有访客均可访问</option>
                <option value="registered">👤 注册用户 — 登录后可见</option>
                <option value="admin">🛡️ 管理员 — 仅管理员与所有者可见</option>
                <option value="self">🔒 仅自己 — 只有你能看到</option>
              </select>
            </div>

            <!-- 密码设置 -->
            <div class="flex flex-col gap-3">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span class="material-symbols-outlined text-lg" :class="editForm.enablePwd ? 'text-error' : 'text-on-surface-variant'">lock</span>
                  <span class="font-label-sm text-label-sm text-on-surface font-medium">开启访问密码</span>
                </div>
                <button @click="editForm.enablePwd = !editForm.enablePwd; editPwdError=''"
                  class="relative w-11 h-6 rounded-full transition-colors duration-200"
                  :class="editForm.enablePwd ? 'bg-primary' : 'bg-surface-variant'">
                  <span class="absolute top-[2px] left-[2px] w-5 h-5 bg-white rounded-full shadow-sm transition-transform duration-200"
                    :class="editForm.enablePwd ? 'translate-x-5' : ''"></span>
                </button>
              </div>
              <p class="font-label-xs text-label-xs text-on-surface-variant pl-1 -mt-1">启用后，访客需输入密码才能打开此链接</p>

              <!-- 密码输入（展开时显示） -->
              <div v-if="editForm.enablePwd" class="space-y-3 pl-1 pt-1 animate-in fade-in slide-in-from-top-2">
                <div class="flex flex-col gap-1">
                  <label class="font-label-xs text-label-xs text-on-surface-variant">新密码</label>
                  <input v-model="editForm.pwdNew" type="password"
                    class="w-full px-4 py-2 bg-bg-card border border-outline-variant rounded-lg font-body-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 transition-all"
                    placeholder="至少 4 位密码" />
                </div>
                <div class="flex flex-col gap-1">
                  <label class="font-label-xs text-label-xs text-on-surface-variant">确认密码</label>
                  <input v-model="editForm.pwdConfirm" type="password"
                    class="w-full px-4 py-2 bg-bg-card border border-outline-variant rounded-lg font-body-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/20 transition-all"
                    placeholder="再次输入密码" />
                </div>
                <p v-if="editPwdError" class="text-error font-label-xs text-label-xs flex items-center gap-1">
                  <span class="material-symbols-outlined text-[14px]">error</span>{{ editPwdError }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="px-8 py-5 border-t border-outline-variant/20 bg-surface-container-lowest flex justify-end gap-3 shrink-0">
          <button class="px-7 py-2.5 rounded-full text-secondary hover:bg-surface-container transition-colors font-headline-sm" @click="showEdit = false">取消</button>
          <button class="px-7 py-2.5 rounded-full bg-primary text-on-primary shadow-md hover:shadow-lg hover:-translate-y-[1px] active:translate-y-0 transition-[transform,background-color,box-shadow] font-headline-sm font-semibold" @click="saveEdit">保存更改</button>
        </div>
      </div>
    </div>

    <!-- 图标选择弹窗（分类 / 链接共用组件，分别控制开关） -->
    <IconPicker :open="catIconPickerOpen" title="选择分类图标" @update:open="catIconPickerOpen = $event" @pick="onPickCatIcon" />
    <IconPicker :open="editIconPickerOpen" title="选择链接图标" @update:open="editIconPickerOpen = $event" @pick="onPickEditIcon" />
  </div>
</template>

<style scoped>
/* 移动端后台抽屉 / 遮罩淡入淡出 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s cubic-bezier(0.32, 0.72, 1);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
.drawer-enter-active,
.drawer-leave-active {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.drawer-enter-from,
.drawer-leave-to {
  transform: translateX(-100%);
}
</style>
