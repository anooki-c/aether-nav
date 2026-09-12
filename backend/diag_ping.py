"""链接可达性探测诊断工具。

用途：当某个链接被标记为「不可达」但你确认实际能打开时，用它在**部署环境**
（NAS 容器内）里实测每个地址，把真实原因打出来：连接超时 / DNS 失败 /
证书校验失败 / HTTP 状态码 / 是否被代理拦截。

用法（在 NAS 上执行）：
    docker exec -it nav sh -c "cd /app && python backend/diag_ping.py"
    仅测某一条：docker exec -it nav sh -c "cd /app && python backend/diag_ping.py <url>"

它只做读取与网络探测，不修改任何数据。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402
import urllib3  # noqa: E402

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def probe_detail(url, timeout=6, proxies=None, verify=True, steps=None):
    """返回 (结果, 说明)。记录每一步的成败原因，便于定位。

    结果可能是 HTTP 状态码（int），或 'ssl'/'proxy'/'timeout'/'conn'/'err'。
    """
    if steps is None:
        steps = []
    # 内网地址禁用环境变量代理：否则会被送到外网代理，必然失败
    from backend.app import _is_private_host

    session = requests.Session()
    if _is_private_host(url):
        session.trust_env = False
    try:
        for method in ("HEAD", "GET"):
            try:
                r = session.request(
                    method, url, timeout=timeout, allow_redirects=True,
                    proxies=proxies, verify=verify, stream=(method == "GET"),
                )
                code = r.status_code
                if method == "GET":
                    r.close()
                steps.append(f"{method} verify={verify} -> HTTP {code}")
                # HEAD 被拒时继续用 GET 复核
                if method == "HEAD" and code in (400, 403, 405, 501):
                    continue
                return code, steps
            except requests.exceptions.SSLError as e:
                steps.append(f"{method} verify={verify} -> SSLError({type(e).__name__})")
                if verify:
                    steps.append("  ^ 证书校验失败，正式探测会自动降级 verify=False 重试")
                    return probe_detail(url, timeout, proxies, verify=False, steps=steps)
                return "ssl", steps
            except requests.exceptions.ProxyError as e:
                steps.append(f"{method} verify={verify} -> ProxyError({str(e)[:60]})")
                return "proxy", steps
            except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout):
                steps.append(f"{method} verify={verify} -> 超时")
                return "timeout", steps
            except requests.exceptions.ConnectionError as e:
                steps.append(f"{method} verify={verify} -> 连接失败({str(e)[:70]})")
                return "conn", steps
            except Exception as e:
                steps.append(f"{method} verify={verify} -> {type(e).__name__}: {str(e)[:70]}")
                return "err", steps
        return "unknown", steps
    finally:
        session.close()


def main():
    print("=" * 78)
    print("环境代理变量（可能导致内网地址被误送到外网代理）")
    print("=" * 78)
    found = False
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "NO_PROXY", "no_proxy"):
        v = os.environ.get(k)
        if v:
            found = True
            print(f"  {k} = {v}")
    if not found:
        print("  （未设置）")

    args = sys.argv[1:]
    if args:
        targets = [(0, "命令行指定", args[0], "手动")]
    else:
        from backend.app import app
        from backend.models import Link

        with app.app_context():
            targets = []
            for l in Link.query.filter_by(is_active=True).order_by(Link.id).all():
                if l.url_internal:
                    targets.append((l.id, l.title, l.url_internal, "内网"))
                if l.url_external:
                    targets.append((l.id, l.title, l.url_external, "外网"))

    from backend.app import _do_ping, _is_private_host, outbound_proxy

    print()
    print("=" * 78)
    print("逐地址实测")
    print("=" * 78)
    for lid, title, url, kind in targets:
        print(f"\n#{lid} {title} [{kind}]")
        print(f"   {url}")
        print(f"   私网地址判定: {_is_private_host(url)}")
        code, steps = probe_detail(url)
        for s in steps:
            print(f"     {s}")
        try:
            final = _do_ping(url)
        except Exception as e:
            final = f"异常 {type(e).__name__}: {e}"
        print(f"   >>> 正式探测判定: {final}")
        if final == "unreachable":
            if code in (502, 503, 504):
                print("       原因：网关错误（反代背后的真实服务不可用）")
            elif code == "timeout":
                print("       原因：超时——地址不通、端口未开放，或容器无法访问该网段")
            elif code == "ssl":
                print("       原因：证书问题（已降级 verify=False 仍失败）")
            elif code == "proxy":
                print("       原因：被代理拦截")
            elif code == "conn":
                print("       原因：连接被拒绝/无法建立（服务未监听或防火墙拦截）")
            elif isinstance(code, int) and code >= 400:
                print(f"       注意：拿到了 HTTP {code}，按当前逻辑应判为可达（不一致请反馈）")
    # 读取应用内配置的出站代理（需要 app context；命令行模式下也要能显示）
    try:
        from backend.app import app as _app

        with _app.app_context():
            proxy = outbound_proxy()
    except Exception as e:
        proxy = None
        print(f"\n（读取出站代理配置失败：{type(e).__name__}: {e}）")
    if proxy:
        print(f"\n（已配置出站代理 {proxy.get('https')}，仅外网地址会用它兜底；内网地址不使用）")


if __name__ == "__main__":
    main()
