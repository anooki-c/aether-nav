"""首次启动初始化。

仅保证「有一个可用的默认管理员账号」，不再注入任何演示数据（分类 / 链接 / 权限）。
管理员凭据通过环境变量提供：
  ADMIN_USERNAME
  ADMIN_PASSWORD
  ADMIN_DISPLAY    默认 管理员
  ADMIN_AVATAR     默认 👑

运行：python -m backend.seed
"""
import os

from backend.models import User, db


def seed():
    if User.query.count() == 0:
        username = os.environ.get("ADMIN_USERNAME", "admin").strip()
        password = os.environ.get("ADMIN_PASSWORD", "")
        if not password:
            raise RuntimeError("首次初始化必须设置 ADMIN_PASSWORD")
        if len(password) < 8:
            raise RuntimeError("ADMIN_PASSWORD 至少需要 8 位")
        display = os.environ.get("ADMIN_DISPLAY", "管理员")
        avatar = os.environ.get("ADMIN_AVATAR", "👑")
        admin = User(username=username, display_name=display, role="admin", avatar=avatar)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"✅ 已创建管理员账号：{username}（密码不会写入日志）")
    else:
        print("ℹ️  已存在用户，跳过管理员创建")


if __name__ == "__main__":
    from backend.app import app
    from backend.migrate import run_migrations
    with app.app_context():
        db.create_all()
        run_migrations(app)
        seed()
        print("✅ 初始化完成")
