import sys, json, urllib.request
sys.path.insert(0, "backend")
from app import app, serializer, User, Link

BASE = "http://localhost:5000"


def req(method, path, token=None, data=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


with app.app_context():
    admin = User.query.filter_by(username="admin").first()
    assert admin, "no admin user"
    token = serializer.dumps({"uid": admin.id})
    target = User.query.filter(User.username != "admin").order_by(User.id).first()
    link = Link.query.filter_by(is_active=True).order_by(Link.id).first()
    TARGET_ID = target.id
    LINK_ID = link.id

print("== 1) settings 含三个新键 ==")
st, settings = req("GET", "/api/settings", token)
print("  allow_register=", settings.get("allow_register"),
      "default_role=", settings.get("default_role"),
      "token_max_age_hours=", settings.get("token_max_age_hours"))

print("== 2) 链接维度权限矩阵 ==")
st, mp = req("GET", f"/api/admin/links/{LINK_ID}/permissions", token)
print("  link:", mp["link"]["title"], "summary:", mp["summary"])
for u in mp["users"][:3]:
    print("   -", u["username"], u["role"], "visible=" + str(u["visible"]),
          ("layer=" + str(u["layer"]) if not u["visible"] else ""))

print("== 3) 审计日志 ==")
st, aud = req("GET", "/api/admin/audit?per=10", token)
before = aud.get("total", 0)
print("  total logs:", before)

print("== 4) POST 拒绝某链接 -> 应写入 perm_deny 审计 ==")
st, r = req("POST", f"/api/admin/users/{TARGET_ID}/permissions", token, {"denies": [LINK_ID]})
print("  save changed=", r.get("changed"))
st, aud2 = req("GET", "/api/admin/audit?per=5", token)
print("  logs now:", aud2.get("total"), "(was", before, ")")
if aud2.get("logs"):
    top = aud2["logs"][0]
    print("  latest:", top["action"], "|", top["operator_name"], "->", top["target_name"], "|", top["detail"])

print("== 5) 注册开关：关闭后自助注册应被拒 ==")
st, _ = req("PUT", "/api/admin/settings", token, {"allow_register": False})
st, reg = req("POST", "/api/auth/register", data={"username": "e2e_tmp_x", "password": "secret123"})
print("  closed-register status=", st, "msg=", reg.get("error"))
st, _ = req("PUT", "/api/admin/settings", token, {"allow_register": True})
print("  restored allow_register=True")

print("== 6) 恢复该链接默认可见（清 deny）==")
st, r = req("POST", f"/api/admin/users/{TARGET_ID}/permissions", token, {"denies": []})
print("  restored changed=", r.get("changed"))

print("\nALL CHECKS DONE")
