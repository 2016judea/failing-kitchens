#!/usr/bin/env python3
"""Deploy site/ to Vercel production over the REST API (project: the "product" in site/offer.json).

    python3 scripts/deploy.py --setup   # create the project, env vars, analytics, public (idempotent)
    python3 scripts/deploy.py           # deploy site/ + private/bundle/ as api/_full/

Not the CLI: `vercel deploy --prod` has returned BLOCKED on this account with no error, while the
same files posted to /v13/deployments went READY. This polls readyState and exits non-zero on
anything but READY. Curl the live URL for a string only the new build contains afterwards.

Needs VERCEL_TOKEN; --setup also needs STRIPE_SECRET_KEY and MAILGUN_* (all in ~/Desktop/bricks/.env).
ACCESS_SECRET is generated once into .env (gitignored) and pushed to Vercel by --setup.
"""
import hashlib, json, os, secrets, sys, time, urllib.error, urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "site"
BUNDLE = REPO / "private" / "bundle"  # the paid feed: uploaded as api/_full/, read by /api/data only
OFFER = json.loads((ROOT / "offer.json").read_text())
PROJECT = OFFER["product"]
TEAM = "team_XnhPzBEcaSfEmZFo9M2isLFY"
API = "https://api.vercel.com"
SKIP_DIRS = {".git", "node_modules", ".vercel", "__pycache__"}
SKIP_FILES = {".env", ".DS_Store"}


def request(method, url, token, body=None, raw=None, headers=None):
    head = {"Authorization": f"Bearer {token}", **(headers or {})}
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    if body is not None:
        head["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=head, method=method)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(2 * (attempt + 1))
    sys.exit(f"network failed: {url}")


def env_file():
    p = REPO / ".env"
    kv = {}
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                kv[k.strip()] = v.strip()
    return p, kv


def setup(token):
    code, p = request("GET", f"{API}/v9/projects/{PROJECT}?teamId={TEAM}", token)
    if code == 404:
        code, p = request("POST", f"{API}/v10/projects?teamId={TEAM}", token, {"name": PROJECT, "framework": None})
        print("created project", code, p.get("id"))
    pid = p["id"]
    path, kv = env_file()
    if "ACCESS_SECRET" not in kv:
        kv["ACCESS_SECRET"] = secrets.token_hex(32)
        path.write_text("".join(f"{k}={v}\n" for k, v in kv.items()))
    env = {"STRIPE_SECRET_KEY": os.environ["STRIPE_SECRET_KEY"], "ACCESS_SECRET": kv["ACCESS_SECRET"], "SITE_URL": OFFER["site"],
           **{k: os.environ[k] for k in ("MAILGUN_API_KEY", "MAILGUN_DOMAIN", "MAILGUN_FROM")}}
    for k, v in env.items():
        c, out = request("POST", f"{API}/v10/projects/{pid}/env?teamId={TEAM}&upsert=true", token,
                         {"key": k, "value": v, "type": "encrypted", "target": ["production", "preview"]})
        print("env", k, c)
    print("analytics", request("POST", f"{API}/web/insights/toggle?projectId={pid}&teamId={TEAM}", token, {"value": True}))
    print("public", request("PATCH", f"{API}/v9/projects/{pid}?teamId={TEAM}", token, {"ssoProtection": None})[0])
    _, prj = request("GET", f"{API}/v9/projects/{PROJECT}?teamId={TEAM}", token)
    print("aliases", (prj.get("targets", {}).get("production") or {}).get("alias"))


def collect():
    assert (BUNDLE / "full.json.gz").exists(), "run scripts/publish.py: private/bundle/ is what the paywall serves"
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts) or rel.name in SKIP_FILES or "_full" in rel.parts:
            continue
        # Only public/ is served statically (outputDirectory). With "." every uploaded file was a
        # URL, the paid bundle included: /api/%5Ffull/full.json.gz answered 200 until 2026-10-19.
        if rel.parts[0] == "api" or rel.name == "vercel.json":
            yield rel, path
        else:
            yield Path("public") / rel, path
        if rel.name == "offer.json":
            yield rel, path  # api/_lib.js requires ../offer.json
    for path in sorted(BUNDLE.rglob("*")):
        if path.is_file():
            yield Path("api/_full") / path.relative_to(BUNDLE), path


def deploy(token):
    files, total = [], 0
    for rel, path in collect():
        body = path.read_bytes()
        sha = hashlib.sha1(body).hexdigest()
        code, out = request("POST", f"{API}/v2/files", token, raw=body,
                            headers={"Content-Type": "application/octet-stream", "x-vercel-digest": sha, "x-vercel-team-id": TEAM})
        if code >= 400:
            sys.exit(f"upload {rel} failed: {code} {out}")
        files.append({"file": str(rel), "sha": sha, "size": len(body)})
        total += len(body)
    print(f"  {len(files)} files, {total:,} bytes")
    code, out = request("POST", f"{API}/v13/deployments?teamId={TEAM}&skipAutoDetectionConfirmation=1", token, {
        "name": PROJECT, "project": PROJECT, "target": "production", "files": files,
        "projectSettings": {"framework": None, "buildCommand": "echo build", "outputDirectory": "public", "installCommand": "echo skip"}})
    if code >= 400 or out.get("error"):
        sys.exit(f"create failed: {code} {json.dumps(out.get('error'))}")
    url = out["url"]
    print(f"  deploying https://{url}")
    for _ in range(80):
        time.sleep(3)
        _, d = request("GET", f"{API}/v13/deployments/{url}?teamId={TEAM}", token)
        state = d.get("readyState")
        if state in ("READY", "ERROR", "BLOCKED", "CANCELED"):
            print(f"  {state} {d.get('errorMessage') or ''}")
            sys.exit(0 if state == "READY" else 1)
    sys.exit("timed out waiting for the deployment to settle")


if __name__ == "__main__":
    tok = os.environ.get("VERCEL_TOKEN") or sys.exit("VERCEL_TOKEN is not set")
    setup(tok) if "--setup" in sys.argv else deploy(tok)
