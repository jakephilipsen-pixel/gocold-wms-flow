"""Read-only pre-flight validation for a hand-edited carton-dim capture sheet (NO CC, NO network).

Jake edits the capture spreadsheet between bulk runs (adds SKUs, tidies values, keeps it uniformly
mm). Before any metres bulk write consumes an edited sheet, this confirms the loader parses it:
header drift surfaces as a CLEAR error (not a silent mis-read that would feed a live write), and a
value that looks like a cm/metres number slipped into the mm sheet is flagged.

It reuses the SAME loader the write path uses (``analysis.dim_loader``) — same sheet read, same
tolerant column resolution — so "it validates here" means "it will load there". It only READS the
local sheet: no CartonCloud client, no network, no writes. Drive it via
``scripts/validate_capture_sheet.py --dims-path <file>``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .dim_loader import load_dimensions, read_capture_sheet, resolve_capture_columns

# A carton linear dimension below this many mm is implausible — almost certainly a metres (0.25) or
# cm (25) value that slipped into the millimetre sheet. The mm->m boundary divides by 1000, so a
# value already in metres would be written 1000x too small. Catch it here, before the bulk.
MIN_PLAUSIBLE_MM = 10.0

# The dim columns the CC write converts — the ones worth range-checking for unit mix-ups.
_DIM_COLUMNS = ("outer_l_mm", "outer_w_mm", "outer_h_mm")

# The logical columns whose resolved header the report highlights (what Jake most needs to eyeball).
_KEY_COLUMNS = ("outer_l_mm", "outer_w_mm", "outer_h_mm", "outer_weight_kg", "cartons_per_pallet")


@dataclass(frozen=True)
class DimFlag:
    """A suspicious RAW dim value: non-numeric, or numeric but implausibly small for a mm sheet."""

    product_code: str
    column: str
    raw_value: object
    issue: str


@dataclass(frozen=True)
class CaptureValidation:
    """The pre-flight verdict for one capture sheet."""

    path: str
    loads: bool                                   # does the real loader accept it (no parse error)?
    column_mapping: dict                           # logical name -> resolved sheet header (None if absent)
    headers_found: list                            # the raw sheet's headers
    error: str | None = None                       # the parse error, surfaced plainly, if it failed
    total_skus: int = 0
    fully_measured: int = 0                         # L/W/H all present
    partial_or_empty: int = 0
    flags: list = field(default_factory=list)       # suspicious dim values (unit mix-ups / non-numeric)


def _is_blank(value) -> bool:
    """A blank cell is 'unmeasured', not 'suspicious' — skip it in the range check."""
    return pd.isna(value) or (isinstance(value, str) and value.strip() == "")


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _flag_suspicious_dims(raw: pd.DataFrame, mapping: dict) -> list:
    """Per row, per dim column: flag a RAW value that is non-numeric, or numeric but implausibly
    small for mm. Works on the RAW values (not the loader's coerced output) so non-numeric text —
    which the loader would silently turn into NaN — is caught here rather than reading as 'missing'.
    """
    flags: list = []
    codes = raw["Product Code"].astype(str).str.strip()
    for logical in _DIM_COLUMNS:
        header = mapping.get(logical)
        if header is None or header not in raw.columns:
            continue
        for code, raw_val in zip(codes, raw[header]):
            if _is_blank(raw_val):
                continue
            num = _to_float(raw_val)
            if num is None:
                flags.append(DimFlag(code, logical, raw_val, "non-numeric value"))
            elif 0 < num < MIN_PLAUSIBLE_MM:
                flags.append(DimFlag(
                    code, logical, raw_val,
                    f"{num} is implausibly small for mm — looks like a cm/metres value in an mm sheet",
                ))
    return flags


def validate_capture_sheet(path) -> CaptureValidation:
    """Parse-check a capture sheet read-only; return a structured verdict. Never raises on a bad
    sheet — a parse failure is reported in ``error`` so the caller (and Jake) sees it plainly."""
    path = Path(path)
    try:
        raw = read_capture_sheet(path)
    except KeyError:
        return CaptureValidation(
            path=str(path), loads=False, column_mapping={}, headers_found=[],
            error="sheet has no 'Product Code' column — is this the right 'SKU Capture' sheet?",
        )
    mapping = resolve_capture_columns(raw)
    headers = [str(c) for c in raw.columns]

    try:
        parsed = load_dimensions(path)
    except Exception as e:  # noqa: BLE001 - a preflight tool must REPORT any load failure, not crash
        return CaptureValidation(
            path=str(path), loads=False, column_mapping=mapping, headers_found=headers,
            error=str(e) if isinstance(e, ValueError) else f"{type(e).__name__}: {e}",
        )

    total = len(parsed)
    lwh_present = (
        parsed["outer_l_mm"].notna() & parsed["outer_w_mm"].notna() & parsed["outer_h_mm"].notna()
    )
    fully = int(lwh_present.sum())
    flags = _flag_suspicious_dims(raw, mapping)
    return CaptureValidation(
        path=str(path), loads=True, column_mapping=mapping, headers_found=headers, error=None,
        total_skus=total, fully_measured=fully, partial_or_empty=total - fully, flags=flags,
    )


def format_validation(v: CaptureValidation) -> str:
    """Render a human-readable pre-flight report for the CLI."""
    lines = [
        "=== capture-sheet pre-flight (read-only, no CartonCloud) ===",
        f"  file : {v.path}",
        "  resolved columns (the header the loader will actually read):",
    ]
    for logical in _KEY_COLUMNS:
        header = v.column_mapping.get(logical)
        shown = repr(header) if header is not None else "‼ NOT FOUND"
        lines.append(f"      {logical:<20} <- {shown}")

    if not v.loads:
        lines += [
            "",
            "  ❌ DOES NOT LOAD — the bulk would refuse this sheet:",
            f"     {v.error}",
            f"  headers found: {v.headers_found}",
        ]
        return "\n".join(lines)

    lines += [
        "",
        f"  SKUs parsed     : {v.total_skus}",
        f"  fully measured  : {v.fully_measured}  (L/W/H all present)",
        f"  partial / empty : {v.partial_or_empty}",
    ]
    if v.flags:
        lines.append(
            f"  ⚠ suspicious values : {len(v.flags)} "
            "(possible unit mix-up — the sheet must be uniformly mm)"
        )
        for flag in v.flags[:50]:
            lines.append(
                f"      {flag.product_code:<16} {flag.column:<12} {flag.raw_value!r}: {flag.issue}"
            )
        if len(v.flags) > 50:
            lines.append(f"      ... and {len(v.flags) - 50} more")
    else:
        lines.append("  ✅ no suspicious dim values (all present dims look like plausible mm)")

    verdict = "✅ OK to feed the bulk" if not v.flags else "⚠ REVIEW the flagged values before the bulk"
    lines += ["", f"  verdict: {verdict}"]
    return "\n".join(lines)
