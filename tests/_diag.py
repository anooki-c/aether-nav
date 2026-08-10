from backend.app import app
from backend.models import db, Link, LinkPermission, User, Category, visible_links_for

with app.app_context():
    alice = User.query.filter_by(username="alice").first()
    admin = User.query.filter_by(username="admin").first()
    leaf = Category.query.filter(Category.parent_id.isnot(None)).first()
    l = Link(title="DIAG", url_external="https://x.com", owner_id=admin.id, category_id=leaf.id, permission="self")
    db.session.add(l)
    db.session.commit()
    print("link", l.id, "owner", l.owner_id, "perm", l.permission)
    print("alice sees before grant?", l.id in [x.id for x in visible_links_for(alice)])
    db.session.add(LinkPermission(link_id=l.id, kind="user", target=str(alice.id)))
    db.session.commit()
    rows = [(p.link_id, p.kind, p.target) for p in LinkPermission.query.filter_by(kind="user").all()]
    print("LinkPermission(user) rows:", rows)
    q = [p.link_id for p in LinkPermission.query.filter_by(kind="user", target=str(alice.id)).all()]
    print("explicit query for alice:", q)
    print("alice sees after grant?", l.id in [x.id for x in visible_links_for(alice)])
    db.session.delete(l)
    db.session.commit()
    print("cleaned")
