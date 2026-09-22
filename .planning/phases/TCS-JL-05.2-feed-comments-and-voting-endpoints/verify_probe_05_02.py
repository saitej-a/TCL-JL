"""INDEPENDENT verification probe for Phase 5.2 (verifier role).

Deliberately separate from drill_05_02.py: it attacks the *claims* the phase
makes (P9 feed exclusion, COMM-02 rate limit, 04 §30/§43 shapes) rather than
re-running the happy path. Run inside the web container:
    python manage.py shell < verify_probe_05_02.py
Every check prints PASS/FAIL; the script never raises so all findings surface.
"""

import json
import urllib.error
import urllib.request
import uuid as uuidlib

from django.contrib.auth import get_user_model

from apps.community.services import create_post

User = get_user_model()
BASE = "http://127.0.0.1:8000/api/v1"
PASSWORD = "Correct Horse Battery 9!"
results = []


def check(name, condition, detail=""):
    results.append((name, bool(condition), detail))
    print(f"{'PASS' if condition else 'FAIL'} | {name}" + (f" | {detail}" if detail else ""))


def api(method, path, token=None, body=None):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw or "{}")
        except json.JSONDecodeError:
            return exc.code, {"_raw": raw[:200]}


def login(email):
    status, body = api("POST", "/auth/login/", body={"email": email, "password": PASSWORD})
    assert status == 200, f"login failed {email}: {status} {body}"
    return body["access"]


stamp = uuidlib.uuid4().hex[:8]
author = User.objects.create_user(f"vp52-author-{stamp}@example.com", PASSWORD, is_verified=True)
reader = User.objects.create_user(f"vp52-reader-{stamp}@example.com", PASSWORD, is_verified=True)
author_tok = login(author.email)
reader_tok = login(reader.email)

# --- V1: P9 feed exclusion — does a soft-deleted post leave the default feed? ---
keep = create_post(author, title=f"KEEPTITLE {stamp}", body="visible body", category="HELP")
gone = create_post(author, title=f"GONETITLE {stamp}", body="secret body", category="HELP")
gone.is_deleted = True
gone.save(update_fields=["is_deleted", "updated_at"])

status, body = api("GET", "/community/posts/", reader_tok)
rows = body.get("results", [])
ids = [r["id"] for r in rows]
check("V1 feed 200", status == 200, str(status))
check(
    "V2 P9: deleted post EXCLUDED from default feed",
    str(gone.id) not in ids,
    f"deleted post {gone.id} PRESENT in feed (P9 violated)" if str(gone.id) in ids else "absent",
)
# does the tombstone leak the original body/title anywhere in the feed payload?
blob = json.dumps(body)
check(
    "V3 deleted post original title/body not leaked in feed",
    f"GONETITLE {stamp}" not in blob and "secret body" not in blob,
    "original text of deleted post leaked" if (f"GONETITLE {stamp}" in blob or "secret body" in blob) else "masked",
)

# --- V4: search must also exclude deleted (P9 search half) ---
status, body = api("GET", f"/community/posts/?search={stamp}", reader_tok)
srows = body.get("results", [])
sids = [r["id"] for r in srows]
check(
    "V4 P9: deleted post EXCLUDED from search results",
    str(gone.id) not in sids,
    f"search returned {len(sids)} rows incl deleted" if str(gone.id) in sids else f"{len(sids)} rows, deleted absent",
)

# --- V5: feed card shape — body_preview vs full body (04 §30) ---
status, body = api("GET", "/community/posts/", reader_tok)
card = next((r for r in body.get("results", []) if r["id"] == str(keep.id)), {})
check(
    "V5 feed card carries body_preview (04 §30), not full body",
    "body_preview" in card,
    f"keys={sorted(card.keys())}",
)

# --- V6: vote response shape (04 §43 {"voted": bool, "vote_count": int}) ---
status, body = api("POST", f"/community/posts/{keep.id}/vote/", reader_tok)
check(
    "V6 vote response carries 'voted' boolean (04 §43)",
    "voted" in body,
    f"status={status} keys={sorted(body.keys())}",
)

# --- V7: COMM-02/T5.7 — post creation rate limited (spec 5/hr) ---
# Fire 8 rapid creates as a fresh user; spec says the 6th+ should 429.
spammer = User.objects.create_user(f"vp52-spam-{stamp}@example.com", PASSWORD, is_verified=True)
spam_tok = login(spammer.email)
codes = []
for i in range(8):
    st, _b = api("POST", "/community/posts/", spam_tok, {"title": f"spam {i} {stamp}", "body": "x", "category": "HELP"})
    codes.append(st)
check(
    "V7 COMM-02: post creation is rate-limited (a 429 appears)",
    429 in codes,
    f"8 rapid creates returned {codes} — NO 429, creation unthrottled",
)

# --- V8: trending tab excludes deleted (impl filters is_deleted there) ---
status, body = api("GET", "/community/posts/?tab=trending", reader_tok)
tids = [r["id"] for r in body.get("results", [])]
check(
    "V8 trending tab excludes deleted post",
    str(gone.id) not in tids,
    "deleted present in trending" if str(gone.id) in tids else "absent (trending filters is_deleted)",
)

passed = sum(1 for _n, ok, _d in results if ok)
print(f"\n{passed}/{len(results)} independent verification checks passed")
failed = [(n, d) for n, ok, d in results if not ok]
if failed:
    print("FAILURES:")
    for n, d in failed:
        print(f"  - {n}: {d}")
