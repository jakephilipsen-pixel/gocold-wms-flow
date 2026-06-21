"""Go Cold's dims write surface (M-DIMS phase).

The first CC write surface, ported natively into the W0–W5 spine (M-DIMS-1 Route B).
M-DIMS-2 is shadow mode: read current dims, compute the diff, require approval, run
the full gate chain — but inject a recorder so nothing is written. Shadow vs live
(M-DIMS-3) differ by a single injected mutate fn (WRITE_ENABLEMENT_PLAN §3.1).
"""
from .approve import (
    approve_dims_write,
    shadow_mutate_fn,
    read_product_for_dims,
    DimsApproveResult,
    ProductDimsRead,
    DIM_FIELDS,
    PRODUCT_PATH,
)
from .roundtrip import (
    live_mutate_fn,
    write_and_verify,
    assert_write_target_allowed,
    gather_active_sandbox_candidates,
    select_writable_sandbox_sku,
    run_sandbox_roundtrip,
    sandbox_desired_lookup,
    SandboxCandidate,
    TargetSelection,
    HardStopInfo,
    RoundtripReport,
    DimsRoundtripError,
    DimsRoundtripRefused,
    NoWritableSandboxSku,
    DimsReadBackMismatch,
)
from .bulk import (
    build_bulk_plan,
    run_sandbox_bulk,
    BulkPlan,
    BulkPlanItem,
    BulkReport,
)

__all__ = [
    "approve_dims_write",
    "shadow_mutate_fn",
    "read_product_for_dims",
    "DimsApproveResult",
    "ProductDimsRead",
    "DIM_FIELDS",
    "PRODUCT_PATH",
    "live_mutate_fn",
    "write_and_verify",
    "assert_write_target_allowed",
    "gather_active_sandbox_candidates",
    "select_writable_sandbox_sku",
    "run_sandbox_roundtrip",
    "sandbox_desired_lookup",
    "SandboxCandidate",
    "TargetSelection",
    "HardStopInfo",
    "RoundtripReport",
    "DimsRoundtripError",
    "DimsRoundtripRefused",
    "NoWritableSandboxSku",
    "DimsReadBackMismatch",
    "build_bulk_plan",
    "run_sandbox_bulk",
    "BulkPlan",
    "BulkPlanItem",
    "BulkReport",
]
