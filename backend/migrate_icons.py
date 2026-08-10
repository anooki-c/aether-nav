"""一次性迁移：把 links / categories 表里的 emoji 图标换成 Material Symbols 名称。

规则：
- 空值、图片路径(/uploads 或 http)、已是 Material Symbols 名称 → 跳过
- 已知 emoji → 按映射表转成语义相近的 Material Symbols
- 未知 emoji → 用默认值（链接留空由前端按标题推断，分类用 folder）

用法：python migrate_icons.py
"""
import re
import sqlite3
import sys

EMOJI_MAP = {
    "🛠️": "construction", "🛠": "construction",
    "📦": "inventory_2",
    "⚙️": "settings", "⚙": "settings",
    "🐳": "deployed_code",
    "🎬": "movie",
    "📺": "live_tv",
    "🎵": "music_note",
    "🌐": "language",
    "🏠": "home",
    "🐙": "code",
    "🌿": "source",
    "🔧": "build",
    "💾": "storage",
    "🔒": "lock",
    "📚": "menu_book",
    "🧪": "science",
    "🔗": "",
}

SYMBOL_RE = re.compile(r"^[a-z0-9_]+$")
IMAGE_RE = re.compile(r"^(/|https?://)")


def migrate(cur, table, default):
    changed = []
    cur.execute("SELECT id, icon FROM {}".format(table))
    for row_id, icon in cur.fetchall():
        icon = (icon or "").strip()
        # 空 / 图片路径 / 已是 Material Symbols → 保持原样
        if not icon or IMAGE_RE.match(icon) or SYMBOL_RE.match(icon):
            continue
        new = EMOJI_MAP.get(icon, default)
        cur.execute(
            "UPDATE {} SET icon=? WHERE id=?".format(table), (new, row_id)
        )
        changed.append((row_id, icon, new))
    return changed


def main(db_path="instance/app.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    total = 0
    for table, default in (("links", ""), ("categories", "folder")):
        changed = migrate(cur, table, default)
        total += len(changed)
        print("== {}: migrated {} rows ==".format(table, len(changed)))
        for row_id, old, new in changed:
            print("   id={}  {!r} -> {!r}".format(row_id, old, new))
    conn.commit()
    conn.close()
    print("\nDone. total =", total)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "instance/app.db")
