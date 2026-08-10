"""E2E test: permission edit modal fix verification."""
import urllib.request, json

BASE = "http://127.0.0.1:5000"

def api(method, path, token=None, body=None):
    hdr = {}
    if token:
        hdr["Authorization"] = f"Bearer {token}"
    if body is not None:
        hdr["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    else:
        data = None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=hdr)
    resp = urllib.request.urlopen(req, timeout=8)
    return json.loads(resp.read())

# 1. Login as admin
resp = api("POST", "/api/auth/login", body={"username": "admin", "password": "admin123"})
admin_token = resp["token"]
print(f"Admin token: {admin_token[:20]}...")

# 2. GET alice (uid=2) permissions
data = api("GET", "/api/admin/users/2/permissions", token=admin_token)
print(f"\n=== Alice permissions GET ===")
print(f"User: {data['user']['username']} role={data['user']['role']}")
for l in data["links"]:
    inh = "INHERITED(disabled)" if l["inherited"] else "EDITABLE(enabled)"
    acc = "VISIBLE" if l["access"] else "HIDDEN"
    print(f"  [{l['id']}] {l['title']:12s} owner={l['owner_name']:6s} | {acc:8s} | {inh}")

# 3. Check if any link is editable for alice
editable = [l for l in data["links"] if not l["inherited"]]
print(f"\nEditable links for alice: {[l['id'] for l in editable]}")

if editable:
    # Grant first editable link to alice
    target_id = editable[0]["id"]
    target_title = editable[0]["title"]
    print(f"\n--- Granting {target_title}(id={target_id}) to alice ---")
    result = api("POST", "/api/admin/users/2/permissions", token=admin_token,
                 body={"link_ids": [target_id]})
    print(f"POST result: {result}")

    # Re-GET to verify persisted
    data2 = api("GET", "/api/admin/users/2/permissions", token=admin_token)
    l2 = next(l for l in data2["links"] if l["id"] == target_id)
    print(f"After grant: access={l2['access']}, inherited={l2['inherited']}")

    # Verify alice can see it in /api/links
    alice_resp = api("POST", "/api/auth/login", body={"username": "alice", "password": "alice123"})
    alice_token = alice_resp["token"]

    links_resp = api("GET", "/api/links", token=alice_token)
    # Handle both list and dict response formats
    items = links_resp.get("links", links_resp) if isinstance(links_resp, dict) else links_resp
    visible_ids = sorted([item["id"] for item in items])
    print(f"Alice visible link IDs: {visible_ids} (expect {target_id} included)")

    # Now revoke and verify
    print(f"\n--- Revoking {target_title} from alice ---")
    api("POST", "/api/admin/users/2/permissions", token=admin_token, body={"link_ids": []})
    data3 = api("GET", "/api/admin/users/2/permissions", token=admin_token)
    l3 = next(l for l in data3["links"] if l["id"] == target_id)
    print(f"After revoke: access={l3['access']}, inherited={l3['inherited']}")

    links_resp2 = api("GET", "/api/links", token=alice_token)
    items2 = links_resp2.get("links", links_resp2) if isinstance(links_resp2, dict) else links_resp2
    visible_ids2 = sorted([item["id"] for item in items2])
    print(f"Alice visible after revoke: {visible_ids2} (expect {target_id} NOT included)")
else:
    print("\nAll links are inherited (permission='all' means everyone sees everything)")
    print("This is expected when all links have permission='all'")
    print("To test toggling, change a link's permission to 'admin' or 'self' first")
