"""End-to-end verification of every portal against the live server."""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"
PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
results = []


def req(method, path, token=None, body=None, raw=False):
    url = BASE + path
    data = None
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            txt = resp.read().decode()
            return resp.status, (txt if raw else json.loads(txt))
    except urllib.error.HTTPError as e:
        txt = e.read().decode()
        try:
            return e.code, json.loads(txt)
        except Exception:
            return e.code, {"raw": txt}


def check(name, cond, extra=""):
    results.append((name, cond, extra))
    print(f"  [{PASS if cond else FAIL}] {name} {extra}")


def login(u, p):
    s, d = req("POST", "/api/auth/login", body={"username": u, "password": p})
    return (s, d)


print("== AUTH ==")
# bad login
s, d = login("employee1", "wrongpass")
check("bad password rejected (401)", s == 401, f"-> {s}")
# good login each portal
creds = {
    "employee": ("employee1", "employee123"),
    "management": ("manager1", "manager123"),
    "counsel": ("counsel1", "counsel123"),
    "client": ("client1", "client123"),
    "tenant": ("tenant1", "tenant123"),
    "auditor": ("auditor1", "auditor123"),
    "admin": ("admin", "admin123"),
}
tokens = {}
for portal, (u, p) in creds.items():
    s, d = login(u, p)
    ok = s == 200 and d.get("token") and d.get("user", {}).get("portal") == portal
    check(f"login {portal} ({u})", ok, f"-> portal={d.get('user', {}).get('portal')}")
    tokens[portal] = d.get("token")

print("== /api/auth/me ==")
s, d = req("GET", "/api/auth/me", token=tokens["employee"])
check("me returns user", s == 200 and d["user"]["username"] == "employee1")
s, d = req("GET", "/api/auth/me")
check("me without token -> 401", s == 401)

print("== PORTAL DATA (role-scoped) ==")
# employee
s, d = req("GET", "/api/portal", token=tokens["employee"])
check("employee data", s == 200 and d["portal"] == "employee" and "cases" in d and "ai_tasks" in d,
      f"cases={len(d.get('cases', []))} tax={len(d.get('tax_matters', []))} ai_tasks={len(d.get('ai_tasks', []))}")

# management
s, d = req("GET", "/api/portal", token=tokens["management"])
check("management data", s == 200 and d["portal"] == "management" and "kpi" in d and "workload" in d,
      f"kpi_docs={d.get('kpi', {}).get('documents')} pending={d.get('kpi', {}).get('pending_approvals')}")

# counsel
s, d = req("GET", "/api/portal", token=tokens["counsel"])
check("counsel data", s == 200 and d["portal"] == "counsel" and "drafts_to_review" in d and "research" in d,
      f"cases={len(d.get('cases', []))} research={len(d.get('research', []))}")

# client
s, d = req("GET", "/api/portal", token=tokens["client"])
check("client data", s == 200 and d["portal"] == "client" and "reports" in d and "my_requests" in d,
      f"cases={len(d.get('cases', []))} reports={len(d.get('reports', []))}")

# tenant
s, d = req("GET", "/api/portal", token=tokens["tenant"])
check("tenant data", s == 200 and d["portal"] == "tenant" and "parcels" in d and "updates" in d,
      f"parcels={len(d.get('parcels', []))} updates={len(d.get('updates', []))}")

# auditor (controlled access)
s, d = req("GET", "/api/portal", token=tokens["auditor"])
check("auditor data", s == 200 and d["portal"] == "auditor" and "compliance_records" in d and "audit_trail" in d,
      f"records={len(d.get('compliance_records', []))} audit={len(d.get('audit_trail', []))}")

# admin
s, d = req("GET", "/api/portal", token=tokens["admin"])
check("admin data", s == 200 and d["portal"] == "admin" and "agents" in d and "kpi" in d,
      f"agents={len(d.get('agents', []))} users={d.get('kpi', {}).get('users')}")

print("== AI TASK (governed orchestrator) ==")
s, d = req("POST", "/api/portal/ai", token=tokens["employee"], body={"prompt": "Summarize the status of my assigned cases and any upcoming deadlines."})
check("employee AI task", s == 200 and d.get("answer"), f"agent={d.get('agent_id')} status={d.get('status')}")

print("== CLIENT REQUEST SUBMIT ==")
s, d = req("POST", "/api/portal/request", token=tokens["client"], body={"subject": "E2E status check", "message": "Please provide an update."})
check("client submit request", s == 200 and d.get("doc_id") and d.get("status") == "submitted", f"doc_id={d.get('doc_id')}")

print("== TENANT REQUEST SUBMIT ==")
s, d = req("POST", "/api/portal/request", token=tokens["tenant"], body={"subject": "E2E tenant request", "message": "Need parcel info."})
check("tenant submit request", s == 200 and d.get("doc_id"))

print("== APPROVAL GATING ==")
# employee cannot approve
s, d = req("POST", "/api/portal/approve", token=tokens["employee"], body={"approval_id": "nonexistent", "decision": "approved"})
check("employee approve -> 403", s == 403, f"-> {s}")
# client cannot approve
s, d = req("POST", "/api/portal/approve", token=tokens["client"], body={"approval_id": "nonexistent", "decision": "approved"})
check("client approve -> 403", s == 403, f"-> {s}")
# manager CAN approve (404 = not found, not 403)
s, d = req("POST", "/api/portal/approve", token=tokens["management"], body={"approval_id": "nonexistent", "decision": "approved"})
check("manager approve -> 404 (allowed, id missing)", s == 404, f"-> {s}")

print("== ADMIN USER MANAGEMENT ==")
s, d = req("GET", "/api/admin/users", token=tokens["admin"])
check("admin list users", s == 200 and len(d.get("users", [])) >= 7, f"users={len(d.get('users', []))}")
# non-admin cannot
s, d = req("GET", "/api/admin/users", token=tokens["employee"])
check("employee list users -> 403", s == 403)
# create user
s, d = req("POST", "/api/admin/users", token=tokens["admin"], body={"username": "e2euser", "password": "pw12345", "role": "employee", "display_name": "E2E User"})
check("admin create user", s == 200 and d.get("ok"))
# duplicate
s, d = req("POST", "/api/admin/users", token=tokens["admin"], body={"username": "e2euser", "password": "pw12345", "role": "employee"})
check("admin create dup -> 409", s == 409)
# disable
s, d = req("POST", "/api/admin/users/enable", token=tokens["admin"], body={"username": "e2euser", "enabled": False})
check("admin disable user", s == 200 and d.get("enabled") is False)

print("== LEGACY API (backward compat) ==")
s, d = req("GET", "/agents")
check("legacy /agents", s == 200 and len(d) == 16, f"agents={len(d)}")
s, d = req("POST", "/ask", body={"user": "admin", "request": "What is the status of matter M-100?"})
check("legacy /ask", s == 200 and d.get("answer") is not None, f"agent={d.get('agent_id')}")
s, d = req("GET", "/approvals")
check("legacy /approvals", s == 200 and isinstance(d, list))

print("== SPA SERVED ==")
s, d = req("GET", "/", raw=True)
check("GET / serves index.html", s == 200 and "<div id=\"root\">" in d, f"len={len(d)}")
s, d = req("GET", "/portal/admin", raw=True)
check("GET /portal/admin serves index.html (SPA fallback)", s == 200 and "<div id=\"root\">" in d)
# asset
import os
js = os.listdir(os.path.join(os.path.dirname(__file__), "frontend", "dist", "assets"))
jsfile = [f for f in js if f.endswith(".js")][0]
s, d = req("GET", f"/assets/{jsfile}", raw=True)
check(f"GET /assets/{jsfile}", s == 200 and len(d) > 1000, f"len={len(d)}")

print()
passed = sum(1 for _, c, _ in results if c)
failed = sum(1 for _, c, _ in results if not c)
print(f"TOTAL: {passed} passed, {failed} failed, {len(results)} checks")
if failed:
    print("FAILURES:")
    for n, c, e in results:
        if not c:
            print(f"  - {n} {e}")
    raise SystemExit(1)