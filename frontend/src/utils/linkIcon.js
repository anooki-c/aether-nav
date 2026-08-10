// 链接标题 → Material Symbols 图标映射（对齐原型卡片图标风格）
export const linkIconMap = {
  github: 'code',
  vscode: 'code',
  git: 'source',
  gitea: 'source',
  postgres: 'database',
  mysql: 'storage',
  redis: 'storage',
  aws: 'cloud',
  cloud: 'cloud',
  docker: 'dns',
  jira: 'bug_report',
  issue: 'bug_report',
  tracker: 'task_alt',
  netflix: 'play_circle',
  spotify: 'music_note',
  youtube: 'play_circle',
  dsm: 'dns',
  nas: 'storage',
  pan: 'cloud',
  baidu: 'search',
  google: 'language',
  chat: 'chat',
  mail: 'email',
  docs: 'description',
  wiki: 'menu_book',
}

// 图标颜色（对齐原型：code=brand, database=info, cloud=error, bug_report=success）
export const iconColorMap = {
  code: 'text-brand',
  source: 'text-brand',
  terminal: 'text-brand',
  folder_open: 'text-brand',
  database: 'text-info',
  storage: 'text-info',
  dns: 'text-info',
  cloud: 'text-error',
  language: 'text-error',
  public: 'text-brand',
  bug_report: 'text-success',
  task_alt: 'text-success',
  play_circle: 'text-error',
  music_note: 'text-brand',
  chat: 'text-info',
  email: 'text-info',
  description: 'text-on-surface-variant',
  menu_book: 'text-on-surface-variant',
}

export function getLinkIcon(title) {
  const lower = (title || '').toLowerCase()
  for (const [key, icon] of Object.entries(linkIconMap)) {
    if (lower.includes(key)) return icon
  }
  return 'link'
}

export function getLinkIconColor(title) {
  const icon = getLinkIcon(title)
  return iconColorMap[icon] || 'text-on-surface-variant'
}
