import json
import urllib.request
import urllib.error

B = "http://127.0.0.1:8011"
results = []
errors = []


def call(method, path, body=None, expect=(200, 201, 202)):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        B + path, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req) as r:
            code = r.status
            text = r.read().decode()
    except urllib.error.HTTPError as e:
        code = e.code
        text = e.read().decode()
    ok = code in expect
    results.append((method, path, code, ok))
    if not ok:
        errors.append((method, path, code, text[:200]))
    return code, (json.loads(text) if text else None)


posts = call("GET", "/posts")[1]["posts"]
fox = next(p for p in posts if "Red Foxes" in p["title"])

# 1. match (and capture suggestion ids)
code, m = call("POST", f"/posts/{fox['id']}/match")
assert code == 200
sug_id = next(c["suggestion_id"] for c in m["candidates"] if c["suggestion_id"])
print("match decision:", m["decision"], "| sample suggestion_id:", sug_id)

# 2. list suggestions
code, sugs = call("GET", f"/suggestions?post_id={fox['id']}")
assert code == 200 and any(s["id"] == sug_id for s in sugs)
print("GET /suggestions ->", len(sugs), "suggestions for fox post")

# 3. approve a suggestion -> review
code, rev = call("POST", f"/suggestions/{sug_id}/approve", {"decision": "APPROVED", "reviewer": "tester", "notes": "looks right"})
assert code == 200
print("approve -> review", rev["decision"], rev["reviewer"])

# 4. reviews list
code, revs = call("GET", "/reviews")
assert code == 200
print("GET /reviews ->", len(revs), "reviews")

# 5. images list + status filter
code, imgs = call("GET", "/images")
print("GET /images -> total", imgs["total"])
code, flagged = call("GET", "/images?status_filter=FLAGGED")
assert code == 200
print("GET /images?status_filter=FLAGGED -> total", flagged["total"], "(expect 1)")

# 6. create image + get
code, newimg = call("POST", "/images", {"filename": "test_img_01.jpg"})
assert code == 201
code, got = call("GET", f"/images/{newimg['id']}")
assert code == 200
print("POST /images + GET ->", got["filename"])

# 7. create post + match + images
code, newpost = call("POST", "/posts", {"title": "Test Post About Wolves", "content": "Wolves are wild canines.", "category": "wolf"})
assert code == 201
code, _ = call("POST", f"/posts/{newpost['id']}/match")
assert code == 200
code, _ = call("GET", f"/posts/{newpost['id']}/images")
assert code == 200
print("POST /posts + match + images -> ok")

# 8. jobs
code, j1 = call("POST", "/jobs/images/process")
assert code == 202
code, jdet = call("GET", f"/jobs/{j1['id']}")
assert code == 200
code, _ = call("POST", "/jobs/posts/process")
assert code == 202
code, _ = call("GET", "/jobs")
assert code == 200
print("jobs -> process 202, get 200, list 200")

# 9. evaluation + usage
code, ev = call("POST", "/evaluation/run")
assert code == 200
print("POST /evaluation/run -> precision", ev["top1_precision"], f"({ev['correct']}/{ev['total']})")
code, _ = call("GET", "/evaluation/latest")
assert code == 200
code, u = call("GET", "/usage")
assert code == 200
print("GET /usage -> calls", u["total_calls"], "budget", u["budget_usd"])

# 10. negative / validation cases (must be 4xx, never 5xx)
call("POST", "/posts", {}, expect=(422,))
call("GET", "/images/nonexistent_id", expect=(404,))
call("POST", "/suggestions/nonexistent_id/approve", {"decision": "APPROVED"}, expect=(404,))
call("POST", "/posts/nonexistent_id/match", expect=(404,))
call("POST", "/suggestions/nonexistent_id/approve", {"decision": "BOGUS"}, expect=(422,))
print("negative cases returned 4xx as expected")

print("\n=== SUMMARY ===")
print("total calls:", len(results), "| unexpected:", len(errors))
for e in errors:
    print("ERROR:", e)
print("ALL GOOD" if not errors else "HAS ERRORS")
