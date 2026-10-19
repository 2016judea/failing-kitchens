# Failing Kitchens

**Live:** https://failing-kitchens.vercel.app

Minneapolis kitchens the health inspector just flagged for a cooler out of temp, pests or a
dirty hood, routed to the trade that fixes it: refrigeration / HVAC-R, pest control, hood and
exhaust cleaning. The step it takes over: finding the kitchen that needs you this week.

Every week the city posts its food-inspection violations as open data. This reads them, keeps
the ones a trade can fix, and shows each kitchen with the inspector's own words, whether the
problem is still open, and how many times it has been flagged before.

## Free and paid

Free, no login: the last 30 days' counts per trade, the map of every flagged kitchen, and three
flagged kitchens per trade (name, neighborhood, the inspector's words, date).

Paid: the full feed since January 2025, per trade, with the address, the rule cited, the repeat
count, whether it is still open, the inspection score, and the spreadsheet. Refreshed weekly
(`.github/workflows/weekly.yml`, Mondays 7am Central).

## Price

**$40, once.** Hypothesis, 2026-10-19. One use is one job won off the feed. A commercial
refrigeration service call, a hood cleaning or a pest-control start-up in the Twin Cities each
run on the order of $300 to $600 per visit (vendor quotes read 10/18; no public rate card
exists), so one won job is worth about $400 and a tenth of that is $40. Untested against a
buyer; revise on evidence (checkouts opened vs paid), never on vibes.

## How a flag is routed

`pipeline/trades.py`, deterministic regexes over the inspector's comment and the rule cited:

- **refrigeration**: a cooler, freezer, walk-in, prep unit or ice machine that is out of temp
  or in disrepair. Food left out on a counter or in an ice bath is not a service call.
- **pest**: evidence of pests (droppings, flies, roaches, mice) or a cited pest-control rule.
  "Seal the gap under the door" is prevention, not a call.
- **hood**: a hood, baffles, exhaust duct, grease build-up or fire suppression, including
  equipment that must move under a hood or a missing hood.

Fixed cases from real comments are in `tests/test_model.py`. `DATA_MODEL.md` has the ideal
model and what the city does not publish (the follow-up calendar: "still open" is what can be
read instead).

## Run it

    python3 pipeline/pull.py        # the city's layer since 2025-01-01 -> private/raw/
    python3 pipeline/build.py       # route, repeat counts, still-open -> private/rows.json
    python3 scripts/publish.py      # site/index.html (free slice) + private/bundle/full.json.gz
    python3 scripts/build_for.py    # one /for/<token>/ page per round-1 recipient
    python3 -m pytest -q tests      # tests/last_run.log
    VERCEL_TOKEN=... python3 scripts/deploy.py

## The paywall

Ported from `~/Desktop/mpls-new-rentals` (product-paywall skill). `site/` ships only the free
slice; `/api/data` serves `private/bundle/full.json.gz` (uploaded as `api/_full/`) to a
password. The password is minted at Stripe embedded Checkout (`POST /api/checkout`), rides in
the invoice footer, and is emailed by the shared Stripe router
(`~/Desktop/stripe-router`, product `failing-kitchens`) through `POST /api/stripe-webhook`.
`GET /api/session-status` is the return page's check. Comp password:
`python3 scripts/issue_password.py "comp:<label>"`. Lost password:
`python3 scripts/fulfil.py <session_id>`.

Vercel env: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `ACCESS_SECRET`, `MAILGUN_*`,
`SITE_URL`. Analytics: Vercel Web Analytics plus the shared B&M PostHog block; events
`preview_open`, `checkout_open`, `paid`, `unlock`, `download`, with `variant` on `/for/` pages.

## Distribution

Round 1 is drafted, not sent (`outreach/build_round1.py`; ledger and drafts are gitignored).
Three segments from Overture Places emails (HVAC-R + appliance repair, pest control) and hood
cleaners read off their own sites. Each recipient's `/for/<token>/` page opens on the flagged
kitchen in their trade nearest their shop. Subject line is `bricks / <their company>`.

One A/B variable, shared with the other six shelf products so results pool: **A** states the
price in the email, **B** leaves it to the page. Assigned alternately within each segment; the
variant rides in the page (`window.FOR.variant`), never the URL, and `preview_open` carries it.
Hypothesis: stating the price in the email lowers clicks but raises paid-per-click. Readout at
day 3: visits, `checkout_open`, `paid`, replies, by variant and pooled.

Source: City of Minneapolis Open Data, Food Inspections (public record). Minneapolis only.
Private repo: the paid feed is in the history.
