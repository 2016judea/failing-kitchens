#!/usr/bin/env python3
"""Write one /for/<token>/ page per sendable row in outreach/round1/ledger.csv.

Each page is site/index.html with the vendor's own record pinned on top: the flagged kitchen in
their trade nearest their shop, inside the current window (`own_record`, `own_name`, `own_hood`,
`own_date`, `own_defect`, `own_km`), their trade chip pre-selected, and the A/B `variant` carried
in the page (never the URL) so preview_open and checkout_open split by variant. The token sits in
the PATH because Vercel analytics drops ?query and #hash. The pages carry a company name and a
public inspection record, nothing personal; site/for/ is committed so the weekly GitHub Action can
redeploy them. Run after scripts/publish.py, before deploy.

    python3 scripts/build_for.py
"""
import csv, html, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "outreach/round1/ledger.csv"
OUT = ROOT / "site/for"


def main():
    page = (ROOT / "site/index.html").read_text()
    shutil.rmtree(OUT, ignore_errors=True)
    n = 0
    if not LEDGER.exists():
        print("no ledger; 0 pages")
        return
    for r in csv.DictReader(LEDGER.open()):
        if r["status"] not in ("drafted", "sent", "scheduled"):
            continue
        me = {"token": r["token"], "trade": r["segment"], "variant": r["variant"], "company": r["company"],
              "own": {"name": r["own_name"], "hood": r["own_hood"], "date": r["own_date"], "defect": r["own_defect"],
                      "km": (round(float(r["own_km"]) * 0.621, 1) if r.get("own_km") else None)}}
        blob = json.dumps(me, ensure_ascii=False).replace("</", "<\\/")
        out = page.replace("<head>", '<head>\n<meta name="robots" content="noindex">', 1)
        out = out.replace("<body>", f"<body>\n<script>window.FOR={blob};</script>", 1)
        out = out.replace("<title>", f"<title>For {html.escape(r['company'])} · ", 1)
        d = OUT / r["token"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(out)
        n += 1
    print(f"{n} pages in {OUT}")


if __name__ == "__main__":
    main()
