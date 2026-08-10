"""注入示例数据（骨架版）。运行：python -m backend.seed"""
from backend.models import (
    Category,
    Link,
    LinkPermission,
    Setting,
    User,
    db,
)


def seed():
    # 用户
    if User.query.count() == 0:
        admin = User(username="admin", display_name="管理员", role="admin")
        admin.set_password("admin123")
        admin.avatar = "👑"
        member = User(username="alice", display_name="Alice", role="member")
        member.set_password("alice123")
        member.avatar = "🦊"
        guest = User(username="guest", display_name="访客", role="guest")
        guest.set_password("guest123")
        guest.avatar = "👤"
        db.session.add_all([admin, member, guest])
        db.session.commit()
    else:
        admin = User.query.filter_by(username="admin").first()
        alice = User.query.filter_by(username="alice").first()

    # 分类（二级）
    if Category.query.count() == 0:
        dev = Category(name="开发工具", icon="construction", color="#6C5CE7", position=1)
        db.session.add(dev)
        db.session.commit()
        db.session.add_all([
            Category(name="源码托管", parent_id=dev.id, icon="inventory_2", position=1),
            Category(name="CI / 构建", parent_id=dev.id, icon="settings", position=2),
            Category(name="容器平台", parent_id=dev.id, icon="deployed_code", position=3),
        ])
        media = Category(name="影音娱乐", icon="movie", color="#10B981", position=2)
        db.session.add(media)
        db.session.commit()
        db.session.add_all([
            Category(name="视频", parent_id=media.id, icon="live_tv", position=1),
            Category(name="音乐", parent_id=media.id, icon="music_note", position=2),
        ])
        net = Category(name="网络服务", icon="language", color="#3B82F6", position=3)
        db.session.add(net)
        db.session.commit()
        intra = Category(name="内网服务", parent_id=net.id, icon="home", position=1)
        db.session.add(intra)
        db.session.commit()
        # 演示「按创建者归属」：网络服务及其子分类归成员 alice，便于验证权限差异
        net.owner_id = alice.id
        intra.owner_id = alice.id
        db.session.commit()

    # 链接
    if Link.query.count() == 0:
        dev = Category.query.filter_by(name="开发工具").first()
        src = Category.query.filter_by(name="源码托管").first()
        ci = Category.query.filter_by(name="CI / 构建").first()
        cont = Category.query.filter_by(name="容器平台").first()
        video = Category.query.filter_by(name="视频").first()
        music = Category.query.filter_by(name="音乐").first()
        intra = Category.query.filter_by(name="内网服务").first()
        admin = User.query.filter_by(username="admin").first()
        alice = User.query.filter_by(username="alice").first()

        links = [
            Link(title="GitHub", description="全球最大代码托管平台", url_external="https://github.com",
                 icon="code", owner_id=admin.id, category_id=src.id),
            Link(title="Gitea", description="自托管 Git 服务(内网)", url_internal="http://192.168.1.10:3000",
                 url_external="https://gitea.example.com", icon="source", owner_id=admin.id, category_id=src.id),
            Link(title="Jenkins", description="持续集成(内网)", url_internal="http://192.168.1.20:8080",
                 icon="build", owner_id=admin.id, category_id=ci.id),
            Link(title="Portainer", description="Docker 可视化管理(内网)", url_internal="http://192.168.1.10:9000",
                 icon="deployed_code", owner_id=admin.id, category_id=cont.id),
            Link(title="Netflix", description="流媒体视频", url_external="https://netflix.com",
                 icon="movie", owner_id=alice.id, category_id=video.id),
            Link(title="Spotify", description="在线音乐", url_external="https://spotify.com",
                 icon="music_note", owner_id=alice.id, category_id=music.id),
            Link(title="群晖 DSM", description="NAS 管理后台(内网)", url_internal="http://192.168.1.5:5000",
                 icon="storage", owner_id=admin.id, category_id=intra.id),
        ]
        # 一条加密链接（PRD item 1）
        secret = Link(title="私有网盘", description="仅授权可见的加密链接", url_internal="http://192.168.1.5:5005",
                      icon="lock", owner_id=admin.id, category_id=intra.id)
        secret.set_link_password("secret123")
        links.append(secret)
        # 一条仅成员可见、非公开的链接（权限演示）
        member_only = Link(title="团队 Wiki", description="团队知识库", url_external="https://wiki.example.com",
                           icon="menu_book", owner_id=alice.id, category_id=dev.id)
        links.append(member_only)

        db.session.add_all(links)
        db.session.commit()

        # 权限（PRD item 11/14）：
        #  - 公开(everyone)：游客可浏览；其中「私有网盘」附密码，演示 item 1
        #  - 仅 member 角色：团队 Wiki
        #  - 无权限记录：仅 owner 与 admin 可见（Jenkins / Portainer 为管理员私有）
        public_links = [links[0], links[1], links[4], links[5], links[6], secret]  # GitHub/Gitea/Netflix/Spotify/群晖/网盘
        for lk in public_links:
            db.session.add(LinkPermission(link_id=lk.id, kind="public", target="everyone"))
        db.session.add(LinkPermission(link_id=member_only.id, kind="role", target="member"))
        db.session.commit()

    # 站点设置：主页拖拽排序默认开启（PRD item 6）
    if Setting.query.filter_by(key="drag_sort_enabled").first() is None:
        Setting.set("drag_sort_enabled", "true")


if __name__ == "__main__":
    from backend.app import app
    with app.app_context():
        db.create_all()
        seed()
        print("✅ 种子数据已注入")
