/* 云航导航 Service Worker
 * ============================================================
 * 更新机制：浏览器每次导航都会按 HTTP 缓存重新拉取 sw.js；
 * 本项目后端对 javascript 响应强制 no-store（见 app.py _no_cache_frontend），
 * 因此 sw.js 始终为最新版本字节对比，内容变化即触发 install → skipWaiting
 * 立即激活 + clients.claim 接管现有页面。
 * CACHE_VERSION 变更时也会触发 activate 清理旧缓存。
 * ============================================================
 */
const CACHE_PREFIX = 'aether-nav';
const CACHE_VERSION = 'v1';                 // 与前端构建大版本同步手动 bump
const RUNTIME_CACHE = `${CACHE_PREFIX}-${CACHE_VERSION}-runtime`;

// 预缓存：站点外壳 + 关键静态资源，确保离线/弱网下首屏可加载
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/favicon.svg',
  '/apple-touch-icon.png',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/icon-maskable-512.png',
  '/vendor/chart.umd.min.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(RUNTIME_CACHE)
      .then((cache) => cache.addAll(PRECACHE_URLS).catch(() => {
        // 预缓存失败不阻塞 SW 安装；个别文件（如 vendor/chart）未来可能删除
      }))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k.startsWith(CACHE_PREFIX) && k !== RUNTIME_CACHE)
            .map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // 跨域（CDN：jsdelivr 等）：stale-while-revalidate，可离线加载字体/图标库
  if (url.origin !== self.location.origin) {
    event.respondWith(staleWhileRevalidate(request));
    return;
  }

  // 后端 API：始终走网络，绝不缓存
  if (url.pathname.startsWith('/api/')) {
    return; // 不调用 respondWith → 默认由浏览器直接发请求
  }

  // 导航请求（SPA 路由）：network-first，回退到缓存的 index.html
  if (request.mode === 'navigate') {
    event.respondWith(networkFirstNavigate(request));
    return;
  }

  // Vite 哈希资源（index-xxx.js / index-xxx.css）：cache-first 安全
  if (/\/assets\/.+\.(js|css|woff2?|ttf)$/.test(url.pathname)) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // 上传图标/头像：stale-while-revalidate（用户经常看到同一图）
  if (url.pathname.startsWith('/uploads/')) {
    event.respondWith(staleWhileRevalidate(request));
    return;
  }

  // 其他同源静态（icons/、favicon、manifest、vendor/*）：stale-while-revalidate
  event.respondWith(staleWhileRevalidate(request));
});

/* ---------- 缓存策略 ---------- */

async function cacheFirst(request) {
  const cache = await caches.open(RUNTIME_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response && response.ok) cache.put(request, response.clone());
    return response;
  } catch (e) {
    return cached || Response.error();
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(RUNTIME_CACHE);
  const cached = await cache.match(request);
  const networkPromise = fetch(request).then((response) => {
    if (response && (response.ok || response.type === 'opaque')) {
      cache.put(request, response.clone());
    }
    return response;
  }).catch(() => null);
  return cached || networkPromise || Response.error();
}

async function networkFirstNavigate(request) {
  const cache = await caches.open(RUNTIME_CACHE);
  try {
    const response = await fetch(request);
    if (response && response.ok) cache.put('/index.html', response.clone());
    return response;
  } catch (e) {
    // 离线：回退到缓存的 SPA shell，让前端路由接管
    const cached = await cache.match('/index.html') || await cache.match('/');
    if (cached) return cached;
    return new Response(
      '<!doctype html><meta charset="utf-8"><title>离线</title>' +
      '<div style="font:14px/1.5 system-ui;padding:24px;color:#333">' +
      '网络已断开，请检查连接后重试。</div>',
      { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
    );
  }
}
