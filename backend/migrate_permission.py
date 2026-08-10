"""一次性迁移：为 links 表增加 permission 列（public/private）。

已存在该列则跳过。用于已有数据库向后兼容。
"""
import os
import sqlite3

# 常见数据库位置
_candidates = [
    os.path.join(os.path.dirname(__file__), "instance", "app.db"),
    os.path.join(os.getcwd(), "instance", "app.db"),
    os.path.join(os.getcwd(), "backend", "instance", "app.db"),
]


def main():
    db_path = next((p for p in _candidates if os.path.exists(p)), None)
    if not db_path:
        print("未找到 app.db，跳过迁移（全新数据库会在 create_all 时自动建列）。")
        return
    print(f"使用数据库: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(links)").fetchall()]
    if "permission" not in cols:
        cur.execute("ALTER TABLE links ADD COLUMN permission VARCHAR(16) NOT NULL DEFAULT 'public'")
        conn.commit()
        print("已添加 permission 列（默认 public）。")
    else:
        print("permission 列已存在，无需迁移。")
    conn.close()


if __name__ == "__main__":
    main()
