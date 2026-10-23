"""
Alert Nexus — download real FDA device enforcement/recall records with recall severity.

This replaces the earlier device/recall.json script. That endpoint does not expose
the FDA recall severity classification, which is why SEVERITY was Unknown.
This script uses the separate official openFDA device/enforcement endpoint, whose
records include classification (Class I, II, III, or Not Yet Classified).

Source/docs:
https://open.fda.gov/apis/device/enforcement/
https://open.fda.gov/apis/device/enforcement/searchable-fields/

Install:
    python -m pip install requests pandas
Run:
    python download_alert_nexus_recalls_FIXED2.py

Output:
    alert_nexus_fda_device_recalls_2021_2026.csv

Coverage is official US FDA device enforcement records, not a global all-country
dataset. No records are invented; unknown fields remain Unknown.
"""
from __future__ import annotations

import calendar
import datetime as dt
import time
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API = "https://api.fda.gov/device/enforcement.json"
START = dt.date(2021, 1, 1)
END = dt.date(2026, 10, 24)
TARGET = 2500
PAGE_SIZE = 1000
OUT = Path(__file__).resolve().parent / "alert_nexus_fda_device_recalls_2021_2026.csv"

session = requests.Session()
retry = Retry(
    total=5, connect=5, read=5, backoff_factor=1.5,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset(["GET"]),
    respect_retry_after_header=True,
)
session.mount("https://", HTTPAdapter(max_retries=retry))


def clean(v):
    if v is None or v == "":
        return "Unknown"
    if isinstance(v, list):
        return "; ".join(str(x) for x in v) if v else "Unknown"
    return str(v)


def months():
    cur = dt.date(START.year, START.month, 1)
    while cur <= END:
        last_day = calendar.monthrange(cur.year, cur.month)[1]
        finish = min(dt.date(cur.year, cur.month, last_day), END)
        yield cur.strftime("%Y%m%d"), finish.strftime("%Y%m%d")
        if cur.month == 12:
            cur = dt.date(cur.year + 1, 1, 1)
        else:
            cur = dt.date(cur.year, cur.month + 1, 1)


def fetch_month(first, last):
    query = f"recall_initiation_date:[{first} TO {last}]"
    found = []
    skip = 0
    while True:
        params = {"search": query, "limit": PAGE_SIZE, "skip": skip}
        response = session.get(API, params=params, timeout=(15, 90))
        if response.status_code == 404:
            return found
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text[:500]
            raise RuntimeError(f"FDA API HTTP {response.status_code}: {detail}")
        payload = response.json()
        batch = payload.get("results", [])
        if not batch:
            return found
        found.extend(batch)
        total = payload.get("meta", {}).get("results", {}).get("total", len(found))
        skip += len(batch)
        if skip >= total or len(batch) < PAGE_SIZE or skip >= 25000:
            return found
        time.sleep(0.15)


def row(r):
    raw_date = clean(r.get("recall_initiation_date"))
    if raw_date != "Unknown" and len(raw_date) == 8 and raw_date.isdigit():
        date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
    else:
        date = raw_date
    year = date[:4] if len(date) >= 4 and date[:4].isdigit() else "Unknown"

    classification = clean(r.get("classification"))
    # Do not infer severity from device_class; recall classification is its own field.
    if classification == "Unknown":
        classification = "Not provided by source"

    recall_num = clean(r.get("recall_number"))
    event_id = clean(r.get("event_id"))
    source_url = "https://api.fda.gov/device/enforcement.json"
    if recall_num != "Unknown":
        source_url += f"?search=recall_number:{recall_num}"

    firm_country = clean(r.get("country"))
    return {
        "DATE": date,
        "YEAR": year,
        "SEVERITY": classification,
        "PRODUCT": clean(r.get("product_description")),
        "CATEGORY": clean(r.get("product_type")),
        "COUNTRY": firm_country if firm_country != "Unknown" else "United States (FDA source; distribution may vary)",
        "RECALL REASON": clean(r.get("reason_for_recall")),
        "BATCH / LOT": clean(r.get("code_info")),
        "SOURCE": "U.S. Food and Drug Administration (FDA), openFDA Device Enforcement",
        "OFFICIAL SOURCE URL": source_url,
        "CONFIDENCE": "Official FDA enforcement record; confirm status and details at source",
        "ACTION / STATUS": clean(r.get("status")),
        "CONTINENT": "North America (FDA source jurisdiction; distribution may include other regions)",
        "DISTRIBUTION": clean(r.get("distribution_pattern")),
        "RECALLING FIRM": clean(r.get("recalling_firm")),
        "FDA EVENT ID": event_id,
        "RECALL NUMBER": recall_num,
        "VOLUNTARY / MANDATED": clean(r.get("voluntary_mandated")),
        "INITIAL FIRM NOTIFICATION": clean(r.get("initial_firm_notification")),
        "TERMINATION DATE": clean(r.get("termination_date")),
        "CENTER CLASSIFICATION DATE": clean(r.get("center_classification_date")),
    }


def main():
    records = []
    seen = set()
    print("Downloading real FDA device enforcement records...")
    for first, last in months():
        try:
            batch = fetch_month(first, last)
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            raise SystemExit(
                f"FDA API request failed for {first}-{last}: {exc}\n"
                "No complete CSV was claimed. Test https://api.fda.gov/device/enforcement.json?limit=1"
            )
        for item in batch:
            key = clean(item.get("recall_number"))
            if key == "Unknown":
                key = (clean(item.get("event_id")), clean(item.get("recall_initiation_date")),
                       clean(item.get("product_description")))
            if key in seen:
                continue
            seen.add(key)
            records.append(row(item))
        print(f"Checked {first[:4]}-{first[4:6]}: {len(records)} unique records")
        if len(records) >= TARGET:
            break

    if not records:
        raise SystemExit("No records returned by FDA API.")

    df = pd.DataFrame(records)
    df = df[df["DATE"].astype(str).between(START.isoformat(), END.isoformat())]
    df = df.drop_duplicates(subset=["FDA EVENT ID", "DATE", "PRODUCT"])
    df = df.sort_values("DATE", ascending=False).head(TARGET)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print("\nSUCCESS")
    print(f"File: {OUT}")
    print(f"Rows: {len(df)}")
    print("SEVERITY values:", ", ".join(sorted(df["SEVERITY"].dropna().astype(str).unique())[:10]))
    print("Coverage: US FDA device enforcement records only, not all continents.")
    if len(df) < TARGET:
        print("Fewer than 2,500 unique matching records were returned; no fake rows were added.")


if __name__ == "__main__":
    main()
