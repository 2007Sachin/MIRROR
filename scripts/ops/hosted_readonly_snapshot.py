"""READ-ONLY inspection of a hosted Supabase project (structure + counts only).

Usage: python scripts/ops/hosted_readonly_snapshot.py [output.json]   (default: .runtime/hosted_snapshot.json, gitignored)

Hard guarantees: only HTTP GET/HEAD are ever sent (enforced by `get()`); secrets are read from .env
into memory and never printed or written; no row data is requested (counts via HEAD, Content-Range).
Importing this module neither loads credentials nor sends requests; run main explicitly.
"""
import json, pathlib, sys, urllib.request, urllib.error, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[2]
URL = None
KEY = None

class RejectRedirects(urllib.request.HTTPRedirectHandler):
    """Never forward authenticated requests, even to the same origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_project_url(url):
    """Require a bare HTTPS origin; never include the configured value in errors."""
    try:
        parts = urllib.parse.urlsplit(url)
        valid = (
            isinstance(url, str) and url.startswith("https://")
            and not any(c.isspace() or ord(c) < 32 for c in url)
            and "\\" not in url and "?" not in url and "#" not in url
            and parts.scheme == "https" and bool(parts.hostname)
            and parts.username is None and parts.password is None
            and not parts.path and not parts.query and not parts.fragment
            and (parts.port is None or 1 <= parts.port <= 65535)
        )
    except (ValueError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise ValueError("project URL must be a bare HTTPS origin without userinfo, path, query or fragment")
    return url


def get(path, method="GET", headers=None, timeout=30):
    if method not in ("GET", "HEAD"):
        raise ValueError("read-only guard: only GET and HEAD are permitted")
    base_url = validate_project_url(URL)
    if (not isinstance(path, str) or not path.startswith("/") or path.startswith("//")
            or "\\" in path or "#" in path
            or any(c.isspace() or ord(c) < 32 for c in path)):
        raise ValueError("request path must be an absolute path on the configured origin")
    h = {"apikey": KEY, "Authorization": f"Bearer {KEY}", **(headers or {})}
    req = urllib.request.Request(base_url + path, method=method, headers=h)
    try:
        with urllib.request.build_opener(RejectRedirects()).open(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()
    except Exception:  # Transport errors can echo request headers/credentials.
        return -1, {}, b"request failed"

def main(argv=None):
    global URL, KEY
    argv = sys.argv[1:] if argv is None else argv
    OUT = pathlib.Path(argv[0]) if argv else ROOT / ".runtime" / "hosted_snapshot.json"
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    URL = validate_project_url(env["NEXT_PUBLIC_SUPABASE_URL"])
    KEY = env["SUPABASE_SERVICE_ROLE_KEY"]
    OUT.parent.mkdir(parents=True, exist_ok=True)

    snap = {"host_hint": URL.split("//")[1][:4] + "…" + URL.split(".")[-2] + "." + URL.split(".")[-1]}

    # 1. PostgREST OpenAPI: exposed tables, columns, rpc functions
    st, _, body = get("/rest/v1/", headers={"Accept": "application/openapi+json"})
    snap["openapi_status"] = st
    tables, rpcs = {}, []
    if st == 200:
        spec = json.loads(body)
        for name, d in spec.get("definitions", {}).items():
            cols = {}
            for c, p in d.get("properties", {}).items():
                cols[c] = {"type": p.get("type"), "format": p.get("format"), "default": p.get("default"),
                           "fk": "<fk" in (p.get("description") or "")}
            tables[name] = {"columns": cols, "required": d.get("required", [])}
        rpcs = sorted(p[len("/rpc/"):] for p in spec.get("paths", {}) if p.startswith("/rpc/"))
    snap["tables"] = tables
    snap["rpc_functions"] = rpcs

    # 2. Row COUNTS only (HEAD + Prefer: count=exact -> Content-Range, no body)
    counts = {}
    for t in sorted(tables):
        s, h, _ = get(f"/rest/v1/{t}?select=*", method="HEAD", headers={"Prefer": "count=exact"})
        cr = h.get("Content-Range") or h.get("content-range") or ""
        counts[t] = {"http": s, "count": cr.split("/")[-1] if "/" in cr else None}
    snap["row_counts"] = counts

    # 3. Storage buckets (config only)
    st, _, body = get("/storage/v1/bucket")
    snap["storage_status"] = st
    if st == 200:
        snap["buckets"] = [{k: b.get(k) for k in ("id", "name", "public", "file_size_limit", "allowed_mime_types", "created_at")} for b in json.loads(body)]

    # 4. What cannot be read through the public API surface: probe once each, read-only
    probes = {}
    s, _, b = get("/rest/v1/schema_migrations?select=version&limit=1", headers={"Accept-Profile": "supabase_migrations"})
    probes["supabase_migrations.schema_migrations via PostgREST"] = s
    for p in ("/pg/policies", "/pg/tables", "/pg/migrations"):
        s, _, _ = get(p)
        probes[f"GET {p} (postgres-meta)"] = s
    snap["catalog_probes_http_status"] = probes

    OUT.write_text(json.dumps(snap, indent=2, default=str), encoding="utf-8")
    print("tables:", len(tables), "| rpc fns:", len(rpcs), "| buckets:", len(snap.get("buckets", [])), "| openapi:", snap["openapi_status"], "| storage:", snap["storage_status"])
    print("catalog probes:", json.dumps(probes))
    print("non-zero tables:", sum(1 for v in counts.values() if v["count"] not in (None, "0")), "/", len(counts))


if __name__ == "__main__":
    main()
