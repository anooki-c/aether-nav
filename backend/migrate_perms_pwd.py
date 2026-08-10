"""一次性迁移（请求 C）：

1. 将旧 permission 取值规整为四选项模型：
   NULL / 'public'  -> 'all'
   'private'       -> 'self'
2. 将旧 Link.password_hash（单密码）迁移为「每用户独立密码」：
   为链接的 owner 在 link_passwords 中创建一条记录（若尚不存在）。
3. 确保 link_passwords 表存在（首次运行且无 create_all 时兜底）。

幂等：重复运行不会产生重复行。
"""
import os
import sqlite3

_candidates = [
    os.path.join(os.path.dirname(__file__), "instance", "app.db"),
    os.path.join(os.getcwd(), "instance", "app.db"),
    os.path.join(os.getcwd(), "backend", "instance", "app.db"),
]


def main():
    db_path = next((p for p in _candidates if os.path.exists(p)), None)
    if not db_path:
        print("未找到 app.db，跳过迁移（全新数据库会在 create_all 时自动建表与默认权限）。")
        return
    print(f"使用数据库: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. 确保 link_passwords 表存在（兜底）
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS link_passwords (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            link_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            password_hash VARCHAR(128) NOT NULL,
            CONSTRAINT uq_link_user_pwd UNIQUE (link_id, user_id)
        )
        """
    )

    # 2. 规整 permission 取值
    mapping = {
        "all": "all",
        "registered": "registered",
        "admin": "admin",
        "self": "self",
        "public": "all",
        "private": "self",
    }
    rows = cur.execute("SELECT id, permission FROM links").fetchall()
    count_perm = 0
    for lid, perm in rows:
        target = mapping.get((perm or "").strip().lower(), "all")
        if target != (perm or ""):
            cur.execute("UPDATE links SET permission = ? WHERE id = ?", (target, lid))
            count_perm += 1
    print(f"permission 已规整 {count_perm} 行（public->all, private->self）。")

    # 3. 旧密码迁移到「每用户独立密码」：以 owner 身份写入
    migrated = 0
    rows = cur.execute(
        "SELECT id, owner_id, password_hash FROM links WHERE has_password = 1 AND password_hash IS NOT NULL AND owner_id IS NOT NULL"
    ).fetchall()
    for lid, owner_id, phash in rows:
        exists = cur.execute(
            "SELECT 1 FROM link_passwords WHERE link_id = ? AND user_id = ?", (lid, owner_id)
        ).fetchone()
        if not exists:
            cur.execute(
                "INSERT INTO link_passwords (link_id, user_id, password_hash) VALUES (?, ?, ?)",
                (lid, owner_id, phash),
            )
            migrated += 1
    print(f"旧 password_hash 已为 {migrated} 个链接迁移到 owner 的 link_passwords。")

    conn.commit()
    conn.close()
    print("迁移完成。")


if __name__ == "__main__":
    main()
