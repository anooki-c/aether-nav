"""图标处理工具：解析图标地址、把地址落地为本地文件。

与 Flask 解耦，便于单独测试。约定：
- 「图标输入框」里可以是图片网址、本地文件绝对路径、Material Symbols 名称或 emoji；
- 提交表单时统一由 :func:`localize_icon` 落地为 ``/uploads/xxx`` 本地文件；
- 落地失败返回空字符串，由前端展示层按标题匹配默认图标。
"""
import ipaddress
import os
import re
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from backend.config import Config

ALLOWED_ICON_EXT = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico")
MAX_ICON_BYTES = 2 * 1024 * 1024  # 单个图标最大 2MB
USER_AGENT = "Mozilla/5.0"

# 内网/本机主机：这类地址第三方 favicon 服务取不到，只能直连站点自身的 /favicon.ico
PRIVATE_HOST_RE = re.compile(
    r"^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|::1$)", re.I
)
# Windows 盘符路径 / UNC 路径
WIN_PATH_RE = re.compile(r"^([A-Za-z]:[\\/]|\\\\)")

# 默认局域网网段（RFC 1918 私有地址 + 本机 + 链路本地），管理员可在系统设置里追加自定义网段
DEFAULT_LAN_CIDRS = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "169.254.0.0/16",
]


def detect_network(url, lan_cidrs=None):
    """判断 URL 属于局域网(lan)还是互联网(wan)，返回 ``"lan"`` / ``"wan"``。

    - 主机名命中 ``PRIVATE_HOST_RE``（localhost / 127. / 10. / 192.168. / 172.16-31.）→ lan；
    - 无点号的主机名（如 ``nas`` / ``router``）→ 视为内网；
    - 能解析成 IP 时：私有地址，或命中 ``DEFAULT_LAN_CIDRS`` / 自定义 ``lan_cidrs`` → lan；
    - 其余（含解析失败）→ wan。
    """
    raw = (url or "").strip()
    if not raw:
        return "wan"
    parsed = urlparse(raw if "//" in raw else "//" + raw, scheme="http")
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return "wan"
    if PRIVATE_HOST_RE.match(hostname):
        return "lan"
    # 单标签主机名（无点号）：通常是内网设备名
    if "." not in hostname:
        return "lan"
    # 解析成 IP 后，按私有地址 / 自定义局域网段判断
    try:
        ip_addr = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_addr)
        if ip.is_private:
            return "lan"
        for c in list(DEFAULT_LAN_CIDRS) + list(lan_cidrs or []):
            try:
                if ip in ipaddress.ip_network(c.strip(), strict=False):
                    return "lan"
            except ValueError:
                continue
    except (socket.gaierror, ValueError, OSError):
        # 解析失败（如外网域名在服务器侧无法出网）按互联网处理
        pass
    return "wan"

# ---------- favicon 获取接口（可在系统设置里由管理员切换） ----------
# Google 的 favicon 服务在国内需要代理才能访问，因此接口做成可配置。
# network 取值：direct=直连目标站点 / cn=国内可直连 / intl=境外服务 / proxy=需要代理 / custom=自定义
FAVICON_SIZE = 64
DEFAULT_FAVICON_PROVIDER = "direct"
DIRECT_FAVICON_TEMPLATE = "{scheme}://{host}/favicon.ico"

FAVICON_PROVIDERS = [
    {
        "key": "direct",
        "label": "站点自身 /favicon.ico",
        "template": DIRECT_FAVICON_TEMPLATE,
        "network": "direct",
        "hint": "不经任何第三方，直连目标站点，无需代理；少数站点没有该文件时会取不到。",
    },
    {
        "key": "zhusl",
        "label": "zhusl 图标接口",
        "template": "https://favicon.zhusl.com/ico?url={domain}",
        "network": "cn",
        "hint": "国内可直连的第三方接口，返回 ico。",
    },
    {
        "key": "favicon_im",
        "label": "favicon.im",
        "template": "https://favicon.im/{domain}?larger=true",
        "network": "cn",
        "hint": "返回较大尺寸图标，国内多数网络可直连。",
    },
    {
        "key": "ddg",
        "label": "DuckDuckGo 图标服务",
        "template": "https://icons.duckduckgo.com/ip3/{domain}.ico",
        "network": "intl",
        "hint": "图标质量高、体积较大；境外 CDN，速度视线路而定。",
    },
    {
        "key": "icon_horse",
        "label": "Icon Horse",
        "template": "https://icon.horse/icon/{domain}",
        "network": "intl",
        "hint": "境外服务，质量好，国内速度不稳定。",
    },
    {
        "key": "unavatar",
        "label": "unavatar.io",
        "template": "https://unavatar.io/{domain}",
        "network": "intl",
        "hint": "境外聚合服务，会自动尝试多个来源。",
    },
    {
        "key": "yandex",
        "label": "Yandex Favicon",
        "template": "https://favicon.yandex.net/favicon/v2/{scheme}://{domain}?size=32",
        "network": "intl",
        "hint": "境外服务，尺寸固定 32（该接口不支持 64，传 64 会报 400）。",
    },
    {
        "key": "google",
        "label": "Google Favicon",
        "template": "https://www.google.com/s2/favicons?domain={domain}&sz={size}",
        "network": "proxy",
        "hint": "质量最好，但国内必须走代理，服务器不能出网时会失败。",
    },
    {
        "key": "gstatic",
        "label": "Google（gstatic 备用域）",
        "template": (
            "https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON"
            "&fallback_opts=TYPE,SIZE,URL&url={scheme}://{domain}&size={size}"
        ),
        "network": "proxy",
        "hint": "Google 的备用域名，同样需要代理。",
    },
    {
        "key": "custom",
        "label": "自定义接口",
        "template": "",
        "network": "custom",
        "hint": "自行填写接口地址，可用占位符：{domain} {host} {scheme} {size} {url}",
    },
]
FAVICON_PROVIDER_MAP = {p["key"]: p for p in FAVICON_PROVIDERS}


def icon_ext_from(content_type="", url=""):
    """按 Content-Type 猜扩展名，取不到时退回 URL 后缀，再退回 .png。"""
    ct = (content_type or "").lower()
    for key, ext in (
        ("svg", ".svg"),
        ("webp", ".webp"),
        ("jpeg", ".jpg"),
        ("png", ".png"),
        ("icon", ".ico"),
    ):
        if key in ct:
            return ext
    ext = os.path.splitext(urlparse(url).path)[1].lower()
    return ext if ext in ALLOWED_ICON_EXT else ".png"


def write_icon(user_id, content, ext):
    """把图标字节写入 uploads 目录，返回前端可访问的路径。"""
    fname = f"icon_{user_id}_{int(time.time() * 1000)}{ext}"
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    with open(os.path.join(Config.UPLOAD_FOLDER, fname), "wb") as fh:
        fh.write(content)
    return f"/uploads/{fname}"


def render_favicon_template(template, parsed, size=FAVICON_SIZE):
    """把模板里的占位符替换成实际值（不用 str.format，避免模板里的其它花括号报错）。"""
    scheme = parsed.scheme or "http"
    return (
        (template or "")
        .replace("{domain}", parsed.hostname or "")
        .replace("{host}", parsed.netloc or "")
        .replace("{scheme}", scheme)
        .replace("{size}", str(size))
        .replace("{url}", f"{scheme}://{parsed.netloc}")
    )


def favicon_template_for(provider=None, custom_template=""):
    """取某个接口的地址模板；custom 用管理员填写的，取不到时退回默认接口。"""
    key = (provider or "").strip() or DEFAULT_FAVICON_PROVIDER
    if key == "custom":
        template = (custom_template or "").strip()
    else:
        template = (FAVICON_PROVIDER_MAP.get(key) or {}).get("template", "")
    return template or FAVICON_PROVIDER_MAP[DEFAULT_FAVICON_PROVIDER]["template"]


def resolve_favicon_url(page_url, provider=None, custom_template="", size=FAVICON_SIZE):
    """由页面地址推断图标地址（只返回地址，不下载）。

    - 内网 / 无点主机 → 优先 ``<origin>/favicon.svg``（现代站点常用 svg）；
    - 公网域名 → 按系统设置里选定的图标接口生成地址。
    """
    raw = (page_url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "//" in raw else "//" + raw, scheme="http")
    if not parsed.netloc:
        return ""
    hostname = parsed.hostname or ""
    scheme = parsed.scheme or "http"
    if PRIVATE_HOST_RE.match(hostname) or "." not in hostname:
        return f"{scheme}://{parsed.netloc}/favicon.svg"
    return render_favicon_template(favicon_template_for(provider, custom_template), parsed, size)


def resolve_favicon_candidates(page_url, provider=None, custom_template="", size=FAVICON_SIZE):
    """返回按优先级排列的候选图标地址：选定接口 → 站点自身 /favicon.ico。

    选定接口挂掉（国内访问不到、接口下线等）时可以自动退到直连，保证「自动获取」可用。

    内网 / 无点主机：第三方服务访问不到，只能直连；此时同时尝试 ``/favicon.svg`` 与
    ``/favicon.ico``（现代站点常用 svg，旧站用 ico），按顺序逐个探测直到成功。
    """
    raw = (page_url or "").strip()
    if not raw:
        return []
    parsed = urlparse(raw if "//" in raw else "//" + raw, scheme="http")
    if not parsed.netloc:
        return []
    hostname = parsed.hostname or ""
    scheme = parsed.scheme or "http"
    base = f"{scheme}://{parsed.netloc}"
    # 内网 / 无点主机：第三方服务访问不到，只能直连；svg 优先于 ico
    if PRIVATE_HOST_RE.match(hostname) or "." not in hostname:
        return [f"{base}/favicon.svg", f"{base}/favicon.ico"]
    direct = render_favicon_template(DIRECT_FAVICON_TEMPLATE, parsed, size)
    primary = render_favicon_template(favicon_template_for(provider, custom_template), parsed, size)
    return [primary] if primary == direct else [primary, direct]


def probe_icon(url, timeout=8):
    """探测图标地址是否可用，返回 ``(内容字节, Content-Type, 错误信息)``，不落地。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read(MAX_ICON_BYTES + 1)
            ct = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        return None, "", f"接口返回 HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return None, "", f"无法连接：{getattr(exc, 'reason', exc)}"
    except Exception as exc:  # 超时等
        return None, "", f"请求失败：{exc.__class__.__name__}"
    if not content:
        return None, ct, "接口返回内容为空"
    if len(content) > MAX_ICON_BYTES:
        return None, ct, "图标文件超过 2MB"
    low = (ct or "").lower()
    if low and not (low.startswith("image/") or "icon" in low or "octet-stream" in low):
        return None, ct, f"返回的不是图片（Content-Type: {ct}）"
    return content, ct, None


def download_icon(user_id, url):
    """下载远程图标并落地，返回 ``(本地路径, 错误信息)``。"""
    content, ct, err = probe_icon(url)
    if err:
        return "", f"图标获取失败（{err}），已改用默认图标"
    try:
        return write_icon(user_id, content, icon_ext_from(ct, url)), None
    except Exception:
        return "", "图标写入本地失败，已改用默认图标"


# 兼容旧调用
_download_icon = download_icon


def _copy_local_icon(user_id, src, allow_passthrough, original):
    exists = False
    try:
        exists = os.path.isfile(src)
    except Exception:
        exists = False
    if not exists:
        # POSIX 风格且文件不存在时，可能是站内相对地址，原样保留交给前端渲染
        if allow_passthrough:
            return original, None
        return "", "本地图标文件不存在，已改用默认图标"
    ext = os.path.splitext(src)[1].lower()
    if ext not in ALLOWED_ICON_EXT:
        return "", "本地图标格式不支持（仅 png/jpg/webp/svg/ico），已改用默认图标"
    try:
        if os.path.getsize(src) > MAX_ICON_BYTES:
            return "", "图标文件超过 2MB，已改用默认图标"
        with open(src, "rb") as fh:
            content = fh.read()
        return write_icon(user_id, content, ext), None
    except Exception:
        return "", "本地图标读取失败（无访问权限？），已改用默认图标"


def localize_icon(value, user_id):
    """把「图标输入框」中的地址落地为本地文件，返回 ``(icon 值, 错误信息)``。

    - 空值 / Material Symbols 名称 / emoji → 原样保留
    - ``/uploads/...`` → 已在本地，原样保留
    - ``http(s)://...`` → 下载并保存到本地
    - ``file://`` 或本地绝对路径 → 读取并复制到本地
    落地失败时返回 ``("", 错误信息)``，图标交由展示层按标题自动匹配。
    """
    v = (value or "").strip()
    if not v or v.startswith("/uploads/"):
        return v, None

    if v.startswith("http://") or v.startswith("https://"):
        return _download_icon(user_id, v)

    src = v
    is_file_scheme = v.lower().startswith("file://")
    if is_file_scheme:
        src = v[7:]
        # file:///D:/a.png → /D:/a.png，去掉多余的前导斜杠
        if re.match(r"^/[A-Za-z]:", src):
            src = src[1:]
    is_win_path = bool(WIN_PATH_RE.match(src))
    is_posix_path = src.startswith("/")
    if is_file_scheme or is_win_path or is_posix_path:
        allow_passthrough = is_posix_path and not is_file_scheme
        return _copy_local_icon(user_id, src, allow_passthrough, v)

    # 其余：Material Symbols 名称 / emoji，原样保留
    return v, None
