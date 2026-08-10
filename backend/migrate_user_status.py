"""迁移：users 表新增 is_active（账号启用状态）与 last_seen（最后活跃时间）。

- is_active：默认 1（启用），所有既有用户保持启用
- last_seen：可空，默认 NULL（首次登录/请求后刷新）
"""
import sqlite3
import os

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "instance", "app.db")


def run():
    if not os.path.exists(DB):
        print("数据库不存在，跳过：", DB)
        return
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
    if "is_active" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1")
        print("已添加列 is_active（默认 1）")
    else:
        print("is_active 已存在，跳过")
    if "last_seen" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN last_seen DATETIME")
        print("已添加列 last_seen（默认 NULL）")
    else:
        print("last_seen 已存在，跳过")
    # 兜底：确保既有用户均为启用
    cur.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")
    conn.commit()
    conn.close()
    print("迁移完成。")


if __name__ == "__main__":
    run()
