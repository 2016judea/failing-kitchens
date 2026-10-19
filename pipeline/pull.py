#!/usr/bin/env python3
"""Pull every Minneapolis food-inspection violation since 2025-01-01 from the city's open
ArcGIS layer into private/raw/violations.json. One row per violation. Pages of 2,000
by OBJECTID. Nothing else is read; the product rebuilds from this file alone.

    python3 pipeline/pull.py            # fresh pull (~25k rows, under a minute)

Source: https://services.arcgis.com/afSMGVsC7QlRK1kZ/arcgis/rest/services/Food_Inspections/FeatureServer/0
(City of Minneapolis Open Data, public record).
"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "private" / "raw" / "violations.json"
LAYER = "https://services.arcgis.com/afSMGVsC7QlRK1kZ/arcgis/rest/services/Food_Inspections/FeatureServer/0"
SINCE = "2025-01-01"
FIELDS = ["OBJECTID", "HealthFacilityIDNumber", "FacilityCategory", "BusinessName", "RiskLevel", "FullAddress",
          "ZipCode", "InspectionType", "InspectionResult", "DateOfInspection", "InspectionIDNumber", "FoodCodeText",
          "InspectorComments", "ViolationPriority", "FoodCodeItem", "ViolationStatus", "ViolationPoints",
          "InspectionScore", "ViolationIDNumber", "APN", "Ward", "Neighborhood", "Latitude", "Longitude"]


def query(where, offset, n=2000):
    q = {"where": where, "outFields": ",".join(FIELDS), "returnGeometry": "false", "orderByFields": "OBJECTID",
         "resultOffset": offset, "resultRecordCount": n, "f": "json"}
    url = f"{LAYER}/query?{urllib.parse.urlencode(q)}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                j = json.load(r)
            if "error" in j:
                raise RuntimeError(j["error"])
            return j
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))


def main():
    where = f"DateOfInspection >= DATE '{SINCE}'"
    rows, offset = [], 0
    while True:
        j = query(where, offset)
        feats = [f["attributes"] for f in j.get("features", [])]
        rows += feats
        if not j.get("exceededTransferLimit") or not feats:
            break
        offset += len(feats)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"pulled": time.strftime("%Y-%m-%d"), "since": SINCE, "source": LAYER, "rows": rows}))
    dates = [r["DateOfInspection"] for r in rows if r.get("DateOfInspection")]
    print(f"{len(rows)} violations, {OUT}, latest {time.strftime('%Y-%m-%d', time.gmtime(max(dates) / 1000))}")


if __name__ == "__main__":
    main()
