"""首次启动初始化。

仅保证「有一个可用的默认管理员账号」，不再注入任何演示数据（分类 / 链接 / 权限）。
管理员凭据可通过环境变量覆盖：
  ADMIN_USERNAME   默认 admin
  ADMIN_PASSWORD   默认 admin123
  ADMIN_DISPLAY    默认 管理员
  ADMIN_AVATAR     默认 👑

运行：python -m backend.seed
"""
import os

from backend.models import User, db


def seed():
    if User.query.count() == 0:
        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD", "admin123")
        display = os.environ.get("ADMIN_DISPLAY", "管理员")
        avatar = os.environ.get("ADMIN_AVATAR", "👑")
        admin = User(username=username, display_name=display, role="admin", avatar=avatar)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"✅ 已创建默认管理员账号：{username} / {password}")
    else:
        print("ℹ️  已存在用户，跳过管理员创建")


if __name__ == "__main__":
    from backend.app import app
    with app.app_context():
        db.create_all()
        seed()
        print("✅ 初始化完成")
