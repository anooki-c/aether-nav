"""一次性迁移：categories 表的 icon_enabled 列改为 visible 列。

语义变更：原先是「图标是否显示」，现改为「该分类是否在主页显示」（全局生效，
关闭后所有用户的首页与侧边栏都不再出现该分类及其下的链接）。

- 若存在旧列 icon_enabled 且不存在 visible：重命名（SQLite 3.25+ 支持）；
  重命名失败时退化为新增 visible 列并把旧值复制过去。
- 若两列都不存在：新增 visible 列（默认 1/显示）。
- 已有 visible 列：跳过。
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
    cols = [r[1] for r in cur.execute("PRAGMA table_info(categories)").fetchall()]

    if "visible" in cols:
        print("visible 列已存在，无需迁移。")
        conn.close()
        return

    if "icon_enabled" in cols:
        try:
            cur.execute("ALTER TABLE categories RENAME COLUMN icon_enabled TO visible")
            conn.commit()
            print("已将 icon_enabled 列重命名为 visible。")
        except sqlite3.OperationalError as e:
            print(f"重命名失败（{e}），改为新增列并复制旧值。")
            cur.execute("ALTER TABLE categories ADD COLUMN visible BOOLEAN NOT NULL DEFAULT 1")
            cur.execute("UPDATE categories SET visible = icon_enabled")
            conn.commit()
            print("已添加 visible 列并复制 icon_enabled 的值。")
    else:
        cur.execute("ALTER TABLE categories ADD COLUMN visible BOOLEAN NOT NULL DEFAULT 1")
        conn.commit()
        print("已添加 visible 列（默认 1/显示）。")

    # 迁移语义：旧的「图标关闭」不应等同于「分类隐藏」，统一重置为显示
    cur.execute("UPDATE categories SET visible = 1")
    conn.commit()
    print("已将所有分类的 visible 重置为 1（显示）。")
    conn.close()


if __name__ == "__main__":
    main()
