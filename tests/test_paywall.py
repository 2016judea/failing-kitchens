"""The paywall split and the API's 401 path. The free slice must never carry a paid field; /api/data
must refuse without a password; a comp password (HMAC, "comp:" domain) must unlock the bundle."""
import gzip, hashlib, hmac, json, os, re, subprocess, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from sitekit import free_slice  # noqa: E402

ROWS = [{"id": i, "fac": f"L{i % 3}", "trade": ["refrigeration", "pest", "hood"][i % 3], "name": f"K{i}", "addr": f"{i} Main St", "zip": "55401",
         "hood": "Whittier", "cat": "Restaurant", "date": "2026-10-01", "defect": "x", "priority": 1, "lat": 44.9 + i / 1000, "lon": -93.2,
         "repeat": i, "prev": "2026-01-01", "still_open": True, "score": 90, "in_window": True, "rule": "r", "code_text": "c", "insp_type": "Routine", "risk": "1", "status": "Observed"} for i in range(9)]
PAID = ["addr", "zip", "repeat", "prev", "still_open", "score", "fac", "rule", "code_text", "insp_type", "risk", "status"]
ORDER = ["refrigeration", "pest", "hood"]


def test_free_slice_strips_every_paid_field_and_keeps_counts():
    free = free_slice(ROWS, ROWS[:3], PAID, "trade", ORDER)
    assert len(free["rows"]) == 3 and free["total"] == 9 and free["counts"] == {"refrigeration": 3, "pest": 3, "hood": 3}
    for r in free["rows"]:
        assert not (set(r) & set(PAID)), r
        assert {"name", "hood", "defect", "date", "trade"} <= set(r)
    assert len(free["dots"]) == 9 and all(len(d) == 3 for d in free["dots"])


def test_free_slice_refuses_a_sample_outside_rows():
    with pytest.raises(AssertionError):
        free_slice(ROWS, [dict(ROWS[0], id=999)], PAID, "trade", ORDER)


def test_published_page_carries_no_paid_field_and_the_analytics_tags():
    page = ROOT / "site" / "index.html"
    if not page.exists():
        pytest.skip("site/index.html not built")
    h = page.read_text()
    free = json.loads(re.search(r"const FREE=(\{.*?\});\nconst FOR", h, re.S).group(1))
    for r in free["rows"]:
        assert not (set(r) & set(PAID)), r
    assert "/_vercel/insights/script.js" in h and "bm-posthog:begin" in h
    assert "__" not in h.split('<script src="/paywall.js">')[0].replace("__SV", "")
    # every number in the stats derives from the data: the kitchens stat equals the distinct kitchens in the window
    bundle = ROOT / "private" / "bundle" / "full.json.gz"
    if bundle.exists():
        full = json.loads(gzip.decompress(bundle.read_bytes()))["rows"]
        kitchens = len({r["fac"] for r in full if r["in_window"]})
        flags = sum(r["in_window"] for r in full)
        assert f'["{flags}","flags at {kitchens} kitchens' in h


# ---- the API, driven with a fake req/res in node (no Vercel CLI on this Mac) ----
ALPHA = "23456789BCDFGHJKMNPQRSTVWXYZ"
SECRET = "test-secret"


def comp_password(label="comp:test"):
    s = SECRET.encode()
    chars = lambda b, n: "".join(ALPHA[x % len(ALPHA)] for x in b[:n])
    nonce = chars(hmac.new(s, ("label:" + label).encode(), hashlib.sha256).digest(), 5)
    raw = nonce + chars(hmac.new(s, ("comp:" + nonce).encode(), hashlib.sha256).digest(), 7)
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def run_data(tmp_path, headers):
    full_dir = tmp_path / "_full"
    full_dir.mkdir(exist_ok=True)
    (full_dir / "full.json.gz").write_bytes(gzip.compress(json.dumps({"rows": ROWS}).encode()))
    js = f"""
    const h = require({json.dumps(str(ROOT / 'site/api/data.js'))});
    const req = {{ headers: {json.dumps(headers)}, query: {{}} }};
    let status = 0, hdrs = {{}}, body = null;
    const res = {{ status(s) {{ status = s; return res; }}, setHeader(k, v) {{ hdrs[k] = v; }}, json(o) {{ body = JSON.stringify(o); return res; }}, end(b) {{ body = b; return res; }} }};
    h(req, res).then(() => {{ process.stdout.write(JSON.stringify({{ status, hdrs, body: Buffer.isBuffer(body) ? require('zlib').gunzipSync(body).toString() : body }})); }});
    """
    env = dict(os.environ, ACCESS_SECRET=SECRET, FULL_DIR=str(full_dir), STRIPE_SECRET_KEY="sk_test_unused")
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, env=env, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])  # data.js logs "[unlock] ..." first


def test_api_data_401_without_password(tmp_path):
    r = run_data(tmp_path, {})
    assert r["status"] == 401 and "password" in json.loads(r["body"])["error"].lower()


def test_api_data_401_with_a_made_up_password(tmp_path):
    r = run_data(tmp_path, {"x-password": "ABCD-EFGH-JKLM"})
    assert r["status"] == 401


def test_api_data_comp_password_unlocks_the_full_rows(tmp_path):
    r = run_data(tmp_path, {"x-password": comp_password()})
    assert r["status"] == 200 and r["hdrs"]["X-Access"] == "comp" and r["hdrs"]["Cache-Control"] == "private, no-store"
    rows = json.loads(r["body"])["rows"]
    assert len(rows) == 9 and rows[0]["addr"] == "0 Main St"


def test_checkout_rejects_get():
    js = f"""
    const h = require({json.dumps(str(ROOT / 'site/api/checkout.js'))});
    let status = 0; const res = {{ status(s) {{ status = s; return res; }}, json(o) {{ process.stdout.write(String(status)); return res; }} }};
    h({{ method: 'GET', headers: {{}} }}, res);
    """
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30, env=dict(os.environ, STRIPE_SECRET_KEY="sk_test_unused", ACCESS_SECRET=SECRET))
    assert out.stdout.strip() == "405", out.stderr


def test_offer_is_one_plain_price():
    o = json.loads((ROOT / "site/offer.json").read_text())
    assert o["product"] == "failing-kitchens" and isinstance(o["price_usd"], int) and o["price_usd"] > 0
    assert f"${o['price_usd']}, once" in o["line"]
    for word in ("discount", "sale", "limited", "bundle", "%"):
        assert word not in o["line"].lower()
