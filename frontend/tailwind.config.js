/** @type {import('tailwindcss').Config} */
// 颜色/字号/圆角 token 全部来自 Stitch 导出的 DESIGN.md，与 PRD §5 视觉风格一致。
// 语义色改由 CSS 变量驱动（style.css 中 :root 与 .dark 分别定义浅/深值），
// 这样切换 .dark 时 bg-surface / text-on-surface 等会自动套用深色值，无需逐处加 dark: 前缀。
const C = (name) => `rgb(var(${name}) / <alpha-value>)`

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      // 弹簧式缓动曲线（来自 Apple「Designing Fluid Interfaces」：临界阻尼=平滑无回弹；
      // spring-bounce=带轻微回弹，仅用于有动量/抛掷感的拖拽落点）。用 CSS 近似，无需弹簧库。
      transitionTimingFunction: {
        /* DEFAULT：所有不带 ease-* 后缀的 transition-* 工具类都回落到这里。
           此前没设 DEFAULT，于是它们一直吃 Tailwind 内置的 cubic-bezier(.4,0,.2,1)
           —— 那是对称 ease-in-out（起步慢），和本项目的 --ease-spring（起步快、平滑收敛）
           完全两回事；实测全站 118 处 transition-colors 等只有 12 处显式带了 ease-spring，
           其余约 92% 都落在错误曲线上，就是「悬停/入场顿一下才动」的来源。 */
        DEFAULT: 'var(--ease-spring)',
        spring: 'var(--ease-spring)',
        'spring-soft': 'var(--ease-out)',
        'spring-bounce': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      transitionDuration: {
        /* 同上：不设 DEFAULT 会吃内置 150ms，与令牌 --dur-base(180ms) 不一致 */
        DEFAULT: 'var(--dur-base)',
        250: '250ms',
        350: '350ms',
        500: '500ms',
      },
      colors: {
        surface: C('--c-surface'),
        'surface-dim': C('--c-surface-dim'),
        'surface-bright': C('--c-surface-bright'),
        'surface-container-lowest': C('--c-surface-container-lowest'),
        'surface-container-low': C('--c-surface-container-low'),
        'surface-container': C('--c-surface-container'),
        'surface-container-high': C('--c-surface-container-high'),
        'surface-container-highest': C('--c-surface-container-highest'),
        'on-surface': C('--c-on-surface'),
        'on-surface-variant': C('--c-on-surface-variant'),
        'inverse-surface': C('--c-inverse-surface'),
        'inverse-on-surface': C('--c-inverse-on-surface'),
        outline: C('--c-outline'),
        'outline-variant': C('--c-outline-variant'),
        'surface-tint': C('--c-surface-tint'),
        primary: C('--c-primary'),
        'on-primary': C('--c-on-primary'),
        'primary-container': C('--c-primary-container'),
        'on-primary-container': C('--c-on-primary-container'),
        'inverse-primary': C('--c-inverse-primary'),
        secondary: C('--c-secondary'),
        'on-secondary': C('--c-on-secondary'),
        'secondary-container': C('--c-secondary-container'),
        'on-secondary-container': C('--c-on-secondary-container'),
        tertiary: C('--c-tertiary'),
        'on-tertiary': C('--c-on-tertiary'),
        'tertiary-container': C('--c-tertiary-container'),
        'on-tertiary-container': C('--c-on-tertiary-container'),
        error: C('--c-error'),
        'on-error': C('--c-on-error'),
        'error-container': C('--c-error-container'),
        'on-error-container': C('--c-on-error-container'),
        'primary-fixed': C('--c-primary-fixed'),
        'primary-fixed-dim': C('--c-primary-fixed-dim'),
        'on-primary-fixed': C('--c-on-primary-fixed'),
        'on-primary-fixed-variant': C('--c-on-primary-fixed-variant'),
        'secondary-fixed': C('--c-secondary-fixed'),
        'secondary-fixed-dim': C('--c-secondary-fixed-dim'),
        'on-secondary-fixed': C('--c-on-secondary-fixed'),
        'on-secondary-fixed-variant': C('--c-on-secondary-fixed-variant'),
        'tertiary-fixed': C('--c-tertiary-fixed'),
        'tertiary-fixed-dim': C('--c-tertiary-fixed-dim'),
        'on-tertiary-fixed': C('--c-on-tertiary-fixed'),
        'on-tertiary-fixed-variant': C('--c-on-tertiary-fixed-variant'),
        background: C('--c-background'),
        'on-background': C('--c-on-background'),
        'surface-variant': C('--c-surface-variant'),
        'bg-page': C('--c-bg-page'),
        'bg-card': C('--c-bg-card'),
        'text-primary': C('--c-text-primary'),
        'text-secondary': C('--c-text-secondary'),
        success: C('--c-success'),
        warning: C('--c-warning'),
        info: C('--c-info'),
        brand: C('--c-brand'),
      },
      borderRadius: {
        DEFAULT: '0.25rem',
        lg: '0.5rem',
        xl: '0.75rem',
        '2xl': '1rem',
        '3xl': '1.5rem',
        full: '9999px',
      },
      spacing: {
        'unit-4': '4px',
        'unit-8': '8px',
        'unit-16': '16px',
        'unit-24': '24px',
        'card-padding': '1.5rem',
        'sidebar-width': '240px',
        'grid-gutter': '1.5rem',
        'hero-gap': '2rem',
      },
      fontFamily: {
        'headline-lg': ['Inter', 'sans-serif'],
        'headline-lg-mobile': ['Inter', 'sans-serif'],
        'headline-md': ['Inter', 'sans-serif'],
        'headline-sm': ['Inter', 'sans-serif'],
        'body-md': ['Inter', 'sans-serif'],
        'body-sm': ['Inter', 'sans-serif'],
        'label-sm': ['Inter', 'sans-serif'],
      },
      // 字距随字号分级（Apple《The Details of UI Typography》：tracking 是字号相关的，
      // 绝不能所有尺寸共用一个值 —— 字号越大，默认字距读起来越"散"，需要收紧；
      // 小字号则要略松以保可读性；正文趋近 0）。
      // 原状是只有 label-sm(12px) 带了 +0.02em，展示级标题完全没有字距，刻度是断的。
      // 现补齐一条单调递减的字距刻度：24 → -0.012em，直到 12px 回到 +0.02em。
      fontSize: {
        'headline-lg': ['24px', { lineHeight: '1.3', letterSpacing: '-0.012em', fontWeight: '600' }],
        'headline-lg-mobile': ['20px', { lineHeight: '1.3', letterSpacing: '-0.01em', fontWeight: '600' }],
        'headline-md': ['18px', { lineHeight: '1.4', letterSpacing: '-0.006em', fontWeight: '600' }],
        'headline-sm': ['15px', { lineHeight: '1.4', letterSpacing: '-0.003em', fontWeight: '600' }],
        'body-md': ['14px', { lineHeight: '1.6', fontWeight: '400' }],
        'body-sm': ['13px', { lineHeight: '1.5', fontWeight: '400' }],
        'label-sm': ['12px', { lineHeight: '1.4', letterSpacing: '0.02em', fontWeight: '400' }],
      },
      boxShadow: {
        /* fab 阴影改用令牌派生（原写死 rgba(108,92,231,0.35)，切配色后泛紫）。
           目前无引用，保留但不再埋雷。 */
        'fab': '0 8px 24px -4px rgb(var(--c-primary) / 0.35)',
        'glass': '0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03)',
        'glass-hover': '0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -2px rgba(0,0,0,0.04)',
      },
    },
  },
  plugins: [],
}
