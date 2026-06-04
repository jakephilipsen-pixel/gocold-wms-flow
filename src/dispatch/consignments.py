"""Parse CC consignments into run-history records."""
from __future__ import annotations

from typing import Any

from .addresses import normalise_address


def extract_run_info(cons: dict[str, Any]) -> tuple[str, str, str, str]:
    """Return (run_sheet_label, run_sheet_date, delivery_run_name, customer)."""
    details = cons.get("details") or {}
    runsheet = details.get("runsheet") or details.get("runSheet") or {}
    rs_name = runsheet.get("name") or ""
    rs_date = runsheet.get("date") or ""
    rs_label = (
        f"{rs_name} ({rs_date})" if rs_name and rs_date else (rs_name or rs_date)
    )
    dr_name = (details.get("deliveryRun") or {}).get("name") or ""
    cust = (cons.get("customer") or {}).get("name") or ""
    return (rs_label, rs_date, dr_name, cust)


def parse_consignment(cons: dict[str, Any]) -> dict[str, Any]:
    """Flatten a consignment into a run-history record.

    ``run`` is the delivery-run name when present, else the run-sheet name
    (the operator-facing run label). ``run_date`` is the run-sheet date.
    """
    details = cons.get("details") or {}
    addr = (details.get("deliver") or {}).get("address")
    key, full, street, suburb, state, postcode = normalise_address(addr)
    rs_label, rs_date, dr_name, cust = extract_run_info(cons)
    run = dr_name or (rs_label.split(" (")[0] if rs_label else "")
    return {
        "address_key": key,
        "full_address": full,
        "street": street,
        "suburb": suburb,
        "state": state,
        "postcode": postcode,
        "run": run,
        "run_sheet": rs_label,
        "run_date": rs_date,
        "customer": cust,
    }
