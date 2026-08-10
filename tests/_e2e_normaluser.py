"""Request D 集成验证：普通用户后台权限分级。
通过 Flask test_client 直接加载最新代码，无需依赖运行中的服务。
"""
import json
from backend.app import app, db
from backend.models import User, Link, Category, check_user_link_password

ADMIN_U, ADMIN_P = "admin", "admin123"

def run():
    results = []
    with app.app_context():
        client = app.test_client()

        def login(u, p):
            r = client.post("/api/auth/login", json={"username": u, "password": p})
            assert r.status_code == 200, f"login {u} failed {r.status_code}"
            return r.get_json()["token"]

        def get(path, token):
            return client.get(path, headers={"Authorization": "Bearer " + token})

        def put(path, token, data):
            return client.put(path, json=data, headers={"Authorization": "Bearer " + token})

        admin = login(ADMIN_U, ADMIN_P)
        # 找一个普通用户 alice；若不存在则创建一个
        users = client.get("/api/admin/users", headers={"Authorization": "Bearer " + admin}).get_json()["users"]
        alice = next((u for u in users if u["username"] == "alice"), None)
        if not alice:
            r = client.post("/api/admin/users", json={"username": "alice", "password": "AliceTest123", "role": "user"},
                            headers={"Authorization": "Bearer " + admin})
            alice_id = r.get_json()["user"]["id"]
        else:
            alice_id = alice["id"]
            client.post(f"/api/admin/users/{alice_id}/reset-password", json={"new_password": "AliceTest123"},
                        headers={"Authorization": "Bearer " + admin})
        alice = login("alice", "AliceTest123")

        # 取一个叶子分类挂链接
        tree = client.get("/api/categories/tree").get_json()["tree"]
        leaf = None
        for p in tree:
            if p.get("children"):
                leaf = p["children"][0]
                break
        if not leaf:
            leaf = tree[0]
        leaf_id = leaf["id"]

        # 1) 管理员建一个 permission=all 的链接（owner=admin，alice 可见但非 owner）
        r = client.post("/api/links", json={"title": "ALICE可见-管理员建", "url_external": "https://example.com/x",
                                            "category_id": leaf_id, "permission": "all"},
                        headers={"Authorization": "Bearer " + admin})
        assert r.status_code in (200, 201), r.get_json()
        admin_link_id = r.get_json()["link"]["id"]

        # 2) 管理员建一个 permission=self 的链接（alice 不应看到）
        r = client.post("/api/links", json={"title": "ALICE不可见-self", "url_external": "https://example.com/y",
                                            "category_id": leaf_id, "permission": "self"},
                        headers={"Authorization": "Bearer " + admin})
        assert r.status_code in (200, 201), r.get_json()
        self_link_id = r.get_json()["link"]["id"]

        # 3) alice GET /api/admin/links
        r = get("/api/admin/links", alice)
        assert r.status_code == 200, r.get_json()
        links = r.get_json()["links"]
        ids = [l["id"] for l in links]
        alice_sees_admin = admin_link_id in ids
        alice_sees_self = self_link_id in ids
        rec = next((l for l in links if l["id"] == admin_link_id), None)
        results.append(("普通用户 GET /api/admin/links 包含可见链接", alice_sees_admin, True))
        results.append(("普通用户看不到 permission=self 的链接", alice_sees_self, False))
        results.append(("非 owner 链接 is_owner=False", rec["is_owner"] if rec else None, False))
        results.append(("非 owner 链接 can_edit=False", rec["can_edit"] if rec else None, False))

        # 4) alice 修改非 owner 链接的标题 -> 403
        r = put(f"/api/links/{admin_link_id}", alice, {"title": "黑客改名"})
        results.append(("非 owner 改标题被拒 403", r.status_code, 403))

        # 5) alice 仅设置自己的访问密码 -> 200
        r = put(f"/api/links/{admin_link_id}", alice, {"password": "secret123"})
        results.append(("非 owner 仅设访问密码成功 200", r.status_code, 200))
        # 校验确实写入了该用户独立密码
        pw_ok = check_user_link_password(admin_link_id, alice_id, "secret123")
        results.append(("独立访问密码已生效", pw_ok, True))

        # 6) alice 清除自己的访问密码 -> 200
        r = put(f"/api/links/{admin_link_id}", alice, {"password": ""})
        results.append(("非 owner 清除访问密码成功 200", r.status_code, 200))
        pw_cleared = not check_user_link_password(admin_link_id, alice_id, "secret123")
        results.append(("独立访问密码已清除", pw_cleared, True))

        # 7) alice 自己建一个链接 -> owner，can_edit=True，且可改标题
        r = client.post("/api/links", json={"title": "ALICE自建", "url_external": "https://example.com/z",
                                            "category_id": leaf_id, "permission": "all"},
                        headers={"Authorization": "Bearer " + alice})
        assert r.status_code in (200, 201), r.get_json()
        own_link_id = r.get_json()["link"]["id"]
        r = get("/api/admin/links", alice).get_json()["links"]
        rec2 = next((l for l in r if l["id"] == own_link_id), None)
        results.append(("自建链接 is_owner=True", rec2["is_owner"] if rec2 else None, True))
        results.append(("自建链接 can_edit=True", rec2["can_edit"] if rec2 else None, True))
        r = put(f"/api/links/{own_link_id}", alice, {"title": "ALICE自建-改名"})
        results.append(("owner 改标题成功 200", r.status_code, 200))

        # 8) 普通用户建分类成功
        r = client.post("/api/categories", json={"name": "ALICE分类", "parent_id": None},
                        headers={"Authorization": "Bearer " + alice})
        results.append(("普通用户可建分类 200/201", r.status_code, 201))

        # 清理测试数据
        for lid in (admin_link_id, self_link_id, own_link_id):
            try:
                client.delete(f"/api/links/{lid}", headers={"Authorization": "Bearer " + admin})
            except Exception:
                pass

    print("\n=== Request D 集成验证 ===")
    ok = True
    for name, got, expect in results:
        flag = "OK " if got == expect else "FAIL"
        if got != expect:
            ok = False
        print(f"[{flag}] {name}  (got={got}, expect={expect})")
    print("\n结果:", "全部通过 ✅" if ok else "存在失败 ❌")
    return ok

if __name__ == "__main__":
    run()
