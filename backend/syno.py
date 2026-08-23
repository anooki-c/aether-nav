"""Synology DSM 监控客户端（基于 SYNO.API）。

通过 DSM WebAPI 拉取 NAS 利用率（CPU/内存/磁盘/网络/存储）与 Docker 容器
运行状态、网络 IP、端口映射，并提供容器启停操作。

凭据来源优先级：
  1. 环境变量 SYNO_HOST / SYNO_PORT / SYNO_USER / SYNO_PASS / SYNO_HTTPS
  2. 数据库 Setting 表（syno_* 键）

关键实现要点（已在 DSM 7.2.2 Container Manager 上实测验证）：
  - 登录必须带 enable_syno_token=yes 以获取 DSM 7 CSRF 令牌 synotoken；
    调用 SYNO.Docker.Container 时若不带 SynoToken 会返回 114。
  - 容器列表：SYNO.Docker.Container v1 method=list（session=Docker）。
    网络 IP / 网关在 NetworkSettings.Networks（多网络即多 key）。
  - 端口映射不在 list 接口里，需对每个容器 SYNO.Docker.Container v1 method=get
    （参数先 name 后 id），从 data.details.NetworkSettings.Ports 取。
  - 利用率：SYNO.Core.System.Utilization v1（session=Core），不强制 SynoToken。
  - 存储容量：SYNO.Storage.CGI.Storage v1 method=load_info（session=Core）。
    替代常返回 101 的 SYNO.Core.Storage.Volume，可拉到真实卷容量（size.total/used）。
  - 系统健康/主机信息：SYNO.Core.System.SystemHealth v1 method=get（session=Core），
    返回 hostname / uptime / interfaces。
  - TLS 默认校验；自签证书可通过 SYNO_VERIFY_SSL=false 或 syno_verify_ssl=false 显式关闭。
  - 密码仅在内存中使用，不写入日志。
"""
import os
import re
import time
import threading
import concurrent.futures
import urllib3
import requests


# ── 静态数据缓存（分层刷新核心）─────────────────────────────────────────
# 存储容量 / 系统健康 变化极慢（硬盘大小、主机名几天不变），但存储接口在部分
# NAS 上偶发缓慢/挂起。故将其与易变数据（容器/利用率）解耦：长 TTL 缓存、
# 后台静默刷新、刷新失败回退旧值且不频繁重试，绝不阻塞页面。
_STATIC_CACHE = {"key": None, "storage": None, "health": None, "ts": 0.0, "next_retry": 0.0}
_STATIC_TTL = 300.0  # 5 分钟：静态数据自动刷新间隔
_STATIC_LOCK = threading.Lock()
_CLIENT_CACHE = {}
_CLIENT_LOCK = threading.Lock()


def _safe_call(fn):
    """执行 fn，任何异常都转为 SynoError 返回（不抛出），便于并发聚合时区分成败。"""
    try:
        return fn()
    except SynoError as e:
        return e
    except Exception as e:  # noqa: BLE001 — 任何意外都转为错误对象，避免拖垮整页
        return SynoError("调用异常: %s" % e)

DEFAULT_PORT_HTTP = 5000
DEFAULT_PORT_HTTPS = 5001
TIMEOUT = 15

# 已实测验证的 API 规范：(api_name, path, version, session)
_CONTAINER_API = ("SYNO.Docker.Container", "entry.cgi", 1, "Docker")
_UTIL_API = ("SYNO.Core.System.Utilization", "entry.cgi", 1, "Core")


class SynoError(Exception):
    pass


def _setting_get(key, default=None):
    from backend.models import Setting
    return Setting.get(key, default)


def load_config():
    """从环境变量或 Setting 表读取群晖连接配置。"""
    host = os.environ.get("SYNO_HOST") or _setting_get("syno_host", "")
    port = os.environ.get("SYNO_PORT") or _setting_get("syno_port", "")
    user = os.environ.get("SYNO_USER") or _setting_get("syno_user", "")
    password = os.environ.get("SYNO_PASS") or _setting_get("syno_pass", "")
    https_env = os.environ.get("SYNO_HTTPS")
    verify_env = os.environ.get("SYNO_VERIFY_SSL")
    if https_env is None:
        https = str(_setting_get("syno_https", "0")).lower() in ("1", "true", "yes")
    else:
        https = str(https_env).lower() in ("1", "true", "yes")
    if verify_env is None:
        verify_ssl = str(_setting_get("syno_verify_ssl", "true")).lower() in ("1", "true", "yes")
    else:
        verify_ssl = str(verify_env).lower() in ("1", "true", "yes")
    try:
        port = int(port) if port else (DEFAULT_PORT_HTTPS if https else DEFAULT_PORT_HTTP)
    except (TypeError, ValueError):
        port = DEFAULT_PORT_HTTPS if https else DEFAULT_PORT_HTTP
    return {
        "host": (host or "").strip(),
        "port": port,
        "user": (user or "").strip(),
        "password": password or "",
        "https": bool(https),
        "verify_ssl": bool(verify_ssl),
    }


def config_key(config):
    """Stable password-free key for DSM client and snapshot caches."""
    cfg = config or load_config()
    return "{}://{}:{}:{}".format(
        "https" if cfg.get("https") else "http",
        cfg.get("host", "").strip().lower(),
        cfg.get("port"),
        cfg.get("user", "").strip(),
    )


def get_client(config=None):
    cfg = config or load_config()
    key = config_key(cfg)
    with _CLIENT_LOCK:
        client = _CLIENT_CACHE.get(key)
        if client is None or client.cfg.get("password") != cfg.get("password"):
            client = SynoClient(cfg)
            _CLIENT_CACHE[key] = client
        return client


def clear_client_cache(config=None):
    with _CLIENT_LOCK:
        if config is None:
            _CLIENT_CACHE.clear()
        else:
            _CLIENT_CACHE.pop(config_key(config), None)
    with _STATIC_LOCK:
        _STATIC_CACHE.update({"key": None, "storage": None, "health": None, "ts": 0.0, "next_retry": 0.0})


def _to_pct(v):
    if v is None:
        return None
    try:
        return round(float(v), 1)
    except (TypeError, ValueError):
        return None


def _to_num(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _norm_volume_name(v):
    """把存储卷归一化为利用率接口同款名称（如 'volume3'）。

    存储 CGI（SYNO.Storage.CGI.Storage）的卷：vol_path='/volume3' 或
    id='volume_3'；利用率接口（SYNO.Core.System.Utilization）的 space.volume
    名称形如 'volume3'。归一化后两者可按名称对齐合并。
    """
    path = (v.get("vol_path") or "") if isinstance(v, dict) else ""
    if path:
        return path.strip("/").split("/")[0]
    vid = (v.get("id") or "") if isinstance(v, dict) else ""
    if vid:
        # 'volume_3' / 'volume 3' -> 'volume3'
        return re.sub(r"[_ ]+", "", vid)
    name = (v.get("display_name") or v.get("name") or "") if isinstance(v, dict) else ""
    return name.strip()


def _extract_networks(c):
    """从容器 dict 提取多网络 [{name, ip, gateway}]。"""
    out = []
    ns = (c.get("NetworkSettings") or {}) if isinstance(c, dict) else {}
    nets = ns.get("Networks") or {}
    if isinstance(nets, dict):
        for name, info in nets.items():
            if not isinstance(info, dict):
                continue
            out.append({
                "name": name,
                "ip": info.get("IPAddress") or None,
                "gateway": info.get("Gateway") or None,
            })
    return out


def _extract_ports(detail):
    """从 get 详情响应（{data:{details:...}}）提取端口 [{ip, host, container, type}]。"""
    out = []
    cont = ((detail.get("data") or {}).get("details")) or {}
    if not isinstance(cont, dict):
        return out
    ns = cont.get("NetworkSettings") or {}
    ports = ns.get("Ports") if isinstance(ns, dict) else None
    if not isinstance(ports, dict):
        return out
    for spec, binds in ports.items():
        if "/" in spec:
            cport, ptype = spec.split("/", 1)
        else:
            cport, ptype = spec, "tcp"
        entries = binds if isinstance(binds, list) and binds else [None]
        for b in entries:
            if isinstance(b, dict):
                out.append({
                    "ip": b.get("HostIp", "0.0.0.0"),
                    "host": b.get("HostPort"),
                    "container": cport,
                    "type": ptype,
                })
            else:
                # 仅容器内暴露、未发布到宿主机
                out.append({"ip": "0.0.0.0", "host": None, "container": cport, "type": ptype})
    return out


class SynoClient:
    def __init__(self, config=None):
        self.cfg = config or load_config()
        self.base = "{scheme}://{host}:{port}".format(
            scheme="https" if self.cfg["https"] else "http",
            host=self.cfg["host"],
            port=self.cfg["port"],
        )
        self._sessions = {}  # session -> (sid, synotoken)
        self.cache_key = config_key(self.cfg)

    # ---------- 登录（按 session 缓存，带 SynoToken） ----------
    def _login(self, session):
        try:
            resp = requests.get(
                self.base + "/webapi/auth.cgi",
                params={
                    "api": "SYNO.API.Auth",
                    "version": 6,
                    "method": "login",
                    "account": self.cfg["user"],
                    "passwd": self.cfg["password"],
                    "session": session,
                    "format": "sid",
                    "enable_syno_token": "yes",
                },
                timeout=TIMEOUT,
                verify=self.cfg["verify_ssl"],
            )
            data = resp.json()
        except requests.RequestException as e:
            raise SynoError("无法连接群晖: %s" % e)
        except ValueError:
            raise SynoError("群晖返回非 JSON 响应（可能地址/端口不正确）")
        if data.get("success") is not True:
            raise SynoError("群晖登录失败（账号/密码错误或未开启 API）")
        d = data.get("data") or {}
        sid = d.get("sid")
        if not sid:
            raise SynoError("群晖登录未返回 sid")
        return sid, d.get("synotoken")

    def _ensure_login(self, session):
        cached = self._sessions.get(session)
        if cached:
            return cached
        sid, synotoken = self._login(session)
        self._sessions[session] = (sid, synotoken)
        return self._sessions[session]

    # ---------- 底层请求 ----------
    def _api(self, api_name, version, method, params=None, session="Core", http_method="get", timeout=TIMEOUT):
        sid, synotoken = self._ensure_login(session)

        def _request(sid_val, synotoken_val):
            qs = {
                "api": api_name,
                "version": version,
                "method": method,
                "_sid": sid_val,
            }
            if synotoken_val:
                qs["SynoToken"] = synotoken_val
            if params:
                qs.update(params)
            try:
                url = self.base + "/webapi/entry.cgi"
                if http_method.lower() == "post":
                    resp = requests.post(url, data=qs, timeout=timeout, verify=self.cfg["verify_ssl"])
                else:
                    resp = requests.get(url, params=qs, timeout=timeout, verify=self.cfg["verify_ssl"])
                return resp.json()
            except requests.RequestException as e:
                raise SynoError("请求 DSM 失败: %s" % e)
            except ValueError:
                raise SynoError("DSM 返回非 JSON 响应（可能地址/端口不正确）")

        data = _request(sid, synotoken)
        if data.get("success") is not True:
            code = (data.get("error") or {}).get("code")
            # 119/105/106 表示未授权或 sid 失效；114 表示 Docker API 缺少/过期 SynoToken → 重新登录一次
            if code in (119, 105, 106, 114):
                self._sessions.pop(session, None)
                sid, synotoken = self._ensure_login(session)
                data = _request(sid, synotoken)
            if data.get("success") is not True:
                raise SynoError("DSM API 错误 code=%s" % (data.get("error") or {}).get("code"))
        return data.get("data", {})

    # ---------- 容器列表（session=Docker） ----------
    def get_containers(self):
        d = self._api("SYNO.Docker.Container", 1, "list",
                      {"limit": -1, "offset": 0}, session="Docker")
        out = []
        for c in (d.get("containers") or []):
            if not isinstance(c, dict):
                continue
            labels = c.get("Labels") or {}
            out.append({
                "id": c.get("id"),
                "name": (c.get("name") or "").lstrip("/"),
                "image": c.get("image"),
                "status": c.get("status") or (c.get("state") or {}).get("Status"),
                "state": (c.get("state") or {}).get("Status") or c.get("status"),
                "networks": _extract_networks(c),
                "created": c.get("created"),
                "project": labels.get("com.docker.compose.project"),
                "up_status": c.get("up_status"),
            })
        return out

    # ---------- 容器详情（按需取端口，session=Docker） ----------
    def get_container_detail(self, name=None, cid=None):
        for key, val in (("name", name), ("id", cid)):
            if not val:
                continue
            try:
                d = self._api("SYNO.Docker.Container", 1, "get", {key: val}, session="Docker")
            except SynoError:
                continue
            return {"ports": _extract_ports({"data": d})}
        return None

    def get_container_ports_batch(self, containers, max_workers=6):
        """Fetch port mappings concurrently and preserve per-container errors."""
        result = {}

        def fetch(container):
            key = container.get("id") or container.get("name")
            try:
                detail = self.get_container_detail(name=container.get("name"), cid=container.get("id"))
                if detail is None:
                    return key, {"ports": [], "ok": False, "error": "容器详情不存在"}
                return key, {"ports": detail.get("ports") or [], "ok": True, "error": None}
            except SynoError as exc:
                return key, {"ports": [], "ok": False, "error": str(exc)}

        items = list(containers or [])
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(fetch, c) for c in items]
            for future in futures:
                key, value = future.result()
                if key:
                    result[key] = value
        return result

    # ---------- 利用率（session=Core） ----------
    def get_utilization(self):
        d = self._api("SYNO.Core.System.Utilization", 1, "get", session="Core")
        cpu = d.get("cpu") or {}
        mem = d.get("memory") or {}
        net = d.get("network") or []
        disk = d.get("disk") or {}
        space = d.get("space") or {}
        rx = tx = 0
        for v in net:
            if isinstance(v, dict):
                rx += int(v.get("rx", 0) or 0)
                tx += int(v.get("tx", 0) or 0)
        disk_util = (disk.get("total") or {}).get("utilization")
        space_util = (space.get("total") or {}).get("utilization")
        # CPU 使用率 = 用户态 + 系统态 + 其他（iowait/irq 等），三者之和即总占用
        cpu_usage = (cpu.get("user_load") or 0) + (cpu.get("system_load") or 0) + (cpu.get("other_load") or 0)
        try:
            cpu_usage = min(100, round(float(cpu_usage), 1))
        except (TypeError, ValueError):
            cpu_usage = None
        # 存储卷列表：优先 space.volume，缺失时回退物理盘 disk.disk
        vols = space.get("volume") or []
        if not vols:
            vols = disk.get("disk") or []
        volumes = []
        for v in vols:
            if not isinstance(v, dict):
                continue
            volumes.append({
                "name": v.get("display_name") or v.get("device"),
                "utilization": _to_pct(v.get("utilization")),
                "read_byte": v.get("read_byte"),
                "write_byte": v.get("write_byte"),
            })
        return {
            "cpu_usage": cpu_usage,
            "cpu_user": cpu.get("user_load"),
            "cpu_system": cpu.get("system_load"),
            "cpu_other": cpu.get("other_load"),
            "cpu_1": cpu.get("1min_load"),
            "cpu_5": cpu.get("5min_load"),
            "cpu_15": cpu.get("15min_load"),
            "memory": _to_pct(mem.get("real_usage")),
            "memory_total": mem.get("total_real"),
            "memory_avail": mem.get("avail_real"),
            "network": {"rx_bytes": rx, "tx_bytes": tx},
            "disk_io": _to_pct(disk_util),
            "space_util": _to_pct(space_util),
            "volumes": volumes,
        }

    # ---------- 存储容量（session=Core） ----------
    def get_storage(self):
        """容量占用（SYNO.Storage.CGI.Storage load_info）。

        替代常返回 101 的 SYNO.Core.Storage.Volume。该接口在 DSM 7.2.2 上实测可用，
        返回每个卷的 size.total / size.used（字符串数字），并与利用率接口的
        space.volume（name 形如 'volume3'）按归一化名称对齐，供前端合并容量与 I/O。
        """
        d = self._api("SYNO.Storage.CGI.Storage", 1, "load_info", session="Core", timeout=30)
        vols = d.get("volumes") or []
        if isinstance(vols, dict):
            vols = list(vols.values())
        out = []
        for v in vols:
            if not isinstance(v, dict):
                continue
            size = v.get("size") or {}
            total = _to_num(size.get("total"))
            if total is None:
                continue
            used = _to_num(size.get("used"))
            pct = round(used / total * 100, 1) if used is not None else None
            norm = _norm_volume_name(v)
            if not norm:
                continue
            out.append({
                "name": norm,
                "display_name": v.get("display_name") or v.get("name") or norm,
                "total": total,
                "used": used,
                "usage_pct": pct,
            })
        return out

    # ---------- 系统健康 / 主机信息（session=Core） ----------
    def get_system_health(self):
        """系统健康 / 主机信息（SYNO.Core.System.SystemHealth get）。

        返回 hostname / uptime（HH:MM:SS）/ interfaces（含 IP）。
        """
        d = self._api("SYNO.Core.System.SystemHealth", 1, "get", session="Core")
        interfaces = []
        for itf in (d.get("interfaces") or []):
            if isinstance(itf, dict):
                interfaces.append({
                    "id": itf.get("id"),
                    "ip": itf.get("ip"),
                    "type": itf.get("type"),
                })
        return {
            "hostname": d.get("hostname"),
            "uptime": d.get("uptime"),
            "interfaces": interfaces,
        }

    # ---------- 启停操作（session=Docker） ----------
    def container_action(self, name, action, cid=None):
        """action: start / stop / restart

        DSM Docker API 的 start/stop/restart 方法使用 ``name`` 参数（容器名），
        而非 ``id``（容器 hash）。前端直接传容器名。
        """
        try:
            self._api("SYNO.Docker.Container", 1, action, {"name": name}, session="Docker")
        except SynoError:
            if not cid:
                raise
            self._api("SYNO.Docker.Container", 1, action, {"id": cid}, session="Docker")
        return True

    # ---------- 一次性快照（分层刷新：易变实时 / 静态长缓存） ----------
    def snapshot(self, force=False):
        diagnostics = {}

        # ① 易变且快：容器列表 + 利用率（CPU/内存/网络/磁盘IO），每次轮询实时拉取。
        #    这两个接口正常 <1s，是监控页最该"新鲜"的数据，保持 15s 实时。
        ex = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        try:
            f_con = ex.submit(_safe_call, self.get_containers)
            f_util = ex.submit(_safe_call, self.get_utilization)
            containers = f_con.result(timeout=20)
            util = f_util.result(timeout=20)
        finally:
            ex.shutdown(wait=False)

        # ② 静态且偶发慢：存储容量 + 系统健康，走长 TTL 缓存（见 _load_static）。
        storage, health, static_diag = self._load_static(force)
        diagnostics.update(static_diag)

        if isinstance(containers, Exception):
            diagnostics["containers"] = {"ok": False, "error": str(containers)}
            containers = []
        else:
            diagnostics["containers"] = {"ok": True}

        if isinstance(util, Exception):
            diagnostics["utilization"] = {"ok": False, "error": str(util)}
            util = {}
        else:
            diagnostics["utilization"] = {"ok": True}

        util = util or {}
        util["storage"] = storage

        return {
            "host": self.cfg["host"],
            "containers": containers,
            "utilization": util,
            "system_health": health,
            "fetched_at": int(time.time()),
            "diagnostics": diagnostics,
        }

    def _load_static(self, force):
        """拉取静态数据（存储容量 + 系统健康），带长 TTL 缓存与失败回退。

        返回 (storage, health, diagnostics)。行为：
          - 缓存新鲜（< _STATIC_TTL 且已有数据）且非强制 → 直接返回缓存（秒级）。
          - 过期 / 强制 → 并发刷新；存储接口单独只等 8s，超时即视为本次失败。
          - 刷新成功才更新数据；失败则回退旧值（若有），并统一设置 next_retry，
            保证挂起/失败期间每 15s 轮询**不会**反复狠打 DSM（最多每 5 分钟一次）。
        """
        diagnostics = {}
        now = time.time()
        with _STATIC_LOCK:
            cached = _STATIC_CACHE
            if cached.get("key") != self.cache_key:
                cached.update({"key": self.cache_key, "storage": None, "health": None, "ts": 0.0, "next_retry": 0.0})
            need_refresh = force or (now >= cached["next_retry"])
            if not need_refresh:
                diagnostics["storage"] = {"ok": True, "cached": True}
                diagnostics["system_health"] = {"ok": True, "cached": True}
                return cached["storage"], cached["health"], diagnostics

        # 需要刷新：并发拉取，存储单独只等 8s
        new_store = None
        new_health = None
        ex = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        try:
            f_store = ex.submit(_safe_call, self.get_storage)
            f_health = ex.submit(_safe_call, self.get_system_health)
            try:
                store_res = f_store.result(timeout=8)
                if not isinstance(store_res, Exception):
                    new_store = store_res
            except concurrent.futures.TimeoutError:
                pass  # 存储缓慢：本次视为失败，回退旧值
            health_res = f_health.result(timeout=20)
            if not isinstance(health_res, Exception):
                new_health = health_res
        finally:
            ex.shutdown(wait=False)

        with _STATIC_LOCK:
            cached = _STATIC_CACHE
            if new_store is not None:
                cached["storage"] = new_store
                diagnostics["storage"] = {"ok": True}
            else:
                if cached["storage"] is not None:
                    new_store = cached["storage"]  # 回退旧值，页面仍有数据
                    diagnostics["storage"] = {"ok": True, "cached": True}
                else:
                    diagnostics["storage"] = {"ok": False, "error": "存储信息获取超时/失败"}
            if new_health is not None:
                cached["health"] = new_health
                diagnostics["system_health"] = {"ok": True}
            else:
                if cached["health"] is not None:
                    new_health = cached["health"]
                    diagnostics["system_health"] = {"ok": True, "cached": True}
                else:
                    diagnostics["system_health"] = {"ok": False, "error": "系统健康获取失败"}
            # 关键：无论成败都更新 next_retry，避免挂起时每轮询都重新打 DSM
            cached["ts"] = now
            cached["next_retry"] = now + _STATIC_TTL
        return new_store, new_health, diagnostics
