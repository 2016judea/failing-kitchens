#!/usr/bin/env python3
"""Build round 1: the ledger and one draft per recipient. Nothing here sends anything.

Recipients: private/vendors_overture.json (HVAC-R, appliance repair, pest control; Overture Places,
CC BY 4.0) plus outreach/round1/hood_firms.json (hood cleaners, each email read off the firm's own
site, dated). Deduped against ~/Desktop/outreach-ledger/outreach.duckdb `contacted`.

Own-record opener: the flagged kitchen in the vendor's trade nearest their shop, inside the current
window (BUSINESS brief 2026-10-18). A vendor with no flagged kitchen in their trade this window is
`hold`. One A/B variable across all seven products: A states the price in the email, B leaves it to
the page. Assigned alternately within each segment so segments stay balanced.

    python3 outreach/build_round1.py            # writes outreach/round1/ledger.csv + drafts/<token>.txt
"""
import csv, hashlib, json, math, sys
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from trades import LABEL  # noqa: E402

R1 = ROOT / "outreach" / "round1"
OFFER = json.loads((ROOT / "site" / "offer.json").read_text())
SITE, PRICE = OFFER["site"], OFFER["price_usd"]
SUBSTACK = "https://randomaidan.substack.com/p/business-prototypes"
TARGET = {"refrigeration": 28, "pest": 15, "hood": 7}  # 50 across three segments; 7 is every MN hood cleaner with a printed email
TRADE_NOUN = {"refrigeration": "a cooler out of temp", "pest": "pests", "hood": "a dirty hood"}
TRADE_FEED = {"refrigeration": "refrigeration", "pest": "pest", "hood": "hood"}


def km(a, b, c, d):
    p = math.pi / 180
    x = 0.5 - math.cos((c - a) * p) / 2 + math.cos(a * p) * math.cos(c * p) * (1 - math.cos((d - b) * p)) / 2
    return 12742 * math.asin(math.sqrt(x))


def token(email):
    return hashlib.sha1(("failing-kitchens:" + email.lower()).encode()).hexdigest()[:10]


def short_defect(s, n=220):
    s = " ".join(s.split())
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(". ", 1)[0]
    return (cut if len(cut) > 60 else s[:n].rsplit(" ", 1)[0]) + ("" if cut.endswith(".") else "...")


def draft(r, variant):
    own = r["own"]
    feed = LABEL[r["segment"]].lower()
    n_free = 3
    price_line = f" The full {feed} feed, every flagged kitchen with its address, repeat count and what is still open, refreshed weekly, is ${PRICE}, once." if variant == "A" else ""
    body = f"""To: {r['email']}
Subject: bricks / {r['company']}

{own['name']} in {own['hood']} was flagged by the Minneapolis health inspector on {own['date_h']}{f", {own['mi']} miles from your shop" if own['mi'] is not None else ""}. The inspector wrote: "{own['defect']}"

In the last 30 days the city flagged {r['n_window']} kitchens for {TRADE_NOUN[r['segment']]}. {r['n_repeat']} of them had been flagged for the same thing before.

{n_free} of them are open to poke at, no login: {SITE}/for/{r['token']}/{price_line}

How this gets built: {SUBSTACK}

Aidan
Brick & Mortar
"""
    return body


def main():
    D = json.loads((ROOT / "private" / "rows.json").read_text())
    win = [f for f in D["rows"] if f["in_window"] and f.get("lat")]
    vendors = json.loads((ROOT / "private" / "vendors_overture.json").read_text())
    hood_path = R1 / "hood_firms.json"
    if hood_path.exists():
        for h in json.loads(hood_path.read_text()):
            vendors.append({**h, "trade": "hood", "category": "hood_cleaning"})
    con = duckdb.connect(str(Path.home() / "Desktop/outreach-ledger/outreach.duckdb"), read_only=True)
    contacted = {r[0].lower() for r in con.execute("select recipient_key from contacted").fetchall()}
    seen, rows = set(), []
    for v in vendors:
        email = (v.get("email") or "").lower().strip()
        if not email or "@" not in email or email in seen:
            continue
        seen.add(email)
        if (v.get("region") or "MN") != "MN":
            continue
        status, why = "drafted", ""
        if email in contacted:
            status, why = "hold", "already contacted (outreach.duckdb)"
        cands = [f for f in win if f["trade"] == v["trade"]]
        own = None
        if cands:
            if v.get("lat"):  # nearest flagged kitchen to the shop, Priority 1 first on a tie
                f = min(cands, key=lambda f: (km(v["lat"], v["lon"], f["lat"], f["lon"]), f["priority"] or 9))
                d = round(km(v["lat"], v["lon"], f["lat"], f["lon"]), 1)
            else:  # no shop address on record: the newest, most serious flag in the trade
                f = max(cands, key=lambda f: (f["date"], -(f["priority"] or 9)))
                d = None
            own = {"name": f["name"], "hood": f["hood"], "date": f["date"], "defect": short_defect(f["defect"]), "km": d, "id": f["id"],
                   "mi": round(d * 0.621, 1) if d is not None else None,
                   "date_h": __import__("datetime").date.fromisoformat(f["date"]).strftime("%B %-d")}
        elif status == "drafted":
            status, why = "hold", "no flagged kitchen in this trade in the window"
        rows.append({"token": token(email), "segment": v["trade"], "company": v["name"], "name": "", "email": email, "email_source": v["email_source"],
                     "email_source_date": v["email_source_date"], "own": own, "status": status, "hold_reason": why, "city": v.get("city") or "",
                     "n_window": D["kitchens"][v["trade"]], "n_repeat": len({f["fac"] for f in win if f["trade"] == v["trade"] and f["repeat"] > 0})})
    # cap each segment at its target, nearest-own-record first, then assign A/B alternately within the segment
    out = []
    for seg, cap in TARGET.items():
        ok = sorted([r for r in rows if r["segment"] == seg and r["status"] == "drafted"], key=lambda r: r["own"]["km"] if r["own"]["km"] is not None else 0)
        held = [r for r in rows if r["segment"] == seg and r["status"] != "drafted"]
        for i, r in enumerate(ok[:cap]):
            r["variant"] = "AB"[i % 2]
        for r in ok[cap:]:
            r["status"], r["hold_reason"], r["variant"] = "hold", "beyond round-1 cap for this segment", ""
        for r in held:
            r["variant"] = ""
        out += ok + held
    R1.mkdir(parents=True, exist_ok=True)
    (R1 / "drafts").mkdir(exist_ok=True)
    cols = ["token", "variant", "segment", "company", "name", "email", "email_source", "email_source_date", "own_record", "own_name", "own_hood", "own_date",
            "own_defect", "own_km", "own_flag_id", "city", "status", "hold_reason", "drafted_on", "sent_on", "reply_kind", "reply_on", "page_url"]
    today = __import__("datetime").date.today().isoformat()
    with (R1 / "ledger.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in out:
            o = r["own"] or {}
            w.writerow({"token": r["token"], "variant": r.get("variant", ""), "segment": r["segment"], "company": r["company"], "name": r["name"], "email": r["email"],
                        "email_source": r["email_source"], "email_source_date": r["email_source_date"],
                        "own_record": f"{o.get('name')} ({o.get('hood')}) flagged {o.get('date')}: {o.get('defect')}" if o else "",
                        "own_name": o.get("name", ""), "own_hood": o.get("hood", ""), "own_date": o.get("date", ""), "own_defect": o.get("defect", ""),
                        "own_km": o.get("km", ""), "own_flag_id": o.get("id", ""), "city": r["city"], "status": r["status"], "hold_reason": r["hold_reason"],
                        "drafted_on": today if r["status"] == "drafted" else "", "sent_on": "", "reply_kind": "", "reply_on": "",
                        "page_url": f"{SITE}/for/{r['token']}/" if r["status"] == "drafted" else ""})
            if r["status"] == "drafted":
                (R1 / "drafts" / f"{r['token']}.txt").write_text(draft(r, r["variant"]))
    from collections import Counter
    print("drafted", Counter((r["segment"], r["variant"]) for r in out if r["status"] == "drafted"))
    print("held", Counter((r["segment"], r["hold_reason"]) for r in out if r["status"] != "drafted"))


if __name__ == "__main__":
    main()
