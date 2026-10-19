#!/usr/bin/env python3
"""Write site/index.html (the free slice) and private/bundle/full.json.gz (the paid feed) from
private/rows.json (pipeline/build.py). Every number on the page is computed here, never typed.

    python3 scripts/publish.py
"""
import json, datetime as dt, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
from sitekit import render  # noqa: E402
from trades import ORDER, LABEL  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# Paid: where it is, the repeat history, whether it is still open, the score. Free: who, where roughly, what, when.
PAID = ["addr", "zip", "repeat", "prev", "still_open", "score", "fac", "rule", "code_text", "insp_type", "risk", "status"]
FREE_PER_TRADE = 3
RIVER = [[45.052, -93.2885], [45.03, -93.2805], [45.012, -93.2745], [44.998, -93.2685], [44.988, -93.2625], [44.9815, -93.2575], [44.977, -93.2475], [44.972, -93.2385], [44.967, -93.2295], [44.962, -93.2225], [44.953, -93.2065], [44.946, -93.2005], [44.935, -93.2005], [44.917, -93.2035], [44.905, -93.1995], [44.889, -93.1935]]
LIGHT = '--bg:#f6f3ec;--panel:#ebe6dc;--ink:#171d1b;--ink2:#3a433f;--muted:#6b746f;--rule:#d6d0c4;--accent:#1d6b5e;--onaccent:#f6f3ec;--hot:#c8401f;--warm:#b07a1a;--ghost:#cfc8bb;--water:#8fb3b8;--tagbg:#e3ded3;--tagfg:#4b534f;--hotbg:#f6d9cf;--hotfg:#8f2d12;'
DARK = '--bg:#121715;--panel:#1b2220;--ink:#e9e6dd;--ink2:#c4c1b6;--muted:#8f978f;--rule:#2d3632;--accent:#6fc3b1;--onaccent:#121715;--hot:#f2855f;--warm:#e0a94a;--ghost:#3a443f;--water:#3f6a70;--tagbg:#242d2a;--tagfg:#b6bdb8;--hotbg:#4a2211;--hotfg:#f6b399;'
COLS = [("trade", "Trade", lambda r: LABEL[r["trade"]]), ("name", "Kitchen"), ("addr", "Address"), ("zip", "ZIP"), ("hood", "Neighborhood"), ("cat", "Facility type"),
        ("date", "Inspected"), ("insp_type", "Inspection type"), ("priority", "Priority (1 = most serious)"), ("rule", "Rule cited"), ("defect", "Inspector's words"),
        ("status", "Status at inspection"), ("still_open", "Still open (no inspection since)"), ("repeat", "Prior flags, same trade, since 2025"), ("prev", "Previous flag"), ("score", "Inspection score")]


def fmt(d):
    return dt.date.fromisoformat(d).strftime("%b %-d, %Y")


def main():
    D = json.loads((ROOT / "private" / "rows.json").read_text())
    rows = D["rows"]
    win = [r for r in rows if r["in_window"]]
    # the free sample: the newest FREE_PER_TRADE flags per trade inside the window, one per kitchen
    sample = []
    for t in ORDER:
        seen = set()
        for r in win:
            if r["trade"] == t and r["fac"] not in seen:
                sample.append(r); seen.add(r["fac"])
            if len(seen) == FREE_PER_TRADE:
                break
    still = sum(r["still_open"] for r in win)
    rep = sum(r["repeat"] > 0 for r in win)
    kitchens = len({r["fac"] for r in win})
    cols_js = "[" + ",".join(f'["{c[0]}","{c[1]}"' + (f',r=>({{"refrigeration":"{LABEL["refrigeration"]}","pest":"{LABEL["pest"]}","hood":"{LABEL["hood"]}"}})[r.trade]' if len(c) == 3 else "") + "]" for c in COLS) + "]"
    cfg = """{chipKey:"trade",chipOrder:%s,labels:%s,river:%s,csv:"failing-kitchens.csv",cols:%s,
 stats:[["%d","flags at %d kitchens, %s to %s",""],["%d","still open: seen, not fixed on site, no inspection since","hot"],["%d","flagged before for the same trade","rep"]],
 history:%d,
 legend:[["var(--accent)","%s"],["var(--hot)","%s"],["var(--warm)","%s"]],
 dotColor:["var(--accent)","var(--hot)","var(--warm)"],
 title:r=>r.name, what:r=>r.defect,
 tag:r=>`<span class="tag ${r.priority===1?"p1":""}">${r.priority===1?"Priority 1 · ":""}${CFG.labels[r.trade]}</span>`,
 meta:r=>[`<span>${esc(r.hood)}</span>`,`<span>${esc(r.cat)}</span>`,`<span>Inspected ${fmt(r.date)}</span>`,r.still_open?`<span class="open">Still open</span>`:"",r.repeat?`<span class="rep">Flagged ${r.repeat} time${r.repeat===1?"":"s"} before</span>`:""],
 paid:r=>[`${esc(r.addr)}, Minneapolis ${esc(r.zip)}`,r.prev?`Last flagged ${fmt(r.prev)}`:"First flag for this trade since 2025",r.score!=null?`Score ${r.score}`:"",`${esc(r.insp_type)} inspection`].filter(Boolean).join(" · "),
 sorts:[["newest","Newest first",false],["open","Still open first",true],["repeat","Repeat problems first",true],["hood","By neighborhood",false]],
 sortFn:{newest:r=>r.sort((a,b)=>b.date.localeCompare(a.date)||(a.priority||9)-(b.priority||9)),open:r=>r.sort((a,b)=>(b.still_open?1:0)-(a.still_open?1:0)||b.date.localeCompare(a.date)),repeat:r=>r.sort((a,b)=>b.repeat-a.repeat||b.date.localeCompare(a.date)),hood:r=>r.sort((a,b)=>a.hood.localeCompare(b.hood)||b.date.localeCompare(a.date))},
 lockText:(n,g)=>`${n} more flags${g?" for "+CFG.labels[g].toLowerCase():""} in these 30 days, and every flag since January 2025 (${CFG.history.toLocaleString("en-US")}), with addresses, repeat counts and what is still open`}""" % (
        json.dumps(ORDER), json.dumps(LABEL), json.dumps(RIVER), cols_js,
        len(win), kitchens, fmt(D["window_from"]), fmt(D["latest"]), still, rep, len(rows),
        LABEL["refrigeration"], LABEL["pest"], LABEL["hood"])
    counts_line = ", ".join(f"<b>{D['counts'][t]}</b> for {LABEL[t].lower()}" for t in ORDER)
    free = render(rows=rows, sample=sample, paid_fields=PAID, chip_key="trade", chip_order=ORDER, cfg_js=cfg, site="failing-kitchens", window_rows=win,
                  extra={"window": {"from": D["window_from"], "to": D["latest"], "counts": D["counts"], "kitchens": D["kitchens"]}},
                  subs={
        "__TITLE__": "Failing Kitchens",
        "__DESC__": f"{kitchens} Minneapolis kitchens the health inspector flagged in the last {D['window_days']} days for a cooler out of temp, pests or a dirty hood, routed to the trade that fixes it.",
        "__LIGHT__": LIGHT, "__DARK__": DARK,
        "__EYEBROW__": f"For refrigeration, pest control and hood cleaning trades · Minneapolis health inspections · updated {fmt(D['pulled'])}",
        "__H1__": f"{kitchens} Minneapolis kitchens just failed on something you fix",
        "__LEDE__": f"Every week the city's health inspectors write down what is broken in a kitchen. In the {D['window_days']} days to {fmt(D['latest'])} they flagged {counts_line}. Each one is a kitchen with a deadline and no one to call yet.",
        "__NOTE__": f"<p>Source, all public: City of Minneapolis Open Data, food inspection violations, pulled {fmt(D['pulled'])}; the newest inspection on record is {fmt(D['latest'])}. The city posts inspections a few days after they happen. The feed starts January 1, 2025 ({len(rows)} flags at {len({r['fac'] for r in rows})} kitchens).</p><p>How a flag is routed. A violation goes to refrigeration when the inspector names a cooler, freezer, walk-in or prep unit that is out of temp or in disrepair, not food left out on a counter. It goes to pest control on evidence of pests (droppings, flies, roaches, mice) or a pest-control rule. It goes to hood cleaning for a hood, baffles, exhaust duct, grease build-up or fire suppression. The routing is a fixed set of word rules, so a few flags are missed or misfiled; the inspector's words are shown so you can judge.</p><p>\"Still open\" means the inspector marked it observed (not corrected on site) and the city has not inspected that kitchen since. The city does not publish when the follow-up is scheduled. \"Flagged before\" counts earlier inspections since 2025 that flagged the same trade at the same kitchen.</p><p>Minneapolis only. From Aidan Jude at Brick &amp; Mortar (aidan@brickandmortar.dev).</p>"})
    print("rows", len(rows), "window", D["counts"], "kitchens", kitchens, "still", still, "repeat", rep, "sample", len(sample), "free counts", free["counts"])


if __name__ == "__main__":
    main()
