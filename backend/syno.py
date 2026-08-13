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
  - 群晖默认自签证书，故关闭 TLS 校验并屏蔽告警。
  - 密码仅在内存中使用，不写入日志。
"""
import os
import time
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
    if https_env is None:
        https = str(_setting_get("syno_https", "0")).lower() in ("1", "true", "yes")
    else:
        https = str(https_env).lower() in ("1", "true", "yes")
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
    }


def _to_pct(v):
    if v is None:
        return None
    try:
        return round(float(v), 1)
    except (TypeError, ValueError):
        return None


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
                verify=False,
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
    def _api(self, api_name, version, method, params=None, session="Core"):
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
                resp = requests.get(
                    self.base + "/webapi/entry.cgi",
                    params=qs,
                    timeout=TIMEOUT,
                    verify=False,
                )
                return resp.json()
            except requests.RequestException as e:
                raise SynoError("请求 DSM 失败: %s" % e)
            except ValueError:
                raise SynoError("DSM 返回非 JSON 响应（可能地址/端口不正确）")

        data = _request(sid, synotoken)
        if data.get("success") is not True:
            code = (data.get("error") or {}).get("code")
            # 119/105/106 表示未授权或 sid 失效 → 重新登录一次
            if code in (119, 105, 106):
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

    # ---------- 存储容量（session=Core，该 DSM 常返回 101） ----------
    def get_storage(self):
        """容量占用（SYNO.Core.Storage.Volume）。该 DSM 常返回 101，需账号有 Storage 权限。"""
        d = self._api("SYNO.Core.Storage.Volume", 1, "list",
                      {"offset": 0, "limit": -1}, session="Core")
        vols = d.get("volumes")
        if isinstance(vols, dict):
            vols = vols.get("volumes") or []
        out = []
        for v in (vols or []):
            if not isinstance(v, dict):
                continue
            total = v.get("total_size") or v.get("size") or 0
            used = v.get("used_size") or v.get("used") or 0
            pct = round(used / total * 100, 1) if total else None
            out.append({
                "name": v.get("name") or v.get("display_name"),
                "total": total,
                "used": used,
                "usage_pct": pct,
            })
        return out

    # ---------- 启停操作（session=Docker） ----------
    def container_action(self, cid, action):
        """action: start / stop / restart"""
        self._api("SYNO.Docker.Container", 1, action, {"id": cid}, session="Docker")
        return True

    # ---------- 一次性快照（容错聚合） ----------
    def snapshot(self):
        diagnostics = {}
        try:
            containers = self.get_containers()
            diagnostics["containers"] = {"ok": True}
        except SynoError as e:
            containers = []
            diagnostics["containers"] = {"ok": False, "error": str(e)}
        try:
            util = self.get_utilization()
            diagnostics["utilization"] = {"ok": True}
        except SynoError as e:
            util = {}
            diagnostics["utilization"] = {"ok": False, "error": str(e)}
        try:
            util["storage"] = self.get_storage()
            diagnostics["storage"] = {"ok": True}
        except SynoError as e:
            util["storage"] = None
            diagnostics["storage"] = {"ok": False, "error": str(e)}
        return {
            "host": self.cfg["host"],
            "containers": containers,
            "utilization": util,
            "fetched_at": int(time.time()),
            "diagnostics": diagnostics,
        }
