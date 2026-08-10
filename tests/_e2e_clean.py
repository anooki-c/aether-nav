"""Clean E2E: full grant/revoke cycle with fresh state."""
import urllib.request, json

BASE = "http://127.0.0.1:5000"

def api(m, p, tk=None, body=None):
    h = {}
    if tk: h["Authorization"] = "Bearer " + tk
    d = None
    if body is not None:
        h["Content-Type"] = "application/json"
        d = json.dumps(body).encode()
    r = urllib.request.Request(BASE + p, data=d, method=m, headers=h)
    return json.loads(urllib.request.urlopen(r, timeout=8).read())

def visible_ids(tk):
    resp = api("GET", "/api/links", tk=tk)
    ids = []
    for g in resp.get("groups", []):
        for link in g.get("links", []):
            ids.append(link["id"])
    return sorted(ids)

# Login
atk = api("POST", "/api/auth/login", body={"username": "admin", "password": "admin123"})["token"]
ltk = api("POST", "/api/auth/login", body={"username": "alice", "password": "alice123"})["token"]

# 0. Clean slate: remove any existing grants for alice, ensure Jenkins=self
print("=== Clean slate ===")
api("POST", "/api/admin/users/2/permissions", tk=atk, body={"link_ids": []})  # clear all grants
api("PUT", "/api/links/3", tk=atk, body={"permission": "self"})  # ensure self

ids0 = visible_ids(ltk)
print(f"Alice sees {len(ids0)} links: {ids0}")
assert 3 not in ids0, "FAIL: Jenkins(self) should be hidden from alice"
print("PASS: Jenkins HIDDEN (base permission=self, no grant)")

# 1. Check perm modal: Jenkins should be EDITABLE for alice
print("\n=== Permission modal GET ===")
pdata = api("GET", "/api/admin/users/2/permissions", tk=atk)
j = next(l for l in pdata["links"] if l["id"] == 3)
print(f"Jenkins: access={j['access']}, inherited={j['inherited']}")
assert j["inherited"] == False, "FAIL: should be editable"
assert j["access"] == False, "FAIL: should be hidden"
print("PASS: Jenkins is EDITABLE+HIDDEN")

# 2. Grant Jenkins to alice
print("\n=== GRANT Jenkins to alice ===")
r = api("POST", "/api/admin/users/2/permissions", tk=atk, body={"link_ids": [3]})
print(f"POST: {r}")
ids2 = visible_ids(ltk)
print(f"Alice sees: {ids2}")
assert 3 in ids2, "FAIL: should see Jenkins after grant"
print("PASS: Jenkins VISIBLE after grant")

# 3. Revoke
print("\n=== REVOKE Jenkins from alice ===")
api("POST", "/api/admin/users/2/permissions", tk=atk, body={"link_ids": []})
ids3 = visible_ids(ltk)
print(f"Alice sees: {ids3}")
assert 3 not in ids3, "FAIL: Jenkins should be hidden after revoke"
print("PASS: Jenkins HIDDEN after revoke")

# 4. Restore demo
api("PUT", "/api/links/3", tk=atk, body={"permission": "all"})
print("\nDemo restored: Jenkins=all")

print("\n" + "="*50)
print("ALL TESTS PASSED!")
print("="*50)
