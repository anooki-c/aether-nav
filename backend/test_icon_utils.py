"""icon_utils 的轻量自测：不依赖 Flask，直接 `python backend/test_icon_utils.py` 运行。"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import Config  # noqa: E402
from backend.icon_utils import (  # noqa: E402
    FAVICON_PROVIDER_MAP,
    localize_icon,
    resolve_favicon_candidates,
    resolve_favicon_url,
)

DEFAULT_TPL = "https://github.com/favicon.ico"  # 默认接口=direct


def main():
    print("--- resolve_favicon_url（默认接口：站点自身 favicon.ico） ---")
    expects = {
        "https://github.com/a/b": DEFAULT_TPL,
        # 内网/本机/无点主机：恒为站点自身 favicon.ico，不走第三方
        "http://192.168.1.10:8080/app": "http://192.168.1.10:8080/favicon.ico",
        "nas:5000": "http://nas:5000/favicon.ico",
        "http://localhost:3000": "http://localhost:3000/favicon.ico",
        "www.baidu.com": "http://www.baidu.com/favicon.ico",
        "": "",
    }
    ok = True
    for url, want in expects.items():
        got = resolve_favicon_url(url)
        flag = "OK " if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"  [{flag}] {url!r:32} -> {got!r}")

    print("--- 切换图标接口 ---")
    provider_cases = {
        "direct": DEFAULT_TPL,
        "zhusl": "https://favicon.zhusl.com/ico?url=github.com",
        "favicon_im": "https://favicon.im/github.com?larger=true",
        "ddg": "https://icons.duckduckgo.com/ip3/github.com.ico",
        "icon_horse": "https://icon.horse/icon/github.com",
        "unavatar": "https://unavatar.io/github.com",
        "yandex": "https://favicon.yandex.net/favicon/v2/https://github.com?size=32",
        "google": "https://www.google.com/s2/favicons?domain=github.com&sz=64",
    }
    for key, want in provider_cases.items():
        got = resolve_favicon_url("https://github.com/a/b", key)
        flag = "OK " if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"  [{flag}] {key:12} -> {got!r}")

    print("--- 自定义接口 & 异常兜底 ---")
    custom_cases = [
        ("custom", "https://ico.example.com/get?d={domain}&s={size}",
         "https://ico.example.com/get?d=github.com&s=64"),
        # custom 但没填地址 → 退回默认接口
        ("custom", "", DEFAULT_TPL),
        # 不存在的接口名 → 退回默认接口
        ("not_exists", "", DEFAULT_TPL),
        # 带端口的 {host} 占位符
        ("custom", "https://p.example.com/{host}/{scheme}.png",
         "https://p.example.com/github.com/https.png"),
    ]
    for key, tpl, want in custom_cases:
        got = resolve_favicon_url("https://github.com/a/b", key, tpl)
        flag = "OK " if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"  [{flag}] {key:10} tpl={tpl[:34]!r:36} -> {got!r}")

    print("--- 候选链（选定接口失败时回退直连） ---")
    cand_cases = [
        # 第三方接口 → 两个候选，第二个是直连
        ("https://github.com/a/b", "google", "",
         ["https://www.google.com/s2/favicons?domain=github.com&sz=64", DEFAULT_TPL]),
        # 本来就是直连 → 不重复
        ("https://github.com/a/b", "direct", "", [DEFAULT_TPL]),
        # 内网地址 → 只有直连一个候选
        ("http://192.168.1.10:8080/app", "google", "", ["http://192.168.1.10:8080/favicon.ico"]),
        ("", "google", "", []),
    ]
    for url, key, tpl, want in cand_cases:
        got = resolve_favicon_candidates(url, key, tpl)
        flag = "OK " if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"  [{flag}] {url!r:30} {key:8} -> {got}")

    # 接口清单结构完整性
    for key, item in FAVICON_PROVIDER_MAP.items():
        if not all(k in item for k in ("key", "label", "template", "network", "hint")):
            ok = False
            print(f"  [FAIL] 接口定义缺字段: {key}")
    print(f"  [OK ] 接口清单共 {len(FAVICON_PROVIDER_MAP)} 项，字段完整")

    print("--- localize_icon 各分支 ---")
    passthrough = ["", "folder", "\U0001f600", "/uploads/icon_1_123.png", "/static/x.png"]
    for v in passthrough:
        got, err = localize_icon(v, 1)
        flag = "OK " if (got == v and err is None) else "FAIL"
        if got != v or err is not None:
            ok = False
        print(f"  [{flag}] 原样保留 {v!r:26} -> {got!r}, {err}")

    failing = ["D:/no/such/file.png", "D:\\no\\such.png", "file:///D:/nope.png"]
    for v in failing:
        got, err = localize_icon(v, 1)
        flag = "OK " if (got == "" and err) else "FAIL"
        if got != "" or not err:
            ok = False
        print(f"  [{flag}] 文件不存在 {v!r:24} -> {got!r}, {err}")

    # 扩展名不支持
    tmp_txt = os.path.join(tempfile.gettempdir(), "zn_test_icon.txt")
    with open(tmp_txt, "wb") as fh:
        fh.write(b"hello")
    got, err = localize_icon(tmp_txt.replace("\\", "/"), 1)
    flag = "OK " if (got == "" and err and "格式" in err) else "FAIL"
    if got != "" or not err:
        ok = False
    print(f"  [{flag}] 格式不支持 -> {got!r}, {err}")
    os.remove(tmp_txt)

    # 真实本地图片复制落地
    tmp_png = os.path.join(tempfile.gettempdir(), "zn_test_icon.png")
    with open(tmp_png, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    got, err = localize_icon(tmp_png.replace("\\", "/"), 99)
    saved = os.path.join(Config.UPLOAD_FOLDER, os.path.basename(got)) if got else ""
    exists = bool(saved) and os.path.isfile(saved)
    flag = "OK " if (got.startswith("/uploads/") and err is None and exists) else "FAIL"
    if not (got.startswith("/uploads/") and err is None and exists):
        ok = False
    print(f"  [{flag}] 本地图片落地 -> {got!r}, err={err}, 文件存在={exists}")
    if exists:
        os.remove(saved)
    os.remove(tmp_png)

    print("\n结果:", "全部通过" if ok else "存在失败用例")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
