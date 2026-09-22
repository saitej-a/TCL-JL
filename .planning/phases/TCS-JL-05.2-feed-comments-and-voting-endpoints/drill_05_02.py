"""Stage 2 live HTTP drill for PLAN 05-02 + 05-03 (run inside the web container:
python manage.py shell < drill_05_02.py).

Real JWTs over real HTTP against gunicorn — this phase IS the API, so the
drill is HTTP, not ORM (the 4.2 escalation, repeated). Uses urllib against
127.0.0.1:8000 inside the container; every check prints PASS/FAIL and the
script exits non-zero on any failure.
"""

import json
import urllib.error
import urllib.request
import uuid as uuidlib
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.community.models import Comment, Post
from apps.community.services import create_comment, create_post

User = get_user_model()
BASE = "http://127.0.0.1:8000/api/v1"
PASSWORD = "Correct Horse Battery 9!"

results = []


def check(name, condition, detail=""):
    results.append((name, bool(condition), detail))
    print(f"{'PASS' if condition else 'FAIL'} | {name}" + (f" | {detail}" if detail and not condition else ""))


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
    assert status == 200, f"login failed for {email}: {status} {body}"
    return body["access"]


# --- seed: three real users, two posts, comments, one vote -------------------
stamp = uuidlib.uuid4().hex[:8]


def mk_user(tag, **kw):
    return User.objects.create_user(f"drill52-{tag}-{stamp}@example.com", PASSWORD, **kw)


author = mk_user("author", is_verified=True)
reader = mk_user("reader", is_verified=True)
attacker = mk_user("attacker", is_verified=True)
mod = mk_user("mod", is_verified=True, is_staff=True)

post_a = create_post(author, title=f"Drill A {stamp}", body="alpha body", category="JOINING_LETTER")
post_b = create_post(author, title=f"Drill B {stamp}", body="beta body", category="HELP")
top1 = create_comment(post_a, reader, body="first top-level")
create_comment(post_a, author, body="a reply", parent=top1)

author_tok = login(author.email)
reader_tok = login(reader.email)
attacker_tok = login(attacker.email)
mod_tok = login(mod.email)
check("1. all four JWT logins", all([author_tok, reader_tok, attacker_tok, mod_tok]))

# --- feed + card -------------------------------------------------------------
status, body = api("GET", "/community/posts/", reader_tok)
check("2. feed 200 for authenticated reader", status == 200, f"{status}")
cards = {c["title"]: c for c in body.get("results", [])}
check("3. feed card shows seeded posts", f"Drill A {stamp}" in cards)
card_a = cards.get(f"Drill A {stamp}", {})
check("4. comment_count includes reply (D4)", card_a.get("comment_count") == 2, str(card_a.get("comment_count")))
check("5. author payload has avatar_seed, no email", "avatar_seed" in card_a.get("author", {}) and "email" not in card_a.get("author", {}))
check("6. has_voted false before voting", card_a.get("has_voted") is False)

status, body = api("GET", "/community/posts/?tab=trending", reader_tok)
check("7. trending tab 200", status == 200, str(status))
status, body = api("GET", f"/community/posts/?search={stamp}", reader_tok)
check("8. search returns exactly this run's seeded posts", body.get("count") == 2, str(body.get("count")))  # Drill A + Drill B carry the stamp; nothing else
status, body = api("GET", "/community/posts/?category=NOT_REAL", reader_tok)
check("9. unknown category 404 invalid_category", status == 404 and body.get("error", {}).get("code") == "invalid_category", f"{status}")
status, body = api("GET", "/community/posts/?ordering=author__email", reader_tok)
check("10. ordering whitelist 400 invalid_ordering", status == 400 and body.get("error", {}).get("code") == "invalid_ordering", f"{status}")

# --- post lifecycle ----------------------------------------------------------
status, body = api("POST", "/community/posts/", reader_tok, {"title": f"Drill C {stamp}", "body": "gamma", "category": "TCS_PROCESS"})
check("11. create post 201", status == 201, f"{status} {body}")
post_c_id = body.get("id", "")

status, body = api("PATCH", f"/community/posts/{post_c_id}/", attacker_tok, {"title": "hijack"})
check("12. foreign edit 403 not_author", status == 403 and body.get("error", {}).get("code") == "not_author", f"{status}")
status, body = api("PATCH", f"/community/posts/{post_c_id}/", reader_tok, {"title": f"Drill C2 {stamp}"})
check("13. author edit 200", status == 200 and body.get("title") == f"Drill C2 {stamp}", f"{status}")

# --- tombstone (P9/D3) -------------------------------------------------------
status, _ = api("DELETE", f"/community/posts/{post_c_id}/", reader_tok)
check("14. author delete 204", status == 204, str(status))
status, body = api("GET", f"/community/posts/{post_c_id}/", attacker_tok)
check("15. tombstone detail 200 masked", status == 200 and body.get("title") == "This content has been removed.", f"{status}")
check("16. author handle kept (D3 deviation)", body.get("author", {}).get("id") == str(reader.id))
status, body = api("POST", f"/community/posts/{post_c_id}/comments/", attacker_tok, {"body": "ghost"})
check("17. comment on tombstone 404 content_deleted", status == 404 and body.get("error", {}).get("code") == "content_deleted", f"{status}")
status, body = api("POST", f"/community/posts/{post_c_id}/vote/", attacker_tok)
check("18. vote on tombstone 404", status == 404 and body.get("error", {}).get("code") == "content_deleted", f"{status}")

# --- comments ----------------------------------------------------------------
status, body = api("GET", f"/community/posts/{post_a.id}/comments/", reader_tok)
check("19. thread 200: count=1 top-level, total=2", status == 200 and body.get("count") == 1 and body.get("total_comments") == 2, f"{status} {body.get('count')},{body.get('total_comments')}")
check("20. reply nested under parent", body["results"][0]["replies"][0]["body"] == "a reply" if body.get("results") else False)
reply_id = body["results"][0]["replies"][0]["id"]  # the REPLY, not top1 — replying to top1 is legal (201)
status, body = api("POST", f"/community/posts/{post_a.id}/comments/", reader_tok, {"body": "too deep", "parent_id": reply_id})
check("21. reply-to-reply 400 nested_reply", status == 400 and body.get("error", {}).get("code") == "nested_reply", f"{status}")

# --- votes -------------------------------------------------------------------
status, body = api("POST", f"/community/posts/{post_a.id}/vote/", attacker_tok)
check("22. vote 201", status == 201 and body.get("vote_count") == 1, f"{status} {body.get('vote_count')}")
status, body = api("POST", f"/community/posts/{post_a.id}/vote/", attacker_tok)
check("23. duplicate vote 409 already_voted", status == 409 and body.get("error", {}).get("code") == "already_voted", f"{status}")
status, _ = api("DELETE", f"/community/posts/{post_a.id}/vote/", attacker_tok)
check("24. unvote 204", status == 204, str(status))
status, body = api("DELETE", f"/community/posts/{post_a.id}/vote/", attacker_tok)
check("25. unvote again 404 vote_not_found", status == 404 and body.get("error", {}).get("code") == "vote_not_found", f"{status}")

# --- lock/pin (staff-only) ---------------------------------------------------
status, body = api("POST", f"/community/posts/{post_b.id}/lock/", author_tok)
check("26. author cannot lock own thread 403", status == 403 and body.get("error", {}).get("code") == "moderator_only", f"{status}")
status, body = api("POST", f"/community/posts/{post_b.id}/lock/", mod_tok)
check("27. staff lock 200", status == 200 and body.get("is_locked") is True, f"{status}")
status, body = api("POST", f"/community/posts/{post_b.id}/comments/", attacker_tok, {"body": "late"})
check("28. locked post refuses comments 400 post_locked", status == 400 and body.get("error", {}).get("code") == "post_locked", f"{status}")
status, body = api("DELETE", f"/community/posts/{post_b.id}/lock/", mod_tok)
check("29. staff unlock 200 (addition)", status == 200 and body.get("is_locked") is False, f"{status}")
status, body = api("POST", f"/community/posts/{post_b.id}/pin/", mod_tok)
check("30. staff pin 200", status == 200 and body.get("is_pinned") is True, f"{status}")
status, body = api("GET", "/community/posts/", reader_tok)
titles = [c["title"] for c in body.get("results", [])]
check("31. pinned post leads feed", titles and titles[0] == f"Drill B {stamp}", str(titles[:3]))

# --- anonymous / authz edges -------------------------------------------------
status, body = api("GET", "/community/posts/")
check("32. anonymous feed 401", status == 401, str(status))
status, body = api("GET", f"/community/posts/{post_a.id}/", attacker_tok)
check("33. foreign detail readable 200 (P5)", status == 200, str(status))

failed = [name for name, ok, _detail in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} live HTTP checks passed")
if failed:
    print("FAILURES:", failed)
    raise SystemExit(1)
