"""Flask 后端入口 + REST API（骨架版）。"""
import base64
import datetime
import json
import logging
import os
import re
import random
import ipaddress
import socket
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

import requests
from werkzeug.utils import secure_filename, safe_join

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from backend.config import Config
from backend.icon_utils import (
    ALLOWED_ICON_EXT,
    DEFAULT_FAVICON_PROVIDER,
    DEFAULT_LAN_CIDRS,
    FAVICON_PROVIDERS,
    USER_AGENT,
    detect_network,
    download_icon,
    localize_icon,
    probe_icon,
    resolve_favicon_candidates,
    resolve_favicon_url,
)
from backend.models import (
    AccessLog,
    AuditLog,
    Category,
    Link,
    LinkPassword,
    LinkPermission,
    LinkSort,
    Setting,
    User,
    UserLinkVisibility,
    check_user_link_password,
    clear_user_link_password,
    db,
    set_user_link_password,
    visible_links_for,
)

app = Flask(__name__, static_folder=None)
logger = logging.getLogger(__name__)

SEARCH_ENGINE_DEFAULTS = [
    {"id": "local", "label": "站内", "url": ""},
    {"id": "google", "label": "Google", "url": "https://www.google.com/search?q={q}"},
    {"id": "baidu", "label": "百度", "url": "https://www.baidu.com/s?wd={q}"},
    {"id": "bing", "label": "必应", "url": "https://www.bing.com/search?q={q}"},
    {"id": "ddg", "label": "DuckDuckGo", "url": "https://duckduckgo.com/?q={q}"},
    {"id": "brave", "label": "Brave", "url": "https://search.brave.com/search?q={q}"},
]


def search_engine_settings():
    """返回经过校验、保留自定义项和顺序的搜索引擎配置。"""
    raw = Setting.get("search_engines", "")
    configured = None
    try:
        parsed = json.loads(raw) if raw else None
        if isinstance(parsed, list):
            configured = parsed
    except (TypeError, ValueError):
        configured = None
    by_id = {item["id"]: item for item in SEARCH_ENGINE_DEFAULTS}
    result = []
    seen = set()
    for item in configured or SEARCH_ENGINE_DEFAULTS:
        if not isinstance(item, dict):
            continue
        engine_id = str(item.get("id", "")).strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,31}", engine_id) or engine_id in seen:
            continue
        if engine_id in by_id:
            base = by_id[engine_id]
        else:
            label = str(item.get("label", "")).strip()
            url = str(item.get("url", "")).strip()
            parsed = urlparse(url)
            if not label or len(label) > 40 or len(url) > 2048 or "{q}" not in url or parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            base = {"id": engine_id, "label": label, "url": url}
        result.append({**base, "enabled": bool(item.get("enabled", True))})
        seen.add(engine_id)
    for item in SEARCH_ENGINE_DEFAULTS:
        if item["id"] not in seen:
            result.append({**item, "enabled": True})
    enabled = [item for item in result if item["enabled"]]
    if not any(item["id"] == "local" for item in enabled):
        next(item for item in result if item["id"] == "local")["enabled"] = True
    return result
app.config.from_object(Config)
if Config.ENV == "production" and (not Config.SECRET_KEY or not Config.TOKEN_SECRET):
    raise RuntimeError("生产环境必须设置 SECRET_KEY 和 TOKEN_SECRET")
# 开发期：禁止前端静态资源缓存，避免 vite build 后浏览器沿用旧 chunk 导致白屏
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
CORS(app, supports_credentials=True, origins=Config.CORS_ORIGINS or ["http://localhost:5001"])
db.init_app(app)

# 启动时幂等迁移（新增列等），确保 gunicorn 直启实例也能补齐 schema
from backend.migrate import run_migrations
run_migrations(app)

serializer = URLSafeTimedSerializer(Config.TOKEN_SECRET)

_rate_limit_events = defaultdict(deque)
_rate_limit_lock = threading.Lock()


def _client_key():
    forwarded = request.headers.get("X-Forwarded-For", "")
    return (forwarded.split(",")[0].strip() or request.remote_addr or "unknown")[:128]


def rate_limited(bucket, limit, window=60, identity=None):
    """轻量进程内限流；生产环境可在反向代理层再配置集中式限流。"""
    now = time.monotonic()
    key = f"{bucket}:{identity or _client_key()}"
    with _rate_limit_lock:
        events = _rate_limit_events[key]
        while events and now - events[0] >= window:
            events.popleft()
        if len(events) >= limit:
            return True
        events.append(now)
    return False


def valid_password(value):
    return isinstance(value, str) and 8 <= len(value) <= 256


def validate_http_url(raw_url, allow_private=None):
    """校验可由服务端访问的 URL，阻止危险协议和本机/链路本地地址。"""
    raw = (raw_url or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        return None, "仅支持不含账号信息的 http/https URL"
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return None, "URL 端口格式无效"
    if not 1 <= port <= 65535:
        return None, "URL 端口范围无效"
    host = parsed.hostname.strip("[]").lower()
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        addresses = []
    if not addresses:
        return None, "主机名无法解析"
    allow_private = Config.ALLOW_PRIVATE_NETWORK_CHECKS if allow_private is None else allow_private
    for addr in {item[4][0] for item in addresses}:
        try:
            ip = ipaddress.ip_address(addr)
            blocked = ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified
            if str(ip) == "169.254.169.254":
                blocked = True
            if blocked or (not allow_private and ip.is_private):
                return None, "不允许访问本机、链路本地或受限网络地址"
        except ValueError:
            continue
    return parsed, None


def token_max_age_seconds():
    """登录有效期（秒），由站点设置 token_max_age_hours 控制，缺省 7 天。"""
    try:
        return int(Setting.get("token_max_age_hours", "168") or 168) * 3600
    except (TypeError, ValueError):
        return Config.TOKEN_MAX_AGE


def _cat_perm_ok(cat, role, uid):
    """L1b 分类权限门禁（与链接权限同构：all/registered/admin/self）。

    all         : 所有人（含游客）可见
    registered  : 登录用户可见
    admin       : 仅管理员与分类所有者可见
    self        : 仅分类所有者可见
    """
    if cat is None:
        return True
    cp = (getattr(cat, "permission", None) or "all").strip()
    if cp == "all":
        return True
    if cp == "registered":
        return uid is not None
    if cp == "admin":
        return role == "admin" or cat.owner_id == uid
    if cp == "self":
        return cat.owner_id == uid
    return True


# ---------- 鉴权辅助 ----------
def make_token(user):
    return serializer.dumps({"uid": user.id})


def current_user():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            data = serializer.loads(token, max_age=token_max_age_seconds())
            return User.query.get(data["uid"])
        except (BadSignature, SignatureExpired, KeyError):
            return None
    return None


def audit(operator, action, target_type, target_id=None, target_name=None, detail=None):
    """写入权限 / 账号操作审计日志。写入失败静默处理，不影响主流程。"""
    try:
        db.session.add(AuditLog(
            operator_id=operator.id if operator else None,
            operator_name=operator.username if operator else "system",
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            detail=detail or "",
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("audit log write failed")


def _cleanup_access_logs():
    """按站点设置 log_retention_days 删除超期访问日志（惰性触发，不依赖外部定时任务）。"""
    try:
        days = int(Setting.get("log_retention_days", "90") or 90)
    except (TypeError, ValueError):
        days = 90
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    try:
        old_ids = [row.id for row in AccessLog.query.with_entities(AccessLog.id).filter(AccessLog.created_at < cutoff).limit(5000).all()]
        if old_ids:
            AccessLog.query.filter(AccessLog.id.in_(old_ids)).delete(synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("access log write failed")


def log_access(user, action, link_id=None):
    """写入访问/行为事件（click / login）。静默失败，不阻塞主流程。
    约每 200 次写入惰性触发一次超期清理。"""
    try:
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
        ip = ip.split(",")[0].strip() if ip else ""
        db.session.add(AccessLog(
            user_id=user.id if user else None,
            link_id=link_id,
            action=action,
            ip=ip,
        ))
        db.session.commit()
        if random.random() < 0.005:
            _cleanup_access_logs()
    except Exception:
        db.session.rollback()
        logger.exception("access log write failed")


def auth_required(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        u = current_user()
        if not u:
            return jsonify({"error": "未登录或登录已过期"}), 401
        # 真实刷新「在线」状态：仅在距上次活跃超过 60 秒时写库，避免高频 commit
        now = datetime.datetime.utcnow()
        if u.last_seen is None or (now - u.last_seen).total_seconds() > 60:
            u.last_seen = now
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        return f(u, *args, **kwargs)

    return wrapper


# ---------- API ----------
@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "product": "云航导航 (Aether Nav)"})


@app.route("/api/auth/login", methods=["POST"])
def login():
    if rate_limited("login", 10, 300):
        return jsonify({"error": "尝试次数过多，请稍后再试"}), 429
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "用户名或密码错误"}), 401
    if user.is_active is False:
        return jsonify({"error": "该账号已被禁用，请联系管理员"}), 403
    user.last_seen = datetime.datetime.utcnow()
    db.session.commit()
    log_access(user, "login")
    return jsonify({"token": make_token(user), "user": user.to_dict()})


@app.route("/api/me")
@auth_required
def me(user):
    return jsonify({"user": user.to_dict()})


# 允许个人修改的偏好键（白名单，防越权写入未定义字段）
_PROFILE_PREF_KEYS = ("network", "theme", "open_new_tab", "weather_city", "color_scheme")


@app.route("/api/me", methods=["PUT"])
@auth_required
def update_me(user):
    """更新当前登录用户自身资料：用户名 / 昵称 / 头像 / 密码 / 个人偏好。
    管理员相关字段（role、is_active）不在此接口处理（由 /api/admin/users 负责）。"""
    data = request.get_json(silent=True) or {}
    changed = []

    # 用户名（唯一校验，不可与他人重复；允许保持原值）
    if "username" in data:
        new_uname = (data["username"] or "").strip()
        if not new_uname:
            return jsonify({"error": "用户名不能为空"}), 400
        if new_uname != user.username:
            if User.query.filter(User.username == new_uname, User.id != user.id).first():
                return jsonify({"error": "用户名已存在"}), 400
            user.username = new_uname
            changed.append("username")

    if "display_name" in data:
        user.display_name = data["display_name"]
        changed.append("display_name")

    if "avatar" in data:
        # 允许：上传路径(/uploads/...)、emoji、Material Symbols 名、或空字符串（清除头像）
        user.avatar = data["avatar"]
        changed.append("avatar")

    # 修改密码：需提供当前密码并校验
    if "current_password" in data and data.get("current_password"):
        if not user.check_password(data["current_password"]):
            return jsonify({"error": "当前密码错误"}), 400
        new_pw = data.get("new_password", "")
        if not valid_password(new_pw):
            return jsonify({"error": "新密码长度需为 8-256 位"}), 400
        user.set_password(new_pw)
        changed.append("password")

    # 个人偏好：合并写入，仅白名单键生效
    if "preferences" in data and isinstance(data["preferences"], dict):
        import json
        prefs = user.prefs()
        for k in _PROFILE_PREF_KEYS:
            if k in data["preferences"]:
                prefs[k] = data["preferences"][k]
        user.preferences = json.dumps(prefs, ensure_ascii=False)
        changed.append("preferences")

    if not changed:
        return jsonify({"user": user.to_dict()})

    db.session.commit()

    # 审计（仅关键项）
    if "username" in changed:
        audit(user, "profile_update", "user", user.id, user.username, "修改用户名")
    if "password" in changed:
        audit(user, "profile_update", "user", user.id, user.username, "修改登录密码")

    return jsonify({"user": user.to_dict()})


@app.route("/api/links/<int:link_id>/track", methods=["POST"])
@auth_required
def track_link(user, link_id):
    """点击埋点：前端在打开链接前异步调用（fire-and-forget）。仅统计存在的活跃链接。"""
    link = Link.query.get(link_id)
    if not link or link.is_active is False:
        return jsonify({"error": "链接不存在"}), 404
    if link not in visible_links_for(user):
        return jsonify({"error": "无权访问该链接"}), 403
    log_access(user, "click", link_id=link_id)
    return jsonify({"ok": True})


@app.route("/api/auth/register", methods=["POST"])
def register():
    # 开放注册开关：关闭后任何人都无法自助注册（私有导航站适用）
    if Setting.get("allow_register", "true") != "true":
        return jsonify({"error": "注册已关闭，请联系管理员开通账号"}), 403
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "用户名与密码必填"}), 400
    if not valid_password(password):
        return jsonify({"error": "密码长度需为 8-256 位"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "用户名已存在"}), 400
    # 新用户默认角色由站点设置决定（缺省 member）
    default_role = Setting.get("default_role", "member")
    if default_role not in ("admin", "member", "guest"):
        default_role = "member"
    u = User(username=username, role=default_role)
    if data.get("display_name"):
        u.display_name = data["display_name"]
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    audit(u, "user_register", "user", u.id, u.username, "自助注册，角色=%s" % default_role)
    return jsonify({"token": make_token(u), "user": u.to_dict()}), 201


@app.route("/api/auth/reset-password", methods=["POST"])
def reset_password():
    if rate_limited("reset-password", 5, 600):
        return jsonify({"error": "尝试次数过多，请稍后再试"}), 429
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    current_pw = data.get("current_password") or ""
    new_pw = data.get("new_password") or ""
    if not username or not valid_password(new_pw):
        return jsonify({"error": "用户名必填，新密码长度需为 8-256 位"}), 400
    u = User.query.filter_by(username=username).first()
    if not u:
        return jsonify({"error": "用户名或验证信息错误"}), 400
    requester = current_user()
    if not current_pw or not u.check_password(current_pw):
        if not requester or requester.role != "admin":
            return jsonify({"error": "需要当前密码，或由管理员执行重置"}), 403
    u.set_password(new_pw)
    db.session.commit()
    audit(requester or u, "password_reset", "user", u.id, u.username, "通过当前密码/管理员授权重置")
    return jsonify({"ok": True})


def hidden_category_ids():
    """返回「不在主页显示」或「已归档」的分类 id 集合（全局生效）。

    父分类被隐藏/归档时，其子分类一并隐藏，保证整个前台都看不到这些分类下的链接。
    """
    hidden = set()
    hidden_parents = []
    for c in Category.query.all():
        if c.visible is False or c.archived:
            hidden.add(c.id)
            if c.parent_id is None:
                hidden_parents.append(c.id)
    if hidden_parents:
        for c in Category.query.filter(Category.parent_id.in_(hidden_parents)).all():
            hidden.add(c.id)
    return hidden


@app.route("/api/categories/tree")
def categories_tree():
    """返回二级分类树（所有分类对所有成员开放），每个节点附带直接链接数与「当前用户可见链接」标记。

    has_links 基于 visible_links_for(user) 计算（与主页 /api/links 同源）：
      仅当该分类(或任一子分类)对当前用户有 ≥1 条可见链接时为 True。
    据此侧边栏可一致地实现「无权限 / 链接全无权限 / 空分类 不显示」(主页显示规则 ①②③)，
    而 Admin 分类管理仍展示全部分类用于维护。
    """
    user = current_user()
    linked_cats = {l.category_id for l in visible_links_for(user)}
    count_rows = db.session.query(Link.category_id, db.func.count(Link.id)).group_by(Link.category_id).all()
    link_counts = {category_id: count for category_id, count in count_rows}
    parents = Category.query.filter_by(parent_id=None).order_by(Category.position).all()
    tree = []
    for p in parents:
        d = p.to_dict(with_children=True)
        d["link_count"] = link_counts.get(p.id, 0)
        d["has_links"] = p.id in linked_cats
        for c in d.get("children", []):
            c["link_count"] = link_counts.get(c["id"], 0)
            c["has_links"] = c["id"] in linked_cats
        tree.append(d)
    return jsonify({"tree": tree})


@app.route("/api/links")
def list_links():
    """返回当前用户可见的链接，按分类分组；支持网络模式与搜索过滤。"""
    user = current_user()
    network = request.args.get("network", "external")
    q = request.args.get("q", "").strip().lower()

    links = visible_links_for(user)
    # 分类级「主页显示」开关（全局生效）：隐藏分类下的链接对所有用户都不展示
    hidden_cats = hidden_category_ids()
    if hidden_cats:
        links = [l for l in links if l.category_id not in hidden_cats]
    # 按用户主页可见性开关过滤（他人链接，PRD item 2）
    if user is not None:
        hidden = {
            v.link_id
            for v in UserLinkVisibility.query.filter_by(user_id=user.id, show_on_home=False)
        }
        links = [l for l in links if l.id not in hidden]

    # 搜索过滤（站内）
    if q:
        links = [l for l in links if q in (l.title or "").lower() or q in (l.description or "").lower()]

    # 按分类分组
    groups = {}
    for l in links:
        groups.setdefault(l.category_id, []).append(l)

    # 应用每用户排序（若有）
    if user is not None:
        sorts = {s.link_id: s.position for s in LinkSort.query.filter_by(user_id=user.id)}
        for cid in groups:
            groups[cid].sort(key=lambda l: sorts.get(l.id, 9999))

    result = []
    for cid, lks in groups.items():
        cat = Category.query.get(cid)
        if not cat:
            continue
        result.append(
            {
                "category": cat.to_dict(),
                "links": [l.to_dict(network=network, user=user) for l in lks],
            }
        )
    # 父分类在前
    result.sort(key=lambda g: (g["category"]["parent_id"] or 0, g["category"].get("position", 0)))
    return jsonify({"groups": result, "network": network, "count": sum(len(g["links"]) for g in result)})


@app.route("/api/search")
def search():
    """站内搜索（同 /api/links 但只返回扁平列表，供搜索下拉使用）。"""
    user = current_user()
    q = request.args.get("q", "").strip().lower()
    links = visible_links_for(user)
    hidden_cats = hidden_category_ids()
    if hidden_cats:
        links = [l for l in links if l.category_id not in hidden_cats]
    if q:
        links = [l for l in links if q in (l.title or "").lower() or q in (l.description or "").lower()]
    return jsonify({"results": [l.to_dict(user=user) for l in links][:20]})


def _host_port_key(url):
    """归一化 URL 为 `host:port`（含默认端口），用于「域名+端口」去重；非法/空返回空串。"""
    if not url:
        return ""
    try:
        p = urlparse(url)
        if not p.hostname:
            return ""
        port = p.port
        if not port:
            port = 443 if p.scheme == "https" else 80
        return f"{p.hostname.lower()}:{port}"
    except Exception:
        return ""


def validate_link_url(raw_url):
    value = (raw_url or "").strip()
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        return "链接地址必须是 http:// 或 https://，且不能包含账号信息"
    if len(value) > 2048:
        return "链接地址不能超过 2048 个字符"
    try:
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            return "链接端口范围无效"
    except ValueError:
        return "链接端口格式无效"
    return None


@app.route("/api/links", methods=["POST"])
@auth_required
def create_link(user):
    """快速添加链接（PRD item 16）。父分类下已有子分类时禁止直接挂链接（item 9）。"""
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "标题必填"}), 400
    category_id = data.get("category_id")
    if not category_id:
        return jsonify({"error": "必须选择分类"}), 400
    for field in ("url_internal", "url_external"):
        url_error = validate_link_url(data.get(field))
        if url_error:
            return jsonify({"error": url_error}), 400
    cat = Category.query.get(category_id)
    if not cat:
        return jsonify({"error": "分类不存在"}), 404
    if cat.parent_id is None and cat.children.count() > 0:
        return jsonify({"error": "该父分类下已有子分类，请添加到子分类"}), 400
    # 域名+端口去重：内网/外网 URL 任一命中已存在链接则拒绝（兜底防护，前端按钮也会预禁用）
    new_keys = {k for k in (_host_port_key(data.get("url_internal")), _host_port_key(data.get("url_external"))) if k}
    if new_keys:
        for existing in Link.query.all():
            ek = {_host_port_key(existing.url_internal), _host_port_key(existing.url_external)} & new_keys
            if ek:
                return jsonify({"error": f"该地址（域名+端口）已存在链接：{existing.title or '未命名'}（{sorted(ek)[0]}）"}), 409
    # 图标：按输入框里的地址（网址 / 本地文件路径）落地到本地，失败则留空由展示层兜底
    icon_value, icon_err = localize_icon(data.get("icon"), user.id)
    link = Link(
        title=title,
        description=data.get("description", ""),
        url_internal=data.get("url_internal"),
        url_external=data.get("url_external"),
        icon=icon_value,
        owner_id=user.id,
        category_id=category_id,
    )
    perm = data.get("permission")
    if perm in ("all", "registered", "admin", "self"):
        link.permission = perm
    db.session.add(link)
    db.session.commit()
    # 每个用户为自己设置独立的访问密码（相互独立）
    if data.get("password"):
        set_user_link_password(link.id, user.id, data["password"])
    resp = {"link": link.to_dict(user=user)}
    if icon_err:
        resp["icon_error"] = icon_err
    return jsonify(resp), 201


@app.route("/api/links/<int:link_id>/unlock", methods=["POST"])
def unlock_link(link_id):
    """验证链接密码（PRD item 1）。密码为每个用户独立设置，按当前登录用户校验。"""
    link = Link.query.get_or_404(link_id)
    user = current_user()
    if user is None:
        # 未登录用户无「个人密码」概念，视为无需密码
        return jsonify({"ok": True})
    data = request.get_json(silent=True) or {}
    if not check_user_link_password(link.id, user.id, data.get("password", "")):
        return jsonify({"ok": False, "error": "密码错误"}), 401
    return jsonify({"ok": True})


# ---------- 链接：排序 / 显隐 / 更新 / 删除 ----------
@app.route("/api/links/reorder", methods=["POST"])
@auth_required
def reorder_links(user):
    """保存主页卡片排序，按用户独立（PRD item 6）。"""
    data = request.get_json(silent=True) or {}
    category_id = data.get("category_id")
    ordered_ids = data.get("ordered_ids", [])
    if not category_id or not isinstance(ordered_ids, list) or len(ordered_ids) > 500:
        return jsonify({"error": "参数错误"}), 400
    try:
        ordered_ids = [int(lid) for lid in ordered_ids]
    except (TypeError, ValueError):
        return jsonify({"error": "排序链接参数错误"}), 400
    visible_ids = {link.id for link in visible_links_for(user) if link.category_id == category_id}
    if set(ordered_ids) - visible_ids:
        return jsonify({"error": "排序列表包含不可见链接"}), 403
    LinkSort.query.filter_by(user_id=user.id, category_id=category_id).delete()
    for pos, lid in enumerate(ordered_ids):
        db.session.add(LinkSort(user_id=user.id, link_id=lid, category_id=category_id, position=pos))
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/links/<int:link_id>/visibility", methods=["POST"])
@auth_required
def toggle_visibility(user, link_id):
    """他人共享给我的链接，是否显示在主页（PRD item 2）。按当前用户独立存储。"""
    link = Link.query.get_or_404(link_id)
    data = request.get_json(silent=True) or {}
    show = bool(data.get("show_on_home", True))
    row = UserLinkVisibility.query.filter_by(user_id=user.id, link_id=link_id).first()
    if not row:
        row = UserLinkVisibility(user_id=user.id, link_id=link_id)
        db.session.add(row)
    row.show_on_home = show
    db.session.commit()
    return jsonify({"ok": True, "show_on_home": show})


def _can_edit_link(user, link):
    return user.role == "admin" or link.owner_id == user.id


@app.route("/api/links/<int:link_id>", methods=["GET"])
@auth_required
def get_link(user, link_id):
    # 编辑弹窗预填用：返回完整字段（含 url_external/url_internal 双 URL），
    # 鉴权与 update_link 一致，仅链接可编辑者可见。
    link = Link.query.get_or_404(link_id)
    if not _can_edit_link(user, link):
        return jsonify({"error": "无权限"}), 403
    return jsonify({
        "id": link.id,
        "title": link.title,
        "description": link.description,
        "url_external": link.url_external or "",
        "url_internal": link.url_internal or "",
        "icon": link.icon or "",
        "category_id": link.category_id,
        "permission": link.permission or "all",
    })


@app.route("/api/links/<int:link_id>", methods=["PUT"])
@auth_required
def update_link(user, link_id):
    link = Link.query.get_or_404(link_id)
    data = request.get_json(silent=True) or {}
    can_edit = _can_edit_link(user, link)
    # 普通成员（非 owner）仅允许为「自己对该链接的访问」设置/清除独立密码；
    # 其余字段（标题/URL/分类/权限等）仍受 owner/admin 限制。
    if not can_edit:
        if "password" in data:
            pw = data["password"]
            if pw:
                set_user_link_password(link.id, user.id, pw)
            else:
                clear_user_link_password(link.id, user.id)
            return jsonify({"link": link.to_dict(user=user)})
        return jsonify({"error": "无权限"}), 403
    old_perm = link.permission
    if "title" in data:
        link.title = data["title"]
    if "description" in data:
        link.description = data["description"]
    if "url_internal" in data:
        url_error = validate_link_url(data.get("url_internal"))
        if url_error:
            return jsonify({"error": url_error}), 400
        link.url_internal = data["url_internal"] or None
    if "url_external" in data:
        url_error = validate_link_url(data.get("url_external"))
        if url_error:
            return jsonify({"error": url_error}), 400
        link.url_external = data["url_external"] or None
    icon_err = None
    if "icon" in data:
        # 依据输入框中的地址重新落地图标；与原值相同则不重复下载
        new_icon = (data["icon"] or "").strip()
        if new_icon != (link.icon or ""):
            link.icon, icon_err = localize_icon(new_icon, user.id)
    if "category_id" in data and data["category_id"]:
        cat = Category.query.get(data["category_id"])
        if not cat:
            return jsonify({"error": "分类不存在"}), 404
        if cat.parent_id is None and cat.children.count() > 0:
            return jsonify({"error": "该父分类下已有子分类，请添加到子分类"}), 400
        link.category_id = data["category_id"]
    if "password" in data:
        pw = data["password"]
        if pw:
            # 为当前用户设置（更新）独立访问密码
            set_user_link_password(link.id, user.id, pw)
        else:
            # 空字符串 = 清除当前用户的访问密码
            clear_user_link_password(link.id, user.id)
    perm_changed = False
    if "permission" in data and data["permission"] in ("all", "registered", "admin", "self"):
        link.permission = data["permission"]
        perm_changed = data["permission"] != old_perm
    db.session.commit()
    if perm_changed:
        audit(user, "link_permission", "link", link.id, link.title,
              "基础权限 %s → %s" % (old_perm, link.permission))
    resp = {"link": link.to_dict(user=user)}
    if icon_err:
        resp["icon_error"] = icon_err
    return jsonify(resp)


@app.route("/api/links/<int:link_id>", methods=["DELETE"])
@auth_required
def delete_link(user, link_id):
    link = Link.query.get_or_404(link_id)
    if not _can_edit_link(user, link):
        return jsonify({"error": "无权限"}), 403
    db.session.delete(link)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/links/batch", methods=["POST"])
@auth_required
def batch_update_links(user):
    """批量更新链接：权限（仅链接可编辑者）+ 是否主页显示（按当前用户独立存储）。

    body: { ids: [int], permission?: 'all'|'registered'|'admin'|'self', show_on_home?: bool }
    """
    data = request.get_json(silent=True) or {}
    ids = data.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "请选择至少一个链接"}), 400
    perm = data.get("permission")
    show = data.get("show_on_home")
    if perm is not None and perm not in ("all", "registered", "admin", "self"):
        return jsonify({"error": "权限值非法"}), 400
    updated = 0
    for raw in ids:
        try:
            lid = int(raw)
        except (TypeError, ValueError):
            continue
        link = Link.query.get(lid)
        if not link:
            continue
        can_edit = _can_edit_link(user, link)
        if perm is not None and can_edit:
            if link.permission != perm:
                audit(user, "link_permission", "link", link.id, link.title,
                      "批量：基础权限 %s → %s" % (link.permission, perm))
            link.permission = perm
        if show is not None:
            row = UserLinkVisibility.query.filter_by(user_id=user.id, link_id=link.id).first()
            if not row:
                row = UserLinkVisibility(user_id=user.id, link_id=link.id)
                db.session.add(row)
            row.show_on_home = bool(show)
        updated += 1
    db.session.commit()
    return jsonify({"ok": True, "updated": updated})


# ---------- 分类：CRUD / 重排 ----------
@app.route("/api/categories", methods=["POST"])
@auth_required
def create_category(user):
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "名称必填"}), 400
    parent_id = data.get("parent_id")
    parent = None
    if parent_id:
        parent = Category.query.get(parent_id)
        if not parent:
            return jsonify({"error": "父分类不存在"}), 404
        if parent.parent_id is not None:
            return jsonify({"error": "只支持两级分类"}), 400
    base_pos = (db.session.query(db.func.max(Category.position)).scalar() or 0) + 1
    allowed_roles = data.get("allowed_roles")
    if isinstance(allowed_roles, list):
        allowed_roles = ",".join([str(r) for r in allowed_roles])
    # 分类权限（与链接一致）：新建子分类继承父分类权限；否则默认 registered（item 9）
    raw_perm = data.get("permission")
    if not raw_perm and parent is not None:
        raw_perm = parent.permission or "registered"
    perm = (raw_perm or "registered").strip()
    if perm not in ("all", "registered", "admin", "self"):
        perm = "registered"
    cat = Category(
        name=name,
        parent_id=parent_id,
        icon=data.get("icon", "📁"),
        visible=bool(data.get("visible", True)),
        owner_id=user.id,
        archived=False,
        allowed_roles=allowed_roles or None,
        permission=perm,
        color=data.get("color", "#6C5CE7"),
        description=data.get("description", ""),
        position=base_pos,
    )
    db.session.add(cat)
    db.session.commit()
    return jsonify({"category": cat.to_dict(with_children=True)}), 201


def _can_edit_category(user, cat):
    """仅管理员可编辑/删除分类；普通成员只能创建分类，不能修改（含自己创建的）。"""
    return user.role == "admin"


@app.route("/api/categories/<int:cat_id>", methods=["PUT"])
@auth_required
def update_category(user, cat_id):
    cat = Category.query.get_or_404(cat_id)
    if not _can_edit_category(user, cat):
        return jsonify({"error": "无权限：只能编辑自己创建的分类"}), 403
    data = request.get_json(silent=True) or {}
    if "name" in data:
        cat.name = data["name"]
    if "icon" in data:
        cat.icon = data["icon"]
    if "color" in data:
        cat.color = data["color"]
    if "description" in data:
        cat.description = data["description"]
    # 「主页显示」仅管理员可设置
    old_visible = cat.visible
    old_ar = cat.allowed_roles
    old_archived = cat.archived
    if "visible" in data and user.role == "admin":
        cat.visible = bool(data["visible"])
    # 分类角色白名单（L1b，旧模型，已废弃）：仅管理员可设置
    if "allowed_roles" in data and user.role == "admin":
        ar = data["allowed_roles"]
        if isinstance(ar, list):
            ar = ",".join([str(r) for r in ar])
        cat.allowed_roles = ar or None
    # 分类权限（与链接一致：all/registered/admin/self）：仅管理员可设置
    old_perm = cat.permission
    if "permission" in data and user.role == "admin":
        p = (data["permission"] or "all").strip()
        if p in ("all", "registered", "admin", "self"):
            cat.permission = p
    # 回收站（归档）状态：编辑者本人或管理员可改
    if "archived" in data:
        cat.archived = bool(data["archived"])
    if "parent_id" in data:
        new_parent = data.get("parent_id")
        if new_parent is not None:
            if new_parent == cat.id:
                return jsonify({"error": "不能将自己设为上级分类"}), 400
            parent = Category.query.get(new_parent)
            if not parent:
                return jsonify({"error": "上级分类不存在"}), 404
            if parent.parent_id is not None:
                return jsonify({"error": "只支持两级分类，上级分类不能是子分类"}), 400
            # 原本是父分类（含子分类）被改为子分类时，把它的子分类提升为顶级，避免产生第三级
            if cat.parent_id is None:
                for child in cat.children.all():
                    child.parent_id = None
        cat.parent_id = new_parent
    db.session.commit()
    parts = []
    if "visible" in data and user.role == "admin" and cat.visible != old_visible:
        parts.append("主页显示 %s→%s" % (old_visible, cat.visible))
    if "allowed_roles" in data and user.role == "admin" and cat.allowed_roles != old_ar:
        parts.append("角色白名单 %s→%s" % (old_ar or "全员", cat.allowed_roles or "全员"))
    if "permission" in data and user.role == "admin" and cat.permission != old_perm:
        parts.append("分类权限 %s→%s" % (old_perm or "all", cat.permission or "all"))
    if "archived" in data and cat.archived != old_archived:
        parts.append("归档 %s→%s" % (old_archived, cat.archived))
    if parts:
        audit(user, "category_update", "category", cat.id, cat.name, "；".join(parts))
    return jsonify({"category": cat.to_dict(with_children=True)})


@app.route("/api/admin/categories/batch", methods=["POST"])
@auth_required
def batch_update_categories(user):
    """批量更新分类权限（仅管理员）。body: { ids: [int], permission: 'all'|'registered'|'admin'|'self' }"""
    if user.role != "admin":
        return jsonify({"error": "无权限：仅管理员可批量修改分类权限"}), 403
    data = request.get_json(silent=True) or {}
    ids = data.get("ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "请选择至少一个分类"}), 400
    perm = data.get("permission")
    if perm not in ("all", "registered", "admin", "self"):
        return jsonify({"error": "权限值非法"}), 400
    updated = 0
    for raw in ids:
        try:
            cid = int(raw)
        except (TypeError, ValueError):
            continue
        cat = Category.query.get(cid)
        if not cat:
            continue
        if cat.permission != perm:
            audit(user, "category_update", "category", cat.id, cat.name,
                  "批量：分类权限 %s→%s" % (cat.permission or "all", perm))
        cat.permission = perm
        updated += 1
    db.session.commit()
    return jsonify({"ok": True, "updated": updated})


@app.route("/api/categories/<int:cat_id>", methods=["DELETE"])
@auth_required
def delete_category(user, cat_id):
    cat = Category.query.get_or_404(cat_id)
    if not _can_edit_category(user, cat):
        return jsonify({"error": "无权限：仅管理员可修改或删除分类"}), 403
    data = request.get_json(silent=True) or {}
    move_to = data.get("move_to")
    delete_links = data.get("delete_links", False)
    archive = data.get("archive", False)
    link_count = Link.query.filter_by(category_id=cat.id).count()
    child_count = cat.children.count()

    # 默认（也是删除弹窗的默认选项）：移动到回收站（归档），保留数据与链接，可恢复
    if archive:
        cat.archived = True
        db.session.commit()
        return jsonify({"ok": True, "archived": True, "link_count": link_count, "child_count": child_count})

    if move_to:
        # 移动到其他分类：链接改挂目标，子分类提升为顶级（保持两级）
        target = Category.query.get(move_to)
        if not target:
            return jsonify({"error": "目标分类不存在"}), 404
        if target.id == cat.id:
            return jsonify({"error": "不能移动到自身"}), 400
        for l in Link.query.filter_by(category_id=cat.id).all():
            l.category_id = target.id
        for ch in cat.children.all():
            ch.parent_id = None
        db.session.delete(cat)
        db.session.commit()
        return jsonify({"ok": True, "moved_links": link_count, "promoted_children": child_count})

    if delete_links:
        # 彻底删除：连同链接与子分类一起删除
        for l in Link.query.filter_by(category_id=cat.id).all():
            db.session.delete(l)
        for ch in cat.children.all():
            db.session.delete(ch)
        db.session.delete(cat)
        db.session.commit()
        return jsonify({"ok": True, "deleted_links": link_count, "deleted_children": child_count})

    # 未指定处理方式：有内容时阻止并给出数量，由前端引导用户选择
    if link_count > 0 or child_count > 0:
        return jsonify({
            "error": "该分类下还有内容，请选择处理方式",
            "link_count": link_count,
            "child_count": child_count,
        }), 400
    db.session.delete(cat)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/categories/reorder", methods=["POST"])
@auth_required
def reorder_categories(user):
    data = request.get_json(silent=True) or {}
    ordered = data.get("ordered", [])
    if user.role != "admin" or not isinstance(ordered, list) or len(ordered) > 500:
        return jsonify({"error": "无权限或排序参数无效"}), 403
    seen = set()
    for item in ordered:
        if not isinstance(item, dict):
            return jsonify({"error": "排序参数无效"}), 400
        cat = Category.query.get(item.get("id"))
        if not cat or cat.id in seen:
            return jsonify({"error": "排序列表包含无效分类"}), 400
        try:
            position = int(item.get("position", 0))
        except (TypeError, ValueError):
            return jsonify({"error": "排序位置无效"}), 400
        cat.position = max(0, min(position, 100000))
        seen.add(cat.id)
    db.session.commit()
    return jsonify({"ok": True})


# ---------- 图标：解析地址 / 上传 / 提交时落地到本地（PRD item 10） ----------
# 纯逻辑在 backend/icon_utils.py，便于脱离 Flask 单测


def favicon_conf():
    """读取系统设置里管理员选定的图标获取接口。"""
    return (
        Setting.get("favicon_provider", DEFAULT_FAVICON_PROVIDER) or DEFAULT_FAVICON_PROVIDER,
        Setting.get("favicon_custom_url", "") or "",
    )


@app.route("/api/icon/providers")
def icon_providers():
    """图标获取接口清单（供新增/编辑链接弹窗里的下拉选择，含占位符说明）。"""
    provider, custom = favicon_conf()
    return jsonify({
        "providers": FAVICON_PROVIDERS,
        "default": DEFAULT_FAVICON_PROVIDER,
        "current": provider,
        "custom_url": custom,
    })


@app.route("/api/icon/resolve", methods=["POST"])
@auth_required
def resolve_icon(user):
    """解析出图标地址填入输入框（不落地文件，落地在提交表单时进行）。

    前端可在新增/编辑链接弹窗里临时选择接口，传 provider / custom_url 覆盖站点默认；
    未传则使用站点默认接口。会快速探测一次选定接口是否真的能取到图，
    取不到则自动退到站点自身 /favicon.ico。
    """
    data = request.get_json(silent=True) or {}
    # 弹窗里可临时覆盖接口；不传则用站点默认（favicon_conf 读设置）
    provider = (data.get("provider") or "").strip()
    custom = (data.get("custom_url") or "").strip()
    if not provider:
        provider, custom = favicon_conf()
    candidates = resolve_favicon_candidates(data.get("url", ""), provider, custom)
    if not candidates:
        return jsonify({"error": "无法从该 URL 解析出域名"}), 400
    last_err = ""
    for idx, url in enumerate(candidates):
        _, _, err = probe_icon(url, timeout=6)
        if not err:
            return jsonify({"icon_url": url, "provider": provider, "fallback": idx > 0})
        last_err = err
    # 都探测失败：仍把首选地址填进去，让用户可以自行改
    return jsonify({
        "icon_url": candidates[0],
        "provider": provider,
        "fallback": False,
        "warning": f"接口未取到图标（{last_err}），可尝试切换其它图标接口",
    })


@app.route("/api/admin/icon/test", methods=["POST"])
@auth_required
def test_icon_provider(user):
    """试跑一次图标接口：解析地址 → 实际请求 → 返回预览，不落地。"""
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    sample = (data.get("url") or "github.com").strip()
    provider = (data.get("provider") or "").strip() or DEFAULT_FAVICON_PROVIDER
    custom = data.get("custom_url") or ""
    icon_url = resolve_favicon_url(sample, provider, custom)
    if not icon_url:
        return jsonify({"ok": False, "error": "无法从该地址解析出域名"}), 400
    started = time.time()
    content, ct, err = probe_icon(icon_url)
    elapsed = int((time.time() - started) * 1000)
    if err:
        return jsonify({"ok": False, "icon_url": icon_url, "elapsed_ms": elapsed, "error": err})
    mime = (ct or "").split(";")[0].strip() or "image/png"
    preview = "data:%s;base64,%s" % (mime, base64.b64encode(content).decode("ascii"))
    return jsonify({
        "ok": True,
        "icon_url": icon_url,
        "elapsed_ms": elapsed,
        "size": len(content),
        "content_type": mime,
        "preview": preview,
    })


@app.route("/api/upload/icon", methods=["POST"])
@auth_required
def upload_icon(user):
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "未找到文件"}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    # 裁剪后上传的是 Blob（无文件名/扩展名），按 MIME 兜底推断
    if ext not in ALLOWED_ICON_EXT:
        mime = (f.mimetype or "").lower()
        ext = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/webp": ".webp",
            "image/svg+xml": ".svg",
            "image/x-icon": ".ico",
            "image/vnd.microsoft.icon": ".ico",
        }.get(mime, "")
    if ext not in ALLOWED_ICON_EXT:
        return jsonify({"error": "不支持的图片格式"}), 400
    content = f.read(Config.MAX_CONTENT_LENGTH + 1)
    from backend.icon_utils import valid_icon_content
    if len(content) > Config.MAX_CONTENT_LENGTH:
        return jsonify({"error": "图标文件超过 2MB"}), 413
    if not valid_icon_content(content, f.mimetype, f.filename):
        return jsonify({"error": "图片内容校验失败，仅支持有效 PNG/JPG/WEBP/ICO 或安全 SVG"}), 400
    fname = f"icon_{user.id}_{int(time.time() * 1000)}{ext}"
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    with open(os.path.join(Config.UPLOAD_FOLDER, secure_filename(fname)), "wb") as out:
        out.write(content)
    return jsonify({"path": f"/uploads/{fname}"})


@app.route("/api/fetch-icon", methods=["POST"])
@auth_required
def fetch_icon(user):
    """抓取并落地图标（分类图标在用），走站点默认或调用方指定的图标接口。"""
    data = request.get_json(silent=True) or {}
    url = data.get("url", "")
    if not url:
        return jsonify({"error": "缺少 url"}), 400
    normalized_url = url if urlparse(url).scheme else "http://" + url
    _, url_error = validate_http_url(normalized_url)
    if url_error:
        return jsonify({"error": url_error}), 400
    provider, custom = favicon_conf()
    candidates = resolve_favicon_candidates(normalized_url, provider, custom)
    if not candidates:
        return jsonify({"error": "无法解析域名"}), 400
    err = ""
    for icon_url in candidates:
        path, err = download_icon(user.id, icon_url)
        if not err:
            return jsonify({"path": path})
    return jsonify({"error": err or "自动获取图标失败"}), 502


def _extract_title(html):
    """从 HTML 里提取 <title> 或 og:title，best-effort，不依赖第三方解析库。"""
    if not html:
        return ""
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    if m:
        title = m.group(1).strip()
    if not title:
        m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']', html, re.I | re.S)
        if m:
            title = m.group(1).strip()
    # 去掉换行与多余空白
    title = re.sub(r"\s+", " ", title).strip()
    return title


@app.route("/api/fetch-link-meta", methods=["POST"])
@auth_required
def fetch_link_meta(user):
    """快速添加：识别 URL 的网络属性（局域网/互联网），抓取标题与图标候选地址。"""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "缺少 url"}), 400
    url = url if urlparse(url).scheme else "http://" + url
    _, url_error = validate_http_url(url)
    if url_error:
        return jsonify({"error": url_error}), 400
    # 局域网网段：管理员可在系统设置里追加自定义网段
    lan_cidrs_raw = Setting.get("lan_cidrs", "") or ""
    lan_cidrs = [c for c in re.split(r"[\s,;]+", lan_cidrs_raw) if c]
    network = detect_network(url, lan_cidrs)

    # 抓取页面标题（best-effort，超时/失败不影响网络判断与图标）
    title = ""
    try:
        parsed = urlparse(url if "//" in url else "//" + url, scheme="http")
        scheme = parsed.scheme or "http"
        fetch_url = f"{scheme}://{parsed.netloc}{parsed.path or '/'}"
        resp = requests.get(
            fetch_url,
            headers={"User-Agent": USER_AGENT},
            timeout=6,
            allow_redirects=False,
            stream=True,
        )
        html_parts = []
        total = 0
        for chunk in resp.iter_content(4096, decode_unicode=True):
            if chunk:
                html_parts.append(chunk)
                total += len(chunk)
                if total > 200000:
                    break
        title = _extract_title("".join(html_parts) or (resp.text or "")[:200000])
    except Exception:
        title = ""

    # 图标候选地址（选定接口 → 站点自身 /favicon.ico）
    provider, custom = favicon_conf()
    candidates = resolve_favicon_candidates(url, provider, custom)
    icon_url = candidates[0] if candidates else ""

    return jsonify({
        "url": url,
        "network": network,
        "title": title,
        "icon_url": icon_url,
    })


# ---------- 站点设置（拖拽排序开关，PRD item 6） ----------
@app.route("/api/settings")
def get_settings():
    try:
        columns = int(Setting.get("columns", "4") or 4)
    except (TypeError, ValueError):
        columns = 4
    engines = search_engine_settings()
    enabled_external = [item["id"] for item in engines if item["enabled"] and item["id"] != "local"]
    configured_default = str(Setting.get("default_engine", "google") or "google").lower()
    configured_default = {item["label"].lower(): item["id"] for item in SEARCH_ENGINE_DEFAULTS}.get(configured_default, configured_default)
    default_engine = configured_default if configured_default in enabled_external else (enabled_external[0] if enabled_external else "google")
    return jsonify({
        "drag_sort_enabled": Setting.get("drag_sort_enabled", "true") == "true",
        "default_engine": default_engine,
        "search_engines": engines,
        "open_new_tab": Setting.get("open_new_tab", "true") == "true",
        "density": Setting.get("density", "comfortable"),
        # 搜索框位置：fixed=固定顶部 / scrolling=随内容滚动
        "search_box_pos": Setting.get("search_box_pos", "fixed"),
        "columns": columns,
        "compact_mode": Setting.get("compact_mode", "false") == "true",
        "allow_home_edit": Setting.get("allow_home_edit", "true") == "true",
        # 图标获取接口（管理员可在系统设置里切换，Google 在国内需要代理）
        "favicon_provider": Setting.get("favicon_provider", DEFAULT_FAVICON_PROVIDER),
        "favicon_custom_url": Setting.get("favicon_custom_url", ""),
        # 账号与安全
        "allow_register": Setting.get("allow_register", "true") == "true",
        "default_role": Setting.get("default_role", "member"),
        # 站点默认主题 / 网络（无个人偏好时的兜底默认值）
        "theme": Setting.get("theme", "light"),
        "network": Setting.get("network", "external"),
        # 站点默认配色方案（accent palette）：default / macaron / sunset / mint / cosmic / berry
        "color_scheme": Setting.get("color_scheme", "default"),
        # 站点级开关：是否将分类颜色应用到首页图标
        "show_category_colors": Setting.get("show_category_colors", "false") == "true",
        # 主页侧边栏是否显示「个人设置 / 管理后台」入口（点击头像菜单也会用到）
        "show_personal_settings": Setting.get("show_personal_settings", "true") == "true",
        "show_admin_console": Setting.get("show_admin_console", "true") == "true",
        # 是否在前端卡片上显示「密码锁」标识（仅影响显示，不影响密码功能本身）
        "show_password_lock": Setting.get("show_password_lock", "true") == "true",
        # 局域网网段（自定义，用于快速添加时识别内网地址）
        "lan_cidrs": Setting.get("lan_cidrs", "") or "",
        # 站点品牌（自定义 logo / 名称 / 副标题，系统设置第三列「站点品牌」）
        "site_name": Setting.get("site_name", "云航导航") or "云航导航",
        "site_subtitle": Setting.get("site_subtitle", "") or "",
        "site_logo": Setting.get("site_logo", "") or "",
        "token_max_age_hours": int(Setting.get("token_max_age_hours", "168") or 168),
        # 访问日志保留天数（用于统计页数据清理）
        "log_retention_days": int(Setting.get("log_retention_days", "90") or 90),
    })


@app.route("/api/admin/settings", methods=["PUT"])
@auth_required
def update_settings(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    whitelist = {
        "drag_sort_enabled", "default_engine", "search_engines", "open_new_tab", "theme",
        "network", "density", "search_box_pos", "columns", "compact_mode",
        "allow_home_edit", "favicon_provider", "favicon_custom_url",
        "allow_register", "default_role", "token_max_age_hours",
        "log_retention_days", "show_personal_settings", "show_admin_console",
        "lan_cidrs", "show_password_lock", "color_scheme", "show_category_colors",
        "site_name", "site_subtitle", "site_logo",
    }
    saved = {}
    bool_keys = {
        "drag_sort_enabled", "open_new_tab", "compact_mode", "allow_home_edit",
        "allow_register", "show_personal_settings", "show_admin_console",
        "show_password_lock", "show_category_colors",
    }
    int_ranges = {"columns": (1, 8), "token_max_age_hours": (1, 24 * 30), "log_retention_days": (1, 3650)}
    enum_values = {
        "theme": {"light", "dark", "system"}, "network": {"external", "internal"},
        "density": {"comfortable", "compact"}, "search_box_pos": {"fixed", "scrolling"},
        "default_role": {"admin", "member", "guest"},
        "color_scheme": {"default", "macaron", "sunset", "mint", "cosmic", "berry"},
    }
    if "default_engine" in data:
        legacy_labels = {item["label"].lower(): item["id"] for item in SEARCH_ENGINE_DEFAULTS}
        engine = str(data["default_engine"]).strip().lower()
        engine = legacy_labels.get(engine, engine)
        if engine == "local" or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,31}", engine):
            return jsonify({"error": "默认搜索引擎无效"}), 400
        data["default_engine"] = engine
    if "search_engines" in data:
        incoming = data["search_engines"]
        valid_ids = {item["id"] for item in SEARCH_ENGINE_DEFAULTS}
        if not isinstance(incoming, list) or not incoming or len(incoming) > 50:
            return jsonify({"error": "搜索引擎配置格式无效"}), 400
        normalized = []
        seen = set()
        for item in incoming:
            if not isinstance(item, dict):
                return jsonify({"error": "搜索引擎配置格式无效"}), 400
            engine_id = str(item.get("id", "")).strip().lower()
            if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,31}", engine_id) or engine_id in seen:
                return jsonify({"error": "搜索引擎列表包含重复或非法项"}), 400
            if engine_id in valid_ids:
                label = next(base["label"] for base in SEARCH_ENGINE_DEFAULTS if base["id"] == engine_id)
                url = next(base["url"] for base in SEARCH_ENGINE_DEFAULTS if base["id"] == engine_id)
            else:
                label = str(item.get("label", "")).strip()
                url = str(item.get("url", "")).strip()
                parsed = urlparse(url)
                if not label or len(label) > 40 or len(url) > 2048 or "{q}" not in url or parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    return jsonify({"error": "自定义搜索引擎名称或 URL 无效，URL 必须包含 {q}"}), 400
            normalized.append({"id": engine_id, "label": label, "url": url, "enabled": bool(item.get("enabled", True))})
            seen.add(engine_id)
        if not any(item["id"] == "local" and item["enabled"] for item in normalized):
            return jsonify({"error": "站内搜索不能被关闭"}), 400
        default_engine = str(data.get("default_engine", Setting.get("default_engine", "google"))).strip().lower()
        default_engine = {item["label"].lower(): item["id"] for item in SEARCH_ENGINE_DEFAULTS}.get(default_engine, default_engine)
        if not any(item["id"] == default_engine and item["enabled"] for item in normalized):
            return jsonify({"error": "默认搜索引擎必须处于启用状态"}), 400
        data["search_engines"] = normalized
    for k in whitelist:
        if k in data:
            val = data[k]
            if k in bool_keys and not isinstance(val, bool):
                return jsonify({"error": f"设置 {k} 必须是布尔值"}), 400
            if k in int_ranges and (isinstance(val, bool) or not isinstance(val, int) or not int_ranges[k][0] <= val <= int_ranges[k][1]):
                return jsonify({"error": f"设置 {k} 超出允许范围"}), 400
            if k in enum_values and val not in enum_values[k]:
                return jsonify({"error": f"设置 {k} 的值无效"}), 400
            if k in {"site_name", "site_subtitle", "favicon_custom_url", "lan_cidrs"} and (not isinstance(val, str) or len(val) > 2048):
                return jsonify({"error": f"设置 {k} 长度或类型无效"}), 400
            if isinstance(val, bool):
                val = "true" if val else "false"
            elif isinstance(val, int):
                val = str(val)
            elif k == "search_engines":
                val = json.dumps(val, ensure_ascii=False)
            Setting.set(k, val)
            saved[k] = data[k]
    # 账号安全相关设置变更记入审计
    sec_labels = {"allow_register": "开放注册", "default_role": "新用户默认角色", "token_max_age_hours": "登录有效期(小时)"}
    for k in ("allow_register", "default_role", "token_max_age_hours"):
        if k in saved:
            audit(user, "setting_update", "setting", None, k, "%s → %s" % (sec_labels[k], saved[k]))
    return jsonify({"ok": True, **saved})


# ---------- 访问统计（admin） ----------
@app.route("/api/admin/stats/overview")
@auth_required
def stats_overview(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    now = datetime.datetime.utcnow()
    today = datetime.datetime(now.year, now.month, now.day)
    since7 = now - datetime.timedelta(days=7)
    total_users = User.query.count()
    active_7d = (db.session.query(AccessLog.user_id)
                 .filter(AccessLog.user_id.isnot(None), AccessLog.created_at >= since7)
                 .distinct().count())
    total_clicks = AccessLog.query.filter_by(action="click").count()
    today_clicks = AccessLog.query.filter(AccessLog.action == "click", AccessLog.created_at >= today).count()
    today_logins = AccessLog.query.filter(AccessLog.action == "login", AccessLog.created_at >= today).count()
    return jsonify({
        "total_users": total_users,
        "active_7d": active_7d,
        "total_clicks": total_clicks,
        "today_clicks": today_clicks,
        "today_logins": today_logins,
    })


@app.route("/api/admin/stats/top-links")
@auth_required
def stats_top_links(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    try:
        limit = int(request.args.get("limit", 10))
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit, 50))
    rows = (db.session.query(
                AccessLog.link_id,
                db.func.count(AccessLog.id),
                db.func.count(db.func.distinct(AccessLog.user_id)),
            )
            .filter(AccessLog.action == "click", AccessLog.link_id.isnot(None))
            .group_by(AccessLog.link_id)
            .order_by(db.func.count(AccessLog.id).desc())
            .limit(limit).all())
    cat_cache = {c.id: c for c in Category.query.all()}
    out = []
    for link_id, cnt, uv in rows:
        l = Link.query.get(link_id)
        if not l:
            continue
        path = []
        c = cat_cache.get(l.category_id)
        while c:
            path.insert(0, c.name)
            c = cat_cache.get(c.parent_id)
        out.append({
            "id": link_id,
            "title": l.title,
            "category_path": path,
            "clicks": cnt,
            "uv": uv,
        })
    return jsonify({"links": out})


@app.route("/api/admin/stats/top-users")
@auth_required
def stats_top_users(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    try:
        limit = int(request.args.get("limit", 10))
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit, 50))
    rows = (db.session.query(
                AccessLog.user_id,
                db.func.count(AccessLog.id),
            )
            .filter(AccessLog.user_id.isnot(None))
            .group_by(AccessLog.user_id)
            .order_by(db.func.count(AccessLog.id).desc())
            .limit(limit).all())
    out = []
    for uid, cnt in rows:
        u = User.query.get(uid)
        if not u:
            continue
        clicks = AccessLog.query.filter_by(user_id=uid, action="click").count()
        logins = AccessLog.query.filter_by(user_id=uid, action="login").count()
        out.append({
            "id": uid,
            "username": u.username,
            "display_name": u.display_name or u.username,
            "role": u.role,
            "total": cnt,
            "clicks": clicks,
            "logins": logins,
            "last_seen": u.last_seen.isoformat() if u.last_seen else None,
        })
    return jsonify({"users": out})


@app.route("/api/admin/stats/trend")
@auth_required
def stats_trend(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    try:
        days = int(request.args.get("days", 30))
    except (TypeError, ValueError):
        days = 30
    days = max(1, min(days, 365))
    now = datetime.datetime.utcnow()
    since = now - datetime.timedelta(days=days - 1)
    since = datetime.datetime(since.year, since.month, since.day)
    rows = (db.session.query(
                db.func.date(AccessLog.created_at),
                AccessLog.action,
                db.func.count(AccessLog.id),
            )
            .filter(AccessLog.created_at >= since)
            .group_by(db.func.date(AccessLog.created_at), AccessLog.action)
            .all())
    agg = {}
    for d, action, cnt in rows:
        agg.setdefault(str(d), {"click": 0, "login": 0})
        agg[str(d)][action] = cnt
    labels, clicks, logins = [], [], []
    for i in range(days):
        day = since + datetime.timedelta(days=i)
        key = day.strftime("%Y-%m-%d")
        labels.append(key)
        rec = agg.get(key, {"click": 0, "login": 0})
        clicks.append(rec.get("click", 0))
        logins.append(rec.get("login", 0))
    return jsonify({"labels": labels, "clicks": clicks, "logins": logins})


@app.route("/api/admin/stats/role-dist")
@auth_required
def stats_role_dist(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    rows = (db.session.query(
                User.role,
                db.func.count(AccessLog.id),
            )
            .join(User, User.id == AccessLog.user_id)
            .filter(AccessLog.action == "click")
            .group_by(User.role)
            .all())
    return jsonify({"roles": [{"role": r, "clicks": c} for r, c in rows]})


# ---------- 统计分析总览（admin，PRD F1–F12） ----------
@app.route("/api/admin/stats/dashboard")
@auth_required
def stats_dashboard(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    try:
        days = int(request.args.get("days", 30))
    except (TypeError, ValueError):
        days = 30
    days = max(1, min(days, 365))
    try:
        topN = int(request.args.get("topN", 10))
    except (TypeError, ValueError):
        topN = 10
    topN = max(5, min(topN, 50))
    dim = request.args.get("dim", "link")
    if dim not in ("link", "parent", "child"):
        dim = "link"
    compare = str(request.args.get("compare", "1")) not in ("0", "false", "False")
    user_id = request.args.get("user_id")
    if user_id:
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            user_id = None

    now = datetime.datetime.utcnow()
    start = now - datetime.timedelta(days=days - 1)
    start = datetime.datetime(start.year, start.month, start.day)
    end = now
    prev_start = start - datetime.timedelta(days=days)
    prev_start = datetime.datetime(prev_start.year, prev_start.month, prev_start.day)

    def cnt(action, s, e):
        return AccessLog.query.filter(AccessLog.action == action,
                                      AccessLog.created_at >= s, AccessLog.created_at < e).count()

    def active_users(s, e):
        return (db.session.query(AccessLog.user_id)
                .filter(AccessLog.user_id.isnot(None), AccessLog.created_at >= s, AccessLog.created_at < e)
                .distinct().count())

    def active_links(s, e):
        return (db.session.query(AccessLog.link_id)
                .filter(AccessLog.action == "click", AccessLog.link_id.isnot(None),
                        AccessLog.created_at >= s, AccessLog.created_at < e)
                .distinct().count())

    # ---- F1 KPI ----
    total_users = User.query.count()
    new_users_period = User.query.filter(User.created_at >= start, User.created_at < end).count()
    new_users_prev = User.query.filter(User.created_at >= prev_start, User.created_at < start).count()
    active_users_cur = active_users(start, end)
    active_users_prev = active_users(prev_start, start)
    dau = active_users(now - datetime.timedelta(days=1), end)
    wau = active_users(now - datetime.timedelta(days=7), end)
    mau = active_users(now - datetime.timedelta(days=30), end)
    parent_categories = Category.query.filter_by(parent_id=None, archived=False).count()
    child_categories = Category.query.filter(Category.parent_id.isnot(None), Category.archived.is_(False)).count()
    links_total = Link.query.filter_by(is_active=True).count()
    new_links_period = Link.query.filter(Link.created_at >= start, Link.created_at < end).count()
    new_links_prev = Link.query.filter(Link.created_at >= prev_start, Link.created_at < start).count()
    active_links_cur = active_links(start, end)
    active_links_prev = active_links(prev_start, start)
    total_clicks = cnt("click", start, end)
    total_clicks_prev = cnt("click", prev_start, start)
    avg_clicks = round(total_clicks / active_users_cur, 2) if active_users_cur else 0.0

    kpis = {
        "total_users": total_users,
        "new_users_period": new_users_period,
        "active_users": active_users_cur,
        "dau": dau, "wau": wau, "mau": mau,
        "parent_categories": parent_categories,
        "child_categories": child_categories,
        "links": links_total,
        "new_links_period": new_links_period,
        "active_links": active_links_cur,
        "total_clicks": total_clicks,
        "avg_clicks_per_user": avg_clicks,
    }
    kpis_prev = {
        "active_users": active_users_prev,
        "total_clicks": total_clicks_prev,
        "active_links": active_links_prev,
        "new_users_period": new_users_prev,
        "new_links_period": new_links_prev,
    }

    # ---- F4 trend ----
    rows = (db.session.query(db.func.date(AccessLog.created_at), AccessLog.action, db.func.count(AccessLog.id))
            .filter(AccessLog.created_at >= start, AccessLog.created_at < end)
            .group_by(db.func.date(AccessLog.created_at), AccessLog.action).all())
    agg = {}
    for d, action, c in rows:
        agg.setdefault(str(d), {"click": 0, "login": 0})
        agg[str(d)][action] = c
    labels, clicks, logins = [], [], []
    for i in range(days):
        key = (start + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        labels.append(key)
        rec = agg.get(key, {"click": 0, "login": 0})
        clicks.append(rec["click"]); logins.append(rec["login"])
    prev_clicks = None
    if compare:
        prows = (db.session.query(db.func.date(AccessLog.created_at), db.func.count(AccessLog.id))
                 .filter(AccessLog.action == "click", AccessLog.created_at >= prev_start, AccessLog.created_at < start)
                 .group_by(db.func.date(AccessLog.created_at)).all())
        pagg = {str(d): c for d, c in prows}
        prev_clicks = [pagg.get((prev_start + datetime.timedelta(days=i)).strftime("%Y-%m-%d"), 0) for i in range(days)]

    # ---- F2 top ranking by dim ----
    link_rows = (db.session.query(AccessLog.link_id, db.func.count(AccessLog.id),
                                  db.func.count(db.func.distinct(AccessLog.user_id)))
                 .filter(AccessLog.action == "click", AccessLog.link_id.isnot(None),
                         AccessLog.created_at >= start, AccessLog.created_at < end)
                 .group_by(AccessLog.link_id).all())
    link_clicks = {lid: [c, uv] for lid, c, uv in link_rows}
    prev_link_rows = (db.session.query(AccessLog.link_id, db.func.count(AccessLog.id))
                      .filter(AccessLog.action == "click", AccessLog.link_id.isnot(None),
                              AccessLog.created_at >= prev_start, AccessLog.created_at < start)
                      .group_by(AccessLog.link_id).all())
    prev_link_clicks = {lid: c for lid, c in prev_link_rows}

    # TOP 排行可按人员筛选（仅影响排行，不影响分类占比等全局指标）
    if user_id:
        trows = (db.session.query(AccessLog.link_id, db.func.count(AccessLog.id),
                                  db.func.count(db.func.distinct(AccessLog.user_id)))
                 .filter(AccessLog.action == "click", AccessLog.link_id.isnot(None),
                         AccessLog.user_id == user_id,
                         AccessLog.created_at >= start, AccessLog.created_at < end)
                 .group_by(AccessLog.link_id).all())
        top_link_clicks = {lid: [c, uv] for lid, c, uv in trows}
        tprev = (db.session.query(AccessLog.link_id, db.func.count(AccessLog.id))
                 .filter(AccessLog.action == "click", AccessLog.link_id.isnot(None),
                         AccessLog.user_id == user_id,
                         AccessLog.created_at >= prev_start, AccessLog.created_at < start)
                 .group_by(AccessLog.link_id).all())
        top_prev_link_clicks = {lid: c for lid, c in tprev}
    else:
        top_link_clicks = link_clicks
        top_prev_link_clicks = prev_link_clicks

    cats = {c.id: c for c in Category.query.all()}
    def parent_of(cat):
        return cats.get(cat.parent_id) if (cat and cat.parent_id) else cat

    items = []
    child_clicks = {}
    if dim == "link":
        for lid, (c, uv) in top_link_clicks.items():
            l = Link.query.get(lid)
            if not l:
                continue
            path = []
            cc = cats.get(l.category_id)
            while cc:
                path.insert(0, cc.name)
                cc = cats.get(cc.parent_id)
            items.append({"id": lid, "title": l.title, "path": path, "clicks": c,
                          "uv": uv, "prev_clicks": top_prev_link_clicks.get(lid, 0)})
    else:
        bucket = {}
        for lid, (c, uv) in top_link_clicks.items():
            l = Link.query.get(lid)
            if not l:
                continue
            cc = cats.get(l.category_id)
            if cc:
                child_clicks[cc.id] = child_clicks.get(cc.id, 0) + c
            if dim == "child":
                key_id = l.category_id
                name = cc.name if cc else "未分类"
            else:
                p = parent_of(cc)
                key_id = p.id if p else 0
                name = p.name if p else "未分类"
            b = bucket.setdefault(key_id, {"id": key_id, "title": name, "clicks": 0, "uv": 0, "prev_clicks": 0})
            b["clicks"] += c
            b["uv"] += uv
            b["prev_clicks"] += top_prev_link_clicks.get(lid, 0)
        items = list(bucket.values())
    items.sort(key=lambda x: x["clicks"], reverse=True)
    items = items[:topN]
    top_total = sum(i["clicks"] for i in items) or 1
    for it in items:
        it["ratio"] = round(it["clicks"] / top_total * 100, 1)
    if dim == "parent":
        for it in items:
            kids = Category.query.filter_by(parent_id=it["id"], archived=False).all()
            it["children"] = sorted(
                [{"id": c.id, "title": c.name, "clicks": child_clicks.get(c.id, 0)} for c in kids],
                key=lambda x: x["clicks"], reverse=True)

    # ---- F3 permission / role distribution ----
    perm_states = (db.session.query(Link.permission, db.func.count(Link.id))
                   .filter_by(is_active=True).group_by(Link.permission).all())
    link_states = [{"state": p or "all", "count": c} for p, c in perm_states]
    denied_rules = LinkPermission.query.filter_by(deny=True).count()
    role_rows = (db.session.query(User.role, db.func.count(AccessLog.id))
                 .join(User, User.id == AccessLog.user_id)
                 .filter(AccessLog.action == "click", AccessLog.created_at >= start, AccessLog.created_at < end)
                 .group_by(User.role).all())
    roles = [{"role": r, "clicks": c} for r, c in role_rows]

    # ---- F10 category click share (parent dims) ----
    cat_share = {}
    for lid, (c, uv) in link_clicks.items():
        l = Link.query.get(lid)
        if not l:
            continue
        p = parent_of(cats.get(l.category_id))
        name = p.name if p else "未分类"
        cat_share[name] = cat_share.get(name, 0) + c
    category_share = sorted([{"name": k, "clicks": v} for k, v in cat_share.items()], key=lambda x: x["clicks"], reverse=True)
    cs_total = sum(x["clicks"] for x in category_share) or 1
    for x in category_share:
        x["ratio"] = round(x["clicks"] / cs_total * 100, 1)

    # ---- F9 hourly + weekday ----
    hrows = (db.session.query(db.func.strftime("%H", AccessLog.created_at), db.func.count(AccessLog.id))
             .filter(AccessLog.action == "click", AccessLog.created_at >= start, AccessLog.created_at < end)
             .group_by(db.func.strftime("%H", AccessLog.created_at)).all())
    hourly = [0] * 24
    for h, c in hrows:
        if h is not None:
            hourly[int(h)] += c
    wrows = (db.session.query(db.func.strftime("%w", AccessLog.created_at), db.func.count(AccessLog.id))
             .filter(AccessLog.action == "click", AccessLog.created_at >= start, AccessLog.created_at < end)
             .group_by(db.func.strftime("%w", AccessLog.created_at)).all())
    week_raw = [0] * 7
    for w, c in wrows:
        if w is not None:
            week_raw[int(w)] += c
    weekly = week_raw[1:] + week_raw[:1]  # Mon..Sun

    # ---- F6 member contribution ----
    members = []
    for u in User.query.filter(User.role.in_(["admin", "member"])).all():
        added_links = Link.query.filter_by(owner_id=u.id).count()
        new_links = Link.query.filter(Link.owner_id == u.id, Link.created_at >= start, Link.created_at < end).count()
        added_child = Category.query.filter(Category.owner_id == u.id, Category.parent_id.isnot(None)).count()
        added_parent = Category.query.filter_by(owner_id=u.id, parent_id=None, archived=False).count()
        edits = AuditLog.query.filter_by(operator_id=u.id).filter(
            AuditLog.action.in_(["link_permission", "category_update", "perm_deny", "perm_restore"])).count()
        members.append({"id": u.id, "username": u.username, "display_name": u.display_name or u.username,
                        "role": u.role, "added_links": added_links, "new_links_period": new_links,
                        "added_categories": added_child, "added_parents": added_parent, "edits": edits})
    members.sort(key=lambda x: x["added_links"], reverse=True)

    # ---- F7 link health ----
    ever_clicked = set(r[0] for r in db.session.query(AccessLog.link_id)
                       .filter(AccessLog.action == "click", AccessLog.link_id.isnot(None)).distinct().all())
    zero_click = max(0, links_total - len(ever_clicked))
    child_cats = Category.query.filter(Category.parent_id.isnot(None), Category.archived.is_(False)).all()
    child_with_links = set(l.category_id for l in Link.query.filter_by(is_active=True).all())
    empty_categories = len([c for c in child_cats if c.id not in child_with_links])
    health = {
        "links_total": links_total,
        "zero_click_links": zero_click,
        "zero_click_ratio": round(zero_click / links_total * 100, 1) if links_total else 0,
        "categories_total": child_categories,
        "empty_categories": empty_categories,
        "empty_ratio": round(empty_categories / child_categories * 100, 1) if child_categories else 0,
    }

    # 链接可达性（系统定时 ping）
    unreachable_links = Link.query.filter_by(is_active=True, ping_status="unreachable").count()
    reachable_links = Link.query.filter_by(is_active=True, ping_status="ok").count()
    unchecked_links = Link.query.filter(Link.is_active.is_(True), Link.ping_status.is_(None)).count()
    last_ping_at = db.session.query(db.func.max(Link.ping_at)).scalar()
    link_ping = {
        "unreachable": unreachable_links,
        "reachable": reachable_links,
        "unchecked": unchecked_links,
        "last_ping_at": last_ping_at.isoformat() if last_ping_at else None,
    }

    # ---- F5 user behavior ----
    user_activity = (db.session.query(AccessLog.user_id, db.func.count(AccessLog.id))
                     .filter(AccessLog.user_id.isnot(None), AccessLog.created_at >= start, AccessLog.created_at < end)
                     .group_by(AccessLog.user_id).all())
    login_rows = (db.session.query(AccessLog.user_id, db.func.count(AccessLog.id))
                  .filter(AccessLog.user_id.isnot(None), AccessLog.action == "login",
                          AccessLog.created_at >= start, AccessLog.created_at < end)
                  .group_by(AccessLog.user_id).all())
    login_map = {uid: c for uid, c in login_rows}
    users = []
    for uid, total in user_activity:
        u = User.query.get(uid)
        if not u:
            continue
        lg = login_map.get(uid, 0)
        users.append({
            "id": uid, "username": u.username, "display_name": u.display_name or u.username,
            "role": u.role, "total": total, "logins": lg, "clicks": total - lg,
            "last_seen": u.last_seen.isoformat() if u.last_seen else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })
    users.sort(key=lambda x: x["total"], reverse=True)
    users = users[:50]

    # 人员筛选下拉（全部用户）
    all_users = User.query.order_by(User.id).all()
    user_options = [{"id": u.id, "username": u.username, "display_name": u.display_name or u.username, "role": u.role} for u in all_users]

    # ---- F8 retention (cohort = users created in period) ----
    cohort = User.query.filter(User.created_at >= start, User.created_at < end).all()
    def retained(u, n):
        return AccessLog.query.filter(AccessLog.user_id == u.id,
                                      AccessLog.created_at >= u.created_at,
                                      AccessLog.created_at < u.created_at + datetime.timedelta(days=n + 1)).count() > 0
    if cohort:
        d1 = d7 = d30 = 0
        for u in cohort:
            if retained(u, 1): d1 += 1
            if retained(u, 7): d7 += 1
            if retained(u, 30): d30 += 1
        n = len(cohort)
        retention = {"d1": round(d1 / n * 100, 1), "d7": round(d7 / n * 100, 1),
                     "d30": round(d30 / n * 100, 1), "cohort": n}
    else:
        retention = {"d1": None, "d7": None, "d30": None, "cohort": 0}

    # ---- new users trend ----
    nrows = (db.session.query(db.func.date(User.created_at), db.func.count(User.id))
             .filter(User.created_at >= start, User.created_at < end)
             .group_by(db.func.date(User.created_at)).all())
    nagg = {str(d): c for d, c in nrows}
    nu_labels, nu_count = [], []
    for i in range(days):
        key = (start + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        nu_labels.append(key); nu_count.append(nagg.get(key, 0))

    return jsonify({
        "days": days,
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "dim": dim,
        "topN": topN,
        "compare": compare,
        "user_id": user_id,
        "kpis": kpis,
        "kpis_prev": kpis_prev,
        "trend": {"labels": labels, "clicks": clicks, "logins": logins, "prev_clicks": prev_clicks},
        "top": {"dim": dim, "items": items},
        "permission": {"link_states": link_states, "denied_rules": denied_rules, "roles": roles},
        "category_share": category_share,
        "hourly": hourly,
        "weekly": weekly,
        "members": members,
        "users": users,
        "user_options": user_options,
        "health": health,
        "link_ping": link_ping,
        "retention": retention,
        "new_users": {"labels": nu_labels, "count": nu_count},
    })


# ---------- 异常数据明细（零点击 / 空壳分类 / 无法访问） ----------

@app.route("/api/admin/stats/anomalies")
@auth_required
def stats_anomalies(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    cats = {c.id: c for c in Category.query.all()}
    active_links = Link.query.filter_by(is_active=True).all()
    child_with_links = set(l.category_id for l in active_links)

    # 零点击链接：从未被点击过的活跃链接
    ever_clicked = set(r[0] for r in db.session.query(AccessLog.link_id)
                       .filter(AccessLog.action == "click", AccessLog.link_id.isnot(None)).distinct().all())
    zero_click_links = []
    for l in active_links:
        if l.id in ever_clicked:
            continue
        cat = cats.get(l.category_id)
        zero_click_links.append({
            "id": l.id,
            "title": l.title,
            "url": l.url_external or l.url_internal,
            "category_id": l.category_id,
            "category_name": cat.name if cat else "",
            "permission": l.permission or "all",
            "created_at": l.created_at.isoformat() if l.created_at else None,
        })

    # 空壳子分类：子分类（有父级）且没有任何活跃链接
    empty_categories = []
    for c in Category.query.filter(Category.parent_id.isnot(None), Category.archived.is_(False)).all():
        if c.id in child_with_links:
            continue
        parent = cats.get(c.parent_id)
        empty_categories.append({
            "id": c.id,
            "name": c.name,
            "parent_id": c.parent_id,
            "parent_name": parent.name if parent else "",
            "icon": c.icon,
            "permission": c.permission or "all",
            "visible": c.visible is not False,
        })

    # 无法访问的链接：ping 状态为 unreachable
    unreachable_links = []
    for l in Link.query.filter_by(is_active=True, ping_status="unreachable").all():
        cat = cats.get(l.category_id)
        unreachable_links.append({
            "id": l.id,
            "title": l.title,
            "url": l.url_external or l.url_internal,
            "category_id": l.category_id,
            "category_name": cat.name if cat else "",
            "ping_at": l.ping_at.isoformat() if l.ping_at else None,
        })

    return jsonify({
        "zero_click_links": zero_click_links,
        "empty_categories": empty_categories,
        "unreachable_links": unreachable_links,
        "counts": {
            "zero_click": len(zero_click_links),
            "empty_category": len(empty_categories),
            "unreachable": len(unreachable_links),
        },
    })


# ---------- 单日明细（热力图点击日期切换） ----------
@app.route("/api/admin/stats/day-detail")
@auth_required
def stats_day_detail(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    date_str = request.args.get("date", "")
    try:
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    except (TypeError, ValueError):
        d = datetime.datetime.utcnow()
    day_start = datetime.datetime(d.year, d.month, d.day)
    day_end = day_start + datetime.timedelta(days=1)
    hrows = (db.session.query(db.func.strftime("%H", AccessLog.created_at), AccessLog.action, db.func.count(AccessLog.id))
             .filter(AccessLog.created_at >= day_start, AccessLog.created_at < day_end)
             .group_by(db.func.strftime("%H", AccessLog.created_at), AccessLog.action).all())
    hourly = [0] * 24
    logins_by_hour = [0] * 24
    for h, action, c in hrows:
        if h is None:
            continue
        idx = int(h)
        if action == "login":
            logins_by_hour[idx] += c
        else:
            hourly[idx] += c
    total_clicks = sum(hourly)
    total_logins = sum(logins_by_hour)
    return jsonify({
        "date": date_str,
        "hourly": hourly,
        "logins_by_hour": logins_by_hour,
        "total_clicks": total_clicks,
        "total_logins": total_logins,
    })


# ---------- 后台管理 ----------
@app.route("/api/admin/users")
@auth_required
def admin_users(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    users = User.query.order_by(User.id).all()
    return jsonify({"users": [u.to_dict() for u in users]})


@app.route("/api/admin/users", methods=["POST"])
@auth_required
def admin_create_user(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "用户名与密码必填"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "用户名已存在"}), 400
    role = data.get("role", "member")
    if role not in ("admin", "member", "guest"):
        role = "member"
    u = User(username=username, role=role)
    u.set_password(password)
    if data.get("display_name"):
        u.display_name = data["display_name"]
    db.session.add(u)
    db.session.commit()
    return jsonify({"user": u.to_dict()}), 201


@app.route("/api/admin/users/<int:uid>", methods=["PUT"])
@auth_required
def admin_update_user(user, uid):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    target = User.query.get_or_404(uid)
    data = request.get_json(silent=True) or {}
    old_role = target.role
    old_active = target.is_active
    if "role" in data and data["role"] in ("admin", "member", "guest"):
        target.role = data["role"]
    if "display_name" in data:
        target.display_name = data["display_name"]
    # 禁用 / 启用账号：管理员可在用户卡片操作
    if "is_active" in data:
        # 安全保护：不能禁用自己，也不能禁用其他管理员（避免锁死后台）
        if uid == user.id:
            return jsonify({"error": "不能禁用当前登录的账号"}), 400
        if target.role == "admin":
            return jsonify({"error": "不能禁用管理员账号"}), 400
        target.is_active = bool(data["is_active"])
    db.session.commit()
    if target.role != old_role:
        audit(user, "user_role", "user", target.id, target.username,
              "角色 %s → %s" % (old_role, target.role))
    if "is_active" in data and target.is_active != old_active:
        audit(user, "user_unban" if target.is_active else "user_ban", "user", target.id,
              target.username, "账号%s" % ("启用" if target.is_active else "禁用"))
    return jsonify({"user": target.to_dict()})


@app.route("/api/admin/users/<int:uid>/reset-password", methods=["POST"])
@auth_required
def admin_reset_user_password(user, uid):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    target = User.query.get_or_404(uid)
    data = request.get_json(silent=True) or {}
    new_pw = (data.get("new_password") or "").strip()
    # 未提供则生成 12 位随机密码
    if new_pw and not valid_password(new_pw):
        return jsonify({"error": "新密码长度需为 8-256 位"}), 400
    if not new_pw:
        import random, string
        new_pw = "".join(random.choices(string.ascii_letters + string.digits, k=12))
    target.set_password(new_pw)
    db.session.commit()
    audit(user, "admin_password_reset", "user", target.id, target.username, "管理员重置密码")
    return jsonify({"ok": True, "new_password": new_pw})


@app.route("/api/admin/users/<int:uid>/permissions")
@auth_required
def admin_user_permissions(user, uid):
    """返回目标用户对每条链接的访问状态，供「编辑权限」弹窗使用。

    响应含两部分：
      links  —— 管理员可逐条开关的链接（分类可见 且 基础可见/已授权/已拒绝）；
                每条带 visible（开关）与 denied（是否显式拒绝）标志。
      denied —— 该用户最终「不可见」的全部链接，每条标注被哪一层拦截：
                L0 账号墙 / L1a 分类墙 / L1b 分类角色白名单 / L2 链接基础权限 / L3 显式拒绝。
                该列表只读，用于排查「为什么某用户看不到某链接」。
    """
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    target = User.query.get_or_404(uid)
    account_active = target.is_active is not False

    # 分类墙（L1a/L1b）缓存：被隐藏/归档的分类（含其下子分类）对所有人不可见
    cat_cache = {c.id: c for c in Category.query.all()}
    hidden_cat = set()
    hidden_parents = []
    for c in cat_cache.values():
        if c.visible is False or c.archived:
            hidden_cat.add(c.id)
            if c.parent_id is None:
                hidden_parents.append(c.id)
    if hidden_parents:
        for c in Category.query.filter(Category.parent_id.in_(hidden_parents)).all():
            hidden_cat.add(c.id)

    def _base_access(link):
        """L2 链接基础权限（不含分类墙与显式授权）。"""
        perm = (link.permission or "all").strip()
        tid, trole = target.id, target.role
        if perm == "all":
            return True
        if perm == "registered":
            return True  # target 为真实用户（非访客）
        if perm == "admin":
            return trole == "admin" or link.owner_id == tid
        if perm == "self":
            return link.owner_id == tid
        return True

    # L3 显式授权 / 拒绝（user 级 + role 级）
    exp_grant, exp_deny = set(), set()
    for p in LinkPermission.query.filter_by(kind="user", target=str(uid)).all():
        (exp_deny if p.deny else exp_grant).add(p.link_id)
    for p in LinkPermission.query.filter_by(kind="role", target=target.role).all():
        (exp_deny if p.deny else exp_grant).add(p.link_id)

    def _evaluate(l):
        """返回 (visible, layer, reason)。
        layer/reason 仅当 visible=False 时有效，表示该链接被哪一层拦截。
        优先级（自顶向下，先命中先返回）：L0 → L1a → L1b → L3(deny) → L2。
        """
        cat = cat_cache.get(l.category_id)
        if not account_active:
            return (False, "L0", "账号已禁用（L0 账号墙）")
        if cat is None or cat.id in hidden_cat:
            return (False, "L1a", "所属分类已隐藏或归档（L1a 分类墙）")
        if not _cat_perm_ok(cat, target.role, target.id):
            return (False, "L1b", "分类权限不足（L1b 分类权限：%s）" % (cat.permission or "all"))
        base = _base_access(l)
        has_grant = l.id in exp_grant
        has_deny = l.id in exp_deny
        if has_deny:
            return (False, "L3", "被管理员显式拒绝（L3 显式拒绝）")
        if base or has_grant:
            return (True, None, None)
        perm = (l.permission or "all").strip()
        if perm == "admin":
            reason = "链接仅限管理员/所有者可见（L2 链接基础权限）"
        elif perm == "self":
            reason = "链接仅限所有者本人可见（L2 链接基础权限）"
        else:
            reason = "链接基础权限不足（L2 链接基础权限）"
        return (False, "L2", reason)

    links = Link.query.filter_by(is_active=True).order_by(Link.id).all()
    manage_out, denied_out = [], []
    for l in links:
        cat = cat_cache.get(l.category_id)
        visible, layer, reason = _evaluate(l)
        owner = User.query.get(l.owner_id)
        path = []
        c = cat
        while c:
            path.insert(0, c.name)
            c = cat_cache.get(c.parent_id)

        # 可管理：分类可见 且 (基础可见 / 已授权 / 已拒绝) —— 即未被 L0/L1a/L1b/L2 拦截
        if layer is None or layer == "L3":
            manage_out.append({
                "id": l.id,
                "title": l.title,
                "url": l.url_external or l.url_internal,
                "icon": l.icon,
                "owner_name": owner.username if owner else "?",
                "category_path": path,
                "visible": layer is None,
                "denied": layer == "L3",
            })
        # 不可见：归入「无权限链接」列表（含 L0/L1a/L1b/L2/L3）
        if not visible:
            denied_out.append({
                "id": l.id,
                "title": l.title,
                "url": l.url_external or l.url_internal,
                "icon": l.icon,
                "owner_name": owner.username if owner else "?",
                "category_path": path,
                "layer": layer,
                "reason": reason,
                "fixable_here": layer == "L3",
            })
    return jsonify({"user": target.to_dict(), "links": manage_out, "denied": denied_out})


@app.route("/api/admin/users/<int:uid>/permissions", methods=["POST"])
@auth_required
def admin_set_user_permissions(user, uid):
    """保存目标用户对各链接的权限（三态）：grants=允许，denies=拒绝，其余=默认(继承/隐藏)。"""
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    target = User.query.get_or_404(uid)
    data = request.get_json(silent=True) or {}
    denies = set(data.get("denies", []))

    cat_cache = {c.id: c for c in Category.query.all()}
    hidden_cat = set()
    hidden_parents = []
    for c in cat_cache.values():
        if c.visible is False or c.archived:
            hidden_cat.add(c.id)
            if c.parent_id is None:
                hidden_parents.append(c.id)
    if hidden_parents:
        for c in Category.query.filter(Category.parent_id.in_(hidden_parents)).all():
            hidden_cat.add(c.id)

    def _category_visible(cat):
        if cat is None:
            return True
        if cat.id in hidden_cat:
            return False
        if not _cat_perm_ok(cat, target.role, target.id):
            return False
        return True

    def _base_access(link):
        perm = (link.permission or "all").strip()
        tid, trole = target.id, target.role
        if perm == "all":
            return True
        if perm == "registered":
            return True
        if perm == "admin":
            return trole == "admin" or link.owner_id == tid
        if perm == "self":
            return link.owner_id == tid
        return True

    links = Link.query.filter_by(is_active=True).all()
    changed = 0
    audit_rows = []
    for l in links:
        # 不可改：被分类墙挡住（category_hidden）——即使有显式授权也无法复活
        if not _category_visible(cat_cache.get(l.category_id)):
            continue
        # 自己的链接始终可见，管理员不可在此弹窗剥夺（避免与 L2「self=仅所有者」冲突）
        if l.owner_id == uid:
            continue
        base = _base_access(l)
        existing = LinkPermission.query.filter_by(link_id=l.id, kind="user", target=str(uid)).first()
        # 仅管理「基础可见 / 已有显式授权或拒绝」的链接；本就无权访问的链接开关不可控
        if not base and existing is None:
            continue
        want_deny = l.id in denies
        if existing:
            if bool(existing.deny) != want_deny:
                existing.deny = want_deny
                changed += 1
                audit_rows.append((l, want_deny))
        elif want_deny:
            db.session.add(LinkPermission(link_id=l.id, kind="user", target=str(uid), deny=True))
            changed += 1
            audit_rows.append((l, True))
        # 基础可见且无需拒绝 → 保持无记录（开关开启即默认可见）
    db.session.commit()
    for (l, is_deny) in audit_rows:
        audit(user, "perm_deny" if is_deny else "perm_restore", "user", target.id, target.username,
              "链接《%s》→ %s" % (l.title, "拒绝(隐藏)" if is_deny else "恢复默认可见"))
    return jsonify({"ok": True, "changed": changed})


@app.route("/api/admin/audit")
@auth_required
def admin_audit(user):
    """权限 / 账号操作审计日志（倒序分页）。"""
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    page = request.args.get("page", 1, type=int)
    per = request.args.get("per", 50, type=int)
    if page < 1:
        page = 1
    if per < 1 or per > 200:
        per = 50
    q = AuditLog.query.order_by(AuditLog.id.desc())
    total = q.count()
    rows = q.offset((page - 1) * per).limit(per).all()
    return jsonify({
        "logs": [r.to_dict() for r in rows],
        "total": total,
        "page": page,
        "per": per,
    })


@app.route("/api/admin/links/<int:lid>/permissions")
@auth_required
def admin_link_permissions(user, lid):
    """链接维度权限矩阵：返回该链接对每个用户的可见性，及被哪一层拦截。

    与「用户维度」页签互补——这里以「链接」为中心，看谁看得见、谁看不见、为什么。
    """
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    link = Link.query.get_or_404(lid)
    cat_cache = {c.id: c for c in Category.query.all()}
    hidden_cat = set()
    hidden_parents = []
    for c in cat_cache.values():
        if c.visible is False or c.archived:
            hidden_cat.add(c.id)
            if c.parent_id is None:
                hidden_parents.append(c.id)
    if hidden_parents:
        for c in Category.query.filter(Category.parent_id.in_(hidden_parents)).all():
            hidden_cat.add(c.id)

    def _evaluate(u):
        """对单个用户 u 评估其对该链接的最终可见性（L0→L1a→L1b→L3→L2）。"""
        cat = cat_cache.get(link.category_id)
        if u.is_active is False:
            return (False, "L0", "账号已禁用（L0 账号墙）")
        if cat is None or cat.id in hidden_cat:
            return (False, "L1a", "所属分类已隐藏或归档（L1a 分类墙）")
        if not _cat_perm_ok(cat, u.role, u.id):
            return (False, "L1b", "分类权限不足（L1b 分类权限：%s）" % (cat.permission or "all"))
        perm = (link.permission or "all").strip()
        if perm == "all":
            base = True
        elif perm == "registered":
            base = True
        elif perm == "admin":
            base = (u.role == "admin") or (link.owner_id == u.id)
        elif perm == "self":
            base = link.owner_id == u.id
        else:
            base = True
        grant_u, deny_u = set(), set()
        for p in LinkPermission.query.filter_by(kind="user", target=str(u.id)).all():
            (deny_u if p.deny else grant_u).add(p.link_id)
        for p in LinkPermission.query.filter_by(kind="role", target=u.role).all():
            (deny_u if p.deny else grant_u).add(p.link_id)
        has_grant = link.id in grant_u
        has_deny = link.id in deny_u
        if has_deny:
            return (False, "L3", "被管理员显式拒绝（L3 显式拒绝）")
        if base or has_grant:
            return (True, None, None)
        if perm == "admin":
            reason = "链接仅限管理员/所有者可见（L2 链接基础权限）"
        elif perm == "self":
            reason = "链接仅限所有者本人可见（L2 链接基础权限）"
        else:
            reason = "链接基础权限不足（L2 链接基础权限）"
        return (False, "L2", reason)

    users = User.query.order_by(User.id).all()
    users_out = []
    summary = {"total": 0, "visible": 0, "hidden": 0, "by_layer": {}}
    for u in users:
        visible, layer, reason = _evaluate(u)
        users_out.append({
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name or u.username,
            "role": u.role,
            "is_active": u.is_active is not False,
            "visible": visible,
            "layer": layer,
            "reason": reason,
            "fixable": layer == "L3",
        })
        summary["total"] += 1
        if visible:
            summary["visible"] += 1
        else:
            summary["hidden"] += 1
            key = layer or "?"
            summary["by_layer"][key] = summary["by_layer"].get(key, 0) + 1
    cat = cat_cache.get(link.category_id)
    cat_path = []
    c = cat
    while c:
        cat_path.insert(0, c.name)
        c = cat_cache.get(c.parent_id)
    owner = User.query.get(link.owner_id)
    return jsonify({
        "link": {
            "id": link.id,
            "title": link.title,
            "permission": link.permission or "all",
            "category_path": cat_path,
            "owner_name": owner.username if owner else "?",
        },
        "users": users_out,
        "summary": summary,
    })


@app.route("/api/admin/links")
@auth_required
def admin_all_links(user):
    if user.role == "admin":
        # 管理员可见全部链接
        links = Link.query.order_by(Link.id).all()
    else:
        # 普通用户仅能查看自己有权限访问的链接（与首页同源的权限模型）
        links = visible_links_for(user)
    # 当前用户的主页可见性开关（仅影响该用户自己的主页，默认显示）
    hidden_ids = {
        v.link_id for v in UserLinkVisibility.query.filter_by(user_id=user.id, show_on_home=False)
    }
    owner_cache = {u.id: u for u in User.query.filter(User.id.in_({l.owner_id for l in links})).all()} if links else {}
    category_cache = {c.id: c for c in Category.query.filter(Category.id.in_({l.category_id for l in links})).all()} if links else {}
    password_ids = {row.link_id for row in LinkPassword.query.filter(
        LinkPassword.user_id == user.id,
        LinkPassword.link_id.in_([l.id for l in links]),
    ).all()} if links else set()
    out = []
    for l in links:
        d = l.to_dict(user=user)
        d["is_active"] = l.is_active
        d["is_owner"] = (l.owner_id == user.id)
        d["can_edit"] = (user.role == "admin" or l.owner_id == user.id)
        l._has_password_cached = l.id in password_ids
        owner = owner_cache.get(l.owner_id)
        d["owner_name"] = owner.username if owner else "?"
        cat = category_cache.get(l.category_id)
        d["category_name"] = cat.name if cat else ""
        d["parent_category_name"] = cat.parent.name if (cat and cat.parent_id) else ""
        # 编辑弹窗需要原始内外网地址
        d["url_external"] = l.url_external
        d["url_internal"] = l.url_internal
        # 是否在自己主页显示（默认显示）
        d["show_on_home"] = l.id not in hidden_ids
        out.append(d)
    return jsonify({"links": out})


# ---------- 生产：托管前端构建产物 ----------
@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(Config.UPLOAD_FOLDER, filename)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    dist = os.path.join(Config.FRONTEND_DIST)
    asset = safe_join(dist, path) if path else None
    if asset and os.path.isfile(asset):
        return send_from_directory(dist, path)
    index = os.path.join(dist, "index.html")
    if os.path.exists(index):
        return send_from_directory(dist, "index.html")
    return jsonify(
        {"message": "云航导航 API 运行中。前端未构建时访问 /api/* 调试接口。", "docs": "/api/health"}
    )


@app.after_request
def _no_cache_frontend(resp):
    # 强制前端资源（HTML/JS/CSS/字体/图标）不缓存，保证每次拉取最新构建
    if resp.content_type and ('text/html' in resp.content_type or 'javascript' in resp.content_type
            or 'css' in resp.content_type or 'font' in resp.content_type or 'application/octet-stream' in resp.content_type):
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('X-Frame-Options', 'DENY')
    resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    return resp


# ---------- 链接可达性探测（系统定时 ping） ----------
_PING_INTERVAL = 600  # 秒，默认 10 分钟探测一次
_PING_SCHEDULER_STARTED = False


def _link_ping_url(link):
    return link.url_external or link.url_internal


def _do_ping(url, timeout=6):
    """返回 'ok' 或 'unreachable'。仅对 http(s) 外部链接做实际探测。"""
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True)
        if r.status_code == 405:  # 部分服务不支持 HEAD，回退 GET
            r = requests.get(url, timeout=timeout, allow_redirects=True, stream=True)
            r.close()
        return "ok" if r.status_code < 400 else "unreachable"
    except Exception:
        return "unreachable"


def ping_all_links():
    """遍历活跃链接探测可达性，更新 ping_status / ping_at。返回变更数。"""
    with app.app_context():
        links = Link.query.filter_by(is_active=True).all()
        now = datetime.datetime.utcnow()
        changed = 0
        for l in links:
            url = _link_ping_url(l)
            if url and (url.startswith("http://") or url.startswith("https://")):
                status = _do_ping(url)
            elif url:
                status = "ok"  # 内部路由不对外探测，视为可达
            else:
                status = None
            if status is None:
                continue
            if l.ping_status != status:
                l.ping_status = status
                changed += 1
            l.ping_at = now
        db.session.commit()
        return changed


def _ping_scheduler_loop():
    while True:
        try:
            ping_all_links()
        except Exception:
            pass
        time.sleep(_PING_INTERVAL)


def start_ping_scheduler():
    global _PING_SCHEDULER_STARTED
    if _PING_SCHEDULER_STARTED:
        return
    _PING_SCHEDULER_STARTED = True
    t = threading.Thread(target=_ping_scheduler_loop, daemon=True)
    t.start()


@app.route("/api/admin/links/ping", methods=["POST"])
@auth_required
def admin_ping_links(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    try:
        changed = ping_all_links()
        return jsonify({"changed": changed, "message": "已完成链接可达性探测"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- 群晖监控（DSM API） ----------
from backend.syno import load_config, config_key, get_client, clear_client_cache, SynoError


@app.route("/api/monitor/config")
@auth_required
def monitor_config(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    cfg = load_config()
    return jsonify({
        "host": cfg["host"],
        "port": cfg["port"],
        "user": cfg["user"],
        "https": cfg["https"],
        "configured": bool(cfg["host"] and cfg["user"]),
        "has_password": bool(cfg["password"]),
    })


@app.route("/api/monitor/config", methods=["POST"])
@auth_required
def monitor_config_save(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    host = (data.get("host") or "").strip()
    port = data.get("port")
    suser = (data.get("user") or "").strip()
    password = data.get("password") or ""  # 留空表示不修改已有密码
    https = bool(data.get("https"))
    if not host or not suser:
        return jsonify({"error": "主机地址和账号不能为空"}), 400
    if host.startswith(("http://", "https://")) or "/" in host or " " in host:
        return jsonify({"error": "主机地址只填写 IP 或域名，不要包含协议和路径"}), 400
    try:
        port = int(port) if port not in (None, "") else (5001 if https else 5000)
    except (TypeError, ValueError):
        return jsonify({"error": "端口必须是数字"}), 400
    if not 1 <= port <= 65535:
        return jsonify({"error": "端口范围必须是 1-65535"}), 400
    Setting.set("syno_host", host)
    Setting.set("syno_port", str(port))
    Setting.set("syno_user", suser)
    if password:
        Setting.set("syno_pass", password)
    Setting.set("syno_https", "1" if https else "0")
    clear_client_cache()
    _MONITOR_CACHE.update({"ts": 0.0, "data": None})
    return jsonify({"ok": True})


@app.route("/api/monitor/config/test", methods=["POST"])
@auth_required
def monitor_config_test(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    host = (data.get("host") or "").strip()
    username = (data.get("user") or "").strip()
    password = data.get("password") or ""
    https = bool(data.get("https"))
    if not host or not username or not password:
        return jsonify({"error": "测试连接需要主机、账号和密码"}), 400
    try:
        port = int(data.get("port") or (5001 if https else 5000))
    except (TypeError, ValueError):
        return jsonify({"error": "端口必须是数字"}), 400
    if not 1 <= port <= 65535:
        return jsonify({"error": "端口范围必须是 1-65535"}), 400
    cfg = {"host": host, "port": port, "user": username, "password": password, "https": https}
    try:
        client = get_client(cfg)
        health = client.get_system_health()
        containers = client.get_containers()
        return jsonify({
            "ok": True,
            "hostname": health.get("hostname"),
            "container_count": len(containers),
            "message": "连接成功",
        })
    except SynoError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502


# 监控快照短期缓存：避免前端每 15s 轮询都狠打 DSM 多个接口，
# 同时让慢响应期间的重复请求直接命中缓存（秒级返回）。
_MONITOR_CACHE = {"key": None, "ts": 0.0, "data": None}
_MONITOR_TTL = 10  # 秒


@app.route("/api/monitor")
@auth_required
def monitor_snapshot(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    cfg = load_config()
    if not cfg["host"] or not cfg["user"]:
        return jsonify({"error": "尚未配置群晖连接", "need_config": True}), 400
    if not cfg["password"]:
        return jsonify({"error": "群晖密码未配置", "need_config": True}), 400
    cache_key = config_key(cfg)
    # 命中缓存（手动刷新带 ?force=1 绕过）
    force = request.args.get("force") == "1"
    now = time.time()
    if _MONITOR_CACHE["key"] != cache_key:
        _MONITOR_CACHE.update({"key": cache_key, "ts": 0.0, "data": None})
    if not force and _MONITOR_CACHE["data"] and (now - _MONITOR_CACHE["ts"]) < _MONITOR_TTL:
        return jsonify(_MONITOR_CACHE["data"])
    try:
        client = get_client(cfg)
        snap = client.snapshot(force=force)
    except SynoError as e:
        return jsonify({"error": str(e)}), 502
    _MONITOR_CACHE["key"] = cache_key
    _MONITOR_CACHE["ts"] = time.time()
    _MONITOR_CACHE["data"] = snap
    return jsonify(snap)


@app.route("/api/monitor/container/action", methods=["POST"])
@auth_required
def monitor_container_action(user):
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    cid = data.get("id")
    action = data.get("action")
    if not cid or action not in ("start", "stop", "restart"):
        return jsonify({"error": "参数无效"}), 400
    try:
        client = get_client()
        client.container_action(data.get("name") or cid, action, cid=cid)
    except SynoError as e:
        return jsonify({"error": str(e)}), 502
    return jsonify({"ok": True, "action": action})


@app.route("/api/monitor/container/detail")
@auth_required
def monitor_container_detail(user):
    """按需返回单个容器的端口映射（列表接口不含端口，需逐个 get 详情）。"""
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    name = (request.args.get("name") or "").strip()
    cid = (request.args.get("id") or "").strip()
    if not name and not cid:
        return jsonify({"error": "缺少 name 或 id 参数"}), 400
    try:
        client = get_client()
        detail = client.get_container_detail(name=name or None, cid=cid or None)
    except SynoError as e:
        return jsonify({"error": str(e)}), 502
    if not detail:
        return jsonify({"error": "未找到该容器（请确认名称/ID）"}), 404
    return jsonify(detail)


def _port_query(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if "-" in raw:
            start, end = [int(v.strip()) for v in raw.split("-", 1)]
            if 1 <= start <= end <= 65535:
                return (start, end)
        port = int(raw)
        if 1 <= port <= 65535:
            return (port, port)
    except (TypeError, ValueError):
        return None
    return None


def _port_matches(port, query):
    if not query:
        return False
    for value in (port.get("host"), port.get("container")):
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if query[0] <= number <= query[1]:
            return True
    return False


@app.route("/api/monitor/diagnostics", methods=["POST"])
@auth_required
def monitor_diagnostics(user):
    """One shared source of truth for Docker IP/port diagnostics."""
    if user.role != "admin":
        return jsonify({"error": "无权限"}), 403
    data = request.get_json(silent=True) or {}
    port_query = _port_query(data.get("port")) if data.get("port") not in (None, "") else None
    target_ip = str(data.get("ip") or "").strip()
    if data.get("port") and not port_query:
        return jsonify({"error": "端口必须是 1-65535，或使用端口范围，例如 3000-3010"}), 400
    if target_ip:
        try:
            ipaddress.ip_address(target_ip)
        except ValueError:
            return jsonify({"error": "IP 地址格式无效"}), 400
    try:
        client = get_client()
        containers = client.get_containers()
        details = client.get_container_ports_batch(containers)
    except SynoError as exc:
        return jsonify({"error": str(exc)}), 502

    port_matches = []
    host_owners = {}
    ip_matches = []
    diagnostics_errors = []
    for container in containers:
        key = container.get("id") or container.get("name")
        detail = details.get(key) or {"ports": [], "ok": False, "error": "未返回容器详情"}
        if not detail.get("ok"):
            diagnostics_errors.append({"container": container.get("name"), "error": detail.get("error")})
        ports = detail.get("ports") or []
        if port_query:
            matched_ports = [p for p in ports if _port_matches(p, port_query)]
            if matched_ports:
                for port in matched_ports:
                    if port.get("host") not in (None, "", "None"):
                        owner_key = (port.get("ip") or "0.0.0.0", str(port.get("host")), port.get("type") or "tcp")
                        host_owners.setdefault(owner_key, set()).add(container.get("name"))
                port_matches.append({
                    "name": container.get("name"),
                    "id": container.get("id"),
                    "state": container.get("state"),
                    "networks": container.get("networks") or [],
                    "ports": [{**p,
                        "hostMatch": p.get("host") not in (None, "", "None") and _port_matches({"host": p.get("host")}, port_query),
                        "contMatch": p.get("container") not in (None, "") and _port_matches({"container": p.get("container")}, port_query),
                    } for p in matched_ports],
                    "host_hit": any(p.get("host") not in (None, "", "None") for p in matched_ports),
                    "container_hit": any(p.get("container") not in (None, "") for p in matched_ports),
                })
        if target_ip:
            matches = [n for n in (container.get("networks") or []) if n.get("ip") == target_ip]
            if matches:
                ip_matches.append({
                    "name": container.get("name"),
                    "id": container.get("id"),
                    "state": container.get("state"),
                    "networks": container.get("networks") or [],
                })

    conflicts = [
        {"ip": key[0], "port": key[1], "type": key[2], "containers": sorted(owners)}
        for key, owners in host_owners.items() if len(owners) > 1
    ]
    return jsonify({
        "checked_at": int(time.time()),
        "port_query": data.get("port") or None,
        "ip_query": target_ip or None,
        "port_matches": port_matches,
        "port_conflicts": conflicts,
        "ip_matches": ip_matches,
        "errors": diagnostics_errors,
        "container_count": len(containers),
    })


@app.route("/api/network/check", methods=["POST"])
@auth_required
def network_check(user):
    """Validate a URL and optionally check its TCP endpoint from the server."""
    data = request.get_json(silent=True) or {}
    raw_url = (data.get("url") or "").strip()
    parsed, url_error = validate_http_url(raw_url, allow_private=True)
    if url_error:
        return jsonify({"error": url_error}), 400
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    result = {"url": raw_url, "hostname": parsed.hostname, "port": port, "valid": True, "reachable": None, "error": None}
    try:
        with socket.create_connection((parsed.hostname, port), timeout=2.5):
            result["reachable"] = True
    except (OSError, ValueError) as exc:
        result["reachable"] = False
        result["error"] = str(exc)
    return jsonify(result)


# ---------------------------------------------------------------------------
# 版本与更新检测
# ---------------------------------------------------------------------------
_VERSION_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "version.json")
_GHCR_REPO = "anooki-c/aether-nav"
# 简单内存缓存：避免反复点击「检查更新」时频繁请求 ghcr.io
_update_cache = {"ts": 0.0, "data": None}
_UPDATE_TTL = 120.0


def _read_version():
    """读取构建时注入的版本文件；开发环境无该文件则返回开发版信息。"""
    try:
        with open(_VERSION_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"commit": None, "tag": "dev", "build_time": None, "source": "dev"}
    data.setdefault("source", "docker")
    return data


def _ghcr_latest_revision():
    """查询 ghcr.io 上 latest 镜像内置的构建提交 SHA（org.opencontainers.image.revision）。

    容器环境（尤其是 NAS）常遇 SSL 证书链 / OCSP 问题，此处跳过 verify 仅读取公开元数据。
    """
    import urllib3
    base = "https://ghcr.io/v2/" + _GHCR_REPO
    sess = requests.Session()
    # 抑制 InsecureRequestWarning（仅针对此会话）
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def fetch(url, accept):
        headers = {"Accept": accept}
        try:
             r = sess.get(url, headers=headers, timeout=12, verify=True)
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError,
                urllib3.exceptions.SSLError) as exc:
            raise RuntimeError("无法连接 ghcr.io（%s）" % str(exc)) from exc
        if r.status_code == 401:
            auth = r.headers.get("WWW-Authenticate", "")
            realm = re.search(r'realm="([^"]+)"', auth)
            service = re.search(r'service="([^"]+)"', auth)
            scope = re.search(r'scope="([^"]+)"', auth)
            if not realm:
                return r
            token_url = realm.group(1)
            params = []
            if service:
                params.append("service=" + service.group(1))
            if scope:
                params.append("scope=" + scope.group(1))
            if params:
                token_url += "?" + "&".join(params)
            tok = sess.get(token_url, timeout=12, verify=True).json().get("token") or \
                sess.get(token_url, timeout=12, verify=True).json().get("access_token")
            r = sess.get(url, headers={**headers, "Authorization": "Bearer " + tok}, timeout=12, verify=True)
        return r

    manifest = fetch(
        base + "/manifests/latest",
        "application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json",
    ).json()
    config_digest = (manifest.get("config") or {}).get("digest")
    if not config_digest:
        # 多架构镜像索引：取第一个子 manifest 的 config
        subs = manifest.get("manifests") or []
        if subs:
            sub = fetch(
                base + "/manifests/" + subs[0].get("digest", ""),
                "application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json",
            ).json()
            config_digest = (sub.get("config") or {}).get("digest")
    if not config_digest:
        raise RuntimeError("无法解析 latest 镜像 manifest")
    config = fetch(
        base + "/blobs/" + config_digest,
        "application/vnd.oci.image.config.v1+json, application/json",
    ).json()
    labels = ((config.get("config") or {}).get("Labels")) or {}
    return labels.get("org.opencontainers.image.revision")


@app.route("/api/version")
@auth_required
def api_version(user):
    return jsonify(_read_version())


@app.route("/api/check-update")
@auth_required
def api_check_update(user):
    info = _read_version()
    current = info.get("commit")
    now = datetime.datetime.utcnow()
    if _update_cache["data"] and (now.timestamp() - _update_cache["ts"]) < _UPDATE_TTL:
        cached = dict(_update_cache["data"])
        cached["cached"] = True
        return jsonify(cached)
    result = {
        "current_commit": current,
        "current_tag": info.get("tag"),
        "build_time": info.get("build_time"),
        "source": info.get("source"),
        "update_available": None,
        "latest_commit": None,
        "latest_build_time": None,
        "checked_at": now.isoformat() + "Z",
        "error": None,
        "cached": False,
    }
    try:
        rev = _ghcr_latest_revision()
        result["latest_commit"] = rev
        if not current:
            result["error"] = "本地为开发版本，无提交号可比"
        elif not rev:
            result["error"] = "无法读取 latest 镜像的构建提交号"
        else:
            result["update_available"] = (current != rev)
    except Exception as e:
        err = str(e)
        # 截断过长的底层 SSL 错误，只保留关键信息
        if "InvalidHeader" in err or "OCSP" in err or "SSL" in err.upper():
            err = "网络连接失败（SSL 证书问题），请检查网络或代理设置"
        result["error"] = "检测失败：" + err
    _update_cache["ts"] = now.timestamp()
    _update_cache["data"] = result
    return jsonify(result)


def create_app():
    with app.app_context():
        db.create_all()
        # 增量迁移：为 users 表补充 preferences 列（SQLite 下 create_all 不会自动加列）
        try:
            from sqlalchemy import inspect, text
            insp = inspect(db.engine)
            cols = [c["name"] for c in insp.get_columns("users")]
            if "preferences" not in cols:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN preferences TEXT"))
                    conn.commit()
            # links 表增量迁移：可达性探测字段
            link_cols = [c["name"] for c in insp.get_columns("links")]
            # Many SQLAlchemy versions return Column objects, normalize to names
            link_col_names = [c["name"] if isinstance(c, dict) else getattr(c, "name", None) for c in link_cols]
            link_col_names = [n for n in link_col_names if n]
            for col in ("ping_status", "ping_at"):
                if col not in link_col_names:
                    with db.engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE links ADD COLUMN {col} {'TEXT' if col == 'ping_status' else 'DATETIME'}"))
                        conn.commit()
        except Exception:
            pass
    # 启动链接可达性定时探测（后台守护线程，首次探测在后台异步执行）
    start_ping_scheduler()
    return app


# 模块导入即同步表结构（含新增列迁移），保证直接 `from backend.app import app` 启动时 schema 最新
create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    # use_reloader=False: 在 PyCharm 里调试时避免重加载子进程堆积、抢占 5000 端口。
    # 如想用 flask 自带热重载，可改回 True（但别和 PyCharm Debug 同时使用）。
    app.run(host="0.0.0.0", port=5001, debug=True, use_reloader=False)
