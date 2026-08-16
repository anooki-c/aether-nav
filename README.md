# 云航导航 (Aether Nav) — 个人导航面板

自托管的书签 / 导航面板，统一管理外网与内网服务入口。基于 **Flask + Vue 3 + Vite + Tailwind**，
视觉风格源自 Stitch 原型（云航导航设计系统）。

---

## 功能

- **导航主页**：卡片式书签，支持内外网切换、明暗主题（浅 / 深 / 跟随系统）、分类二级树。
- **搜索**：站内搜索 + 一键跳转 Google / DuckDuckGo / Bing / Brave / Baidu。
- **快速添加**：粘贴链接自动识别内外网并归类，一键入库。
- **图标本地化**：自动抓取 favicon、本地上传、自定义 URL 或文字图标，离线 / 内网可用。
- **主页拖拽排序**：卡片可拖拽排序，按用户独立保存（后台可开关）。
- **后台管理**（`/admin`）：用户 / 分类 / 链接 / 权限审计 / 系统设置 / 数据统计。
- **四层权限模型**：账号墙 → 分类显隐与角色墙 → 链接基础权限 → 显式授权 / 拒绝；
  支持按用户独立访问密码、他人链接主页显隐开关、用户维度与链接维度权限矩阵。
- **普通成员分级后台权限**：可管理自身链接与分类，按角色受限操作。
- **天气组件**、个人设置页、注册 / 重置密码流程、游客模式、移动端抽屉与底部导航。
- **数据统计**：零依赖原生 SVG 图表（KPI / 趋势 / 角色分布 / Top 榜）。

---

## 用法

### 1. 本地运行

后端（Flask）：

```bash
python -m venv .venv && .venv/Scripts/activate      # Windows
pip install -r backend/requirements.txt
python -m backend.seed        # 首次：建表并创建默认管理员
python -m backend.app          # 启动，监听 http://localhost:5000
```

前端（Vite，开发模式）：

```bash
cd frontend
npm install
npm run dev            # 开发服务器 http://localhost:5173
```

### 2. Docker 部署

项目根提供 `Dockerfile` 与 `docker-compose.yml`，一键构建启动：

```bash
docker compose up -d --build      # 构建并启动，监听 http://localhost:5000
```

或拉取已构建镜像（群晖 Container Manager 等场景）：

```bash
docker pull ghcr.io/anooki-c/aether-nav:latest
docker run -d -p 5000:5000 \
  -v $(pwd)/data/instance:/app/backend/instance \
  -v $(pwd)/data/uploads:/app/backend/uploads \
  ghcr.io/anooki-c/aether-nav:latest
```

数据通过 `./data` 落到宿主机：

- `./data/instance/app.db` —— SQLite 数据库
- `./data/uploads` —— 本地图标存储

### 3. 首次登录与默认管理员

首次启动（或容器启动）会自动建表并创建默认管理员，**不注入任何演示数据**。

| 用户  | 密码      | 角色   |
|-------|-----------|--------|
| admin | admin123  | 管理员 |

凭据可用环境变量覆盖：`ADMIN_USERNAME`、`ADMIN_PASSWORD`、`ADMIN_DISPLAY`、`ADMIN_AVATAR`。

> 建议首次登录后立即修改默认密码。

### 4. 基本使用

1. 访问 `http://<host>:5000`，用 `admin / admin123` 登录。
2. 进入 `/admin` 后台：先建**分类**，再在分类下**添加链接**（内外网地址至少填一个）。
3. 主页可用**拖拽**调整卡片顺序；右上角切换内外网 / 主题。
4. 在「系统设置」中按需开启开放注册、配置局域网网段、调整令牌有效期与日志保留。
5. 如需对特定链接 / 分类设权限，在后台使用权限矩阵进行授权或拒绝。

---

完整功能需求见 `docs/需求文档.md`；权限模型设计见 `docs/权限模型设计.md`。
