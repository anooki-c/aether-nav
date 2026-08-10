"""Full E2E: permission modal grant -> /api/links visibility cycle."""
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

def visible_link_ids(tk):
    resp = api("GET", "/api/links", tk=tk)
    ids = []
    for g in resp.get("groups", []):
        for link in g.get("links", []):
            ids.append(link["id"])
    return sorted(ids)

# Login
atk = api("POST", "/api/auth/login", body={"username": "admin", "password": "admin123"})["token"]
ltk = api("POST", "/api/auth/login", body={"username": "alice", "password": "alice123"})["token"]

# Step 0: baseline — all links are 'all', alice sees all
ids0 = visible_link_ids(ltk)
print(f"Step 0 - Baseline (all=permission all): alice sees {len(ids0)} links: {ids0}")

# Step 1: Set Jenkins(id=3) to self-only
print("\nStep 1 - Set Jenkins permission=self")
api("PUT", "/api/links/3", tk=atk, body={"permission": "self"})
ids1 = visible_link_ids(ltk)
print(f"  Alice sees {len(ids1)} links: {ids1}")
assert 3 not in ids1, "FAIL: alice should NOT see Jenkins(self)"
print("  PASS: Jenkins hidden from alice")

# Step 2: Check perm modal shows Jenkins as editable for alice
print("\nStep 2 - Permission GET for alice")
pdata = api("GET", "/api/admin/users/2/permissions", tk=atk)
jenkins = next(l for l in pdata["links"] if l["id"] == 3)
print(f"  Jenkins: access={jenkins['access']}, inherited={jenkins['inherited']}")
assert jenkins["inherited"] == False, "FAIL: should be editable"
assert jenkins["access"] == False, "FAIL: should be hidden by default"
print("  PASS: Jenkins is EDITABLE and HIDDEN for alice")

# Step 3: Grant Jenkins to alice via POST
print("\nStep 3 - Grant Jenkins to alice")
r = api("POST", "/api/admin/users/2/permissions", tk=atk, body={"link_ids": [3]})
print(f"  POST result: {r}")
ids3 = visible_link_ids(ltk)
print(f"  Alice sees {len(ids3)} links: {ids3}")
assert 3 in ids3, "FAIL: alice SHOULD see Jenkins after grant"
print("  PASS: Jenkins visible after grant")

# Step 4: Revoke
print("\nStep 4 - Revoke Jenkins from alice")
api("POST", "/api/admin/users/2/permissions", tk=atk, body={"link_ids": []})
ids4 = visible_link_ids(ltk)
print(f"  Alice sees {len(ids4)} links: {ids4}")
assert 3 not in ids4, "FAIL: alice should NOT see Jenkins after revoke"
print("  PASS: Jenkins hidden after revoke")

# Step 5: Restore demo state
print("\nStep 5 - Restore demo (Jenkins=all)")
api("PUT", "/api/links/3", tk=atk, body={"permission": "all"})
ids5 = visible_link_ids(ltk)
print(f"  Alice sees {len(ids5)} links: {ids5}")

print("\n" + "="*50)
print("ALL E2E TESTS PASSED!")
print("="*50)
