# 开发 / 集成测试脚本

本目录存放研发期的**一次性调试与端到端（E2E）验证脚本**，不属于应用运行依赖。
它们依赖项目根目录的 `backend` 包，因此运行前请在 **项目根目录**（`aether-nav/`）执行：

```bash
# 以普通用户权限为核心的端到端验证（推荐入口）
python tests/_e2e_normaluser.py

# 其他历史脚本（按需运行；多数通过 app.test_client() 直接验证后端逻辑）
python tests/_e2e_perm_visible.py
python tests/_e2e_denied.py
python tests/_diag.py
```

> 说明：脚本从根目录的 `backend` 包导入（`from backend.app import app, db`），故必须保持 cwd 为 `aether-nav/`。
> 这些脚本仅用于本地验证，不会随前端构建或 Docker 镜像发布。
