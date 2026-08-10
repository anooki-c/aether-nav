import requests, json

BASE = "http://127.0.0.1:5000"
def login(u, p):
    r = requests.post(f"{BASE}/api/auth/login", json={"username": u, "password": p}, timeout=10)
    return r.json().get("token", "")

tok = login("Anooki", "admin123")
H = {"Authorization": f"Bearer {tok}"}
print("login token len:", len(tok))

# 1) dashboard default
r = requests.get(f"{BASE}/api/admin/stats/dashboard?days=30", headers=H, timeout=10)
d = r.json()
print("\n[1] dashboard default status", r.status_code)
print("    kpi keys:", list(d.get("kpis", {}).keys()))
print("    user_options count:", len(d.get("user_options", [])))
print("    top dim:", d.get("top", {}).get("dim"), "items:", len(d.get("top", {}).get("items", [])))
print("    permission roles:", [(x["role"], x["clicks"]) for x in d.get("permission", {}).get("roles", [])])
print("    trend days:", len(d.get("trend", {}).get("labels", [])))
print("    weekly len:", len(d.get("weekly", [])))

# 2) user_id filter on TOP
uid = d["user_options"][0]["id"]
r2 = requests.get(f"{BASE}/api/admin/stats/dashboard?days=30&user_id={uid}", headers=H, timeout=10)
d2 = r2.json()
print("\n[2] dashboard user_id=%s status %s" % (uid, r2.status_code))
print("    returned user_id:", d2.get("user_id"))
print("    top items (should be that user's links):", len(d2.get("top", {}).get("items", [])))
print("    category_share unaffected (global):", len(d2.get("category_share", [])))

# 3) day-detail
last = d["trend"]["labels"][-1]
r3 = requests.get(f"{BASE}/api/admin/stats/day-detail?date={last}", headers=H, timeout=10)
dd = r3.json()
print("\n[3] day-detail date=%s status %s" % (last, r3.status_code))
print("    hourly len:", len(dd.get("hourly", [])), "total_clicks:", dd.get("total_clicks"), "total_logins:", dd.get("total_logins"))

# 4) auth guard
r4 = requests.get(f"{BASE}/api/admin/stats/dashboard", timeout=10)
print("\n[4] no-auth status (expect 401):", r4.status_code)
r5 = requests.get(f"{BASE}/api/admin/stats/day-detail?date={last}", timeout=10)
print("    day-detail no-auth status (expect 401):", r5.status_code)

# 5) page served
rp = requests.get(f"{BASE}/admin", timeout=10)
print("\n[5] /admin page status:", rp.status_code)
print("    index.html has StatsView chunk reference:", "Admin-" in rp.text or "assets/Admin" in rp.text)
