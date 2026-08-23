"""容器内运维命令（无需经过 Web 界面，适合密码找回 / 账号排查）。

脚本随镜像打包在 /app/backend/cli.py，运行时会复用 backend.app 的同一份
SQLAlchemy 配置，直接操作 instance/app.db，与 Web 服务指向同一个库。

推荐以 appuser 身份运行（避免把 instance 目录属主改成 root 导致 Web 服务
写入报 readonly）；若以 root 运行，脚本会在写入后自动把 instance/uploads
目录 chown 回 appuser。

示例：
  # 列出所有用户（id / 用户名 / 角色）
  docker exec nav python -m backend.cli list-users

  # 重置某用户密码（密码至少 6 位）
  docker exec -u appuser nav python -m backend.cli reset-password --username alice --password NewPass123

说明：
  - reset-password 对管理员与普通用户均生效，按用户名定位。
  - 若忘记用户名，先用 list-users 查看。
"""
import argparse
import os
import sys

from backend.app import app
from backend.models import User, db


def _heal_ownership():
    """若以 root 运行，把持久化目录属主改回 appuser，避免 Web 服务写入报 readonly。"""
    if os.geteuid() != 0:
        return
    try:
        import grp  # Unix 专属，容器内可用；非 Unix 平台直接跳过
        import pwd
        pw = pwd.getpwnam("appuser")
        uid, gid = pw.pw_uid, pw.pw_gid
    except (KeyError, ImportError, ModuleNotFoundError):
        return
    targets = ["/app/backend/instance", "/app/backend/uploads"]
    for path in targets:
        if not os.path.exists(path):
            continue
        try:
            for root, dirs, files in os.walk(path):
                for name in dirs + files:
                    os.chown(os.path.join(root, name), uid, gid)
            os.chown(path, uid, gid)
        except OSError:
            pass


def cmd_reset_password(args):
    if len(args.password) < 6:
        print("❌ 密码至少 6 位", file=sys.stderr)
        return 2
    with app.app_context():
        user = User.query.filter_by(username=args.username).first()
        if not user:
            print(f"❌ 用户不存在：{args.username}", file=sys.stderr)
            return 2
        user.set_password(args.password)
        db.session.commit()
        print(f"✅ 已重置用户「{user.username}」（角色={user.role}）的密码")
    _heal_ownership()
    return 0


def cmd_list_users(args):
    with app.app_context():
        users = User.query.order_by(User.id).all()
        if not users:
            print("（数据库暂无用户）")
            return 0
        print(f"{'id':<5} {'用户名':<20} {'角色':<10} {'显示名'}")
        for u in users:
            print(f"{u.id:<5} {u.username:<20} {u.role:<10} {u.display_name or ''}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="backend.cli", description="aether-nav 容器内运维命令"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("reset-password", help="重置指定用户密码")
    p.add_argument("--username", required=True, help="用户名（精确匹配）")
    p.add_argument("--password", required=True, help="新密码（至少 6 位）")
    p.set_defaults(func=cmd_reset_password)

    p = sub.add_parser("list-users", help="列出所有用户（id / 用户名 / 角色）")
    p.set_defaults(func=cmd_list_users)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
