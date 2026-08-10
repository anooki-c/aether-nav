import json, urllib.request

BASE = "http://localhost:5000"

def call(path, token=None, data=None, method=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as r:
        return json.load(r)

def login(u, p):
    return call("/api/auth/login", data={"username": u, "password": p}, method="POST")["token"]

admin = login("admin", "admin123")
uid = [u["id"] for u in call("/api/admin/users", token=admin)["users"] if u["username"] == "alice"][0]
# 演示库 alice 密码可能已被先前测试改动，先用管理员重设一个已知密码（顺便验证重设密码接口）
r = call(f"/api/admin/users/{uid}/reset-password", token=admin, data={"new_password": "AliceTest123"}, method="POST")
print("重设 alice 密码 ->", r.get("new_password"))
alice = login("alice", "AliceTest123")
print("alice 用新密码登录: OK")

# 用 admin 建一个 permission=self 的链接（仅 owner 可见），alice 默认看不到
tree = call("/api/categories/tree")
# 选一个「叶子」分类（无子分类）来挂链接
leaf = None
for p in tree["tree"]:
    for c in p.get("children", []):
        leaf = c
        break
    if leaf:
        break
if not leaf:
    leaf = tree["tree"][0]
print("挂到分类:", leaf["name"], leaf["id"])
link = call("/api/links", token=admin, data={
    "title": "E2E权限测试链接", "url_external": "https://example.com/e2e",
    "category_id": leaf["id"], "permission": "self",
}, method="POST")
lid = link["link"]["id"]
print("created link id =", lid, "(permission=self, 仅 owner 可见)")

def alice_sees():
    d = call("/api/links", token=alice)
    return lid in [l["id"] for g in d["groups"] for l in g["links"]]

print("alice 初始可见?", alice_sees(), "(期望 False)")

# 关键修复：在权限弹窗中把该链接授予 alice
call(f"/api/admin/users/{uid}/permissions", token=admin, data={"link_ids": [lid]}, method="POST")
print("alice 授权后可见?", alice_sees(), "(期望 True)  <-- 修复验证")

call(f"/api/admin/users/{uid}/permissions", token=admin, data={"link_ids": []}, method="POST")
print("alice 撤销后可见?", alice_sees(), "(期望 False)")

call(f"/api/links/{lid}", token=admin, method="DELETE")
print("已删除测试链接")

# 禁用 / 启用
r = call(f"/api/admin/users/{uid}", token=admin, data={"is_active": False}, method="PUT")
print("禁用 alice -> is_active =", r["user"]["is_active"], "(期望 False)")
try:
    login("alice", "alice123")
    print("禁用后 alice 仍能登录? (期望不能)")
except urllib.error.HTTPError as e:
    print("禁用后 alice 登录被拒:", e.code, "(期望 403)")
r = call(f"/api/admin/users/{uid}", token=admin, data={"is_active": True}, method="PUT")
print("重新启用 alice -> is_active =", r["user"]["is_active"], "(期望 True)")
print("ALL DONE")
