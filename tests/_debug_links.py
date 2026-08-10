"""Debug /api/links response format."""
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

ltk = api("POST", "/api/auth/login", body={"username": "alice", "password": "alice123"})["token"]
print(f"alice token: {ltk[:20]}...")

resp = api("GET", "/api/links", tk=ltk)
print(f"Raw type: {type(resp)}")
print(f"Raw keys if dict: {list(resp.keys()) if isinstance(resp, dict) else 'N/A'}")
print(f"Raw: {json.dumps(resp, ensure_ascii=False)[:500]}")
