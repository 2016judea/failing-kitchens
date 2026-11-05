"""Render site/index.html from template.html with the free slice written in, and gzip the full
feed for /api/data (private/bundle/full.json.gz, uploaded by scripts/deploy.py as api/_full/).

The free slice is: the sample rows with the paid fields stripped, every flag's dot on the map
(rounded to ~100 m), and the counts. Nothing else of the feed ever lands in site/.
Ported from ~/Desktop/workspace/mpls-new-rentals/scripts/sitekit.py (product-paywall skill).
"""
import gzip, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE, BUNDLE = ROOT / "site", ROOT / "private" / "bundle"
dump = lambda o: json.dumps(o, separators=(",", ":"), ensure_ascii=False)


def analytics(site):
    # The shared B&M PostHog block (source of truth: ~/.claude/skills/site-analytics/posthog_snippet.html),
    # vendored here so the weekly GitHub Action can render the page without the skills folder.
    ph = (Path(__file__).resolve().parent / "posthog_snippet.html").read_text().replace("__SITE__", site)
    reader = (Path(__file__).resolve().parent / "reader_events.js").read_text().strip()
    return ph + "<script>" + reader + "</script>"


def free_slice(rows, sample, paid_fields, chip_key, chip_order, extra=None, window_rows=None):
    """Counts and dots describe `window_rows` (what is new) when given; the sample must sit inside them."""
    scope = window_rows if window_rows is not None else rows
    for r in sample:
        assert r in scope and r in rows
    free_rows = [{k: v for k, v in r.items() if k not in paid_fields} for r in sample]
    counts = {g: sum(r[chip_key] == g for r in scope) for g in chip_order}
    dots = [[round(r["lat"], 3), round(r["lon"], 3), chip_order.index(r[chip_key])] for r in scope if r.get("lat")]
    leak = [f for f in paid_fields if any(r.get(f) for r in free_rows)]
    assert not leak, leak
    return {"rows": free_rows, "counts": counts, "total": len(scope), "dots": dots, **(extra or {})}


def render(*, rows, sample, paid_fields, chip_key, chip_order, cfg_js, subs, site, extra=None, template=None, out=None, window_rows=None):
    free = free_slice(rows, sample, paid_fields, chip_key, chip_order, extra, window_rows)
    h = (template or Path(__file__).resolve().parent / "template.html").read_text()
    for k, v in subs.items():
        h = h.replace(k, v)
    h = h.replace("__ANALYTICS__", analytics(site)).replace("__CFG__", cfg_js).replace("__FREE__", dump(free))
    head = h.split('<script src="/paywall.js">')[0]
    assert "__" not in head.replace("__SV", "").replace("__proto__", ""), "unfilled token"
    (out or SITE / "index.html").write_text(h)
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / "full.json.gz").write_bytes(gzip.compress(dump({"rows": rows}).encode(), 9))
    return free
