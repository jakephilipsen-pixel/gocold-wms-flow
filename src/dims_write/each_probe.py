"""M-DIMS-5d probe — read-only Base/Each UoM name-shape census (NO WRITES).

Why this exists
---------------
M-DIMS-5c (write carton dims to the **CT** carton UoM) is being dropped from automated scope:
CC rejects a dims PATCH to the CT UoM because writing a dim sub-field forces validation of the
whole CT UoM object, and every live CT UoM is named "CT" (2 chars), which fails CC's 3–64 char
rule (422). Fixing CT names is a manual CC-UI operation. So the automated target moves to the
**Each / Base UoM**, which every SKU has and which should accept dims cleanly.

Before building the each-write, this probe answers the go/no-go question READ-ONLY: across the
live Forage cohort, does each SKU's Base UoM carry a valid (3–64 char) name, or would the
each-write hit the SAME name trap CT did? We find that out here, not mid-write.

Buckets per SKU:
  - **each-writable** — Base UoM present with a valid name (dims would attach cleanly)
  - **each-blocked**  — Base UoM present but name missing / too short / too long (would 422)
  - **no-each**       — no resolvable default UoM (shouldn't happen; reported if it does)

It also reports how many Base UoMs already carry dims (a future each-write would no-op those).

Safety
------
NO WRITES. Reuses the read path the write flow uses — ``gather_active_live_candidates`` →
``read_product_for_dims`` (GET ``/warehouse-products/{id}`` under Accept-Version 8). The Base
UoM is the product's ``defaultUnitOfMeasure``. Nothing flips ``write_enabled``; ``CC_LIVE_PROMOTION``
is irrelevant. One GET per candidate, JSON inspected — no PATCH is ever built.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from cc_client.client import CartonCloudClient

from .approve import read_product_for_dims
from .live_proving import gather_active_live_candidates, LiveCandidate
from .uom_name import uom_name_status

log = logging.getLogger(__name__)

# The L/W/H dim fields that decide "does this UoM already carry dims" (weight is separate).
_LWH_FIELDS = ("length", "width", "height")

BUCKET_WRITABLE = "each-writable"
BUCKET_BLOCKED = "each-blocked"
BUCKET_NO_EACH = "no-each"


def resolve_base_uom(raw: Mapping[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """The product's Base/Each UoM: its id (``defaultUnitOfMeasure``) and the UoM object.

    Returns ``(uom_id, uom_obj)``; ``(None, {})`` when there is no default UoM or the id isn't
    present in ``unitOfMeasures``. The id is the key the dims PATCH path would target, so an
    each-write resolves the SAME UoM this probe inspects.
    """
    base_id = raw.get("defaultUnitOfMeasure")
    uoms = raw.get("unitOfMeasures") or {}
    if not base_id or base_id not in uoms:
        return None, {}
    return base_id, (uoms.get(base_id) or {})


@dataclass(frozen=True)
class EachUomProbe:
    """One SKU's Base-UoM census result: bucket, the UoM id+code, name shape, dims-set flag."""

    code: str
    product_id: str
    bucket: str            # BUCKET_WRITABLE | BUCKET_BLOCKED | BUCKET_NO_EACH
    uom: str | None        # Base UoM id (the defaultUnitOfMeasure key); None when no-each
    uom_code: str | None   # the UoM's code (e.g. EA); falls back to the id
    name: Any              # the Base UoM's name as read
    name_len: int | None
    has_dims: bool         # does the Base UoM already carry any of L/W/H?
    reason: str


def classify_each_uom(code: str, product_id: str, raw: Mapping[str, Any]) -> EachUomProbe:
    """Bucket one product by its Base/Each UoM's name shape — the pure logic the census applies.

    - no resolvable default UoM         -> ``no-each``
    - Base UoM name valid (3–64 chars)  -> ``each-writable``
    - Base UoM name missing/out-of-range -> ``each-blocked`` (would 422 the same way CT did)
    """
    uom_id, obj = resolve_base_uom(raw)
    if not uom_id:
        return EachUomProbe(
            code, product_id, BUCKET_NO_EACH, None, None, None, None, False,
            "no default UoM",
        )
    uom_code = obj.get("code") or uom_id
    has_dims = any(obj.get(f) is not None for f in _LWH_FIELDS)
    status = uom_name_status(obj.get("name"))
    bucket = BUCKET_WRITABLE if status.ok else BUCKET_BLOCKED
    return EachUomProbe(
        code, product_id, bucket, uom_id, uom_code, status.name, status.length, has_dims,
        status.reason,
    )


@dataclass(frozen=True)
class EachUomCensus:
    """The full census over the candidate set, with the three buckets pre-split."""

    probes: list[EachUomProbe] = field(default_factory=list)

    @property
    def each_writable(self) -> list[EachUomProbe]:
        return [p for p in self.probes if p.bucket == BUCKET_WRITABLE]

    @property
    def each_blocked(self) -> list[EachUomProbe]:
        return [p for p in self.probes if p.bucket == BUCKET_BLOCKED]

    @property
    def no_each(self) -> list[EachUomProbe]:
        return [p for p in self.probes if p.bucket == BUCKET_NO_EACH]

    @property
    def with_dims(self) -> list[EachUomProbe]:
        """Base UoMs that already carry dims — a future each-write would no-op these."""
        return [p for p in self.probes if p.has_dims]


def probe_each_uom_names(
    client: CartonCloudClient,
    *,
    candidates: list[LiveCandidate] | None = None,
    pace_seconds: float = 0.2,
    sleep: Callable[[float], None] = time.sleep,
) -> EachUomCensus:
    """Read-only census of Base/Each UoM names across the active live Forage products.

    Gathers candidates (unless supplied), then for each issues ONE GET via
    ``read_product_for_dims`` (the same v8 read the write flow uses) and classifies the Base
    UoM's name. ``pace_seconds`` spaces the GETs to stay polite over a ~450-product sweep.
    Nothing here writes.
    """
    cands = candidates if candidates is not None else gather_active_live_candidates(client)
    probes: list[EachUomProbe] = []
    for i, cand in enumerate(cands):
        if i > 0 and pace_seconds > 0:
            sleep(pace_seconds)
        read = read_product_for_dims(client, cand.product_id)
        probes.append(classify_each_uom(cand.code, cand.product_id, read.raw))
    return EachUomCensus(probes=probes)


def format_each_uom_census(census: EachUomCensus) -> str:
    """Render the census as the go/no-go shape for the each-write."""
    n = len(census.probes)
    lines = [
        "=== M-DIMS-5d — Base/Each UoM name-shape census (READ-ONLY, no writes) ===",
        f"  live products scanned          : {n}",
        f"  each-writable (name 3–64)      : {len(census.each_writable)}",
        f"  each-blocked (short/missing)   : {len(census.each_blocked)}",
        f"  no-each (no default UoM)       : {len(census.no_each)}",
        f"  (of all) Base UoM already has dims : {len(census.with_dims)}  "
        "(a future each-write would no-op these)",
    ]
    if census.each_blocked:
        lines.append("")
        lines.append("  each-BLOCKED SKUs (these would 422 the same way CT did — fix names first):")
        for p in sorted(census.each_blocked, key=lambda x: x.code):
            lines.append(
                f"    {p.code:<16} uom={p.uom_code!s:<8} name={p.name!r:<24} len={p.name_len}  ({p.reason})"
            )
    if census.no_each:
        lines.append("")
        lines.append("  no-each SKUs (no resolvable default UoM — investigate):")
        for p in sorted(census.no_each, key=lambda x: x.code):
            lines.append(f"    {p.code}")
    lines += [
        "",
        "  Go/no-go for the each-write:",
        "    - each-blocked == 0  -> the Base UoM cohort is CLEAN; the each-write is unblocked.",
        "    - each-blocked > 0   -> those SKUs need a UoM name set (≥3 chars) first, exactly",
        "                            like CT — the each-write must skip them or wait on a fix.",
    ]
    return "\n".join(lines)
