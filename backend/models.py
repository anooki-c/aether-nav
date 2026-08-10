"""数据模型 —— 对应 PRD v1.3 的实体与权限模型（骨架版）。"""
import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

# 在线判定窗口（秒）：最后活跃时间在此窗口内视为「在线」
ONLINE_WINDOW = 300


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    display_name = db.Column(db.String(64))
    avatar = db.Column(db.String(256))  # 本地路径或 emoji
    role = db.Column(db.String(16), default="member")  # admin / member / guest
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # 账号是否启用：管理员可禁用/启用。禁用后无法登录。
    is_active = db.Column(db.Boolean, default=True)
    # 最后活跃时间：每次带 token 请求都会刷新，用于前端展示真实「在线」状态
    last_seen = db.Column(db.DateTime, nullable=True)
    # 个人偏好（JSON）：默认网络模式 / 界面主题 / 链接打开方式 / 天气城市 等
    preferences = db.Column(db.Text, default="{}")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    def prefs(self):
        """解析个人偏好 JSON（容错：损坏值回落空 dict）。"""
        import json
        try:
            return json.loads(self.preferences or "{}") or {}
        except Exception:
            return {}

    def to_dict(self, include_admin=False):
        d = {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name or self.username,
            "avatar": self.avatar,
            "role": self.role,
            "is_active": self.is_active is not False,
            "banned": self.is_active is False,
            "online": bool(
                self.last_seen
                and (datetime.datetime.utcnow() - self.last_seen).total_seconds() < ONLINE_WINDOW
            ),
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "preferences": self.prefs(),
        }
        return d


class Category(db.Model):
    """二级分类。parent_id 为空表示父分类；所有分类对所有成员开放（PRD item 5）。"""

    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)
    icon = db.Column(db.String(64))  # emoji 或本地图标路径
    # 分类是否在主页显示（全局生效）：关闭后所有用户的首页/侧边栏都不再出现该分类及其下的链接
    visible = db.Column(db.Boolean, default=True)
    # 分类归属：谁创建的谁拥有。管理员可编辑任意分类；普通成员只能编辑自己创建的分类。
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    # 是否已移入回收站（归档）：归档后前台不再显示，但保留数据可恢复
    archived = db.Column(db.Boolean, default=False)
    # 分类按角色可见的「白名单」（L1b）：逗号分隔 "admin,member"；NULL/空 = 所有角色可见
    allowed_roles = db.Column(db.String(64), nullable=True)
    color = db.Column(db.String(16), default="#6C5CE7")
    description = db.Column(db.String(256))
    position = db.Column(db.Integer, default=0)
    children = db.relationship(
        "Category",
        backref=db.backref("parent", remote_side=[id]),
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def to_dict(self, with_children=False):
        d = {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "icon": self.icon,
            "visible": self.visible is not False,
            "owner_id": self.owner_id,
            "archived": bool(self.archived),
            "allowed_roles": self.allowed_roles or "",
            "color": self.color,
            "description": self.description,
            "position": self.position,
        }
        if with_children:
            d["children"] = [c.to_dict() for c in self.children.order_by(Category.position).all()]
        return d


class Link(db.Model):
    """链接。url_internal / url_external 至少其一；可设独立密码（PRD item 1）。"""

    __tablename__ = "links"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(256))
    url_internal = db.Column(db.String(512))
    url_external = db.Column(db.String(512))
    icon = db.Column(db.String(256))  # 本地路径或 emoji
    has_password = db.Column(db.Boolean, default=False)
    password_hash = db.Column(db.String(128))
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True)
    # 可见权限：all=所有人可见；registered=登录用户可见；admin=仅管理员（及所有者）；self=仅自己
    permission = db.Column(db.String(16), default="all")
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # 可达性探测（系统定时 ping）：ok=可达 / unreachable=无法访问 / None=尚未检测
    ping_status = db.Column(db.String(16), default=None, index=True)
    ping_at = db.Column(db.DateTime, default=None)

    def set_link_password(self, pw):
        self.password_hash = generate_password_hash(pw)
        self.has_password = True

    def check_link_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    def to_dict(self, network="external", user=None):
        """网络模式决定返回哪个 URL（item 8 单 URL 始终显示规则在 API 层处理）。
        has_password 按当前访问用户各自独立判断（每个用户可设置自己的访问密码）。"""
        internal_only = bool(self.url_internal) and not self.url_external
        external_only = bool(self.url_external) and not self.url_internal
        if network == "internal":
            url = self.url_internal or self.url_external
            net = "internal" if self.url_internal else "external"
        else:
            url = self.url_external or self.url_internal
            net = "external" if self.url_external else "internal"
        has_pwd = False
        if user is not None:
            has_pwd = LinkPassword.query.filter_by(link_id=self.id, user_id=user.id).first() is not None
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "url": url,
            "network": net,
            "network_locked": not (internal_only or external_only),  # 双 URL 时随模式切换
            "icon": self.icon,
            "has_password": has_pwd,
            "owner_id": self.owner_id,
            "category_id": self.category_id,
            "permission": self.permission or "all",
        }


class LinkPermission(db.Model):
    """链接可见性权限（PRD item 11）：按角色或具体用户，或公开(everyone)。"""

    __tablename__ = "link_permissions"
    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(db.Integer, db.ForeignKey("links.id"), nullable=False, index=True)
    kind = db.Column(db.String(16), nullable=False)  # user / role（public 已废弃）
    target = db.Column(db.String(64))  # kind=role -> 角色名; kind=user -> 用户名
    deny = db.Column(db.Boolean, default=False)  # False=授予(grant)，True=拒绝(deny)


class LinkPassword(db.Model):
    """每个用户对某链接的独立访问密码（相互独立）。

    link_id + user_id 唯一：同一链接，不同用户可设置各自不同的访问密码。
    """

    __tablename__ = "link_passwords"
    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(db.Integer, db.ForeignKey("links.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    __table_args__ = (db.UniqueConstraint("link_id", "user_id", name="uq_link_user_pwd"),)


def set_user_link_password(link_id, user_id, pw):
    """为某用户设置（或更新）某链接的访问密码。"""
    row = LinkPassword.query.filter_by(link_id=link_id, user_id=user_id).first()
    if not row:
        row = LinkPassword(link_id=link_id, user_id=user_id)
    row.password_hash = generate_password_hash(pw)
    db.session.add(row)
    db.session.commit()


def clear_user_link_password(link_id, user_id):
    """清除某用户在某链接上的访问密码。"""
    row = LinkPassword.query.filter_by(link_id=link_id, user_id=user_id).first()
    if row:
        db.session.delete(row)
        db.session.commit()


def check_user_link_password(link_id, user_id, pw):
    """校验某用户在某链接上的访问密码。"""
    row = LinkPassword.query.filter_by(link_id=link_id, user_id=user_id).first()
    return row is not None and check_password_hash(row.password_hash, pw)


class UserLinkVisibility(db.Model):
    """他人共享给我的链接，是否显示在主页（PRD item 2）。默认显示。"""

    __tablename__ = "user_link_visibility"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    link_id = db.Column(db.Integer, db.ForeignKey("links.id"), nullable=False, index=True)
    show_on_home = db.Column(db.Boolean, default=True)
    __table_args__ = (db.UniqueConstraint("user_id", "link_id"),)


class LinkSort(db.Model):
    """主页卡片排序，按用户独立（PRD item 6）。"""

    __tablename__ = "link_sorts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    link_id = db.Column(db.Integer, db.ForeignKey("links.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    position = db.Column(db.Integer, default=0)


class Setting(db.Model):
    """站点级开关（如：主页拖拽排序是否开启，PRD item 6）。"""

    __tablename__ = "settings"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    # 放宽到 512：图标接口等设置项会存较长的 URL 模板
    value = db.Column(db.String(512), default="")

    @classmethod
    def get(cls, key, default=""):
        row = cls.query.filter_by(key=key).first()
        return row.value if row else default

    @classmethod
    def set(cls, key, value):
        row = cls.query.filter_by(key=key).first()
        if not row:
            row = cls(key=key)
            db.session.add(row)
        row.value = str(value)
        db.session.commit()


class AuditLog(db.Model):
    """权限 / 账号操作的审计日志（谁、在何时、对什么、做了什么）。

    核心动作：
      perm_deny / perm_restore —— 用户维度显式拒绝/恢复
      link_permission           —— 链接基础权限变更（all/registered/admin/self）
      category_update           —— 分类「主页显示 / 角色白名单 / 归档」变更
      user_role / user_ban / user_unban —— 用户角色与启用状态变更
      register_closed           —— 关闭开放注册（站点设置）
    """

    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    operator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    operator_name = db.Column(db.String(64))
    action = db.Column(db.String(32), nullable=False, index=True)
    target_type = db.Column(db.String(32))  # user / link / category / setting / system
    target_id = db.Column(db.Integer, nullable=True)
    target_name = db.Column(db.String(128))
    detail = db.Column(db.String(512))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "operator_id": self.operator_id,
            "operator_name": self.operator_name,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "detail": self.detail or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def visible_links_for(user):
    """返回某用户可见的链接列表。

    按最终权限模型（四层 + 单向放大 + 显式拒绝）判定，公式见 docs/权限模型设计.md：
      L0 账号墙        : 用户被禁用 → 全隐藏
      L1a 分类全局隐藏  : Category.visible=False 或 archived → 该分类下所有链接对所有人隐藏（含管理员）
      L1b 分类角色白名单: Category.allowed_roles 非空时，仅列表内角色可见；空=全员
      L2 链接基础权限  : Link.permission 四选项
      L3 显式授权/拒绝  : LinkPermission(user/role) 的 grant / deny；deny 优先于 grant 与 base

    关键修正（相较旧版）：
      - 分类墙（L1a/L1b）下沉到本函数，所有调用方（/api/links、/api/search 等）一致生效；
      - 删除旧的 `if is_admin: visible=True` 全局豁免，使「分类隐藏对所有人生效（含管理员）」成立；
      - deny 是唯一的「减法」，可在分类可见前提下收回某链接。
    """
    role = user.role if user else "guest"
    uid = user.id if user else None
    # L0 账号墙：仅「被禁用账号」全隐藏；游客(user=None)按 guest 角色正常走四层权限，
    # 不再误伤（原 `user is None` 会让游客主页完全空白，与「游客按权限可见公开分类」矛盾）
    if user is not None and user.is_active is False:
        return []

    # L1a：预计算隐藏分类集合（含「父分类隐藏则其子分类一并隐藏」的联动）
    hidden_cat = set()
    hidden_parents = []
    cat_cache = {}
    for c in Category.query.all():
        cat_cache[c.id] = c
        if c.visible is False or c.archived:
            hidden_cat.add(c.id)
            if c.parent_id is None:
                hidden_parents.append(c.id)
    if hidden_parents:
        for c in Category.query.filter(Category.parent_id.in_(hidden_parents)).all():
            hidden_cat.add(c.id)

    # L3：预加载该用户的显式授权 / 拒绝（user 级 + role 级）
    grant_user, grant_role, deny_user, deny_role = set(), set(), set(), set()
    if uid is not None:
        for p in LinkPermission.query.filter_by(kind="user", target=str(uid)).all():
            (deny_user if p.deny else grant_user).add(p.link_id)
        for p in LinkPermission.query.filter_by(kind="role", target=role).all():
            (deny_role if p.deny else grant_role).add(p.link_id)

    result = []
    for l in Link.query.filter_by(is_active=True).all():
        # L1a 分类全局隐藏：对所有人生效，含管理员；即使有 grant 也无法复活
        if l.category_id in hidden_cat:
            continue
        # L1b 分类角色白名单
        cat = cat_cache.get(l.category_id)
        if cat is not None and cat.allowed_roles:
            allowed = [r.strip() for r in cat.allowed_roles.split(",") if r.strip()]
            if allowed and role not in allowed:
                continue
        # L2 链接基础权限
        perm = (l.permission or "all").strip()
        if perm == "all":
            base = True
        elif perm == "registered":
            base = uid is not None
        elif perm == "admin":
            base = (role == "admin") or (l.owner_id == uid)
        elif perm == "self":
            base = l.owner_id == uid
        else:
            base = True  # 未知值兜底「所有人」
        # L3 显式拒绝优先于授权与基础权限
        if l.id in deny_user or l.id in deny_role:
            visible = False
        else:
            visible = base or (l.id in grant_user) or (l.id in grant_role)
        if visible:
            result.append(l)
    return result


class AccessLog(db.Model):
    """访问 / 行为事件日志（与 AuditLog 分离：本表是高频事件流，不污染低频变更审计）。

    仅记录两类事件：
      click —— 用户点击某个链接（来自 POST /api/links/<id>/track）
      login —— 用户成功登录
    link_id 为 NULL 时表示非链接行为（如 login）。
    """

    __tablename__ = "access_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    link_id = db.Column(db.Integer, db.ForeignKey("links.id"), nullable=True, index=True)
    action = db.Column(db.String(16), nullable=False, index=True)  # click / login
    ip = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "link_id": self.link_id,
            "action": self.action,
            "ip": self.ip,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
