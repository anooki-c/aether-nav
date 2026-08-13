#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
独立测试脚本：直连 Synology DSM 7.2 Container Manager，
仅拉取 Docker 容器信息（多网络 IP + 端口映射），并打印原始响应，
用于验证 API 字段结构后再集成进项目。

用法（环境变量）：
    export SYNO_HOST="10.10.123.106"
    export SYNO_PORT="5000"          # 或 5001(HTTPS)
    export SYNO_USER="Anooki"
    export SYNO_HTTPS="0"            # 1=HTTPS, 0=HTTP
    export SYNO_PASS="你的密码"       # 不设则运行时交互输入
    python scripts/test_syno_containers.py

也可命令行覆盖：
    python scripts/test_syno_containers.py --host 10.10.123.106 --port 5000 --user Anooki --https 0
"""
import argparse
import getpass
import json
import os
import sys
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TIMEOUT = 15


def build_client(args):
    host = args.host or os.environ.get("SYNO_HOST")
    if not host:
        host = input("DSM 地址 (IP): ").strip()
    port = args.port or os.environ.get("SYNO_PORT")
    user = args.user or os.environ.get("SYNO_USER") or input("用户名: ").strip()
    password = os.environ.get("SYNO_PASS") or args.password or getpass.getpass("密码: ")
    if args.https is not None:
        https = args.https
    else:
        env = os.environ.get("SYNO_HTTPS")
        https = str(env or "0").lower() in ("1", "true", "yes")
    if not port:
        port = 5001 if https else 5000
    else:
        port = int(port)
    scheme = "https" if https else "http"
    base = "%s://%s:%s" % (scheme, host, port)
    return {
        "base": base,
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "https": https,
    }


def login(cfg, session="Core"):
    """登录，返回 (sid, synotoken)。session 可选 Core / Docker。

    synotoken 是 DSM 7 引入的 CSRF 令牌。部分 API（尤其是 Container Manager 的
    SYNO.Docker.*）在调用时【必须】带上它，否则返回错误码 114。Utilization 等
    Core API 不强制，但统一带上最稳妥。
    """
    resp = requests.get(
        cfg["base"] + "/webapi/auth.cgi",
        params={
            "api": "SYNO.API.Auth",
            "version": 6,
            "method": "login",
            "account": cfg["user"],
            "passwd": cfg["password"],
            "session": session,
            "format": "sid",
            "enable_syno_token": "yes",
        },
        timeout=TIMEOUT,
        verify=False,
    )
    body = resp.text
    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError(
            "auth.cgi 返回非 JSON (HTTP %s, session=%s)：\n%s" % (resp.status_code, session, body[:400])
        )
    if data.get("success") is not True:
        raise RuntimeError("登录失败 (session=%s)：%s" % (session, json.dumps(data, ensure_ascii=False)))
    d = data.get("data") or {}
    sid = d.get("sid")
    if not sid:
        raise RuntimeError("登录成功但未返回 sid (session=%s)：%s" % (session, json.dumps(data, ensure_ascii=False)))
    synotoken = d.get("synotoken")
    return sid, synotoken


def fetch_containers(cfg, sid, path, version):
    """拉取容器列表，返回完整原始 JSON。"""
    resp = requests.get(
        cfg["base"] + "/webapi/" + path,
        params={
            "api": "SYNO.Docker.Container.Container",
            "version": version,
            "method": "list",
            "limit": -1,
            "_sid": sid,
        },
        timeout=TIMEOUT,
        verify=False,
    )
    return resp.json()


def probe_versions(cfg, sid, api_name, path, method="get", extra=None, versions=(1, 2, 3, 4, 5, 6, 7), synotoken=None):
    """对某个 API 依次尝试多个版本，返回 (best_raw, best_version)。"""
    best = None
    best_ver = None
    for ver in versions:
        try:
            raw = fetch_api(cfg, sid, api_name, path, ver, method=method, extra=extra, synotoken=synotoken)
        except Exception as e:
            print("    v%d 请求异常: %s" % (ver, e))
            continue
        success = raw.get("success")
        err = raw.get("error", {})
        code = err.get("code") if isinstance(err, dict) else err
        if success:
            best = raw
            best_ver = ver
            print("    %s v%d -> ✅ success" % (api_name, ver))
            break
        else:
            print("    %s v%d -> 失败 code=%s" % (api_name, ver, code))
    return best, best_ver


# ---------- 多网络 / 端口解析（兼容多种 DSM 返回结构） ----------
def extract_networks(c):
    """返回 [{name, ip, gateway}]，支持一个容器加入多个网络。"""
    out = []
    # 结构1：Synology 7.2 list 的 network 字典（键=网络名）
    net = c.get("network")
    if isinstance(net, dict) and net:
        for name, v in net.items():
            if isinstance(v, dict):
                out.append({
                    "name": name,
                    "ip": v.get("ip") or v.get("IPv4Address") or v.get("addr"),
                    "gateway": v.get("gateway"),
                })
        if out:
            return out
    # 结构2：Docker 引擎风格 NetworkSettings.Networks
    ns = (c.get("NetworkSettings") or {}).get("Networks")
    if isinstance(ns, dict) and ns:
        for name, v in ns.items():
            if isinstance(v, dict):
                out.append({
                    "name": name,
                    "ip": v.get("IPAddress") or v.get("IPv4Address"),
                    "gateway": v.get("Gateway"),
                })
        if out:
            return out
    # 结构3：顶层 networks 字典
    nets2 = c.get("networks")
    if isinstance(nets2, dict) and nets2:
        for name, v in nets2.items():
            if isinstance(v, dict):
                out.append({
                    "name": name,
                    "ip": v.get("ip") or v.get("IPv4Address") or v.get("addr"),
                    "gateway": v.get("gateway"),
                })
        if out:
            return out
    # 兼容：单个 ip 字段
    single = c.get("ip")
    if isinstance(single, str) and single:
        out.append({"name": "default", "ip": single, "gateway": c.get("gateway")})
    return out


def extract_ports(c, detail=None):
    """归一化为 [{ip, host, container, type}]。

    重要：SYNO.Docker.Container 的 list 接口【不返回端口】，端口需要从
    get 详情的 NetworkSettings.Ports（Docker inspect 字典格式）里取。
    因此解析时传入 detail（get 详情原始响应）才能拿到端口。
    """
    out = []
    # 收集所有可用的 NetworkSettings 来源（list 项 + get 详情）
    ns_sources = []
    if isinstance(c, dict):
        ns = (c.get("NetworkSettings") or {})
        if ns:
            ns_sources.append(ns)
    if isinstance(detail, dict):
        d = detail.get("data") or {}
        # get 详情真实结构：data.details.NetworkSettings.Ports
        cont = d.get("details") or d.get("container") or d
        if isinstance(cont, dict):
            ns = (cont.get("NetworkSettings") or {})
            if ns:
                ns_sources.append(ns)
    # 1) Docker inspect 字典格式：{"5000/tcp": [{"HostIp":"0.0.0.0","HostPort":"5000"}]}
    for ns in ns_sources:
        for key_field in ("Ports", "PortBindings"):
            pb = ns.get(key_field)
            if isinstance(pb, dict) and pb:
                for spec, binds in pb.items():
                    if "/" in spec:
                        cport, ptype = spec.split("/", 1)
                    else:
                        cport, ptype = spec, "tcp"
                    if isinstance(binds, list) and binds:
                        for b in binds:
                            if isinstance(b, dict):
                                out.append({
                                    "ip": b.get("HostIp", "0.0.0.0"),
                                    "host": b.get("HostPort"),
                                    "container": cport,
                                    "type": ptype,
                                })
                    else:
                        # 仅声明未映射到主机（binds 为 null）
                        out.append({"ip": "0.0.0.0", "host": None,
                                    "container": cport, "type": ptype})
                if out:
                    return out
    # 2) 数组格式 Ports：[{IP, PublicPort, PrivatePort, Type}]
    for ns in ns_sources:
        ports = ns.get("Ports")
        if isinstance(ports, list) and ports:
            for p in ports:
                if isinstance(p, dict):
                    out.append({
                        "ip": p.get("IP", "0.0.0.0"),
                        "host": p.get("PublicPort"),
                        "container": p.get("PrivatePort"),
                        "type": p.get("Type", "tcp"),
                    })
            if out:
                return out
    # 3) 顶层 ports 字典（键=容器端口）
    ports_d = c.get("ports") if isinstance(c, dict) else None
    if isinstance(ports_d, dict):
        for cport, v in ports_d.items():
            if isinstance(v, dict):
                out.append({
                    "ip": v.get("ip", "0.0.0.0"),
                    "host": v.get("host"),
                    "container": cport,
                    "type": v.get("type", "tcp"),
                })
            else:
                out.append({"ip": "0.0.0.0", "host": v, "container": cport, "type": "tcp"})
        if out:
            return out
    return out


def query_apis(cfg):
    """query.cgi 动态发现多个 API 的真实 path / version（不需要 sid）。
    返回 (meta, raw_data)。"""
    names = [
        "SYNO.Docker.Container.Container",
        "SYNO.Core.System.Info",
        "SYNO.Core.System.Utilization",
        "SYNO.Core.Storage.Storage",
    ]
    resp = requests.get(
        cfg["base"] + "/webapi/query.cgi",
        params={
            "api": "SYNO.API.Info",
            "method": "query",
            "version": 1,
            "query": ",".join(names),
        },
        timeout=TIMEOUT,
        verify=False,
    )
    data = resp.json().get("data", {}) or {}
    meta = {}
    for n in names:
        info = data.get(n) or {}
        path = info.get("path") or "entry.cgi"
        # 用 maxVersion（API 支持的最高版本），避免低版本缺少 method 导致 102
        ver = info.get("maxVersion") or info.get("minVersion") or 1
        meta[n] = (path, int(ver))
    return meta, data


def dump_all_apis(cfg):
    """列出 DSM 上 query.cgi 能发现的所有 API 名（用于核对真实注册名）。"""
    print("\n[列出 DSM 上所有可发现的 API 名（含 Docker 相关）]")
    resp = requests.get(
        cfg["base"] + "/webapi/query.cgi",
        params={"api": "SYNO.API.Info", "method": "query", "version": 1,
                "query": "all"},
        timeout=TIMEOUT,
        verify=False,
    )
    try:
        d = resp.json().get("data", {}) or {}
    except ValueError:
        print("    query=all 返回非 JSON: %s" % resp.text[:300])
        return []
    keys = list(d.keys())
    print("    共 %d 个 API。" % len(keys))
    # 只打印含 Docker / Container / Core 关键字的部分，便于定位
    interesting = [k for k in keys if any(
        x in k for x in ("Docker", "Container", "Core.System", "Core.Storage"))]
    print("    相关 API 名:")
    for k in interesting:
        info = d.get(k) or {}
        print("      - %s  (path=%s maxVer=%s)" % (
            k, info.get("path"), info.get("maxVersion")))
    return keys


def fetch_api(cfg, sid, api_name, path, version, method="get", extra=None, synotoken=None):
    """通用 API 调用，返回完整原始 JSON。synotoken 缺失时自动省略。"""
    params = {
        "api": api_name,
        "version": version,
        "method": method,
        "_sid": sid,
    }
    if synotoken:
        params["SynoToken"] = synotoken
    if extra:
        params.update(extra)
    resp = requests.get(
        cfg["base"] + "/webapi/" + path,
        params=params,
        timeout=TIMEOUT,
        verify=False,
    )
    return resp.json()


def fetch_container_detail(cfg, sid, synotoken, name, cid):
    """拉取单个容器详情（含端口映射）。method=get，先试 name，失败试 id。返回原始 JSON 或 None。"""
    for key, val in (("name", name), ("id", cid)):
        if not val:
            continue
        try:
            raw = fetch_api(cfg, sid, "SYNO.Docker.Container", "entry.cgi", 1,
                            method="get", extra={key: val}, synotoken=synotoken)
        except Exception:
            continue
        if raw.get("success"):
            return raw
    return None


def try_session(cfg, session_name):
    """用指定 session 登录 + 拉容器，返回 (raw_json, sid) 或 (None, None)。"""
    print("\n>>> 尝试 session='%s' ..." % session_name)
    try:
        sid, synotoken = login(cfg, session=session_name)
        print("    登录成功 sid=%s... synotoken=%s" % (sid[:8], "有" if synotoken else "无"))
    except Exception as e:
        print("    [登录失败] %s" % e)
        return None, None, None

    # 发现 API（不需要特定 session）
    meta, _ = query_apis(cfg)

    # 正确的 Docker API 名（来自 dump_all_apis 实测）：SYNO.Docker.Container
    path = "entry.cgi"
    api_name = "SYNO.Docker.Container"
    methods = ["list", "get"]  # list 是列出容器；get 取单个（需 id）。优先 list
    versions = [1]             # maxVer=1

    raw = None
    used_method = None
    used_ver = None
    for method in methods:
        for ver in versions:
            print("    >>> %s v%d method=%s ..." % (api_name, ver, method))
            try:
                r = fetch_api(cfg, sid, api_name, path, ver,
                              method=method, extra={"limit": -1, "offset": 0},
                              synotoken=synotoken)
            except Exception as e:
                print("        异常: %s" % e)
                continue
            if r.get("success"):
                raw = r
                used_method = method
                used_ver = ver
                print("        ✅ success")
                break
            else:
                err = r.get("error")
                print("        失败: %s" % json.dumps(err, ensure_ascii=False))
        if raw:
            break

    if raw is None:
        print("    [SYNO.Docker.Container 所有 method/version 失败] 无法获取容器")
        return None, sid, synotoken

    print("    命中: %s v%d method=%s" % (api_name, used_ver, used_method))

    success = raw.get("success")
    print("    success=%s" % success)

    if success:
        data = raw.get("data") or {}
        if isinstance(data, dict):
            print("    data keys: %s" % list(data.keys()))
            # 容器列表可能在 containers 键下
            containers_raw = data.get("containers") or []
        else:
            containers_raw = data if isinstance(data, list) else []
        print("    容器数量: %d" % len(containers_raw))
        return raw, sid, synotoken
    else:
        print("    [API 返回失败] 完整响应:")
        print("    %s" % json.dumps(raw, ensure_ascii=False, indent=2))
        return raw, sid, synotoken


def test_core_system(cfg, meta):
    """用 Core session 拉取系统信息 / 利用率 / 存储，并打印原始响应。"""
    print("\n" + "=" * 60)
    print("[群晖系统信息测试] (session=Core)")
    print("=" * 60)
    try:
        sid, synotoken = login(cfg, session="Core")
        print("[Core 登录成功] sid=%s... synotoken=%s" % (sid[:8], "有" if synotoken else "无"))
    except Exception as e:
        print("[Core 登录失败] %s" % e)
        return

    probes = [
        ("SYNO.Core.System", "get", None, [1, 2, 3]),
        ("SYNO.Core.System.Utilization", "get", {"resource": "cpu,mem,network,disk"}, [1]),
        ("SYNO.Core.Storage.Volume", "get", None, [1]),
        ("SYNO.Core.Storage.Pool", "get", None, [1]),
        ("SYNO.Core.Storage.Storage", "get", {"type": "raid", "api": "SYNO.Core.Storage.Storage"}, [1]),
    ]
    for api_name, method, extra, versions in probes:
        path = "entry.cgi"
        print("\n[%s] 探测版本 %s ..." % (api_name, versions))
        raw, version = probe_versions(cfg, sid, api_name, path, method=method,
                                      extra=extra, versions=tuple(versions),
                                      synotoken=synotoken)
        if raw is None:
            print("    [全部版本失败]")
            continue
        success = raw.get("success")
        if not success:
            print("    完整响应:")
            print("    %s" % json.dumps(raw, ensure_ascii=False, indent=2))
            continue
        # 打印 data 顶层结构
        data = raw.get("data") or {}
        if isinstance(data, dict):
            print("    data keys: %s" % list(data.keys()))
        print("    原始 data:")
        print("    %s" % json.dumps(data, ensure_ascii=False, indent=2, default=str)[:2000])


def main():
    ap = argparse.ArgumentParser(description="测试 DSM Docker 容器 + 系统信息拉取")
    ap.add_argument("--host")
    ap.add_argument("--port")
    ap.add_argument("--user")
    ap.add_argument("--password")
    ap.add_argument("--https", choices=["0", "1"], dest="https_arg")
    args = ap.parse_args()
    https = None
    if args.https_arg is not None:
        https = args.https_arg == "1"
    cfg = build_client(type("A", (), {"host": args.host, "port": args.port,
                                      "user": args.user, "password": args.password,
                                      "https": https})())

    print("=" * 60)
    print("目标: %s" % cfg["base"])
    print("用户: %s" % cfg["user"])
    print("=" * 60)

    # 先发现 API（不需要登录），并打印原始响应
    meta, raw_meta = query_apis(cfg)
    print("[API 发现 原始响应 data 字段]")
    print("    %s" % json.dumps(raw_meta, ensure_ascii=False, indent=2))
    for n, (p, v) in meta.items():
        info = raw_meta.get(n) or {}
        print("    %s -> path=%s (原始info: %s)" % (n, p, json.dumps(info, ensure_ascii=False)))

    # 列出 DSM 上所有可发现的 API 名，定位真实的 Docker / Core API 注册名
    dump_all_apis(cfg)

    # ---------- 1) 容器测试（Docker / Core 双 session 尝试） ----------
    print("\n" + "=" * 60)
    print("[容器信息测试]")
    print("=" * 60)
    results = {}
    for sess in ["Docker", "Core"]:
        raw, sid, synotoken = try_session(cfg, sess)
        results[sess] = (raw, sid, synotoken)
        if raw and raw.get("success"):
            break

    best_raw = None
    best_sess = None
    best_sid = None
    best_synotoken = None
    for sess in ["Docker", "Core"]:
        r, s, st = results.get(sess, (None, None, None))
        if r and r.get("success"):
            best_raw = r
            best_sess = sess
            best_sid = s
            best_synotoken = st
            print("\n✅ 容器使用 session='%s' 的结果" % sess)
            break

    if not best_raw:
        print("\n❌ 容器：两种 session 都失败了。")
        print("   可能原因：账号没有 Container Manager 权限、或 DSM 版本不支持。")
    else:
        data = best_raw.get("data") or {}
        containers_raw = data.get("containers") or []

        print("\n[前 3 个容器原始字段样例]")
        for i, c in enumerate(containers_raw[:3]):
            print("\n--- 容器 #%d ---" % i)
            print(json.dumps(c, ensure_ascii=False, indent=2, default=str))

        print("\n" + "=" * 60)
        print("[解析结果：容器网络 IP + 端口]")
        print("=" * 60)
        printed_detail_raw = False
        for idx, c in enumerate(containers_raw):
            name = (c.get("name") or "").lstrip("/")
            state = c.get("state") or c.get("status")
            nets = extract_networks(c)
            # 端口需 get 详情；拉取单个容器详情
            detail = fetch_container_detail(cfg, best_sid, best_synotoken, name, c.get("id"))
            # 打印首个容器的 get 详情原始结构，便于确认端口字段位置
            if detail and not printed_detail_raw:
                printed_detail_raw = True
                d = detail.get("data") or {}
                cont = d.get("details") or d.get("container") or d
                print("\n[首个容器 get 详情 NetworkSettings 端口字段]")
                ns = (cont.get("NetworkSettings") or {}) if isinstance(cont, dict) else {}
                print(json.dumps(ns.get("Ports"), ensure_ascii=False, indent=2, default=str))
                print("\n[首个容器 get 详情（前 2500 字符）]")
                print(json.dumps(cont, ensure_ascii=False, indent=2, default=str)[:2500])
            ports = extract_ports(c, detail)
            print("\n• 容器: %s  状态: %s" % (name or c.get("id"), state))
            if nets:
                for n in nets:
                    print("    网络 [%s] IP=%s 网关=%s" % (n["name"], n["ip"], n["gateway"]))
            else:
                print("    网络: (无)")
            if ports:
                for p in ports:
                    print("    端口 %s:%s -> %s/%s" % (p["ip"], p["host"], p["container"], p["type"]))
            else:
                print("    端口: (无)")

        print("\n[完成] 共解析 %d 个容器。" % len(containers_raw))

    # ---------- 2) 系统信息测试（Core session） ----------
    test_core_system(cfg, meta)

    print("\n" + "=" * 60)
    print("[全部测试完成]")
    print("=" * 60)


if __name__ == "__main__":
    main()
