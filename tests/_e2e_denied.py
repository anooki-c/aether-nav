import json
import urllib.request
from backend.app import app, db, User, Category, Link, LinkPermission, make_token

with app.app_context():
    admin = User.query.filter_by(role="admin").first()
    alice = User.query.filter_by(username="alice").first()
    assert admin and alice, "need admin + alice"

    # ---- build temporary scenario ----
    catA = Category(name="__tA__", visible=False, owner_id=admin.id, color="#000")
    catB = Category(name="__tB__", visible=True, allowed_roles="admin", owner_id=admin.id, color="#000")
    catC = Category(name="__tC__", visible=True, owner_id=admin.id, color="#000")
    db.session.add_all([catA, catB, catC])
    db.session.flush()

    linkA = Link(title="__L1a__", url_external="http://x", owner_id=admin.id, category_id=catA.id, permission="all")
    linkB = Link(title="__L1b__", url_external="http://x", owner_id=admin.id, category_id=catB.id, permission="all")
    linkC = Link(title="__L2__", url_external="http://x", owner_id=admin.id, category_id=catC.id, permission="self")
    linkD = Link(title="__L3__", url_external="http://x", owner_id=admin.id, category_id=catC.id, permission="all")
    db.session.add_all([linkA, linkB, linkC, linkD])
    db.session.flush()
    db.session.add(LinkPermission(link_id=linkD.id, kind="user", target=str(alice.id), deny=True))
    db.session.commit()

    token = make_token(admin)
    url = f"http://localhost:5000/api/admin/users/{alice.id}/permissions"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode())

    print("manageable:", len(data["links"]), "| denied:", len(data["denied"]))
    print("----- DENIED layers -----")
    ok = True
    seen = set()
    for d in data["denied"]:
        print(f"  [{d['layer']}] {d['title']}  -> {d['reason']}  fixable_here={d.get('fixable_here')}")
        seen.add(d["layer"])
    for expected in ("L1a", "L1b", "L2", "L3"):
        if expected not in seen:
            ok = False
            print("  !! MISSING layer", expected)
    print("ALL LAYERS PRESENT:" , ok)

    # ---- cleanup ----
    LinkPermission.query.filter_by(target=str(alice.id)).delete()
    for l in (linkA, linkB, linkC, linkD):
        db.session.delete(l)
    for c in (catA, catB, catC):
        db.session.delete(c)
    db.session.commit()
    print("cleanup done")
