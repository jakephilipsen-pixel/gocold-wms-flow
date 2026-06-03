"""Flagged estimated-weight fallback for un-weighed cartons (AUDIT R6).

Outer weight is captured for ~281/409 SKUs; the remaining ~128 have never
been weighed and the data exists nowhere digital. Cartonisation and
dispatch-load maths still need *a* number, so this module synthesises a
conservative estimate from carton cube — but never silently: every estimate
is tagged with its source and a confidence level, the measured column is
left untouched, and estimates are meant to be reviewed (output as CSV)
before anything downstream relies on them.

Method
------
Weight is estimated as ``density × cube``. Density (kg per litre) is learned
from the SKUs that *do* have a measured weight:

  * **family density** — the median density of measured SKUs in the same
    product family (the code prefix before "-", e.g. ``RK`` in ``RK-9LY``),
    used when that family has at least ``min_family_samples`` measured SKUs.
    Density is tight *within* a family, so these are the trustworthy
    estimates (confidence = ``medium``).
  * **global density** — the median density across all measured SKUs, used
    when the family has too few samples. Density varies wildly *across*
    families, so these are weak (confidence = ``low``). Whole high-velocity
    families (RK, GP, HP) have zero measured cartons, so they land here —
    weigh those first; the estimate is a placeholder, not a measurement.

Medians (not means) are used throughout — one dense outlier shouldn't drag
a whole family's estimate up.

Read-only. Produces data; writes nothing to CartonCloud.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# A family needs at least this many measured SKUs before we trust its density.
MIN_FAMILY_SAMPLES = 3

# Litres per cubic millimetre (1 L = 1e6 mm³).
_MM3_PER_LITRE = 1_000_000.0

# No carton weighs less than this; guards against zero/negative estimates.
WEIGHT_FLOOR_KG = 0.05

# Output column names.
SOURCE_MEASURED = "measured"
SOURCE_FAMILY = "estimated_family"
SOURCE_GLOBAL = "estimated_global"
SOURCE_NONE = "none"

CONF_MEASURED = "measured"
CONF_MEDIUM = "medium"
CONF_LOW = "low"
CONF_NONE = "none"


def product_family(code: object) -> str:
    """Family key = the code prefix before the first '-' (e.g. RK-9LY → RK)."""
    s = str(code).strip()
    return s.split("-", 1)[0] if "-" in s else s


def _density_kg_per_l(weight_kg: pd.Series, cube_mm3: pd.Series) -> pd.Series:
    cube_l = cube_mm3 / _MM3_PER_LITRE
    return weight_kg / cube_l.where(cube_l > 0)


def estimate_carton_weights(
    dims: pd.DataFrame,
    min_family_samples: int = MIN_FAMILY_SAMPLES,
) -> pd.DataFrame:
    """Add a flagged effective-weight column to a dim frame.

    Parameters
    ----------
    dims :
        Frame with at least ``product_code``, ``outer_weight_kg`` (NaN where
        un-measured) and ``outer_cube_mm3``.
    min_family_samples :
        Minimum measured SKUs in a family before its density is trusted.

    Returns
    -------
    A copy of ``dims`` with added columns:
        ``family``                — product family key
        ``outer_weight_kg``       — unchanged (measured only; NaN if missing)
        ``outer_weight_kg_effective`` — measured value, or the estimate
        ``weight_source``         — measured / estimated_family /
                                     estimated_global / none
        ``weight_confidence``     — measured / medium / low / none
        ``weight_estimate_basis`` — human-readable explanation per row
    """
    if "outer_weight_kg" not in dims or "outer_cube_mm3" not in dims:
        raise ValueError(
            "dims must have 'outer_weight_kg' and 'outer_cube_mm3' columns"
        )

    out = dims.copy()
    out["family"] = out["product_code"].map(product_family)

    weight = pd.to_numeric(out["outer_weight_kg"], errors="coerce")
    cube = pd.to_numeric(out["outer_cube_mm3"], errors="coerce")
    cube_l = cube / _MM3_PER_LITRE

    measured_mask = weight.notna()
    meas = out[measured_mask & (cube > 0)]
    meas_density = _density_kg_per_l(weight[meas.index], cube[meas.index])

    global_density = float(meas_density.median()) if not meas_density.empty else np.nan
    fam_counts = meas.groupby("family").size()
    fam_density = meas_density.groupby(meas["family"]).median()
    trusted_fams = set(fam_counts[fam_counts >= min_family_samples].index)

    log.info(
        "weight estimate: %d measured, global density %.3f kg/L, "
        "%d trusted families (>=%d samples)",
        int(measured_mask.sum()), global_density,
        len(trusted_fams), min_family_samples,
    )

    eff = weight.copy()
    source = pd.Series(SOURCE_MEASURED, index=out.index)
    conf = pd.Series(CONF_MEASURED, index=out.index)
    basis = pd.Series("", index=out.index)
    source[~measured_mask] = SOURCE_NONE
    conf[~measured_mask] = CONF_NONE

    for i in out.index[~measured_mask]:
        c_l = cube_l.get(i)
        if pd.isna(c_l) or c_l <= 0:
            basis[i] = "no carton cube — cannot estimate"
            continue  # eff stays NaN, source/conf = none
        fam = out.at[i, "family"]
        if fam in trusted_fams and pd.notna(fam_density.get(fam, np.nan)):
            dens = float(fam_density[fam])
            est = max(dens * c_l, WEIGHT_FLOOR_KG)
            eff[i] = round(est, 2)
            source[i] = SOURCE_FAMILY
            conf[i] = CONF_MEDIUM
            basis[i] = (
                f"family {fam} median density {dens:.3f} kg/L "
                f"(n={int(fam_counts[fam])}) × {c_l:.1f} L"
            )
        elif not np.isnan(global_density):
            est = max(global_density * c_l, WEIGHT_FLOOR_KG)
            eff[i] = round(est, 2)
            source[i] = SOURCE_GLOBAL
            conf[i] = CONF_LOW
            n_fam = int(fam_counts.get(fam, 0))
            basis[i] = (
                f"global median density {global_density:.3f} kg/L × {c_l:.1f} L "
                f"(family {fam} has only {n_fam} measured)"
            )
        else:
            basis[i] = "no measured weights anywhere — cannot estimate"

    out["outer_weight_kg_effective"] = eff
    out["weight_source"] = source
    out["weight_confidence"] = conf
    out["weight_estimate_basis"] = basis
    return out


def summarise(estimated: pd.DataFrame) -> dict:
    """Counts by source/confidence for a quick console summary."""
    return {
        "total": len(estimated),
        "by_source": estimated["weight_source"].value_counts().to_dict(),
        "by_confidence": estimated["weight_confidence"].value_counts().to_dict(),
    }
