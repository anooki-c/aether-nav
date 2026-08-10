import sys, json, urllib.request
sys.path.insert(0, "backend")
from app import app, serializer, User, Link, db

BASE = "http://localhost:5000"
def req(method, path, token=None):
    r = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + token} if token else {})
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read().decode() or "{}")

with app.app_context():
    admin = User.query.filter_by(username="admin").first()
    token = serializer.dumps({"uid": admin.id})
    link = Link.query.filter_by(is_active=True).order_by(Link.id).first()
    LINK_ID = link.id
    old = link.permission
    link.permission = "self"
    db.session.commit()

try:
    mp = req("GET", f"/api/admin/links/{LINK_ID}/permissions", token)
    print("title:", mp["link"]["title"], "perm:", mp["link"]["permission"], "summary:", mp["summary"])
    for u in mp["users"]:
        print("  ", u["username"], u["role"], "visible=" + str(u["visible"]),
              ("layer=" + u["layer"] + " " + u["reason"] if not u["visible"] else ""))
finally:
    with app.app_context():
        link = Link.query.get(LINK_ID)
        link.permission = old
        db.session.commit()
        print("restored permission ->", old)
