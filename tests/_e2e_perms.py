import json
import urllib.request
from backend.app import app, db, User, make_token

with app.app_context():
    admin = User.query.filter_by(role="admin").first()
    if not admin:
        print("NO ADMIN FOUND")
        raise SystemExit(1)
    # pick a target: prefer a non-admin, else any other user
    target = User.query.filter(User.role != "admin").first() or User.query.filter(User.id != admin.id).first()
    print("admin:", admin.username, "target:", target.username, "role:", target.role,
          "active:", target.is_active is not False)
    token = make_token(admin)
    url = f"http://localhost:5000/api/admin/users/{target.id}/permissions"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode())
    print("manageable links:", len(data.get("links", [])))
    print("denied links:", len(data.get("denied", [])))
    print("----- DENIED (layer / reason) -----")
    for d in data.get("denied", []):
        print(f"  [{d['layer']}] #{d['id']} {d['title']}  -> {d['reason']}  (fixable_here={d.get('fixable_here')})")
    print("----- MANAGE (visible/denied flag) -----")
    for m in data.get("links", []):
        print(f"  vis={int(m['visible'])} denied_flag={int(m['denied'])} #{m['id']} {m['title']}")
