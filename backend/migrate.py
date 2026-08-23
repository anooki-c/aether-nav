"""一次性 schema 迁移。

v0.3 引入 Category.permission 列（分类权限与链接权限统一为 all/registered/admin/self）。
SQLite 下 SQLAlchemy 的 db.create_all 不会给已存在的表追加新列，故这里用原生
ALTER TABLE 补列，并把历史分类回填为 'all'（旧模型 allowed_roles 为空=全员可见）。

该函数在 backend.seed 与 gunicorn 启动前均可安全重复调用（幂等）。
"""
from sqlalchemy import inspect, text

from backend.models import Category, db


def run_migrations(app):
    with app.app_context():
        with db.engine.begin() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(32) PRIMARY KEY, applied_at DATETIME NOT NULL)"))
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        if "categories" not in tables:
            # 全新部署：表尚未创建，交由 db.create_all 按模型建表（已含 permission 列）
            print("ℹ️  迁移：categories 表尚不存在，跳过（将由 db.create_all 创建）")
            return
        cols = [c["name"] for c in inspector.get_columns("categories")]
        if "permission" not in cols:
            # NOT NULL + DEFAULT 会让已有行自动回填为 'all'
            with db.engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE categories ADD COLUMN permission VARCHAR(16) NOT NULL DEFAULT 'all'")
                )
            with db.engine.begin() as conn:
                conn.execute(text("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES ('category_permission_v1', CURRENT_TIMESTAMP)"))

        # 兜底：任何 permission 为空的残留行统一置为 'all'
        dirty = False
        for c in Category.query.all():
            if not c.permission:
                c.permission = "all"
                dirty = True
        if dirty:
            db.session.commit()
