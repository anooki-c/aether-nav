// URL scheme 辅助：把「完整 URL」拆成 {ssl, body}，以及反向拼接。
// 输入框只让用户填 host/path（body），scheme 由 SSL 勾选框控制（默认 http）。

export function parseUrlScheme(full) {
  const v = (full || '').trim()
  if (v.startsWith('https://')) return { ssl: true, body: v.slice(8) }
  if (v.startsWith('http://')) return { ssl: false, body: v.slice(7) }
  if (v.startsWith('//')) return { ssl: false, body: v.slice(2) }
  return { ssl: false, body: v }
}

export function buildUrl(ssl, body) {
  const b = (body || '').trim()
  if (!b) return ''
  return (ssl ? 'https://' : 'http://') + b
}
