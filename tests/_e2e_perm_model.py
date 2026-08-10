import urllib.request, json, os

BASE = "http://127.0.0.1:5000"

def api(m, p, tk=None, body=None):
    h = {}
    if tk:
        h["Authorization"] = "Bearer " + tk
    d = None
    if body is not None:
        h["Content-Type"] = "application/json"
        d = json.dumps(body).encode()
    req = urllib.request.Request(BASE + p, data=d, method=m, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_body": e.read().decode()[:300]}

atk = api("POST", "/api/auth/login", body={"username": "admin", "password": "admin123"})["token"]
ltk = api("POST", "/api/auth/login", body={"username": "alice", "password": "alice123"})["token"]

def link_ids(resp):
    if isinstance(resp, list):
        return [x["id"] for x in resp]
    if "groups" in resp:
        return [x["id"] for g in resp["groups"] for x in g["links"]]
    if "links" in resp:
        return [x["id"] for x in resp["links"]]
    return []

def cat_ids(resp):
    if isinstance(resp, list):
        return set(x.get("category", {}).get("id") for x in resp)
    if "groups" in resp:
        return set(g["category"]["id"] for g in resp["groups"])
    return set()

# 选一个含子分类的父分类
tree = api("GET", "/api/categories/tree")["tree"]
cat = next((p for p in tree if p.get("children")), tree[0])
print("TEST CAT:", cat["id"], cat["name"], "visible=", cat.get("visible"), "allowed_roles=", repr(cat.get("allowed_roles")))

# --- 1) 分类隐藏对管理员生效（L1a，含管理员）---
api("PUT", f"/api/categories/{cat['id']}", tk=atk, body={"visible": False})
admin_cats = cat_ids(api("GET", "/api/links", tk=atk))
print("[1] 分类隐藏后 管理员仍可见该分类?", cat["id"] in admin_cats, "(应 False)")
api("PUT", f"/api/categories/{cat['id']}", tk=atk, body={"visible": True})

# --- 2) 分类角色白名单（L1b）---
api("PUT", f"/api/categories/{cat['id']}", tk=atk, body={"allowed_roles": ["admin"]})
alice_cats = cat_ids(api("GET", "/api/links", tk=ltk))
admin_cats2 = cat_ids(api("GET", "/api/links", tk=atk))
print("[2] allowed_roles=[admin]: alice可见该分类?", cat["id"] in alice_cats, "(应 False) | admin可见?", cat["id"] in admin_cats2, "(应 True)")
api("PUT", f"/api/categories/{cat['id']}", tk=atk, body={"allowed_roles": []})

# --- 3) 链接三态（L2/L3）---
raw = api("GET", "/api/admin/links", tk=atk)
allinks = raw if isinstance(raw, list) else raw.get("links", [])
link = allinks[0]
lid = link["id"]
api("PUT", f"/api/links/{lid}", tk=atk, body={"permission": "self"})

alice_ids = link_ids(api("GET", "/api/links", tk=ltk))
print(f"[3a] link {lid} self默认 alice可见?", lid in alice_ids, "(应 False)")

api("POST", f"/api/admin/users/2/permissions", tk=atk, body={"grants": [lid], "denies": []})
alice_ids = link_ids(api("GET", "/api/links", tk=ltk))
print(f"[3b] grant后 alice可见?", lid in alice_ids, "(应 True)")

api("POST", f"/api/admin/users/2/permissions", tk=atk, body={"grants": [], "denies": [lid]})
alice_ids = link_ids(api("GET", "/api/links", tk=ltk))
print(f"[3c] deny后 alice可见?", lid in alice_ids, "(应 False)")

perm = api("GET", f"/api/admin/users/2/permissions", tk=atk)
pl = next((x for x in perm["links"] if x["id"] == lid), None)
print(f"[3d] GET权限接口 link {lid} state=", pl["state"], "(应 denied)")

# 恢复默认 + all
api("POST", f"/api/admin/users/2/permissions", tk=atk, body={"grants": [], "denies": []})
api("PUT", f"/api/links/{lid}", tk=atk, body={"permission": "all"})
perm2 = api("GET", f"/api/admin/users/2/permissions", tk=atk)
pl2 = next((x for x in perm2["links"] if x["id"] == lid), None)
print(f"[3e] 恢复后 link {lid} state=", pl2["state"], "(应 inherited)")

print("E2E_DONE")
os.remove(__file__)
print("SELF_REMOVED")
