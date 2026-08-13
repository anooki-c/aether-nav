#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
独立测试脚本：验证群晖存储相关 API（参考
https://www.chenxin.info/2025/08/26/quickstart-synology-web-api-watching-system-status/）。

目标：确认 SYNO.Storage.CGI.Storage (method=load_info) 能否在 DSM 7.2.2 上拉到
卷/存储池/磁盘容量（之前用的 SYNO.Core.Storage.Volume 返回 101 不可用）。

本脚本【仅测试，不修改任何项目代码】。

凭据获取顺序：
  1) 环境变量 SYNO_HOST / SYNO_PORT / SYNO_USER / SYNO_PASS / SYNO_HTTPS
  2) 否则读取 backend/instance/app.db 的 settings 表（syno_* 字段）

用法：
  python scripts/test_syno_storage.py
  python scripts/test_syno_storage.py --host 10.10.123.106 --user Anooki --https 1
"""
import argparse
import getpass
import json
import os
import sqlite3
import sys
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TIMEOUT = 20
HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "..", "backend", "instance", "app.db")


# ---------- 凭据 ----------
def load_cfg_from_db():
    """从 backend/instance/app.db 的 settings 表读取 syno_* 配置。"""
    cfg = {}
    if not os.path.exists(DB_PATH):
        return cfg
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        conn.close()
        for r in rows:
            k, v = r["key"], r["value"]
            if k in ("syno_host", "syno_port", "syno_user", "syno_pass", "syno_https"):
                cfg[k] = v
    except Exception as e:
        print("  [读库失败] %s" % e)
    return cfg


def build_client(args):
    db = load_cfg_from_db()
    host = args.host or os.environ.get("SYNO_HOST") or db.get("syno_host")
    if not host:
        host = input("DSM 地址 (IP): ").strip()
    port = args.port or os.environ.get("SYNO_PORT") or db.get("syno_port")
    user = args.user or os.environ.get("SYNO_USER") or db.get("syno_user") or input("用户名: ").strip()
    password = os.environ.get("SYNO_PASS") or args.password or db.get("syno_pass") or getpass.getpass("密码: ")

    if args.https is not None:
        https = args.https == 1
    else:
        env = os.environ.get("SYNO_HTTPS")
        if env is not None:
            https = str(env).lower() in ("1", "true", "yes")
        else:
            https = str(db.get("syno_https", "0")).lower() in ("1", "true", "yes")

    if not port:
        port = 5001 if https else 5000
    else:
        port = int(port)
    scheme = "https" if https else "http"
    base = "%s://%s:%s" % (scheme, host, port)
    return {"base": base, "host": host, "port": port, "user": user,
            "password": password, "https": https}


# ---------- 登录/请求 ----------
def login(cfg, session="Core"):
    resp = requests.get(
        cfg["base"] + "/webapi/auth.cgi",
        params={
            "api": "SYNO.API.Auth", "version": 6, "method": "login",
            "account": cfg["user"], "passwd": cfg["password"],
            "session": session, "format": "sid", "enable_syno_token": "yes",
        },
        timeout=TIMEOUT, verify=False,
    )
    data = resp.json()
    if data.get("success") is not True:
        raise RuntimeError("登录失败 (session=%s): %s" % (session, json.dumps(data, ensure_ascii=False)))
    d = data.get("data") or {}
    sid = d.get("sid")
    if not sid:
        raise RuntimeError("登录成功但未返回 sid")
    return sid, d.get("synotoken")


def fetch_api(cfg, sid, api_name, path, version, method="get", extra=None, synotoken=None):
    params = {"api": api_name, "version": version, "method": method, "_sid": sid}
    if synotoken:
        params["SynoToken"] = synotoken
    if extra:
        params.update(extra)
    resp = requests.get(cfg["base"] + "/webapi/" + path, params=params,
                       timeout=TIMEOUT, verify=False)
    return resp.json()


def query_api(cfg, name):
    """query.cgi 发现 API 真实 path / maxVersion。"""
    resp = requests.get(
        cfg["base"] + "/webapi/query.cgi",
        params={"api": "SYNO.API.Info", "method": "query", "version": 1, "query": name},
        timeout=TIMEOUT, verify=False,
    )
    info = (resp.json().get("data") or {}).get(name) or {}
    return info.get("path") or "entry.cgi", int(info.get("maxVersion") or 1)


def try_storage(cfg, sid, synotoken):
    """测试 SYNO.Storage.CGI.Storage load_info。"""
    print("\n" + "=" * 64)
    print("[测试] SYNO.Storage.CGI.Storage (method=load_info)")
    print("=" * 64)
    try:
        path, maxver = query_api(cfg, "SYNO.Storage.CGI.Storage")
        print("  query.cgi: path=%s maxVersion=%s" % (path, maxver))
    except Exception as e:
        print("  query.cgi 失败: %s" % e)
        path, maxver = "entry.cgi", 1

    best = None
    for ver in range(1, maxver + 1):
        print("  >>> load_info v%d ..." % ver)
        try:
            raw = fetch_api(cfg, sid, "SYNO.Storage.CGI.Storage", path, ver,
                            method="load_info", synotoken=synotoken)
        except Exception as e:
            print("      异常: %s" % e)
            continue
        if raw.get("success"):
            best = (raw, ver)
            print("      ✅ success")
            break
        else:
            print("      失败: %s" % json.dumps(raw.get("error"), ensure_ascii=False))
    if best is None:
        print("  [全部版本失败] SYNO.Storage.CGI.Storage 不可用")
        return

    raw, ver = best
    data = raw.get("data") or {}
    print("\n  data 顶层 keys: %s" % list(data.keys()))
    if isinstance(data, dict):
        for key in ("volumes", "storagePools", "disks", "sharedCaches", "ssdCaches", "overview_data"):
            if key in data:
                val = data[key]
                if isinstance(val, list):
                    print("\n  --- %s (%d 项) ---" % (key, len(val)))
                    print(json.dumps(val, ensure_ascii=False, indent=2, default=str)[:3000])
                elif isinstance(val, dict):
                    print("\n  --- %s (dict) ---" % key)
                    print(json.dumps(val, ensure_ascii=False, indent=2, default=str)[:1500])
                else:
                    print("  %s: %s" % (key, val))


def try_system_health(cfg, sid, synotoken):
    """测试 SYNO.Core.System.SystemHealth get（链接推荐）。"""
    print("\n" + "=" * 64)
    print("[测试] SYNO.Core.System.SystemHealth (method=get)")
    print("=" * 64)
    try:
        path, maxver = query_api(cfg, "SYNO.Core.System.SystemHealth")
        print("  query.cgi: path=%s maxVersion=%s" % (path, maxver))
    except Exception as e:
        print("  query.cgi 失败: %s" % e)
        path, maxver = "entry.cgi", 1
    for ver in range(1, maxver + 1):
        print("  >>> get v%d ..." % ver)
        try:
            raw = fetch_api(cfg, sid, "SYNO.Core.System.SystemHealth", path, ver,
                            method="get", synotoken=synotoken)
        except Exception as e:
            print("      异常: %s" % e)
            continue
        if raw.get("success"):
            print("      ✅ success")
            data = raw.get("data") or {}
            print("  data keys: %s" % list(data.keys()))
            print(json.dumps(data, ensure_ascii=False, indent=2, default=str)[:2500])
            return
        else:
            print("      失败: %s" % json.dumps(raw.get("error"), ensure_ascii=False))
    print("  [全部版本失败] SystemHealth 不可用")


def main():
    ap = argparse.ArgumentParser(description="测试群晖存储 API（只读，不改项目）")
    ap.add_argument("--host")
    ap.add_argument("--port")
    ap.add_argument("--user")
    ap.add_argument("--password")
    ap.add_argument("--https", type=int, choices=[0, 1])
    args = ap.parse_args()

    cfg = build_client(args)
    print("=" * 64)
    print("目标: %s" % cfg["base"])
    print("用户: %s" % cfg["user"])
    print("=" * 64)

    try:
        sid, synotoken = login(cfg, session="Core")
        print("[Core 登录成功] sid=%s... synotoken=%s" % (sid[:8], "有" if synotoken else "无"))
    except Exception as e:
        print("[登录失败] %s" % e)
        sys.exit(1)

    try_storage(cfg, sid, synotoken)
    try_system_health(cfg, sid, synotoken)

    print("\n" + "=" * 64)
    print("[测试完成]")
    print("=" * 64)


if __name__ == "__main__":
    main()
