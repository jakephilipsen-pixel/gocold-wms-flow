"""M-DIMS-5c probe — read-only CT UoM name-shape census (NO WRITES).

Why this exists
---------------
The first armed 5c live run fail-fast halted on SKU #1 (AE-BLA, product 55811cf3-…) with a
422 from CartonCloud — ZERO dims written, no bad data landed:

    {"field":"/unitOfMeasures/CT/name","message":"Must be between 3 and 64 characters."}

This is NOT a dims problem. The L/W/H/weight payload was fine. CC rejected because add-ing
dimension sub-fields under ``/unitOfMeasures/CT/`` makes it validate the WHOLE CT UoM object,
and that UoM's ``name`` was missing / too short — the CT UoM on AE-BLA is an incomplete shell.

Two signals point the same way: (1) the cohort resolved to 77 CT SKUs, not the 81 an earlier
probe predicted — a gap suggesting CT UoMs aren't uniformly present; (2) the name 422 says at
least one CT UoM is a shell. Together: some live CT UoMs may be half-created.

What this answers
-----------------
Across the live Forage set, READ-ONLY: for every SKU that has a CT UoM, is that UoM's ``name``
present and 3–64 chars (**CT-complete**) or missing / out-of-range (**CT-incomplete**)? Plus
the SKUs with **no CT UoM** at all. The bucket counts decide whether AE-BLA is a handful of
bad-data exceptions 5c should simply skip, or whether there is a systemic "set/verify the CT
UoM name first" prerequisite step before dims can attach.

Safety
------
NO WRITES. Reuses the EXACT read path the live run uses — ``gather_active_live_candidates`` →
``read_product_for_dims`` (GET ``/warehouse-products/{id}`` under Accept-Version 8) →
``resolve_ct_uom``. ``CC_LIVE_PROMOTION`` is irrelevant here; nothing flips ``write_enabled``.
The census issues one GET per candidate and inspects the JSON — it never builds or sends a
PATCH.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from cc_client.client import CartonCloudClient

from .approve import read_product_for_dims
from .bulk import resolve_ct_uom
from .live_proving import gather_active_live_candidates, LiveCandidate
from .uom_name import uom_name_status, UOM_NAME_MIN_CHARS, UOM_NAME_MAX_CHARS

log = logging.getLogger(__name__)

# CC's UoM-name rule (3–64 chars) is shared across UoM types — see uom_name.py. Re-exported
# under the CT-prefixed names this module's callers already use.
CT_NAME_MIN_CHARS = UOM_NAME_MIN_CHARS
CT_NAME_MAX_CHARS = UOM_NAME_MAX_CHARS

BUCKET_NO_CT = "no-ct"
BUCKET_COMPLETE = "ct-complete"
BUCKET_INCOMPLETE = "ct-incomplete"


def ct_uom_name(raw: Mapping[str, Any], uom: str) -> Any:
    """The CT UoM's ``name`` value as read (``None`` when absent).

    Reads the SAME UoM ``resolve_ct_uom`` selected — for both the keyed-by-code and the
    keyed-by-uuid v8 shapes, ``uom`` is the map key, so this looks the name up directly.
    """
    uom_obj = (raw.get("unitOfMeasures") or {}).get(uom) or {}
    return uom_obj.get("name")


@dataclass(frozen=True)
class CtUomProbe:
    """One SKU's CT-UoM census result: its bucket, the resolved CT UoM key, and the name shape."""

    code: str
    product_id: str
    bucket: str            # BUCKET_NO_CT | BUCKET_COMPLETE | BUCKET_INCOMPLETE
    uom: str | None        # resolved CT UoM key/id; None when no-ct
    name: Any              # the CT UoM's name as read (None when missing / no-ct)
    name_len: int | None   # len(name) when name is a string, else None
    reason: str


def classify_ct_uom(code: str, product_id: str, raw: Mapping[str, Any]) -> CtUomProbe:
    """Bucket one product by its CT UoM's name shape — the pure logic the census applies.

    - no CT UoM (``resolve_ct_uom`` → None)             -> ``no-ct``
    - CT UoM name is a string of 3–64 chars             -> ``ct-complete``
    - CT UoM name missing / non-string / out-of-range   -> ``ct-incomplete`` (the AE-BLA 422)

    The 3–64 bound is CC's own (the 422 message). Boundaries are inclusive. A non-string name
    (shouldn't happen, but CC's JSON is untyped to us) is treated as incomplete, not crashed.
    """
    uom = resolve_ct_uom(raw)
    if not uom:
        return CtUomProbe(code, product_id, BUCKET_NO_CT, None, None, None, "no CT UoM")

    status = uom_name_status(ct_uom_name(raw, uom))
    bucket = BUCKET_COMPLETE if status.ok else BUCKET_INCOMPLETE
    return CtUomProbe(code, product_id, bucket, uom, status.name, status.length, status.reason)


@dataclass(frozen=True)
class CtUomCensus:
    """The full census over the candidate set, with the three buckets pre-split."""

    probes: list[CtUomProbe] = field(default_factory=list)

    @property
    def no_ct(self) -> list[CtUomProbe]:
        return [p for p in self.probes if p.bucket == BUCKET_NO_CT]

    @property
    def ct_complete(self) -> list[CtUomProbe]:
        return [p for p in self.probes if p.bucket == BUCKET_COMPLETE]

    @property
    def ct_incomplete(self) -> list[CtUomProbe]:
        return [p for p in self.probes if p.bucket == BUCKET_INCOMPLETE]

    @property
    def ct_cohort(self) -> list[CtUomProbe]:
        """Every SKU with a CT UoM (complete + incomplete) — the population 5c targets."""
        return [p for p in self.probes if p.bucket != BUCKET_NO_CT]


def probe_ct_uom_names(
    client: CartonCloudClient,
    *,
    candidates: list[LiveCandidate] | None = None,
    pace_seconds: float = 0.2,
    sleep: Callable[[float], None] = time.sleep,
) -> CtUomCensus:
    """Read-only census of CT UoM names across the active live Forage products.

    Gathers candidates (unless supplied), then for each issues ONE GET via
    ``read_product_for_dims`` (the same v8 read the live run uses) and classifies the CT UoM's
    name. ``pace_seconds`` spaces the GETs to stay polite — reads aren't hard-capped, but a
    ~450-product sweep should not hammer the API. Nothing here writes.
    """
    cands = candidates if candidates is not None else gather_active_live_candidates(client)
    probes: list[CtUomProbe] = []
    for i, cand in enumerate(cands):
        if i > 0 and pace_seconds > 0:
            sleep(pace_seconds)
        read = read_product_for_dims(client, cand.product_id)
        probes.append(classify_ct_uom(cand.code, cand.product_id, read.raw))
    return CtUomCensus(probes=probes)


def format_ct_uom_census(census: CtUomCensus) -> str:
    """Render the census so the systemic-vs-exception decision is legible at a glance."""
    cohort = census.ct_cohort
    lines = [
        "=== M-DIMS-5c — CT UoM name-shape census (READ-ONLY, no writes) ===",
        f"  live products scanned        : {len(census.probes)}",
        f"  with a CT UoM (the cohort)   : {len(cohort)}",
        f"    - CT-complete (name 3–64)  : {len(census.ct_complete)}",
        f"    - CT-incomplete (shell)    : {len(census.ct_incomplete)}",
        f"  no CT UoM (not 5c's job)     : {len(census.no_ct)}",
    ]
    if census.ct_incomplete:
        lines.append("")
        lines.append("  CT-incomplete SKUs (these are what 422'd the live run):")
        for p in sorted(census.ct_incomplete, key=lambda x: x.code):
            lines.append(
                f"    {p.code:<16} uom={p.uom!s:<10} name={p.name!r:<24} len={p.name_len}  ({p.reason})"
            )
    lines += [
        "",
        "  Read the verdict:",
        "    - incomplete == 0           -> every CT UoM has a valid name; AE-BLA was not the",
        "                                   blocker (re-investigate); 5c can run as-is.",
        "    - incomplete is a handful   -> bad-data EXCEPTIONS; 5c should SKIP them (skip-list)",
        "                                   and write the CT-complete cohort.",
        "    - incomplete is most/all    -> SYSTEMIC: CT UoMs are half-created shells; a",
        "                                   prerequisite 'set the CT UoM name' step is needed",
        "                                   before dims can attach. Do NOT just skip.",
    ]
    return "\n".join(lines)
