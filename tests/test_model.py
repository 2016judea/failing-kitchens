"""Fixed cases for the trade classifier and the flag builder. No network, no private/ data.

    python3 -m pytest tests
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
from trades import trade_of  # noqa: E402
from build import build, day  # noqa: E402


def test_pest_needs_a_pest_word_not_a_word_ending_in_ants():
    # all three are real comments from the 2026-10-18 pull that were filed as pest
    assert trade_of("MN Rule 4626.0405A", "Food in the walk-in past 7 days: croissants (10/1) and pico (10/3).") is None
    assert trade_of("MN Rule 4626.0395A2", "Eggplants (65*F) on ice at the dimsum station above 41*F.") is None
    assert trade_of("MN Rule 4626.0408A", "Salsa in an ice bucket. Either use refrigeration or time as a public health control for restaurants.") is None
    assert trade_of("MN Rule 4626.0130A", "Observed ants along the back wall by the dish machine.") == "pest"
    assert trade_of("MN Rule 4626.0130A", "Observed an ant trail near the dry storage.") == "pest"
    assert trade_of("MN Rule 4626.1565ABD", "") == "pest"


def test_hood_and_refrigeration_rules():
    assert trade_of("MN Rule 4626.1530A", "") == "hood"
    assert trade_of("MN Rule 4626.0130A", "Heavy grease build-up on the hood baffles.") == "hood"
    assert trade_of("MN Rule 4626.0395A2", "Walk-in cooler holding at 48 F ambient. Have the unit serviced.") == "refrigeration"
    assert trade_of("MN Rule 4626.0395A2", "Cut melon sitting out on the counter at 55 F.") is None


def _ms(iso):
    import datetime as dt
    return int(dt.datetime.fromisoformat(iso).timestamp() * 1000)


def test_an_evening_inspection_keeps_its_minneapolis_date():
    # 2026-10-15 20:30 CDT is 2026-10-16 01:30 UTC
    assert day(_ms("2026-10-16T01:30:00+00:00")).isoformat() == "2026-10-15"
    assert day(_ms("2026-10-15T14:00:00+00:00")).isoformat() == "2026-10-15"


def _row(oid, fac, date_iso, comment="Mouse droppings in dry storage.", code="MN Rule 4626.1565ABD", status="Observed", vid=None):
    return {"OBJECTID": oid, "ViolationIDNumber": vid if vid is not None else oid, "HealthFacilityIDNumber": fac, "BusinessName": "PHO PLACE LLC",
            "FullAddress": "1 MAIN ST", "DateOfInspection": _ms(date_iso), "FoodCodeItem": code, "InspectorComments": comment,
            "ViolationStatus": status, "ViolationPriority": "Priority1", "InspectionType": "Routine"}


def test_repeat_count_still_open_and_window():
    raw = {"pulled": "2026-10-18", "since": "2025-01-01", "rows": [
        _row(1, "A", "2026-03-10T15:00:00+00:00"),
        _row(2, "A", "2026-10-15T15:00:00+00:00"),
        _row(3, "B", "2026-10-14T15:00:00+00:00"),
        # B was visited again later with no violation: its flag is no longer open
        {**_row(4, "B", "2026-10-16T15:00:00+00:00", comment=None, code=None, status=None), "ViolationPriority": None},
    ]}
    out = build(raw)
    a_new = next(f for f in out["rows"] if f["id"] == 2)
    a_old = next(f for f in out["rows"] if f["id"] == 1)
    b = next(f for f in out["rows"] if f["id"] == 3)
    assert (a_new["repeat"], a_new["prev"], a_new["still_open"]) == (1, "2026-03-10", True)
    assert (a_old["repeat"], a_old["still_open"], a_old["in_window"]) == (0, False, False)
    assert b["still_open"] is False
    assert out["counts"]["pest"] == 2 and out["kitchens"]["pest"] == 2
    assert len(out["rows"]) == 3, "the no-violation visit is not a flag"
