# Dispatch Run Prediction (v1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only daily tool that predicts which CartonCloud delivery run each open order belongs on, by learning habitual address→run pairings from consignment history.

**Architecture:** A `src/dispatch/` library (address normalisation → history model → prediction → output) driven by a batch orchestrator `scripts/build_dispatch.py`. CartonCloud is read-only; a `DispatchSink` seam isolates a future write-back (`CartonCloudSink` exists but refuses to write in v1). Deterministic recency-weighted-frequency model — no LLM in the pipeline.

**Tech Stack:** Python 3.11+, httpx (existing CC client), pandas + pyarrow (model cache), openpyxl (manifests), stdlib `tomllib` (zone config). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-06-05-dispatch-run-prediction-design.md`

---

## File Structure

| File | Responsibility |
| --- | --- |
| `src/cc_client/queries.py` (modify) | Add `search_consignments()` read helper |
| `src/cc_client/__init__.py` (modify) | Export `search_consignments` |
| `src/dispatch/__init__.py` (create) | Package exports |
| `src/dispatch/addresses.py` (create) | `normalise_address`, `address_key` |
| `src/dispatch/consignments.py` (create) | `extract_run_info`, `parse_consignment` |
| `src/dispatch/history.py` (create) | `RunCandidate`, `RunHistoryModel`, `compute_run_history`, `save_model`, `load_model` |
| `src/dispatch/zones.py` (create) | `ZoneRule`, `ZoneConfig`, `load_zone_config`, `assign_zone` |
| `src/dispatch/predict.py` (create) | `RunAssignment`, `DispatchPlan`, `predict_runs` |
| `src/dispatch/output.py` (create) | `write_dispatch_plan` (CSVs, manifests, summary) |
| `src/dispatch/sinks.py` (create) | `DispatchSink`, `AssignResult`, `FileSink`, `CartonCloudSink` |
| `config/dispatch_zones.toml` (create) | Operator-editable zone fallback |
| `scripts/build_dispatch.py` (create) | Orchestrator: learn → predict → write |
| `scripts/extract_address_runs.py` (modify) | Re-point to lifted library + new `search_consignments` |
| `tests/test_*.py` (create) | One test module per library file |

Dependency order of tasks: 1 (client) → 2 (addresses/consignments) → 3 (history) → 4 (zones) → 5 (predict) → 6 (output) → 7 (sinks) → 8 (orchestrator + script re-point).

**Run tests with** `.venv/bin/python -m pytest` (the venv bin wrappers have a stale shebang — always invoke `python -m`).

---

## Task 1: `search_consignments()` read path

**Files:**
- Modify: `src/cc_client/queries.py` (add function near the other `search_*`)
- Modify: `src/cc_client/__init__.py`
- Test: `tests/test_consignments_query.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_consignments_query.py`:

```python
"""search_consignments must POST /consignments/search as a read."""
from __future__ import annotations

import time

import httpx

from cc_client.client import CartonCloudClient, _Token
from cc_client.queries import search_consignments


class _FakeTransport:
    def __init__(self, response):
        self._response = response
        self.calls: list[dict] = []

    def request(self, method, url, *, params=None, json=None, headers=None):
        self.calls.append({"method": method, "url": url, "params": params,
                           "json": json, "headers": headers})
        resp = self._response
        if callable(resp):
            resp = resp(method, url, params=params, json=json, headers=headers)
        resp.request = httpx.Request(method, url)
        return resp

    def close(self):  # pragma: no cover
        pass


def _client() -> CartonCloudClient:
    c = CartonCloudClient(client_id="id", client_secret="secret",
                          tenant_id="tenant", write_enabled=False)
    c._token = _Token(access_token="tok", expires_at=time.time() + 3600)
    return c


def test_search_consignments_posts_run_sheet_date_condition():
    c = _client()

    def transport(method, url, *, params, json, headers):
        # First page returns one item; any further page returns empty.
        if params and params.get("page", 1) > 1:
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=[{"id": "c1"}])

    c._http = _FakeTransport(transport)

    items = list(search_consignments(c, run_sheet_date_from="2026-05-01"))

    assert items == [{"id": "c1"}]
    call = c._http.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/tenants/tenant/consignments/search")
    cond = call["json"]["condition"]["conditions"][0]
    assert cond["field"]["value"] == "runSheetDate"
    assert cond["value"]["value"] == "2026-05-01"
    assert cond["method"] == "GREATER_THAN_OR_EQUAL_TO"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_consignments_query.py -v`
Expected: FAIL with `ImportError: cannot import name 'search_consignments'`.

- [ ] **Step 3: Add the function**

In `src/cc_client/queries.py`, after `search_warehouse_locations` (end of file), add:

```python
def search_consignments(
    client: CartonCloudClient,
    *,
    run_sheet_date_from: date | datetime | str,
    page_size: int = 100,
    max_pages: int | None = None,
) -> Iterator[dict[str, Any]]:
    """Iterate consignments whose run sheet is dated on/after a cutoff.

    Consignments are CC's source of truth for "what address went on what
    run": each carries the delivery address plus ``details.runsheet`` and
    ``details.deliveryRun``. ``runSheetDate`` is a ValueField search taking
    an ISO date (YYYY-MM-DD). Read-only despite the POST verb, like the
    other search helpers.
    """
    body = {
        "condition": {
            "type": "AndCondition",
            "conditions": [
                {
                    "type": "TextComparisonCondition",
                    "field": {"type": "ValueField", "value": "runSheetDate"},
                    "value": {
                        "type": "ValueField",
                        "value": _iso(run_sheet_date_from)[:10],
                    },
                    "method": "GREATER_THAN_OR_EQUAL_TO",
                }
            ],
        }
    }
    yield from client.post_search(
        "/consignments/search", body, page_size=page_size, max_pages=max_pages,
    )
```

In `src/cc_client/__init__.py`, add `search_consignments` to both the
`from .queries import (...)` block and `__all__` (keep alphabetical order
within the existing list).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_consignments_query.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cc_client/queries.py src/cc_client/__init__.py tests/test_consignments_query.py
git commit -m "feat(cc): add read-only search_consignments helper"
```

- [ ] **Step 6: Live scope probe (manual, gating — Open Question #1)**

Write a throwaway probe `scripts/_probe_consignments.py` that loads `.env`,
builds `CartonCloudClient.from_env()`, and does
`next(iter(search_consignments(client, run_sheet_date_from=<today-30d>)), None)`,
printing the first consignment's keys or the error. Run it:
`.venv/bin/python scripts/_probe_consignments.py`

- If it returns data → scope OK, continue.
- If it 403/404 → **stop**: the consignment read scope is missing. Raise
  with the operator (add the read role in CC Admin, re-verify) before
  building further. Delete the probe either way: `rm scripts/_probe_consignments.py`.

---

## Task 2: Address + run-info library (lift from script)

**Files:**
- Create: `src/dispatch/__init__.py`
- Create: `src/dispatch/addresses.py`
- Create: `src/dispatch/consignments.py`
- Test: `tests/test_dispatch_addresses.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_dispatch_addresses.py`:

```python
from __future__ import annotations

from dispatch.addresses import address_key, normalise_address
from dispatch.consignments import extract_run_info, parse_consignment


def test_normalise_handles_list_lines_and_dict_state():
    addr = {"lines": ["12 Cold St ", "Unit 3"], "suburb": "Scoresby",
            "state": {"code": "VIC"}, "postcode": "3179"}
    key, full, street, suburb, state, postcode = normalise_address(addr)
    assert street == "12 Cold St, Unit 3"
    assert suburb == "Scoresby"
    assert state == "VIC"
    assert postcode == "3179"
    assert key == "12 cold st, unit 3 scoresby vic 3179"


def test_normalise_none_address_is_empty_key():
    assert address_key(None) == ""


def test_address_key_collapses_case_and_whitespace():
    a = {"lines": ["12  COLD  St"], "suburb": "Scoresby",
         "state": "VIC", "postcode": "3179"}
    b = {"lines": ["12 cold st"], "suburb": "scoresby",
         "state": "VIC", "postcode": "3179"}
    assert address_key(a) == address_key(b)


def test_extract_run_info_prefers_delivery_run():
    cons = {"details": {"runsheet": {"name": "RS-12", "date": "2026-06-03"},
                        "deliveryRun": {"name": "West-Tue"}},
            "customer": {"name": "Forage"}}
    rs_label, rs_date, dr_name, cust = extract_run_info(cons)
    assert rs_label == "RS-12 (2026-06-03)"
    assert rs_date == "2026-06-03"
    assert dr_name == "West-Tue"
    assert cust == "Forage"


def test_parse_consignment_run_is_delivery_run_then_runsheet():
    cons = {"details": {"deliver": {"address": {"lines": ["1 A St"],
            "suburb": "Geelong", "state": "VIC", "postcode": "3220"}},
            "runsheet": {"name": "RS-9", "date": "2026-06-02"},
            "deliveryRun": {"name": "Geelong-Mon"}}}
    rec = parse_consignment(cons)
    assert rec["run"] == "Geelong-Mon"
    assert rec["run_date"] == "2026-06-02"
    assert rec["address_key"] == "1 a st geelong vic 3220"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dispatch_addresses.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dispatch'`.

- [ ] **Step 3: Create the package and modules**

Create `src/dispatch/__init__.py`:

```python
"""Go Cold dispatch: read-only run prediction from CC consignment history."""
```

Create `src/dispatch/addresses.py`:

```python
"""Delivery-address normalisation for run prediction.

Lifted from scripts/extract_address_runs.py so the script and the
predictor share one implementation. The address_key is the dedup key
the history model is built and queried on.
"""
from __future__ import annotations

from typing import Any


def normalise_address(
    addr: dict[str, Any] | None,
) -> tuple[str, str, str, str, str, str]:
    """Return (key, full, street, suburb, state, postcode).

    key is a lower-cased, whitespace-collapsed join of street + suburb +
    state + postcode. Two addresses with the same key are the same
    delivery point even if CC formatting differs (case, trailing spaces).
    """
    if not addr:
        return ("", "", "", "", "", "")

    lines = addr.get("lines") or addr.get("addressLines") or []
    if isinstance(lines, str):
        street = lines.strip()
    elif isinstance(lines, list):
        street = ", ".join(str(x).strip() for x in lines if x)
    else:
        street = ""

    state_raw = addr.get("state") or {}
    if isinstance(state_raw, dict):
        state = state_raw.get("code") or state_raw.get("name") or ""
    else:
        state = str(state_raw)

    suburb = addr.get("suburb") or addr.get("city") or ""
    postcode = addr.get("postcode") or addr.get("postCode") or ""

    full = ", ".join(p for p in [street, suburb, state, postcode] if p)
    key = " ".join(
        " ".join(str(x).lower().split())
        for x in [street, suburb, state, postcode] if x
    )
    return (key, full, street, suburb, state, postcode)


def address_key(addr: dict[str, Any] | None) -> str:
    """Just the normalised dedup key for an address."""
    return normalise_address(addr)[0]
```

Create `src/dispatch/consignments.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dispatch_addresses.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/dispatch/__init__.py src/dispatch/addresses.py src/dispatch/consignments.py tests/test_dispatch_addresses.py
git commit -m "feat(dispatch): address normalisation + consignment parsing"
```

---

## Task 3: History model (recency-weighted)

**Files:**
- Create: `src/dispatch/history.py`
- Test: `tests/test_dispatch_history.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_dispatch_history.py`:

```python
from __future__ import annotations

from datetime import date

from dispatch.history import compute_run_history, load_model, save_model


def _rec(key, run, run_date):
    return {"address_key": key, "run": run, "run_date": run_date}


def test_recent_run_outranks_older_for_same_address():
    recs = [
        _rec("a", "West-Tue", "2026-06-03"),   # recent
        _rec("a", "West-Tue", "2026-06-01"),
        _rec("a", "Old-Run", "2026-04-01"),    # stale
    ]
    model = compute_run_history(recs, as_of=date(2026, 6, 5), half_life_days=30)
    cands = model.by_address["a"]
    assert cands[0].run == "West-Tue"
    assert cands[0].n == 2
    assert cands[0].score > cands[1].score
    assert cands[0].last_seen == date(2026, 6, 3)


def test_records_without_run_or_key_are_skipped():
    recs = [_rec("", "X", "2026-06-03"), _rec("a", "", "2026-06-03")]
    model = compute_run_history(recs, as_of=date(2026, 6, 5))
    assert model.by_address == {}


def test_model_round_trips_through_parquet(tmp_path):
    recs = [_rec("a", "West-Tue", "2026-06-03")]
    model = compute_run_history(recs, as_of=date(2026, 6, 5))
    p = tmp_path / "m.parquet"
    save_model(model, p)
    loaded = load_model(p)
    assert loaded.by_address["a"][0].run == "West-Tue"
    assert loaded.by_address["a"][0].last_seen == date(2026, 6, 3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dispatch_history.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dispatch.history'`.

- [ ] **Step 3: Create `src/dispatch/history.py`**

```python
"""Recency-weighted address→run history model."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunCandidate:
    run: str
    score: float          # recency-weighted sum of consignments
    n: int                # raw consignment count for this (address, run)
    last_seen: date | None


@dataclass(frozen=True)
class RunHistoryModel:
    by_address: dict[str, list[RunCandidate]]   # sorted best-first
    window_days: int
    half_life_days: int
    generated_at: datetime


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def compute_run_history(
    records: list[dict[str, Any]],
    *,
    as_of: date | None = None,
    window_days: int = 90,
    half_life_days: int = 30,
) -> RunHistoryModel:
    """Aggregate consignment records into per-address run candidates.

    Each record needs ``address_key``, ``run`` and ``run_date`` (ISO str).
    Weight per consignment = 0.5 ** (age_days / half_life_days), so recent
    runs dominate. Records with no key or no run are skipped.
    """
    as_of = as_of or date.today()
    # (address_key, run) -> {"score", "n", "last_seen"}
    acc: dict[tuple[str, str], dict[str, Any]] = {}
    for rec in records:
        key = rec.get("address_key") or ""
        run = rec.get("run") or ""
        if not key or not run:
            continue
        d = _parse_date(rec.get("run_date")) or as_of
        age = max((as_of - d).days, 0)
        weight = 0.5 ** (age / half_life_days)
        slot = acc.setdefault((key, run), {"score": 0.0, "n": 0, "last_seen": d})
        slot["score"] += weight
        slot["n"] += 1
        if slot["last_seen"] is None or d > slot["last_seen"]:
            slot["last_seen"] = d

    by_address: dict[str, list[RunCandidate]] = {}
    for (key, run), v in acc.items():
        by_address.setdefault(key, []).append(
            RunCandidate(run=run, score=v["score"], n=v["n"],
                         last_seen=v["last_seen"])
        )
    for key in by_address:
        by_address[key].sort(key=lambda c: c.score, reverse=True)

    log.info("history model: %d addresses, %d (address,run) pairs",
             len(by_address), len(acc))
    return RunHistoryModel(
        by_address=by_address, window_days=window_days,
        half_life_days=half_life_days,
        generated_at=datetime.now(),
    )


def save_model(model: RunHistoryModel, path: Path) -> None:
    """Persist the model to parquet (one row per address/run candidate)."""
    rows = [
        {"address_key": key, "run": c.run, "score": c.score, "n": c.n,
         "last_seen": c.last_seen.isoformat() if c.last_seen else None}
        for key, cands in model.by_address.items() for c in cands
    ]
    df = pd.DataFrame(rows, columns=["address_key", "run", "score", "n",
                                     "last_seen"])
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def load_model(path: Path) -> RunHistoryModel:
    """Rebuild a model from a parquet written by save_model."""
    df = pd.read_parquet(path)
    by_address: dict[str, list[RunCandidate]] = {}
    for row in df.itertuples(index=False):
        by_address.setdefault(row.address_key, []).append(
            RunCandidate(run=row.run, score=float(row.score), n=int(row.n),
                         last_seen=_parse_date(row.last_seen))
        )
    for key in by_address:
        by_address[key].sort(key=lambda c: c.score, reverse=True)
    return RunHistoryModel(by_address=by_address, window_days=0,
                           half_life_days=0, generated_at=datetime.now())
```

Note: `as_of` and `datetime.now()` are real-time calls — fine in library
code (the harness's no-`Date.now()` rule is workflow-script specific).
Tests always pass an explicit `as_of` for determinism.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dispatch_history.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/dispatch/history.py tests/test_dispatch_history.py
git commit -m "feat(dispatch): recency-weighted run-history model + parquet cache"
```

---

## Task 4: Zone fallback config (TOML)

**Files:**
- Create: `config/dispatch_zones.toml`
- Create: `src/dispatch/zones.py`
- Test: `tests/test_dispatch_zones.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_dispatch_zones.py`:

```python
from __future__ import annotations

from pathlib import Path

from dispatch.zones import assign_zone, load_zone_config

_TOML = """
fallback = "Unzoned"

[[zone]]
name = "Metro Melbourne"
state = "VIC"
postcodes = ["3000-3207"]

[[zone]]
name = "Geelong"
state = "VIC"
postcodes = ["3211-3242"]

[[zone]]
name = "Interstate NSW"
state = "NSW"
"""


def _cfg(tmp_path: Path):
    p = tmp_path / "z.toml"
    p.write_text(_TOML)
    return load_zone_config(p)


def test_postcode_range_match(tmp_path):
    cfg = _cfg(tmp_path)
    assert assign_zone("VIC", "3179", cfg) == "Metro Melbourne"
    assert assign_zone("VIC", "3220", cfg) == "Geelong"


def test_state_only_zone_matches_without_postcode(tmp_path):
    cfg = _cfg(tmp_path)
    assert assign_zone("NSW", "2000", cfg) == "Interstate NSW"


def test_no_match_returns_fallback(tmp_path):
    cfg = _cfg(tmp_path)
    assert assign_zone("QLD", "4000", cfg) == "Unzoned"
    assert assign_zone("VIC", "3999", cfg) == "Unzoned"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dispatch_zones.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dispatch.zones'`.

- [ ] **Step 3: Create config + module**

Create `config/dispatch_zones.toml`:

```toml
# Dispatch zone fallback — used ONLY for delivery addresses with no run
# history. Operator-editable. First matching zone wins (order matters).
# postcodes: list of exact strings ("3210") or inclusive ranges ("3000-3207").
# A zone with no postcodes matches on state alone.

fallback = "Unzoned"

[[zone]]
name = "Metro Melbourne"
state = "VIC"
postcodes = ["3000-3207"]

[[zone]]
name = "Geelong"
state = "VIC"
postcodes = ["3211-3242"]

[[zone]]
name = "Regional VIC"
state = "VIC"
postcodes = ["3210", "3243-3999"]

[[zone]]
name = "Interstate NSW"
state = "NSW"

[[zone]]
name = "Interstate QLD"
state = "QLD"

[[zone]]
name = "Interstate SA"
state = "SA"
```

Create `src/dispatch/zones.py`:

```python
"""Zone fallback for delivery addresses with no run history (TOML config)."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ZoneRule:
    name: str
    state: str | None
    postcode_ranges: list[tuple[int, int]]   # inclusive; exact = (n, n)


@dataclass(frozen=True)
class ZoneConfig:
    zones: list[ZoneRule]
    fallback: str


def _parse_range(token: str) -> tuple[int, int]:
    token = str(token).strip()
    if "-" in token:
        lo, hi = token.split("-", 1)
        return (int(lo), int(hi))
    return (int(token), int(token))


def load_zone_config(path: Path) -> ZoneConfig:
    """Load zone rules from a TOML file (stdlib tomllib)."""
    data = tomllib.loads(Path(path).read_text())
    zones: list[ZoneRule] = []
    for z in data.get("zone", []):
        ranges = [_parse_range(t) for t in z.get("postcodes", [])]
        zones.append(ZoneRule(name=z["name"], state=z.get("state"),
                              postcode_ranges=ranges))
    return ZoneConfig(zones=zones, fallback=data.get("fallback", "Unzoned"))


def assign_zone(state: str | None, postcode: str | None,
                config: ZoneConfig) -> str:
    """First matching zone name, else the fallback.

    A zone with postcode ranges requires the postcode to fall in one range
    AND (if the zone sets a state) the state to match. A zone with no ranges
    matches on state alone.
    """
    try:
        pc = int(str(postcode).strip()) if postcode else None
    except ValueError:
        pc = None
    for z in config.zones:
        if z.state and state and z.state != state:
            continue
        if z.postcode_ranges:
            if pc is not None and any(lo <= pc <= hi
                                      for lo, hi in z.postcode_ranges):
                return z.name
            continue
        if z.state and state == z.state:
            return z.name
    return config.fallback
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dispatch_zones.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add config/dispatch_zones.toml src/dispatch/zones.py tests/test_dispatch_zones.py
git commit -m "feat(dispatch): TOML zone fallback for unknown addresses"
```

---

## Task 5: Prediction engine

**Files:**
- Create: `src/dispatch/predict.py`
- Test: `tests/test_dispatch_predict.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_dispatch_predict.py`:

```python
from __future__ import annotations

from datetime import date

from dispatch.history import RunCandidate, RunHistoryModel
from dispatch.predict import predict_runs
from dispatch.zones import ZoneConfig, ZoneRule


def _model(by_address):
    from datetime import datetime
    return RunHistoryModel(by_address=by_address, window_days=90,
                           half_life_days=30, generated_at=datetime(2026, 6, 5))


_ZONES = ZoneConfig(zones=[ZoneRule("Metro Melbourne", "VIC", [(3000, 3207)])],
                    fallback="Unzoned")


def _order(so_id, suburb, postcode, state="VIC"):
    return {"so_id": so_id, "so_ref": f"SO-{so_id}",
            "address": {"lines": [f"{so_id} A St"], "suburb": suburb,
                        "state": state, "postcode": postcode}}


def test_stable_address_goes_to_assignments():
    key = "1 a st scoresby vic 3179"
    model = _model({key: [RunCandidate("West-Tue", 9.0, 9, date(2026, 6, 3))]})
    plan = predict_runs([_order("1", "Scoresby", "3179")], model, _ZONES,
                        as_of=date(2026, 6, 5))
    assert len(plan.assignments) == 1
    a = plan.assignments[0]
    assert a.predicted_run == "West-Tue"
    assert a.flag == "stable"
    assert a.confidence == 1.0
    assert plan.review == []


def test_mixed_address_goes_to_review_with_alternatives():
    key = "2 a st scoresby vic 3179"
    model = _model({key: [RunCandidate("West-Tue", 5.0, 5, date(2026, 6, 3)),
                          RunCandidate("West-Wed", 4.0, 4, date(2026, 6, 2))]})
    plan = predict_runs([_order("2", "Scoresby", "3179")], model, _ZONES,
                        as_of=date(2026, 6, 5))
    assert plan.assignments == []
    r = plan.review[0]
    assert r.flag == "mixed"
    assert r.predicted_run == "West-Tue"
    assert "West-Wed" in r.alternatives


def test_new_address_uses_zone_fallback_and_review():
    model = _model({})
    plan = predict_runs([_order("3", "Scoresby", "3179")], model, _ZONES,
                        as_of=date(2026, 6, 5))
    r = plan.review[0]
    assert r.flag == "new_address"
    assert r.predicted_run is None
    assert "Metro Melbourne" in r.reason


def test_stale_address_flagged():
    key = "4 a st scoresby vic 3179"
    model = _model({key: [RunCandidate("West-Tue", 1.0, 1, date(2026, 4, 1))]})
    plan = predict_runs([_order("4", "Scoresby", "3179")], model, _ZONES,
                        as_of=date(2026, 6, 5), stale_days=30)
    assert plan.review[0].flag == "stale"


def test_missing_address_flagged_no_address():
    order = {"so_id": "5", "so_ref": "SO-5", "address": None}
    plan = predict_runs([order], _model({}), _ZONES, as_of=date(2026, 6, 5))
    assert plan.review[0].flag == "no_address"


def test_carrier_order_split_out():
    order = _order("6", "Scoresby", "3179")
    order["carrier"] = "TollExpress"
    plan = predict_runs([order], _model({}), _ZONES, as_of=date(2026, 6, 5),
                        carrier_rule=lambda o: o.get("carrier"))
    assert "TollExpress" in plan.carriers
    assert plan.assignments == [] and plan.review == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dispatch_predict.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dispatch.predict'`.

- [ ] **Step 3: Create `src/dispatch/predict.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dispatch_predict.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/dispatch/predict.py tests/test_dispatch_predict.py
git commit -m "feat(dispatch): predict_runs assignment/carrier/review buckets"
```

---

## Task 6: Output writer

**Files:**
- Create: `src/dispatch/output.py`
- Test: `tests/test_dispatch_output.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_dispatch_output.py`:

```python
from __future__ import annotations

import pandas as pd

from dispatch.output import write_dispatch_plan
from dispatch.predict import DispatchPlan, RunAssignment


def _plan():
    af = {"full_address": "1 A St, Scoresby VIC 3179", "street": "1 A St",
          "suburb": "Scoresby", "state": "VIC", "postcode": "3179"}
    return DispatchPlan(
        assignments=[RunAssignment("1", "SO-1", "West-Tue", 1.0, "stable",
                                   "reason", [], af)],
        carriers={"TollExpress": [RunAssignment("2", "SO-2", None, 1.0,
                                                 "carrier", "carrier", [], af)]},
        review=[RunAssignment("3", "SO-3", None, 0.0, "new_address",
                              "no history; zone=Metro Melbourne", [], af)],
    )


def test_writes_all_outputs(tmp_path):
    write_dispatch_plan(_plan(), tmp_path)
    assert (tmp_path / "suggested_runs.csv").exists()
    assert (tmp_path / "review.csv").exists()
    assert (tmp_path / "summary.md").exists()
    assert (tmp_path / "carriers_TollExpress.csv").exists()
    assert (tmp_path / "run_West-Tue.xlsx").exists()

    df = pd.read_csv(tmp_path / "suggested_runs.csv")
    assert list(df["predicted_run"]) == ["West-Tue"]
    assert "confidence" in df.columns


def test_summary_flags_review_count(tmp_path):
    write_dispatch_plan(_plan(), tmp_path)
    text = (tmp_path / "summary.md").read_text()
    assert "1" in text and "review" in text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dispatch_output.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dispatch.output'`.

- [ ] **Step 3: Create `src/dispatch/output.py`**

```python
"""Write a DispatchPlan to operator-facing files."""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

from .predict import DispatchPlan, RunAssignment

log = logging.getLogger(__name__)

_ASSIGN_COLS = ["so_ref", "so_id", "predicted_run", "confidence", "flag",
                "reason", "alternatives", "full_address", "street", "suburb",
                "state", "postcode"]


def _rows(items: list[RunAssignment]) -> list[dict]:
    out = []
    for a in items:
        out.append({
            "so_ref": a.so_ref, "so_id": a.so_id,
            "predicted_run": a.predicted_run,
            "confidence": round(a.confidence, 3), "flag": a.flag,
            "reason": a.reason, "alternatives": ", ".join(a.alternatives),
            "full_address": a.address.get("full_address", ""),
            "street": a.address.get("street", ""),
            "suburb": a.address.get("suburb", ""),
            "state": a.address.get("state", ""),
            "postcode": a.address.get("postcode", ""),
        })
    return out


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "unnamed"


def write_dispatch_plan(plan: DispatchPlan, out_dir: Path) -> None:
    """Write suggested_runs.csv, per-run xlsx, carrier CSVs, review.csv, summary."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    assign_df = pd.DataFrame(_rows(plan.assignments), columns=_ASSIGN_COLS)
    assign_df.to_csv(out_dir / "suggested_runs.csv", index=False)

    review_df = pd.DataFrame(_rows(plan.review), columns=_ASSIGN_COLS)
    review_df.to_csv(out_dir / "review.csv", index=False)

    for carrier, items in plan.carriers.items():
        pd.DataFrame(_rows(items), columns=_ASSIGN_COLS).to_csv(
            out_dir / f"carriers_{_safe(carrier)}.csv", index=False)

    # One manifest per predicted run (own-fleet assignments only).
    if not assign_df.empty:
        for run, g in assign_df.groupby("predicted_run", sort=True):
            g.sort_values("postcode").to_excel(
                out_dir / f"run_{_safe(str(run))}.xlsx",
                index=False, sheet_name="run")

    n_runs = assign_df["predicted_run"].nunique() if not assign_df.empty else 0
    n_carrier = sum(len(v) for v in plan.carriers.values())
    summary = [
        "# Dispatch run prediction summary", "",
        f"- Own-fleet assignments: {len(plan.assignments)} across {n_runs} runs",
        f"- Carrier orders: {n_carrier} across {len(plan.carriers)} carriers",
        f"- **Review queue: {len(plan.review)}**"
        + ("  ← needs dispatcher attention" if plan.review else ""),
        "",
    ]
    if not assign_df.empty:
        summary.append("## Assignments per run")
        for run, g in assign_df.groupby("predicted_run", sort=True):
            summary.append(f"- {run}: {len(g)} stops")
    (out_dir / "summary.md").write_text("\n".join(summary) + "\n")
    log.info("wrote dispatch outputs to %s", out_dir)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dispatch_output.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/dispatch/output.py tests/test_dispatch_output.py
git commit -m "feat(dispatch): output writer (CSVs, run manifests, summary)"
```

---

## Task 7: Write-seam sinks

**Files:**
- Create: `src/dispatch/sinks.py`
- Test: `tests/test_dispatch_sinks.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_dispatch_sinks.py`:

```python
from __future__ import annotations

import pytest

from dispatch.predict import DispatchPlan, RunAssignment
from dispatch.sinks import CartonCloudSink, FileSink


def _plan():
    return DispatchPlan(assignments=[RunAssignment(
        "1", "SO-1", "West-Tue", 1.0, "stable", "reason", [], {})])


def test_file_sink_writes_and_reports_ok(tmp_path):
    results = FileSink(tmp_path).apply(_plan())
    assert (tmp_path / "suggested_runs.csv").exists()
    assert all(r.ok for r in results)


def test_cartoncloud_sink_refuses_without_both_flags():
    # Default: read-only — must refuse.
    with pytest.raises(PermissionError):
        CartonCloudSink(write_enabled=False, dispatch_write_approved=False).apply(_plan())
    with pytest.raises(PermissionError):
        CartonCloudSink(write_enabled=True, dispatch_write_approved=False).apply(_plan())
    with pytest.raises(PermissionError):
        CartonCloudSink(write_enabled=False, dispatch_write_approved=True).apply(_plan())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dispatch_sinks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dispatch.sinks'`.

- [ ] **Step 3: Create `src/dispatch/sinks.py`**

```python
"""Dispatch write seam.

FileSink is the v1 destination (writes the review files). CartonCloudSink
is built so a future write-back is one tested adapter — but it refuses to
act unless BOTH write_enabled AND dispatch_write_approved are set, neither
of which is true in v1. CartonCloud is read-only.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .output import write_dispatch_plan
from .predict import DispatchPlan


@dataclass(frozen=True)
class AssignResult:
    so_id: str
    ok: bool
    detail: str


class DispatchSink(Protocol):
    def apply(self, plan: DispatchPlan) -> list[AssignResult]:
        ...


class FileSink:
    """v1 sink: write the plan to operator-facing files."""

    def __init__(self, out_dir: Path):
        self.out_dir = Path(out_dir)

    def apply(self, plan: DispatchPlan) -> list[AssignResult]:
        write_dispatch_plan(plan, self.out_dir)
        return [AssignResult(a.so_id, True, f"written → {a.predicted_run}")
                for a in plan.assignments]


class CartonCloudSink:
    """Future write-back. Refuses to act in v1 (CC stays read-only)."""

    def __init__(self, *, write_enabled: bool = False,
                 dispatch_write_approved: bool = False):
        self.write_enabled = write_enabled
        self.dispatch_write_approved = dispatch_write_approved

    def apply(self, plan: DispatchPlan) -> list[AssignResult]:
        if not (self.write_enabled and self.dispatch_write_approved):
            raise PermissionError(
                "CC dispatch write-back not approved; CartonCloud is "
                "read-only. Both write_enabled and dispatch_write_approved "
                "must be set, and the SAP B1 boundary cleared, first.")
        raise NotImplementedError(  # pragma: no cover - not built in v1
            "CartonCloudSink write path is intentionally unbuilt in v1")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dispatch_sinks.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/dispatch/sinks.py tests/test_dispatch_sinks.py
git commit -m "feat(dispatch): write-seam sinks (FileSink now, CartonCloudSink refuses)"
```

---

## Task 8: Orchestrator + re-point existing script

**Files:**
- Create: `scripts/build_dispatch.py`
- Modify: `scripts/extract_address_runs.py` (use lifted library + `search_consignments`)
- Test: `tests/test_build_dispatch.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/test_build_dispatch.py`:

```python
"""Integration: orchestrator produces a plan from fixture pulls (offline)."""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_orchestrator():
    p = ROOT / "scripts" / "build_dispatch.py"
    spec = importlib.util.spec_from_file_location("_build_dispatch", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CONSIGNMENTS = [
    {"details": {"deliver": {"address": {"lines": ["1 A St"],
     "suburb": "Scoresby", "state": "VIC", "postcode": "3179"}},
     "runsheet": {"name": "RS-1", "date": "2026-06-03"},
     "deliveryRun": {"name": "West-Tue"}}}
    for _ in range(3)
]
_OPEN_ORDERS = [
    {"id": "SO9", "references": {"customer": "SO-9"},
     "details": {"deliver": {"address": {"lines": ["1 A St"],
      "suburb": "Scoresby", "state": "VIC", "postcode": "3179"}}}}
]


def test_run_dispatch_builds_plan(monkeypatch, tmp_path):
    mod = _load_orchestrator()
    monkeypatch.setattr(mod, "search_consignments",
                        lambda *a, **k: iter(_CONSIGNMENTS))
    monkeypatch.setattr(mod, "search_outbound_orders",
                        lambda *a, **k: iter(_OPEN_ORDERS))
    monkeypatch.setattr(mod, "CartonCloudClient",
                        type("C", (), {"from_env": staticmethod(lambda: object())}))

    plan = mod.run_dispatch(
        client=object(),
        zones_path=ROOT / "config" / "dispatch_zones.toml",
        history_days=90, as_of=date(2026, 6, 5))

    assert len(plan.assignments) == 1
    assert plan.assignments[0].predicted_run == "West-Tue"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_build_dispatch.py -v`
Expected: FAIL (no `scripts/build_dispatch.py`).

- [ ] **Step 3: Create `scripts/build_dispatch.py`**

```python
"""Build today's dispatch run predictions from CC consignment history.

READ-ONLY. learn → predict → write files. CartonCloud is never mutated.

    python3 scripts/build_dispatch.py                 # learn + predict
    python3 scripts/build_dispatch.py --skip-learn    # reuse cached model
    python3 scripts/build_dispatch.py --history-days 90
    python3 scripts/build_dispatch.py --dry-run       # summary only, no files
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from cc_client import (  # noqa: E402
    CartonCloudClient,
    search_consignments,
    search_outbound_orders,
)
from dispatch.consignments import parse_consignment  # noqa: E402
from dispatch.history import (  # noqa: E402
    compute_run_history,
    load_model,
    save_model,
)
from dispatch.predict import DispatchPlan, predict_runs  # noqa: E402
from dispatch.sinks import FileSink  # noqa: E402
from dispatch.zones import load_zone_config  # noqa: E402

log = logging.getLogger("build_dispatch")

DEFAULT_STATUS = ["AWAITING_PICK_AND_PACK", "PACKED"]
_MODEL_DIR = ROOT / "data" / "dispatch"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    import os
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _open_order_stops(client) -> list[dict]:
    """Pull open orders and reduce to {so_id, so_ref, address}."""
    stops = []
    for o in search_outbound_orders(client, status=DEFAULT_STATUS):
        addr = ((o.get("details") or {}).get("deliver") or {}).get("address")
        stops.append({"so_id": o.get("id"),
                      "so_ref": (o.get("references") or {}).get("customer"),
                      "address": addr})
    return stops


def run_dispatch(*, client, zones_path: Path, history_days: int,
                 as_of: date | None = None, model_path: Path | None = None,
                 skip_learn: bool = False) -> DispatchPlan:
    """Learn (or load) the model, pull open orders, predict. Returns the plan."""
    as_of = as_of or date.today()
    if skip_learn and model_path and model_path.exists():
        model = load_model(model_path)
        log.info("loaded cached model from %s", model_path)
    else:
        cutoff = (as_of - timedelta(days=history_days)).isoformat()
        records = [parse_consignment(c)
                   for c in search_consignments(client, run_sheet_date_from=cutoff)]
        model = compute_run_history(records, as_of=as_of,
                                    window_days=history_days)
        if model_path:
            save_model(model, model_path)
            log.info("cached model → %s", model_path)

    zones = load_zone_config(zones_path)
    stops = _open_order_stops(client)
    return predict_runs(stops, model, zones, as_of=as_of)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--history-days", type=int, default=90)
    ap.add_argument("--skip-learn", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--zones-config", type=Path,
                    default=ROOT / "config" / "dispatch_zones.toml")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    _load_dotenv(ROOT / ".env")
    client = CartonCloudClient.from_env()   # write_enabled=False
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = _MODEL_DIR / "run_history.parquet"

    plan = run_dispatch(client=client, zones_path=args.zones_config,
                        history_days=args.history_days,
                        model_path=model_path, skip_learn=args.skip_learn)

    print(f"assignments={len(plan.assignments)} "
          f"carriers={sum(len(v) for v in plan.carriers.values())} "
          f"review={len(plan.review)}")

    if args.dry_run:
        print("(dry run — no files written)")
        return 0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "data" / "processed" / "dispatch" / stamp
    FileSink(out_dir).apply(plan)
    print(f"wrote → {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run integration test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_build_dispatch.py -v`
Expected: PASS.

- [ ] **Step 5: Re-point `scripts/extract_address_runs.py`**

In `scripts/extract_address_runs.py`:
1. Change `from src.cc_client.client import CartonCloudClient` to add the
   src path and import from the package, matching `build_dispatch.py`:
   ```python
   ROOT = Path(__file__).resolve().parent.parent
   sys.path.insert(0, str(ROOT / "src"))
   from cc_client import CartonCloudClient, search_consignments  # noqa: E402
   from dispatch.addresses import normalise_address  # noqa: E402
   from dispatch.consignments import extract_run_info  # noqa: E402
   ```
2. Delete the script's local `normalise_address` and `extract_run_info`
   definitions (now imported from the library).
3. Replace the `client.search_consignments(condition["condition"])` loop
   with the package helper:
   ```python
   cutoff = (date.today() - timedelta(days=args.days)).isoformat()
   for cons in search_consignments(client, run_sheet_date_from=cutoff):
   ```
   and delete the now-unused `build_condition`.

Run: `.venv/bin/python -m pytest -q` (full suite) and
`.venv/bin/python -c "import ast; ast.parse(open('scripts/extract_address_runs.py').read())"`
Expected: suite PASS, script parses.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_dispatch.py scripts/extract_address_runs.py tests/test_build_dispatch.py
git commit -m "feat(dispatch): build_dispatch orchestrator + re-point address-runs script"
```

---

## Task 9: Docs + full-suite verification

**Files:**
- Modify: `CLAUDE.md` (Current capabilities + Open work)
- Modify: `src/dispatch/__init__.py` (export the public API)

- [ ] **Step 1: Export the package API**

In `src/dispatch/__init__.py`, add:

```python
from .predict import DispatchPlan, RunAssignment, predict_runs
from .history import RunHistoryModel, compute_run_history
from .sinks import FileSink, CartonCloudSink
from .zones import load_zone_config, assign_zone

__all__ = [
    "DispatchPlan", "RunAssignment", "predict_runs",
    "RunHistoryModel", "compute_run_history",
    "FileSink", "CartonCloudSink",
    "load_zone_config", "assign_zone",
]
```

- [ ] **Step 2: Update CLAUDE.md**

Under "Current capabilities", add a bullet:

```
- `src/dispatch/`: read-only delivery-run prediction — learns habitual
  address→run pairings from CC consignment history, predicts today's open
  orders onto runs (confidence + reason), splits carriers, writes review
  files. Orchestrator: `scripts/build_dispatch.py`. CC stays read-only;
  `CartonCloudSink` write-back is built but refuses to act (v1).
```

Under "Open work", note: "Dispatch v1 (predict-to-run) built; v2 = stop
sequencing; write-back pending SAP B1 boundary."

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all PASS (existing 73 + new dispatch tests).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md src/dispatch/__init__.py
git commit -m "docs(dispatch): record v1 capability + export package API"
```

---

## Done criteria

- `search_consignments` read path exists, tested, and the live scope probe
  (Task 1 Step 6) returned data (or the scope gap was raised with the operator).
- `build_dispatch.py --dry-run` against real CC prints non-zero assignments
  for a normal day of open orders.
- Full test suite green.
- No CC writes anywhere; `CartonCloudSink` refuses; `write_enabled` never set.
- Shadow-mode rollout: diff predictions vs the dispatcher's actual choices
  for ~2 weeks before considering the web console (B) or write-back.
```
