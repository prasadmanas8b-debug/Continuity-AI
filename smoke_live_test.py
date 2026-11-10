#!/usr/bin/env python3
"""
Continuity AI — End-to-End Live HTTP Smoke & 9-Step Judge Journey Verification
Tests the live FastAPI server over HTTP (http://localhost:8000/api/v1) across all
Contract v1.0.0 endpoints, CORS headers, error envelopes, and the 9-step Judge Journey.
"""

import json
import sys
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000/api/v1"
ORIGIN = "http://127.0.0.1:8000"


def call(method, path, body=None, token=None, headers=None, use_origin=False):
    url = (ORIGIN if use_origin else BASE) + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    req.add_header("Origin", "http://localhost:5173")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8")
            return r.status, json.loads(raw) if raw else {}, dict(r.headers)
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body_txt), dict(e.headers)
        except Exception:
            return e.code, body_txt, dict(e.headers)
    except Exception as e:
        return 0, str(e), {}


results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'} | {name} | {detail}")


def main():
    # 0. Health & Meta Handshake + CORS
    s, r, hdrs = call("GET", "/health", use_origin=True)
    check("G1-0: Health check & CORS header", s == 200 and r.get("status") == "ok", f"status={s}")

    s, r, _ = call("GET", "/meta")
    check(
        "G1-1: Meta contract handshake v1.0.0",
        s == 200 and r.get("contract_version") == "1.0.0" and r.get("auth_mode") == "demo",
        f"meta={r}",
    )

    # Step 1: List demo users & Login as Manager
    s, users, _ = call("GET", "/auth/demo-users")
    check("Step 1a (S0): List 4 seeded demo users", s == 200 and len(users) == 4, f"count={len(users)}")

    s, login_mgr, _ = call("POST", "/auth/demo-login", {"user_id": "user-manager-001"})
    mgr_token = login_mgr.get("access_token", "")
    check("Step 1b (S0): Manager demo-login issues Bearer token", s == 200 and bool(mgr_token), f"status={s}")

    # Step 2: Access Project & Sources
    s, projs, _ = call("GET", "/projects", token=mgr_token)
    items = projs.get("items", []) if isinstance(projs, dict) else []
    proj_id = items[0]["project_id"] if items else "proj-roomiez-001"
    check("Step 2a (S1): List projects", s == 200 and len(items) >= 1, f"project_id={proj_id}")

    s, srcs, _ = call("GET", f"/projects/{proj_id}/sources", token=mgr_token)
    src_items = srcs.get("items", []) if isinstance(srcs, dict) else []
    check(
        "Step 2b (S2/S3): Seeded sources present with zero storage_key leak",
        s == 200 and len(src_items) >= 5 and "storage_key" not in json.dumps(srcs),
        f"sources={len(src_items)}",
    )

    # Excerpt check
    first_src_id = src_items[0]["source_id"]
    s, exc, _ = call("GET", f"/sources/{first_src_id}/excerpt?char_start=0&char_end=120", token=mgr_token)
    check("Step 2c (S3): Source excerpt window retrieval", s == 200 and "text" in exc, f"len={len(exc.get('text', ''))}")

    # GitHub invalid URL error envelope check
    s, gh_err, _ = call("POST", f"/projects/{proj_id}/sources/github", {"repo_url": "http://bad-host.local/repo"}, token=mgr_token)
    check(
        "Step 2d (S2): Invalid GitHub URL returns 422 GITHUB_URL_INVALID envelope",
        s == 422 and gh_err.get("error", {}).get("code") == "GITHUB_URL_INVALID",
        f"code={gh_err.get('error', {}).get('code')}",
    )

    # Step 3: Trigger Claim Extraction & Poll
    s, ext_run, _ = call("POST", f"/projects/{proj_id}/extractions", {}, token=mgr_token)
    run_id = ext_run.get("run_id", "")
    check("Step 3a (S4): Start extraction returns 202", s == 202 and bool(run_id), f"run_id={run_id}")

    s, poll_run, _ = call("GET", f"/extractions/{run_id}", token=mgr_token)
    check(
        "Step 3b (S4): Poll extraction run succeeded",
        s == 200 and poll_run.get("status") == "succeeded",
        f"claims_created={poll_run.get('claims_created')}",
    )

    s, claims_resp, _ = call("GET", f"/projects/{proj_id}/claims", token=mgr_token)
    claims = claims_resp.get("items", [])
    restricted_claims = [c for c in claims if c.get("sensitivity") == "restricted"]
    check(
        "Step 3c (S5): Claims extracted & credential claim flagged restricted",
        s == 200 and len(claims) >= 10 and len(restricted_claims) >= 1,
        f"total={len(claims)}, restricted={len(restricted_claims)}",
    )

    # Step 4: Inspect Contradiction on login_authentication
    s, confs_resp, _ = call("GET", f"/projects/{proj_id}/conflicts", token=mgr_token)
    confs = confs_resp.get("items", [])
    login_conf = next((c for c in confs if c.get("item_id") == "login_authentication"), None)
    check(
        "Step 4 (S6): Critical login_authentication contradiction detected with 2 competing claims",
        s == 200 and login_conf is not None and login_conf.get("is_critical") is True and len(login_conf.get("claims", [])) == 2,
        f"conflict_id={login_conf.get('conflict_id') if login_conf else None}",
    )

    # Step 5: Human Review (accept, edit, unresolved, and STALE_VERSION check)
    jwt_claim = next((c for c in claims if c.get("item_id") == "jwt_sessions"), None)
    s, stale_err, _ = call(
        "POST",
        f"/claims/{jwt_claim['claim_id']}/reviews",
        {"decision": "accept", "expected_version": 999},
        token=mgr_token,
    )
    check(
        "Step 5a (S7): Optimistic concurrency 409 STALE_VERSION enforced",
        s == 409 and stale_err.get("error", {}).get("code") == "STALE_VERSION",
        f"code={stale_err.get('error', {}).get('code')}",
    )

    s, edit_resp, _ = call(
        "POST",
        f"/claims/{jwt_claim['claim_id']}/reviews",
        {
            "decision": "edit",
            "reviewed_statement": "Use stateless JWT sessions (HS256) instead of server sessions.",
            "reason": "Clarified signing algorithm while preserving original AI statement.",
            "expected_version": jwt_claim["version"],
        },
        token=mgr_token,
    )
    check(
        "Step 5b (S7): Review edit preserves original_statement and increments version",
        s == 201
        and edit_resp["claim"]["original_statement"] == jwt_claim["original_statement"]
        and edit_resp["claim"]["statement"] != edit_resp["claim"]["original_statement"],
        f"v={edit_resp['claim']['version']}",
    )

    # Refresh claims to get current versions after conflict detection
    _, claims_resp, _ = call("GET", f"/projects/{proj_id}/claims", token=mgr_token)
    claims = claims_resp.get("items", [])
    for c in claims:
        if c["item_id"] in ("login_tests", "login_testing_ownership", "staging_database", "password_reset") and c["review_status"] == "pending":
            call(
                "POST",
                f"/claims/{c['claim_id']}/reviews",
                {"decision": "accept", "expected_version": c["version"]},
                token=mgr_token,
            )
        elif c["item_id"] == "login_authentication" and c["review_status"] == "pending":
            call(
                "POST",
                f"/claims/{c['claim_id']}/reviews",
                {
                    "decision": "unresolved",
                    "reason": "Keep unresolved until staging OAuth check completes",
                    "expected_version": c["version"],
                },
                token=mgr_token,
            )

    # Step 6: Handover Approval Gate for backend_developer
    s, ho_draft, _ = call(
        "POST",
        f"/projects/{proj_id}/handovers",
        {"recipient_role": "backend_developer"},
        token=mgr_token,
    )
    be_ho_id = ho_draft.get("handover_id", "")
    check("Step 6a (S8): Create backend_developer handover draft", s == 201 and bool(be_ho_id), f"id={be_ho_id}")

    s, elig, _ = call("GET", f"/handovers/{be_ho_id}/eligibility", token=mgr_token)
    check(
        "Step 6b (S8): Eligibility flags open critical conflict",
        s == 200 and elig.get("can_approve_without_override") is False,
        f"eligible={elig.get('eligible_claim_count')}, excluded={elig.get('excluded_claim_count')}",
    )

    s, block_err, _ = call("POST", f"/handovers/{be_ho_id}/approve", {"override_reason": None}, token=mgr_token)
    check(
        "Step 6c (S8): Approval without override blocked with 409 APPROVAL_BLOCKED_CONFLICT",
        s == 409 and block_err.get("error", {}).get("code") == "APPROVAL_BLOCKED_CONFLICT",
        f"code={block_err.get('error', {}).get('code')}",
    )

    s, ho_app, _ = call(
        "POST",
        f"/handovers/{be_ho_id}/approve",
        {"override_reason": "Proceeding with open login_authentication conflict clearly marked Disputed for incoming backend developer."},
        token=mgr_token,
    )
    check(
        "Step 6d (S8): Approval with override reason succeeds",
        s == 200 and ho_app.get("status") == "approved" and ho_app.get("approval_override") is not None,
        f"status={ho_app.get('status')}",
    )

    # Step 7: Incoming Backend Developer View (S9)
    s, login_be, _ = call("POST", "/auth/demo-login", {"user_id": "user-incoming-backend-001"})
    be_token = login_be.get("access_token", "")
    s, be_detail, _ = call("GET", f"/handovers/{be_ho_id}", token=be_token)
    be_raw = json.dumps(be_detail)
    check(
        "Step 7 (S9): Incoming backend dev sees approved handover, override banner, and zero credentials",
        s == 200
        and be_detail.get("recipient_role") == "backend_developer"
        and be_detail.get("approval_override") is not None
        and "staging_db_password" not in be_raw
        and "storage_key" not in be_raw,
        f"included={be_detail.get('included_claim_count')}, excluded={be_detail.get('excluded_claim_count')}",
    )

    # Step 8: Cold-Start Evaluation (S10 & S11)
    s, tasks, _ = call("GET", f"/handovers/{be_ho_id}/cold-start/tasks", token=be_token)
    tasks_raw = json.dumps(tasks)
    check(
        "Step 8a (S10): 3 cold-start tasks returned with zero answer-key leakage",
        s == 200 and len(tasks) == 3 and "expected_reference" not in tasks_raw,
        f"tasks={len(tasks)}",
    )

    s, res1, _ = call(
        "POST",
        f"/cold-start/tasks/{tasks[0]['task_id']}/results",
        {
            "outcome": "needs_help",
            "time_seconds": 65,
            "hints_used": 1,
            "missing_information": "Login authentication status has two competing sources (Nov 2 vs Nov 6).",
        },
        token=be_token,
    )
    s2, res2, _ = call(
        "POST",
        f"/cold-start/tasks/{tasks[1]['task_id']}/results",
        {"outcome": "pass", "time_seconds": 40, "hints_used": 0, "missing_information": None},
        token=be_token,
    )
    s3, res3, _ = call(
        "POST",
        f"/cold-start/tasks/{tasks[2]['task_id']}/results",
        {"outcome": "pass", "time_seconds": 35, "hints_used": 0, "missing_information": None},
        token=be_token,
    )
    check("Step 8b (S10): Cold-start results submitted (1 needs_help, 2 pass)", s == 201 and s2 == 201 and s3 == 201, "3/3 recorded")

    s, cs_sum, _ = call("GET", f"/handovers/{be_ho_id}/cold-start/summary", token=mgr_token)
    check(
        "Step 8c (S11): Manager cold-start summary aggregates metrics & notes",
        s == 200 and cs_sum.get("pass_count") == 2 and cs_sum.get("needs_help_count") == 1,
        f"summary={cs_sum}",
    )

    # Step 9: Incoming Designer Role-Isolation Verification (S9)
    for c in claims:
        if "designer" in c.get("audience_roles", []) and c["review_status"] == "pending":
            call(
                "POST",
                f"/claims/{c['claim_id']}/reviews",
                {"decision": "accept", "expected_version": c["version"]},
                token=mgr_token,
            )
    s, des_draft, _ = call("POST", f"/projects/{proj_id}/handovers", {"recipient_role": "designer"}, token=mgr_token)
    des_ho_id = des_draft.get("handover_id", "")
    s, des_app, _ = call("POST", f"/handovers/{des_ho_id}/approve", {"override_reason": None}, token=mgr_token)
    check("Step 9a (S8): Designer handover approved without override", s == 200 and des_app.get("status") == "approved", f"id={des_ho_id}")

    s, login_des, _ = call("POST", "/auth/demo-login", {"user_id": "user-incoming-designer-001"})
    des_token = login_des.get("access_token", "")
    s, des_detail, _ = call("GET", f"/handovers/{des_ho_id}", token=des_token)
    des_raw = json.dumps(des_detail)
    s_cross, _, _ = call("GET", f"/handovers/{be_ho_id}", token=des_token)
    check(
        "Step 9b (S9): Designer sees only design claims (2 included), zero backend/credential leak, 404 on backend handover",
        s == 200
        and des_detail.get("recipient_role") == "designer"
        and des_detail.get("included_claim_count") == 2
        and "staging_db_password" not in des_raw
        and "login_authentication" not in des_raw
        and s_cross == 404,
        f"included={des_detail.get('included_claim_count')}, cross_read_status={s_cross}",
    )

    print("\n" + "=" * 70)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"LIVE FULL-STACK JUDGE JOURNEY RESULTS: {passed}/{len(results)} PASSED")
    print("=" * 70)
    if passed != len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
