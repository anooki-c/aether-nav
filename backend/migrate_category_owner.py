"""迁移：为 categories 表增加 owner_id 与 archived 列。

- owner_id：分类归属（创建者）。既有分类统一归属到管理员 admin。
- archived：回收站（归档）标记，默认 0（未归档）。

运行：python -m backend.migrate_category_owner
"""
import os
import sqlite3

from backend.app import app
from backend.models import Category, User, db

DB = os.path.join(os.path.dirname(__file__), "instance", "app.db")


def col_exists(conn, table, col):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == col for r in rows)


def main():
    conn = sqlite3.connect(DB)
    try:
        if not col_exists(conn, "categories", "owner_id"):
            conn.execute("ALTER TABLE categories ADD COLUMN owner_id INTEGER")
            print("+ 已为 categories 增加 owner_id 列")
        if not col_exists(conn, "categories", "archived"):
            conn.execute("ALTER TABLE categories ADD COLUMN archived BOOLEAN DEFAULT 0")
            print("+ 已为 categories 增加 archived 列")
        conn.commit()
    finally:
        conn.close()

    with app.app_context():
        admin = User.query.filter_by(username="admin").first()
        admin_id = admin.id if admin else None
        updated = 0
        for c in Category.query.all():
            changed = False
            if c.owner_id is None and admin_id is not None:
                c.owner_id = admin_id
                changed = True
            if c.archived is None:
                c.archived = False
                changed = True
            if changed:
                db.session.add(c)
                updated += 1
        db.session.commit()
        print(f"✅ 迁移完成：{updated} 个分类归属管理员，archived 默认置为未归档。")


if __name__ == "__main__":
    main()
