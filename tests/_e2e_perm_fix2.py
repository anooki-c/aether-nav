"""E2E: change one link to self-only, test full grant/revoke cycle."""
import urllib.request, json

BASE = "http://127.0.0.1:5000"

def api(method, path, token=None, body=None):
    hdr = {}
    if token:
        hdr["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        hdr["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=hdr)
    return json.loads(urllib.request.urlopen(req, timeout=8).read())

# Login admin
resp = api("POST", "/api/auth/login", body={"username": "admin", "password": "admin123"})
tk = resp["token"]

# Change Jenkins(id=3) to permission=self (only owner=admin can see)
print("=== Set Jenkins permission=self ===")
r = api("PUT", "/api/links/3", token=tk, body={"permission": "self"})
print(f"Update result: {list(r.keys()) if isinstance(r, dict) else r}")

# Check alice's permissions - Jenkins should be EDITABLE now
print("\n=== Alice perms (Jenkins=self) ===")
data = api("GET", "/api/admin/users/2/permissions", token=tk)
for l in data["links"]:
    inh = "INHERITED(disabled)" if l["inherited"] else "EDITABLE(enabled)"
    acc = "VISIBLE" if l["access"] else "HIDDEN"
    mark = " <<<" if not l["inherited"] else ""
    print(f"  [{l['id']}] {l['title']:12s} | {acc:8s} | {inh}{mark}")

# Grant Jenkins to alice
editable = [l for l in data["links"] if not l["inherited"]]
if editable:
    tid = editable[0]["id"]
    tname = editable[0]["title"]
    print(f"\n--- Granting {tname}(id={tid}) to alice ---")
    r2 = api("POST", "/api/admin/users/2/permissions", token=tk, body={"link_ids": [tid]})
    print(f"POST result: {r2}")

    # Verify GET reflects grant
    data3 = api("GET", "/api/admin/users/2/permissions", token=tk)
    l3 = next(l for l in data3["links"] if l["id"] == tid)
    print(f"After grant:  access={l3['access']}, inherited={l3['inherited']}")

    # Verify alice /api/links includes Jenkins
    atk = api("POST", "/api/auth/login", body={"username": "alice", "password": "alice123"})["token"]
    al = api("GET", "/api/links", token=atk)
    items = al.get("links", al) if isinstance(al, dict) else al
    ids = sorted([x["id"] for x in items])
    print(f"Alice visible IDs: {ids} (expect 3 included)")

    # Revoke
    print(f"\n--- Revoking {tname} from alice ---")
    api("POST", "/api/admin/users/2/permissions", token=tk, body={"link_ids": []})
    data4 = api("GET", "/api/admin/users/2/permissions", token=tk)
    l4 = next(l for l in data4["links"] if l["id"] == tid)
    print(f"After revoke: access={l4['access']}, inherited={l4['inherited']}")

    al2 = api("GET", "/api/links", token=atk)
    items2 = al2.get("links", al2) if isinstance(al2, dict) else al2
    ids2 = sorted([x["id"] for x in items2])
    print(f"Alice after revoke: {ids2} (expect 3 NOT included)")

# Check admin self-perms (admin sees all -> all inherited)
print("\n=== Admin self-perms (all INHERITED expected) ===")
adata = api("GET", "/api/admin/users/1/permissions", token=tk)
for l in adata["links"]:
    inh = "INHERITED" if l["inherited"] else "EDITABLE"
    mark = " <<<" if not l["inherited"] else ""
    print(f"  [{l['id']}] {l['title']:12s} | {inh}{mark}")
