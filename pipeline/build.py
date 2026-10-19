#!/usr/bin/env python3
"""Turn private/raw/violations.json into private/rows.json: one row per flag a trade can fix,
with the kitchen, the inspector's words, the repeat count and whether it is still open.

    python3 pipeline/build.py

Every number the page shows is computed from this file by scripts/publish.py.
"""
import json, sys, datetime as dt
from zoneinfo import ZoneInfo
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trades import trade_of, ORDER  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "private" / "raw" / "violations.json"
OUT = ROOT / "private" / "rows.json"
WINDOW_DAYS = 30


CITY_TZ = ZoneInfo("America/Chicago")


def day(ms):
    """The inspection's calendar day in Minneapolis. The layer stores an instant; read as
    UTC, an inspection after 7pm CDT lands on the next day."""
    return dt.datetime.fromtimestamp(ms / 1000, CITY_TZ).date()


def title(s):
    s = (s or "").strip()
    small = {"of", "and", "the", "at", "on", "in", "by", "for", "a", "an", "&", "llc", "inc", "co"}
    out = []
    for i, w in enumerate(s.lower().split()):
        if w in ("llc", "inc", "inc.", "llc."):
            out.append(w.upper().rstrip("."))
        elif w in small and i:
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


def build(raw):
    rows = raw["rows"]
    by_fac = defaultdict(list)
    for r in rows:
        if r.get("DateOfInspection"):
            by_fac[r["HealthFacilityIDNumber"]].append(r)
    latest = max(day(r["DateOfInspection"]) for r in rows if r.get("DateOfInspection"))
    window_from = latest - dt.timedelta(days=WINDOW_DAYS - 1)
    flags = []
    for fac, vs in by_fac.items():
        last_insp = max(day(v["DateOfInspection"]) for v in vs)
        hist = defaultdict(list)  # trade -> sorted inspection dates that flagged it
        tagged = []
        for v in vs:
            t = trade_of(v.get("FoodCodeItem"), v.get("InspectorComments"))
            if t:
                d = day(v["DateOfInspection"])
                hist[t].append(d)
                tagged.append((t, d, v))
        for t in hist:
            hist[t] = sorted(set(hist[t]))
        for t, d, v in tagged:
            prior = [x for x in hist[t] if x < d]
            flags.append({
                "id": v["ViolationIDNumber"] or v["OBJECTID"],
                "fac": fac,
                "trade": t,
                "name": title(v["BusinessName"]),
                "addr": title(v["FullAddress"]),
                "hood": v.get("Neighborhood") or "",
                "zip": v.get("ZipCode") or "",
                "cat": title(v.get("FacilityCategory")),
                "risk": v.get("RiskLevel"),
                "lat": v.get("Latitude"), "lon": v.get("Longitude"),
                "date": d.isoformat(),
                "insp_type": v.get("InspectionType"),
                "priority": {"Priority1": 1, "Priority2": 2, "Priority3": 3}.get(v.get("ViolationPriority")),
                "rule": v.get("FoodCodeItem") or "",
                "code_text": (v.get("FoodCodeText") or "").strip(),
                "defect": (v.get("InspectorComments") or v.get("FoodCodeText") or "").strip(),
                "status": v.get("ViolationStatus") or "",
                "score": v.get("InspectionScore"),
                "repeat": len(prior),
                "prev": prior[-1].isoformat() if prior else None,
                # still open: the inspector saw it (not corrected on site) and the city has not been back since
                "still_open": (v.get("ViolationStatus") == "Observed") and d == last_insp,
                "in_window": d >= window_from,
            })
    flags.sort(key=lambda f: (f["date"], f["priority"] or 9, f["name"]), reverse=True)
    counts = {t: sum(f["trade"] == t and f["in_window"] for f in flags) for t in ORDER}
    kitchens = {t: len({f["fac"] for f in flags if f["trade"] == t and f["in_window"]}) for t in ORDER}
    return {"pulled": raw["pulled"], "since": raw["since"], "latest": latest.isoformat(), "window_from": window_from.isoformat(),
            "window_days": WINDOW_DAYS, "counts": counts, "kitchens": kitchens, "rows": flags}


if __name__ == "__main__":
    out = build(json.loads(RAW.read_text()))
    OUT.write_text(json.dumps(out))
    print(f"{len(out['rows'])} flags since {out['since']}, latest {out['latest']}; last {WINDOW_DAYS} days: {out['counts']} flags at {out['kitchens']} kitchens")
