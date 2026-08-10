import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { store, applyTheme } from './store'
import './style.css'

// 本地化字体（契合 PRD：离线/内网可用，不依赖 Google Fonts CDN）
import '@fontsource/inter/400.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
import '@fontsource/material-symbols-outlined/400.css'
import '@fontsource/material-symbols-outlined/700.css'

// 应用初始主题
applyTheme(store.theme)

const app = createApp(App)

// 全局错误浮层：任何前端运行时报错都会以红字显示，便于排查白屏问题
function showErrorOverlay(msg) {
  let el = document.getElementById('__app_error__')
  if (!el) {
    el = document.createElement('div')
    el.id = '__app_error__'
    el.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:9999;background:#7f1d1d;color:#fff;font:13px/1.5 monospace;padding:10px 14px;white-space:pre-wrap;max-height:40vh;overflow:auto;box-shadow:0 -2px 8px rgba(0,0,0,.3)'
    document.body.appendChild(el)
  }
  el.textContent = '⚠️ 前端错误：\n' + msg
}
app.config.errorHandler = (err, instance, info) => { showErrorOverlay((err && err.stack) || String(err) + '\n' + info) }
window.addEventListener('error', (e) => showErrorOverlay((e.error && e.error.stack) || e.message))
window.addEventListener('unhandledrejection', (e) => showErrorOverlay('Promise: ' + ((e.reason && e.reason.stack) || e.reason)))

app.use(router).mount('#app')
