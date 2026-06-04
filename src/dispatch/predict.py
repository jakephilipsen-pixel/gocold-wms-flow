"""Assign open orders to delivery runs from the history model."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from .addresses import normalise_address
from .history import RunHistoryModel
from .zones import ZoneConfig, assign_zone

log = logging.getLogger(__name__)

CarrierRule = Callable[[dict[str, Any]], str | None]


@dataclass(frozen=True)
class RunAssignment:
    so_id: str
    so_ref: str
    predicted_run: str | None
    confidence: float
    flag: str                       # stable|mixed|new_address|stale|no_address
    reason: str
    alternatives: list[str] = field(default_factory=list)
    address: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DispatchPlan:
    assignments: list[RunAssignment] = field(default_factory=list)
    carriers: dict[str, list[RunAssignment]] = field(default_factory=dict)
    review: list[RunAssignment] = field(default_factory=list)


def _address_fields(addr: dict[str, Any] | None) -> dict[str, Any]:
    key, full, street, suburb, state, postcode = normalise_address(addr)
    return {"address_key": key, "full_address": full, "street": street,
            "suburb": suburb, "state": state, "postcode": postcode}


def predict_runs(
    orders: list[dict[str, Any]],
    model: RunHistoryModel,
    zones: ZoneConfig,
    *,
    carrier_rule: CarrierRule | None = None,
    as_of: date | None = None,
    stale_days: int = 30,
    stable_share: float = 0.8,
    stable_min_n: int = 3,
) -> DispatchPlan:
    """Bucket each order into assignments / carriers / review.

    Each order dict needs ``so_id``, ``so_ref`` and ``address`` (the CC
    address dict, may be None). ``carrier_rule(order)`` returns a carrier
    name for carrier-bound orders, else None.
    """
    as_of = as_of or date.today()
    assignments: list[RunAssignment] = []
    carriers: dict[str, list[RunAssignment]] = {}
    review: list[RunAssignment] = []

    for o in orders:
        so_id = str(o.get("so_id", ""))
        so_ref = str(o.get("so_ref", ""))
        af = _address_fields(o.get("address"))

        carrier = carrier_rule(o) if carrier_rule else None
        if carrier:
            ra = RunAssignment(so_id, so_ref, None, 1.0, "carrier",
                               f"carrier order ({carrier})", [], af)
            carriers.setdefault(carrier, []).append(ra)
            continue

        key = af["address_key"]
        if not key:
            review.append(RunAssignment(so_id, so_ref, None, 0.0, "no_address",
                                        "order has no delivery address", [], af))
            continue

        cands = model.by_address.get(key)
        if not cands:
            zone = assign_zone(af["state"], af["postcode"], zones)
            review.append(RunAssignment(
                so_id, so_ref, None, 0.0, "new_address",
                f"no run history for this address; zone={zone}", [], af))
            continue

        best = cands[0]
        total = sum(c.score for c in cands) or 1.0
        confidence = best.score / total
        alternatives = [c.run for c in cands[1:]]
        last = best.last_seen

        if last is not None and (as_of - last).days > stale_days:
            review.append(RunAssignment(
                so_id, so_ref, best.run, confidence, "stale",
                f"last seen {last.isoformat()} (> {stale_days}d ago)",
                alternatives, af))
            continue

        reason = (f"{best.n} consignments to this address went on "
                  f"{best.run}; last {last.isoformat() if last else 'unknown'}")
        if best.n >= stable_min_n and confidence >= stable_share:
            assignments.append(RunAssignment(
                so_id, so_ref, best.run, confidence, "stable", reason,
                alternatives, af))
        else:
            review.append(RunAssignment(
                so_id, so_ref, best.run, confidence, "mixed",
                reason + " (mixed history)", alternatives, af))

    log.info("predicted %d assignments, %d carrier orders, %d review",
             len(assignments), sum(len(v) for v in carriers.values()),
             len(review))
    return DispatchPlan(assignments=assignments, carriers=carriers,
                        review=review)
