"""迁移：为 link_permissions 表增加 deny 列，并清理废弃的 kind='public' 数据。

- deny：默认 0（grant，即允许）。True = 拒绝(deny)。对应权限模型 L3 的「显式拒绝」。
- kind='public' 为旧模型残留（新模型仅用 user / role），删除这些行避免脏数据干扰判定。

运行：python -m backend.migrate_linkpermission_deny
"""
import os
import sqlite3

from backend.app import app

DB = os.path.join(os.path.dirname(__file__), "instance", "app.db")


def col_exists(conn, table, col):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == col for r in rows)


def main():
    conn = sqlite3.connect(DB)
    try:
        if not col_exists(conn, "link_permissions", "deny"):
            conn.execute("ALTER TABLE link_permissions ADD COLUMN deny BOOLEAN DEFAULT 0")
            print("+ 已为 link_permissions 增加 deny 列")
        else:
            print("= deny 列已存在，跳过")
        cur = conn.execute("DELETE FROM link_permissions WHERE kind='public'")
        removed = cur.rowcount
        conn.commit()
        print(f"+ 已清理 {removed} 条废弃 kind='public' 记录")
    finally:
        conn.close()
    print("✅ 迁移完成。")


if __name__ == "__main__":
    main()
