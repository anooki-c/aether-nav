import { store } from '../store'

const BASE = '/api'

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) }
  if (store.token) headers['Authorization'] = `Bearer ${store.token}`
  const res = await fetch(BASE + path, { ...options, headers })
  if (!res.ok) {
    let msg = `请求失败 (${res.status})`
    try {
      const data = await res.json()
      if (data.error) msg = data.error
    } catch (e) { /* ignore */ }
    throw new Error(msg)
  }
  if (res.status === 204) return null
  return res.json()
}

const json = (body) => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  // ---------- 基础 ----------
  health: () => request('/health'),
  login: (username, password) =>
    request('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) }),
  register: (payload) =>
    request('/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  resetPassword: (payload) =>
    request('/auth/reset-password', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  me: () => request('/me'),
  // 更新当前用户自身资料（用户名 / 昵称 / 头像 / 密码 / 个人偏好）
  updateProfile: (payload) =>
    request('/me', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  categoryTree: () => request('/categories/tree'),
  links: (network, q) => {
    const params = new URLSearchParams()
    if (network) params.set('network', network)
    if (q) params.set('q', q)
    return request('/links?' + params.toString())
  },
  search: (q) => request('/search?q=' + encodeURIComponent(q)),
  unlock: (id, password) => request(`/links/${id}/unlock`, json({ password })),
  createLink: (payload) => request('/links', json(payload)),
  // 快速添加：识别 URL 的网络属性 + 抓取标题/图标候选地址
  fetchLinkMeta: (url) => request('/fetch-link-meta', json({ url })),

  // ---------- 链接：排序 / 显隐 / 改删 ----------
  reorderLinks: (categoryId, orderedIds) => request('/links/reorder', json({ category_id: categoryId, ordered_ids: orderedIds })),
  setVisibility: (linkId, show) => request(`/links/${linkId}/visibility`, json({ show_on_home: show })),
  getLink: (id) => request(`/links/${id}`),
  updateLink: (id, payload) => request(`/links/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  deleteLink: (id) => request(`/links/${id}`, { method: 'DELETE' }),

  // ---------- 分类：CRUD / 重排 ----------
  createCategory: (payload) => request('/categories', json(payload)),
  updateCategory: (id, payload) => request(`/categories/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  deleteCategory: (id, body = null) => request(`/categories/${id}`, {
    method: 'DELETE',
    ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}),
  }),
  reorderCategories: (ordered) => request('/categories/reorder', json({ ordered })),

  // ---------- 图标：上传 / 自动抓取 ----------
  uploadIcon: (file, filename) => {
    const fd = new FormData()
    fd.append('file', file, filename || (file && file.name) || 'image.png')
    return request('/upload/icon', { method: 'POST', body: fd })
  },
  // 只解析图标地址填入输入框（不下载），真正落地在提交表单时由后端完成
  // provider / customUrl 可选：新增/编辑弹窗里临时切换接口时传入，覆盖站点默认
  resolveIcon: (url, provider = '', customUrl = '') =>
    request('/icon/resolve', json({
      url,
      ...(provider ? { provider } : {}),
      ...(customUrl ? { custom_url: customUrl } : {}),
    })),
  fetchIcon: (url) => request('/fetch-icon', json({ url })),
  // 图标获取接口清单（系统设置页用，管理员可切换）
  getIconProviders: () => request('/icon/providers'),
  // 在系统设置页试跑选中的图标接口，返回预览图
  testIconProvider: (url, provider, customUrl) =>
    request('/admin/icon/test', json({ url, provider, custom_url: customUrl })),

  // ---------- 站点设置 ----------
  getSettings: () => request('/settings'),
  updateSettings: (payload) => request('/admin/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),

  // ---------- 后台管理 ----------
  adminUsers: () => request('/admin/users'),
  createUser: (payload) => request('/admin/users', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  updateUser: (id, payload) => request(`/admin/users/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
  resetUserPassword: (id, newPassword) =>
    request(`/admin/users/${id}/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_password: newPassword || '' }),
    }),
  adminLinks: () => request('/admin/links'),

  // ---------- 用户权限（编辑弹窗 edit_permissions） ----------
  userPermissions: (uid) => request(`/admin/users/${uid}/permissions`),
  // denies=对该用户隐藏的链接 id 列表；其余（未列出的）开关开启=默认可见
  setUserPermissions: (uid, denies = []) =>
    request(`/admin/users/${uid}/permissions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ denies }) }),

  // ---------- 链接维度权限矩阵（反向视图） ----------
  linkPermissions: (lid) => request(`/admin/links/${lid}/permissions`),

  // ---------- 权限审计日志 ----------
  adminAudit: (page = 1, per = 50) => request(`/admin/audit?page=${page}&per=${per}`),

  // ---------- 访问统计 ----------
  // 链接点击埋点：前端在打开链接前异步调用，fire-and-forget（不 await、失败不阻塞）
  trackClick: (id) => request(`/links/${id}/track`, { method: 'POST' }),
  statsOverview: () => request('/admin/stats/overview'),
  statsTopLinks: (limit = 10) => request(`/admin/stats/top-links?limit=${limit}`),
  statsTopUsers: (limit = 10) => request(`/admin/stats/top-users?limit=${limit}`),
  statsTrend: (days = 30) => request(`/admin/stats/trend?days=${days}`),
  statsRoleDist: () => request('/admin/stats/role-dist'),
  // 统计分析总览（PRD F1–F12）：单一聚合接口，支持时间范围 / TopN / 维度 / 环比对比
  statsDashboard: (params = {}) => {
    const p = new URLSearchParams()
    if (params.days != null) p.set('days', params.days)
    if (params.topN != null) p.set('topN', params.topN)
    if (params.dim) p.set('dim', params.dim)
    if (params.compare != null) p.set('compare', params.compare ? '1' : '0')
    if (params.userId != null) p.set('user_id', params.userId)
    const qs = p.toString()
    return request(`/admin/stats/dashboard${qs ? '?' + qs : ''}`)
  },
  // 单日明细（热力图点击日期切换）：返回该日 24h 点击 / 登录分布
  statsDayDetail: (date) => request(`/admin/stats/day-detail?date=${encodeURIComponent(date)}`),
  // 手动触发链接可达性探测（系统也会定时自动 ping）
  pingLinks: () => request('/admin/links/ping', { method: 'POST' }),

  // ---------- 群晖监控（DSM API） ----------
  monitorConfig: () => request('/monitor/config'),
  monitorConfigSave: (payload) => request('/monitor/config', json(payload)),
  monitorSnapshot: (force) => request('/monitor' + (force ? '?force=1' : '')),
  monitorContainerAction: (id, action) => request('/monitor/container/action', json({ id, action })),
  monitorContainerDetail: (params) => request('/monitor/container/detail?' + new URLSearchParams(params).toString()),

  // ---------- 版本与更新检测 ----------
  version: () => request('/version'),
  checkUpdate: () => request('/check-update'),
}
