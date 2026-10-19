"""The model loader and the trade routing. Fixed cases are real inspector comments read on 2026-10-18."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
from trades import trade_of, ORDER, LABEL  # noqa: E402
from build import build  # noqa: E402

CASES = [
    ("MN Rule 4626.0395A2", "Observed 3 door prep cooler above 41 degrees (see temps above). Have unit serviced to ensure food is at or below 41 degrees.", "refrigeration"),
    ("MN Rule 4626.0395A2", "Observed several TCS foods in the walk-in cooler had temps above 41°F (chicken 44°F); the Manager on Duty was informed that the cooler is not holding.", "refrigeration"),
    ("MN Rule 4626.0735AB", "2 door prep cooler is not maintaining temperature at or below 41 degrees. Repair or replace. Observed broken gasket on 2 door prep cooler.", "refrigeration"),
    # food left out is a kitchen habit, not a service call
    ("MN Rule 4626.0395A2", "Observed cut watermelon in an ice bath holding at 54F. All TCS foods must be kept at 41F or below.", None),
    ("MN Rule 4626.0395A2", "Butter was observed being cold held at 72F room temperature at the time of inspection.", None),
    ("MN Rule 4626.1565ABD", "Observed several drain flies by mop sink in back room. Notify pest control company.", "pest"),
    ("MN Rule 4626.1520A", "Observed mouse droppings on floor in dry storage room. Clean and maintain.", "pest"),
    ("MCO 188.590", "OBSERVED FRUIT / DRAIN FLIES IN THE KITCHEN. OBSERVED ONE COCKROACH BY THE 3-COMP SINK.", "pest"),
    # 'designated' is not a gnat; 'restaurants' are not ants; sealing a door gap is prevention
    ("MN Rule 4626.1560B", "Store all personal items in the separate designated place away from food.", None),
    ("MN Rule 4626.0025", "A designated PIC needs to be on site to respond to restaurant/food safety issues.", None),
    ("MN Rule 4626.1395A", "Observed large gap under back door. Ensure outer openings are sealed from pest entry.", None),
    ("MN Rule 4626.1530A", "Observed hood baffles heavily greased. Clean and maintain.", "hood"),
    ("MN Rule 4626.0565", "OBSERVED GREASE DROPS HANGING FROM KITCHEN HOOD. CLEAN KITCHEN HOOD AS NEEDED.", "hood"),
    ("MN Rule 4626.1475A", "Observed cooking on a hotplate in the basement prep room without a hood.", "hood"),
    # a cooler across from the hood is a cooler; an ice machine baffle is not a hood baffle
    ("MN Rule 4626.0395A2", "Tandoori Chicken measured at 43 F in the middle prep cooler across from the hood. The cooler is to be adjusted.", "refrigeration"),
    ("MN Rule 4626.0845E", "Baffle of ice machine contains a large amount of microbial growth. Clean and maintain.", None),
    # read 2026-10-19: grease on a floor or a cooler handle, a dish machine hood, a plan-review aside
    ("MN Rule 4626.0855", "Observed some grease buildup on handles of coolers. Clean and maintain clean.", None),
    ("MN Rule 4626.1520A", "Deep clean the following areas: -The floors near the downstairs hood with a stain/build up.", None),
    ("MN Rule 4626.1530A", "Observed inside of dish machine hood dusty.    Clean and maintain.", None),
    ("MN Rule 4626.1720A", "OBSERVED NEWLY INSTALLED ICE MACHINE. SUBMIT FOOD PLANS. NOTE: IF YOU ARE PLANNING ON MAKING MORE CHANGES TO THE RESTAURANT (E.G: HOOD, DISHWASHER, ETC.) SUBMIT ALL CHANGES IN ONE FOOD PLAN REVIEW APPLICATION.", None),
    ("MN Rule 4626.1475D", "Hood system in the outdoor kitchen is missing a section of hood filters. Ensure all filters are in place.", "hood"),
    ("MN Rule 4626.1530A", "Observed the warewash ductwork above the machine very dirty and in need of cleaning.", "hood"),
    ("MN Rule 4626.1395D", "Observed unscreened doors in back of kitchen left open for ventilation. Screening needs to be provided.", None),
    ("MN Rule 4626.1040B", "The water leakage around the base of the mop sink still not fixed.", None),
]


def test_routing_cases():
    bad = [(c, got, want) for code, c, want in CASES if (got := trade_of(code, c)) != want]
    assert not bad, bad


def test_labels_cover_every_trade():
    assert set(LABEL) == set(ORDER) == {"refrigeration", "pest", "hood"}


def test_build_from_raw_fixture():
    raw = {"pulled": "2026-10-18", "since": "2025-01-01", "rows": [
        {"OBJECTID": 1, "HealthFacilityIDNumber": "LIC1", "BusinessName": "TEST KITCHEN LLC", "FullAddress": "1 MAIN ST", "Neighborhood": "Whittier",
         "FacilityCategory": "RESTAURANT", "RiskLevel": "1", "Latitude": 44.95, "Longitude": -93.27, "DateOfInspection": 1757000000000,
         "InspectionType": "Routine", "ViolationPriority": "Priority1", "FoodCodeItem": "MN Rule 4626.0395A2", "FoodCodeText": "Keep cold.",
         "InspectorComments": "Walk-in cooler not holding; food at 48F. Have unit serviced.", "ViolationStatus": "Observed", "InspectionScore": 80, "ViolationIDNumber": 11, "ZipCode": "55408"},
        {"OBJECTID": 2, "HealthFacilityIDNumber": "LIC1", "BusinessName": "TEST KITCHEN LLC", "FullAddress": "1 MAIN ST", "Neighborhood": "Whittier",
         "FacilityCategory": "RESTAURANT", "RiskLevel": "1", "Latitude": 44.95, "Longitude": -93.27, "DateOfInspection": 1760000000000,
         "InspectionType": "Follow-Up", "ViolationPriority": "Priority1", "FoodCodeItem": "MN Rule 4626.0395A2", "FoodCodeText": "Keep cold.",
         "InspectorComments": "Reach-in cooler still not holding; ambient 47F. Repair.", "ViolationStatus": "Observed", "InspectionScore": 85, "ViolationIDNumber": 12, "ZipCode": "55408"},
        {"OBJECTID": 3, "HealthFacilityIDNumber": "LIC2", "BusinessName": "OTHER PLACE", "FullAddress": "2 OAK AVE", "Neighborhood": "Seward",
         "FacilityCategory": "GROCERY", "RiskLevel": "2", "Latitude": 44.96, "Longitude": -93.23, "DateOfInspection": 1760000000000,
         "InspectionType": "Routine", "ViolationPriority": "Priority3", "FoodCodeItem": "MN Rule 4626.1520A", "FoodCodeText": "Clean.",
         "InspectorComments": "Clean the floor.", "ViolationStatus": "Corrected on-site", "InspectionScore": 95, "ViolationIDNumber": 13, "ZipCode": "55406"},
    ]}
    out = build(raw)
    rows = out["rows"]
    assert len(rows) == 2 and {r["trade"] for r in rows} == {"refrigeration"}
    newest = rows[0]
    assert newest["repeat"] == 1 and newest["prev"] == "2025-09-04" and newest["still_open"] is True and newest["in_window"] is True
    assert rows[1]["repeat"] == 0 and rows[1]["still_open"] is False and rows[1]["in_window"] is False
    assert newest["name"] == "Test Kitchen LLC" and newest["addr"] == "1 Main St"
    assert out["counts"] == {"refrigeration": 1, "pest": 0, "hood": 0} and out["kitchens"]["refrigeration"] == 1
