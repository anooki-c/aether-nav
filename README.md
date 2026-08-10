# 云航导航 (Aether Nav) — 个人导航面板

自托管的书签/导航面板，统一管理外网与内网服务入口。基于 **Flask + Vue 3 + Vite + Tailwind**，
视觉风格源自 Stitch 原型（云航导航 设计系统）。

> 当前为 **可运行产品（v1.0）**：主页卡片拖拽排序（按用户独立、后台可开关）、图标本地化（自动抓取 + 上传）、
> 后台管理（用户 / 分类 / 链接 / 审计 / 设置 / 统计）、他人链接主页显隐开关、按用户独立访问密码、四层权限模型
> （账号墙 → 分类墙 → 链接权限 → 显式授权/拒绝）、用户维度与链接维度权限编辑、权限审计、访问数据统计、
> 天气组件、普通成员分级后台权限、移动端抽屉与底部导航。PWA、引导流程等仍待迭代。
>
> 完整功能需求见 **[docs/需求文档.md](docs/需求文档.md)**；权限模型设计见 **[docs/权限模型设计.md](docs/权限模型设计.md)**。

## 目录结构

```
aether-nav/
├─ docs/                   需求文档 / 权限模型设计
├─ tests/                  研发期 E2E / 调试脚本（非运行依赖）
├─ backend/                Flask 后端（REST API + SQLite）
│  ├─ app.py               入口与 API 路由
│  ├─ models.py            数据模型与 visible_links_for（四层权限）
│  ├─ config.py            配置（SQLite 路径、上传目录、前端 dist）
│  ├─ seed.py              示例数据注入
│  ├─ migrate_*.py         数据迁移脚本（运行一次）
│  ├─ requirements.txt
│  ├─ instance/app.db      SQLite 数据库（运行时生成）
│  └─ uploads/             本地图标存储目录
└─ frontend/               Vue 3 前端（Vite + Tailwind）
   ├─ src/
   │  ├─ components/       Sidebar / TopBar / SearchHero / LinkCard / SquareCard / MobileNav /
   │  │                    AddLinkModal / QuickAddLink / PasswordModal / UserMenu / WeatherWidget /
   │  │                    IconPicker / EntityIcon / PermissionEditModal / LinkPermissionMatrixModal
   │  ├─ views/            Home / Login / Admin / ProfileView / Register / ResetPassword / StatsView
   │  ├─ api/client.js     API 封装
   │  ├─ store.js          全局状态（主题/内外网/认证/分类树）
   │  ├─ router.js
   │  ├─ style.css         玻璃卡片等全局样式 + 本地化字体
   │  └─ main.js
   ├─ tailwind.config.js   设计 token（来自 DESIGN.md）
   └─ package.json         依赖含 vuedraggable（拖拽排序）
```

## 本地开发

### 1. 后端（Flask）

```bash
# 使用任意 Python 3.11+ 创建虚拟环境
python -m venv .venv && .venv/Scripts/activate      # Windows
pip install -r backend/requirements.txt
cd aether-nav
python -m backend.seed        # 首次：建表并注入示例数据
python -m backend.app          # 启动，监听 http://localhost:5000
```

> 开发时前端通过 Vite 代理 `/api` 到 `:5000`，无需手动起后端 CORS。

### 2. 前端（Vite）

```bash
cd aether-nav/frontend
npm install
npm run dev            # 开发服务器 http://localhost:5173
```

字体（Inter）与图标（Material Symbols）已通过 `@fontsource` **本地化打包**，离线/内网可用，
不再依赖 Google Fonts CDN。

### 演示账号

| 用户   | 密码      | 角色   |
|--------|-----------|--------|
| admin  | admin123  | 管理员 |
| alice  | alice123  | 成员   |
| guest  | guest123  | 访客   |

访客仅可见「权限=所有人」的链接，并可使用站内搜索；加密链接（如「私有网盘」，密码 `secret123`）
打开前需输入密码。

## 生产构建 & 部署

```bash
cd aether-nav/frontend
npm install && npm run build     # 产物输出到 frontend/dist
cd aether-nav
python -m backend.app            # Flask 自动托管 dist/ 下的 SPA
```

> **构建说明**：`vite.config.js` 已设置 `build.emptyOutDir: false`。原因是部分环境下 Vite 清理
> `dist` 会被安全删除包装拦截而构建失败；构建改为「覆盖写入」，旧的无用哈希产物可手动删除
> （不影响新产物引用）。如需彻底清空，请手动删除 `frontend/dist` 目录后重新构建。

访问 `http://<host>:5000` 即为完整应用。

### Docker（群晖 DSM 部署）

项目根提供 `Dockerfile`，多阶段构建：stage1 用 Node 构建前端，stage2 用 Python 运行 Flask。

```bash
docker build -t aether-nav .
docker run -d -p 5000:5000 -v aether-data:/app/backend/instance -v aether-uploads:/app/backend/uploads aether-nav
```

在群晖 Container Manager 中：导入上述镜像，映射端口 `5000`，并挂载两个卷保留数据库与上传的图标，
即可常年运行。详见 `docker-compose.yml`。

## 已实现 / 待迭代

**已实现**：
- 分类二级树、权限与可见性（按用户/角色/公开/私有）、链接密码、快速添加（粘贴自动识别内外网）
- 内外网切换、明暗主题（浅/深/跟随系统）、搜索（站内 + Google/DuckDuckGo/Bing/Brave/Baidu）、移动端方形卡 + 底部导航、游客模式
- **主页卡片拖拽排序**（按用户独立，后台可开关 —— `drag_sort_enabled`）
- **图标本地化**（自动抓取 favicon / 本地上传 / 自定义 URL / 文字图标，管理员与添加人可改）
- **后台管理页** `/admin`：链接管理、分类管理、用户管理、权限审计、系统设置、数据统计
- **四层权限模型**（账号墙 → 分类隐藏/角色墙 → 链接基础权限 → 显式授权/拒绝），详见 `docs/权限模型设计.md`
- **用户维度 / 链接维度权限编辑**（两类权限矩阵弹窗 + 拦截层原因标注）
- **按用户独立访问密码** 与 **他人链接主页显隐开关**（均按查看者个人生效）
- **普通成员分级后台权限**：可访问链接/分类管理；自身链接可编辑，他人链接仅可设密码与主页显隐；分类仅可新增不可改删
- **系统设置**（单卡片三列铺满：账号安全 / 主页与网络 / 显示外观搜索）、**账号与安全开关**（开放注册、默认角色、令牌有效期、日志保留、局域网网段）
- **权限审计日志**（`AuditLog`）、**访问数据统计**（零依赖原生 SVG 图表：KPI/趋势/角色分布/Top 榜）
- **天气组件**、**个人设置页**、注册 / 重置密码流程、头像菜单全角色一致

**待迭代**：PWA、首次使用引导流程、密码验证强度/限次策略细化、分类拖拽（当前为上下移按钮）、
更多角色权限粒度、图表 hover 交互。
