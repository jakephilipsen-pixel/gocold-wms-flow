"""Extract address → run sheet / delivery run mapping from CartonCloud.

READ-ONLY. Searches consignments in the last N days and groups deliveries
by address, listing every run sheet and delivery run each address has
been allocated to.

Why search consignments? CartonCloud doesn't expose run sheets as a
top-level API resource — but the consignment search endpoint accepts
run sheet filters (runSheetId, runSheetName, runSheetDate, runSheetStatus,
deliveryRunId, deliveryRunName) and consignments carry the delivery
address. So consignments are the source of truth for "what address went
on what run".

Filter approach: search for consignments with runSheetDate >= today-30d.
Anything with a run sheet attached in that window is captured.

Output: data/processed/address_runs_<stamp>.csv
Columns:
    address_key          - normalised address string used for dedup
    full_address         - human-readable single-line address
    street               - street line 1
    suburb               - suburb / city
    state                - state code (VIC/NSW/etc)
    postcode             - postcode
    customer_name        - last consignee customer name seen
    consignment_count    - how many consignments to this address in window
    run_sheets           - "; "-joined list of distinct run sheet names (with dates)
    delivery_runs        - "; "-joined list of distinct delivery run names
    first_seen           - earliest run sheet date for this address
    last_seen            - latest run sheet date for this address

Usage:
    python scripts/extract_address_runs.py
    python scripts/extract_address_runs.py --days 14
    python scripts/extract_address_runs.py --days 30 --out data/processed
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# allow `python scripts/extract_address_runs.py` from repo root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.cc_client.client import CartonCloudClient  # noqa: E402

log = logging.getLogger("extract_address_runs")


def _load_env() -> None:
    """Lightweight .env loader so we don't need python-dotenv as a dep."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def build_condition(days: int) -> dict[str, Any]:
    """Build search condition: run sheet date in the last `days` days.

    runSheetDate is a value-field search on consignments. We use
    GREATER_THAN_OR_EQUAL_TO against today minus N days. CC accepts
    ISO date strings (YYYY-MM-DD) for runSheetDate.
    """
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    return {
        "condition": {
            "type": "AndCondition",
            "conditions": [
                {
                    "type": "TextComparisonCondition",
                    "field": {"type": "ValueField", "value": "runSheetDate"},
                    "value": {"type": "ValueField", "value": cutoff},
                    "method": "GREATER_THAN_OR_EQUAL_TO",
                }
            ],
        }
    }


def normalise_address(addr: dict[str, Any] | None) -> tuple[str, str, str, str, str, str]:
    """Return (key, full, street, suburb, state, postcode).

    The key is a lowercased, whitespace-collapsed concatenation of
    street + suburb + state + postcode. Two addresses with the same key
    are treated as the same delivery point even if minor formatting
    differs in CC (e.g. trailing spaces, case).
    """
    if not addr:
        return ("", "", "", "", "", "")

    # CC Address shape per docs: lines, suburb, state, postcode, country.
    # 'lines' is typically an array; defensively handle string too.
    lines = addr.get("lines") or addr.get("addressLines") or []
    if isinstance(lines, str):
        street = lines.strip()
    elif isinstance(lines, list):
        street = ", ".join(str(x).strip() for x in lines if x)
    else:
        street = ""

    # state can be {"code": "VIC", "name": "Victoria"} or a string
    state_raw = addr.get("state") or {}
    if isinstance(state_raw, dict):
        state = state_raw.get("code") or state_raw.get("name") or ""
    else:
        state = str(state_raw)

    suburb = addr.get("suburb") or addr.get("city") or ""
    postcode = addr.get("postcode") or addr.get("postCode") or ""

    full_parts = [p for p in [street, suburb, state, postcode] if p]
    full = ", ".join(full_parts)

    key = " ".join(
        " ".join(str(x).lower().split()) for x in [street, suburb, state, postcode] if x
    )

    return (key, full, street, suburb, state, postcode)


def extract_run_info(cons: dict[str, Any]) -> tuple[str, str, str, str]:
    """Return (run_sheet_label, run_sheet_date, delivery_run_name, customer_name)."""
    details = cons.get("details") or {}

    runsheet = details.get("runsheet") or details.get("runSheet") or {}
    rs_name = runsheet.get("name") or ""
    rs_date = runsheet.get("date") or ""
    rs_label = f"{rs_name} ({rs_date})" if rs_name and rs_date else (rs_name or rs_date)

    dr = details.get("deliveryRun") or {}
    dr_name = dr.get("name") or ""

    cust = (cons.get("customer") or {}).get("name") or ""

    return (rs_label, rs_date, dr_name, cust)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30, help="How many days back (default 30)")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "processed",
        help="Output directory",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    _load_env()
    args.out.mkdir(parents=True, exist_ok=True)

    client = CartonCloudClient.from_env()  # write_enabled=False by default
    log.info("CartonCloud client ready. Searching last %d days of consignments.", args.days)

    condition = build_condition(args.days)
    log.debug("Search condition: %s", condition)

    # aggregator keyed by normalised address
    agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "full_address": "",
            "street": "",
            "suburb": "",
            "state": "",
            "postcode": "",
            "customer_name": "",
            "consignment_count": 0,
            "run_sheets": set(),
            "delivery_runs": set(),
            "dates": [],
        }
    )

    total = 0
    for cons in client.search_consignments(condition["condition"]):
        total += 1
        details = cons.get("details") or {}
        deliver = details.get("deliver") or {}
        addr = deliver.get("address")

        key, full, street, suburb, state, postcode = normalise_address(addr)
        if not key:
            log.debug("Skipping consignment %s — no delivery address", cons.get("id"))
            continue

        rs_label, rs_date, dr_name, cust = extract_run_info(cons)

        rec = agg[key]
        rec["full_address"] = full
        rec["street"] = street
        rec["suburb"] = suburb
        rec["state"] = state
        rec["postcode"] = postcode
        if cust:
            rec["customer_name"] = cust  # last-seen wins; good enough for a mapping
        rec["consignment_count"] += 1
        if rs_label:
            rec["run_sheets"].add(rs_label)
        if dr_name:
            rec["delivery_runs"].add(dr_name)
        if rs_date:
            rec["dates"].append(rs_date)

    log.info(
        "Pulled %d consignments. %d unique delivery addresses with run sheets.",
        total,
        len(agg),
    )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = args.out / f"address_runs_{stamp}.csv"

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "address_key",
                "full_address",
                "street",
                "suburb",
                "state",
                "postcode",
                "customer_name",
                "consignment_count",
                "run_sheets",
                "delivery_runs",
                "first_seen",
                "last_seen",
            ]
        )

        # sort by consignment count desc so the heaviest delivery points float to the top
        for key, rec in sorted(
            agg.items(), key=lambda kv: kv[1]["consignment_count"], reverse=True
        ):
            dates_sorted = sorted(d for d in rec["dates"] if d)
            writer.writerow(
                [
                    key,
                    rec["full_address"],
                    rec["street"],
                    rec["suburb"],
                    rec["state"],
                    rec["postcode"],
                    rec["customer_name"],
                    rec["consignment_count"],
                    "; ".join(sorted(rec["run_sheets"])),
                    "; ".join(sorted(rec["delivery_runs"])),
                    dates_sorted[0] if dates_sorted else "",
                    dates_sorted[-1] if dates_sorted else "",
                ]
            )

    log.info("Wrote %s", out_path)
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
