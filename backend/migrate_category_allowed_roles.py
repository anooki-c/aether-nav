"""迁移：为 categories 表增加 allowed_roles 列（分类角色白名单，对应权限模型 L1b）。

- allowed_roles：逗号分隔的角色白名单，如 "admin,member"；NULL/空 = 所有角色可见。
- 默认 NULL（全员可见），无需回填既有数据。

运行：python -m backend.migrate_category_allowed_roles
"""
import os
import sqlite3

from backend.app import app
from backend.models import Category

DB = os.path.join(os.path.dirname(__file__), "instance", "app.db")


def col_exists(conn, table, col):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == col for r in rows)


def main():
    conn = sqlite3.connect(DB)
    try:
        if not col_exists(conn, "categories", "allowed_roles"):
            conn.execute("ALTER TABLE categories ADD COLUMN allowed_roles VARCHAR(64)")
            print("+ 已为 categories 增加 allowed_roles 列")
        else:
            print("= allowed_roles 列已存在，跳过")
        conn.commit()
    finally:
        conn.close()

    with app.app_context():
        # allowed_roles 默认 NULL = 所有角色可见，无需回填
        total = Category.query.count()
        print(f"✅ 迁移完成：{total} 个分类，allowed_roles 默认 NULL（全员可见）。")


if __name__ == "__main__":
    main()
