# Failing Kitchens — data model

Written 2026-10-18 from the need, before the pipeline existed (BUSINESS.md rule 5).
The customer is a trade that fixes kitchens: refrigeration / HVAC-R, pest control,
hood and duct cleaning. The step we take over: finding the kitchen that needs you
this week, from what the Minneapolis health inspector just wrote down.

## Entities

### Kitchen
One licensed food facility.

| field | answers | 
|---|---|
| `facility_id` | the city's licence id; the key every inspection hangs off |
| `name` | who to call |
| `address` | where to send the truck |
| `neighborhood` | is it in my service area |
| `category` | restaurant, grocery, school kitchen: what kind of equipment is inside |
| `risk_level` | how often the city comes back (risk 1 = most often) |
| `lat`, `lon` | the dot on the map; distance from the vendor's shop |

### Flag
One inspector finding that a trade can fix. The grain of the product.

| field | answers |
|---|---|
| `flag_id` | the city's violation id |
| `facility_id` | which kitchen |
| `trade` | who fixes it: `refrigeration`, `pest`, `hood` |
| `defect` | what the inspector saw, in the inspector's words |
| `rule` | the food-code item cited (proof it's a finding, not an opinion) |
| `priority` | P1 (imminent health risk) vs P2/P3: how urgent the fix is to the owner |
| `inspected_on` | when: "this week" is the whole pitch |
| `inspection_type` | routine, follow-up, complaint: was the city already back for this |
| `score` | the kitchen's inspection score that day: how much trouble it is in |
| `status` | observed vs corrected on site: still broken when the inspector left? |

### Repeat
Derived per kitchen and trade.

| field | answers |
|---|---|
| `repeat_count` | how many prior inspections flagged the same trade at this kitchen: a chronic cooler or pest problem is a contract, not a call |
| `last_flagged_before` | the previous time, for the recurrence rhythm |
| `follow_up_due` | whether a follow-up inspection is on the city's calendar: the owner has a deadline, which is when they buy |

### Vendor (distribution only; never on the page)

| field | answers |
|---|---|
| `name`, `email`, `email_source`, `email_source_date` | who we write to, and proof the address is real |
| `trade` | which feed is theirs |
| `lat`, `lon` | which flagged kitchen is nearest them: their own-record opener |

## Joins

- Kitchen 1→N Flag on `facility_id`.
- Flag N→1 Trade by text and rule classification (deterministic regex over `defect` + `rule`).
- Repeat is Flag grouped by (`facility_id`, `trade`) ordered by `inspected_on`.
- Vendor → Flag by `trade` and nearest `lat`/`lon` within the last 30 days.

## Free vs paid

Free: this month's count of flags per trade, and three flagged kitchens with
`name`, `neighborhood`, `defect`, `inspected_on`. Paid: every flag per trade with
`address`, `defect`, `rule`, `inspected_on`, `repeat_count`, `follow_up_due`,
refreshed weekly.

## Reality check (filled in after the first pull, 2026-10-18)

Source: City of Minneapolis Open Data, `Food_Inspections` FeatureServer/0,
one row per violation, 2023-01 to the week before last. Checked field by field:

| model field | source | status |
|---|---|---|
| facility_id, name, address, neighborhood, category, risk_level, lat/lon | `HealthFacilityIDNumber`, `BusinessName`, `FullAddress`, `Neighborhood`, `FacilityCategory`, `RiskLevel`, `Latitude/Longitude` | filled |
| flag_id, defect, rule, priority, inspected_on, inspection_type, score, status | `ViolationIDNumber`, `InspectorComments` + `FoodCodeText`, `FoodCodeItem`, `ViolationPriority`, `DateOfInspection`, `InspectionType`, `InspectionScore`, `ViolationStatus` | filled |
| trade | classified from `InspectorComments`, `FoodCodeText`, `FoodCodeItem` (pipeline/trades.py) | filled; a regex, so some flags are missed or misfiled. Hand-read of 60 rows per trade in `pipeline/trades.py` docstring |
| repeat_count, last_flagged_before | derived | filled |
| follow_up_due | **no field says a follow-up is scheduled.** `InspectionResult` only says Complete / Incomplete; the city does not publish the follow-up calendar. What CAN be read: whether a follow-up has already happened (`InspectionType = Follow-Up` at the same facility after the flag) and whether the flag was still `Observed` (not corrected on site). Shipped as `still_open`: a P1 observed and no later inspection on record. Named plainly on the page; not a schedule | **partly filled, reframed** |
| vendor email | Overture Places (CC BY 4.0) for HVAC-R and pest; hood cleaners hand-sourced from their own sites | filled for HVAC-R (173) and pest (45); hood cleaning had 0 emails in Overture, so each was read off the firm's site and dated |

**Note 2026-10-19 — "Priority 1 only" does not hold for two of three trades.** Of 2,236 routed
flags since 2025-01, Priority 1 is 487 of 1,253 refrigeration, 8 of 559 pest, 4 of 424 hood: the
city files most pest and hood findings as P2/P3. A P1-only feed would show a pest or hood vendor
almost nothing. Shipped: every flag a trade can fix, with `priority` on each row and P1 tagged
first on the page. `priority` stays the urgency field the model asked for; it is not a filter.
