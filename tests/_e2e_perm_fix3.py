"""Verify alice /api/links after grant/revoke."""
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

atk = api("POST", "/api/auth/login", body={"username": "admin", "password": "admin123"})["token"]
ltk = api("POST", "/api/auth/login", body={"username": "alice", "password": "alice123"})["token"]

# Alice visible NOW (Jenkins was granted in previous test)
resp = api("GET", "/api/links", tk=ltk)
items = resp if isinstance(resp, list) else resp.get("data", resp.get("links", []))
ids = sorted([x["id"] for x in items])
print(f"Alice with grant:  IDs={ids}")
assert 3 in ids, "FAIL Jenkins should be visible"
print("PASS: Jenkins visible after grant")

# Revoke
api("POST", "/api/admin/users/2/permissions", token=atk, body={"link_ids": []})
resp2 = api("GET", "/api/links", tk=ltk)
items2 = resp2 if isinstance(resp2, list) else resp2.get("data", resp2.get("links", []))
ids2 = sorted([x["id"] for x in items2])
print(f"Alice after revoke: IDs={ids2}")
assert 3 not in ids2, "FAIL Jenkins should be hidden"
print("PASS: Jenkins hidden after revoke")

# Restore demo
api("PUT", "/api/links/3", token=atk, body={"permission": "all"})
print("\nDemo restored: Jenkins permission=all")
