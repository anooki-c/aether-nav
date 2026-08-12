"""Synology DSM 监控客户端（基于 SYNO.API）。

通过 DSM WebAPI 拉取 NAS 系统状态（CPU/内存/磁盘/网络/温度/型号）与
Docker 容器运行状态，并提供容器启停操作。

凭据来源优先级：
  1. 环境变量 SYNO_HOST / SYNO_PORT / SYNO_USER / SYNO_PASS / SYNO_HTTPS
  2. 数据库 Setting 表（syno_* 键）

设计要点：
  - 密码仅在内存中使用，不写入日志。
  - 群晖默认自签证书，故关闭 TLS 校验并屏蔽告警。
  - 不同 DSM 版本字段差异较大，各 get_* 独立容错，单个 API 失败不影响其余。
"""
import os
import time
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_PORT_HTTP = 5000
DEFAULT_PORT_HTTPS = 5001
TIMEOUT = 10


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


class SynoClient:
    def __init__(self, config=None):
        self.cfg = config or load_config()
        self.sid = None
        self.base = "{scheme}://{host}:{port}".format(
            scheme="https" if self.cfg["https"] else "http",
            host=self.cfg["host"],
            port=self.cfg["port"],
        )

    # ---------- 底层请求 ----------
    def _api(self, api_name, version, method, params=None, try_login=True):
        if not self.sid and try_login:
            self.login()
        qs = {
            "api": api_name,
            "version": version,
            "method": method,
            "_sid": self.sid or "",
        }
        if params:
            qs.update(params)
        try:
            resp = requests.get(
                self.base + "/webapi/entry.cgi",
                params=qs,
                timeout=TIMEOUT,
                verify=False,
            )
            data = resp.json()
        except requests.RequestException as e:
            raise SynoError("请求 DSM 失败: %s" % e)
        except ValueError:
            raise SynoError("DSM 返回非 JSON 响应（可能地址/端口不正确）")
        if data.get("success") is not True:
            code = (data.get("error") or {}).get("code")
            # 119/105/106 多表示未授权或 sid 失效 → 重试一次登录
            if code in (119, 105, 106) and try_login:
                self.sid = None
                self.login()
                return self._api(api_name, version, method, params, try_login=False)
            raise SynoError("DSM API 错误 code=%s" % code)
        return data.get("data", {})

    def login(self):
        try:
            resp = requests.get(
                self.base + "/webapi/auth.cgi",
                params={
                    "api": "SYNO.API.Auth",
                    "version": 6,
                    "method": "login",
                    "account": self.cfg["user"],
                    "passwd": self.cfg["password"],
                    "session": "Docker",
                    "format": "sid",
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
        self.sid = (data.get("data") or {}).get("sid")
        if not self.sid:
            raise SynoError("群晖登录未返回 sid")
        return self.sid

    def logout(self):
        if self.sid:
            try:
                requests.get(
                    self.base + "/webapi/auth.cgi",
                    params={"api": "SYNO.API.Auth", "version": 1, "method": "logout", "_sid": self.sid},
                    timeout=TIMEOUT,
                    verify=False,
                )
            except requests.RequestException:
                pass
        self.sid = None

    # ---------- 数据拉取（各自容错） ----------
    def get_system_info(self):
        try:
            d = self._api("SYNO.Core.System.Info", 1, "get")
        except SynoError:
            d = {}
        return {
            "model": d.get("model"),
            "version": d.get("version"),
            "uptime_seconds": d.get("uptime"),
            "temperature": d.get("temperature"),
        }

    def get_utilization(self):
        try:
            d = self._api("SYNO.Core.System.Utilization", 1, "get")
        except SynoError:
            d = {}
        cpu = d.get("cpu") or {}
        cpu_pct = cpu.get("15min")
        if cpu_pct is None:
            cpu_pct = cpu.get("user")
        mem = d.get("memory") or {}
        net = d.get("network") or {}
        disk = d.get("disk") or {}

        # 网络：聚合各接口累计 rx/tx 字节
        rx = tx = 0
        for v in net.values():
            if isinstance(v, dict):
                rx += int(v.get("rx", 0) or 0)
                tx += int(v.get("tx", 0) or 0)

        # 磁盘：优先 util 字段，否则取各设备利用率均值
        disk_util = None
        if isinstance(disk, dict):
            if "util" in disk:
                disk_util = disk["util"]
            else:
                vals = [float(x) for x in disk.values() if isinstance(x, (int, float))]
                if vals:
                    disk_util = round(sum(vals) / len(vals), 1)

        return {
            "cpu": _to_pct(cpu_pct),
            "memory": _to_pct(mem.get("real_usage")),
            "network": {"rx_bytes": rx, "tx_bytes": tx},
            "disk_util": _to_pct(disk_util),
        }

    def get_storage(self):
        try:
            d = self._api("SYNO.Core.Storage.Storage", 1, "get")
        except SynoError:
            d = {}
        volumes = []
        for v in (d.get("volumes") or []):
            total = v.get("size")
            used = v.get("used")
            pct = None
            if total and used is not None and total:
                try:
                    pct = round(used / total * 100, 1)
                except (TypeError, ValueError):
                    pct = None
            volumes.append({
                "name": v.get("name") or v.get("id"),
                "total_bytes": total,
                "used_bytes": used,
                "usage_pct": pct,
            })
        return {"volumes": volumes}

    def _extract_container_ip(self, c):
        """容错提取容器网络 IP（不同 DSM 版本字段名不同）。"""
        ip = c.get("ip")
        if isinstance(ip, str) and ip:
            return ip

        def _dig(o):
            if isinstance(o, dict):
                for k in ("ip", "ip_address", "addr", "IPv4Address"):
                    v = o.get(k)
                    if isinstance(v, str) and v:
                        return v
                for v in o.values():
                    r = _dig(v)
                    if r:
                        return r
            elif isinstance(o, list):
                for v in o:
                    r = _dig(v)
                    if r:
                        return r
            return None

        return _dig(c.get("network"))

    def get_containers(self):
        try:
            d = self._api("SYNO.Docker.Container.Container", 1, "list", {"limit": -1})
        except SynoError:
            d = {}
        out = []
        for c in (d.get("containers") or []):
            out.append({
                "id": c.get("id"),
                "name": c.get("name"),
                "state": c.get("state"),
                "status": c.get("status"),
                "image": c.get("image"),
                "cpu_pct": c.get("cpu"),
                "mem_bytes": c.get("mem"),
                "container_ip": self._extract_container_ip(c),
                "ports": c.get("ports"),
            })
        return {"containers": out}

    def container_action(self, container_id, action):
        """action: start / stop / restart"""
        self._api("SYNO.Docker.Container.Container", 1, action, {"id": container_id})
        return True

    def snapshot(self):
        """一次性拉取所有监控数据；单模块失败不阻断其他。"""
        errors = []
        try:
            info = self.get_system_info()
        except SynoError as e:
            info, errors = {}, [str(e)]
        util = self.get_utilization()
        storage = self.get_storage()
        try:
            containers = self.get_containers().get("containers", [])
        except SynoError as e:
            containers = []
            errors.append(str(e))
        return {
            "host": self.cfg["host"],
            "system": info,
            "cpu": util.get("cpu"),
            "memory": util.get("memory"),
            "network": util.get("network"),
            "disk_util": util.get("disk_util"),
            "storage": storage,
            "containers": containers,
            "fetched_at": int(time.time()),
            "errors": errors,
        }
