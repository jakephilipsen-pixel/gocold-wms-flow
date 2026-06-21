"""W3 — cc-write-customer-guard: the §0 guard rail, the most safety-critical check.

Sandbox and live Forage share ONE CC tenant (WRITE_ENABLEMENT_PLAN §2.3): the same
OAuth2 client that can PATCH a sandbox product can physically reach a live Forage
product. There is no tenant boundary protecting live data. The customer-id allow-list
is the ONLY thing standing between a test write and a real Forage product — so this
guard must refuse **independently of every other gate**.

The non-negotiable property under test: a target carrying the live Forage id is
**refused even with every other gate open** (write_enabled=True, a valid auth token,
approved=True). Every other gate is open; this one still stops it.

Also covered: sandbox id passes; an unknown id refuses; an empty/blank allow-list
still refuses live (fail-closed — empty never means allow-all); the offending id is
logged loudly on refusal.

GROUND_TRUTH caveat (§5 / WRITE_ENABLEMENT_PLAN §2.3): this guard gates by *customer*,
so an allow-listed sandbox customer admits ALL 1111 of its products — only 46 active
(`s`-prefixed), the other ~1065 inactive/archived ZZ* legacy SKUs. "Allow-listed" is
NOT "intended target": active-status is M-DIMS-3's concern, NOT this guard's. The guard
proves a target's *customer* cleared the boundary, nothing about the product itself.

Fully offline — no client, no network, no CC write.
"""
from __future__ import annotations

import logging

import pytest

from cc_client.write_customer_guard import (
    verify_customer_allowed,
    CartonCloudCustomerNotAllowed,
)
from cc_client.write_config import WriteConfig, SANDBOX_CUSTOMER_ID

# The live customer id MUST NOT appear in the production module. Declared here (as W0
# did) so a test failure is the alarm if it ever leaks into the guard's source.
LIVE_FORAGE_CUSTOMER_ID = "d4810e1e-91ab-43ed-b68e-b72bd858b122"


# ---------- the non-negotiable test: live refused with every other gate open ----------

def test_live_forage_refused_even_with_every_other_gate_open():
    # Every OTHER gate is wide open: write enabled, a valid secret configured, and the
    # caller "approved". The customer guard alone must still refuse the live target.
    cfg = WriteConfig(
        write_enabled=True,
        write_secret="a-valid-write-secret",
    )
    approved = True
    assert cfg.write_enabled is True
    assert cfg.write_secret is not None
    assert approved is True

    with pytest.raises(CartonCloudCustomerNotAllowed):
        verify_customer_allowed(LIVE_FORAGE_CUSTOMER_ID, cfg)


def test_live_forage_refused_under_default_config():
    # The default config (closed) also refuses live — live is absent from the default.
    with pytest.raises(CartonCloudCustomerNotAllowed):
        verify_customer_allowed(LIVE_FORAGE_CUSTOMER_ID, WriteConfig())


# ---------- M-DIMS-5a: the guard re-checks the live target against the promotion flag ----------

def test_live_forage_allowed_only_when_promotion_armed():
    # The W3 guard gates the live id by the CC_LIVE_PROMOTION flag (via is_customer_allowed):
    # refused when unset, cleared when armed. This is the per-write re-check that makes the
    # named live gate real — even at write time, not just at run start.
    unarmed = WriteConfig(write_enabled=True, write_secret="valid", live_promotion=False)
    armed = WriteConfig(write_enabled=True, write_secret="valid", live_promotion=True)

    with pytest.raises(CartonCloudCustomerNotAllowed):
        verify_customer_allowed(LIVE_FORAGE_CUSTOMER_ID, unarmed)
    assert verify_customer_allowed(LIVE_FORAGE_CUSTOMER_ID, armed) is None


def test_promotion_flag_does_not_widen_to_other_customers():
    # Arming live promotion admits ONLY the live Forage id — not some other unknown customer.
    armed = WriteConfig(write_enabled=True, write_secret="valid", live_promotion=True)
    with pytest.raises(CartonCloudCustomerNotAllowed):
        verify_customer_allowed("00000000-0000-0000-0000-000000000000", armed)


# ---------- sandbox passes, unknown refuses ----------

def test_sandbox_customer_passes():
    # Returns None (no exception) — the only allow path.
    assert verify_customer_allowed(SANDBOX_CUSTOMER_ID, WriteConfig()) is None


def test_unknown_customer_refused():
    with pytest.raises(CartonCloudCustomerNotAllowed):
        verify_customer_allowed("00000000-0000-0000-0000-000000000000", WriteConfig())


# ---------- fail-closed: empty/blank allow-list still refuses live ----------

def test_empty_allowlist_still_refuses_live():
    # An empty allow-list must never mean "allow everything". Fail closed.
    cfg = WriteConfig(
        write_enabled=True,
        write_secret="a-valid-write-secret",
        customer_allowlist=frozenset(),
    )
    with pytest.raises(CartonCloudCustomerNotAllowed):
        verify_customer_allowed(LIVE_FORAGE_CUSTOMER_ID, cfg)


def test_empty_allowlist_refuses_sandbox_too():
    # With nothing allow-listed, even the sandbox is refused — positive allow-list only.
    cfg = WriteConfig(customer_allowlist=frozenset())
    with pytest.raises(CartonCloudCustomerNotAllowed):
        verify_customer_allowed(SANDBOX_CUSTOMER_ID, cfg)


def test_blank_or_none_customer_id_refused():
    # A missing/blank resolved customer id can never clear a positive allow-list.
    cfg = WriteConfig()
    for bad in ("", "   ", None):
        with pytest.raises(CartonCloudCustomerNotAllowed):
            verify_customer_allowed(bad, cfg)


# ---------- refuses loudly: the offending id is logged ----------

def test_offending_customer_id_is_logged(caplog):
    with caplog.at_level(logging.WARNING, logger="cc_client.write_customer_guard"):
        with pytest.raises(CartonCloudCustomerNotAllowed):
            verify_customer_allowed(LIVE_FORAGE_CUSTOMER_ID, WriteConfig())
    assert LIVE_FORAGE_CUSTOMER_ID in caplog.text, (
        "the offending customer id must be logged on refusal"
    )


def test_refusal_message_names_the_offending_id():
    with pytest.raises(CartonCloudCustomerNotAllowed) as exc:
        verify_customer_allowed(LIVE_FORAGE_CUSTOMER_ID, WriteConfig())
    assert LIVE_FORAGE_CUSTOMER_ID in str(exc.value)


# ---------- typed: subclass of CartonCloudError ----------

def test_exception_subclasses_carton_cloud_error():
    from cc_client.client import CartonCloudError

    assert issubclass(CartonCloudCustomerNotAllowed, CartonCloudError)


# ---------- composition: this guard is independent of authz (W2) ----------

def test_guard_is_independent_of_authz_gate():
    # The surface composes guard -> authz -> _mutate. This guard knows nothing about
    # tokens: it refuses live purely on customer id, regardless of any auth state.
    with pytest.raises(CartonCloudCustomerNotAllowed):
        verify_customer_allowed(
            LIVE_FORAGE_CUSTOMER_ID,
            WriteConfig(write_enabled=True, write_secret="valid"),
        )


# ---------- GROUND_TRUTH caveat: allow-listed != intended target ----------

def test_allowlisted_customer_admits_all_its_products_caveat():
    # GROUND_TRUTH §5 / WRITE_ENABLEMENT_PLAN §2.3: the guard gates by CUSTOMER, not by
    # active-status. An allow-listed sandbox customer admits ALL 1111 of its products
    # (only 46 active s-prefixed; ~1065 inactive ZZ*). The guard cannot and must not
    # distinguish an active SKU from an inactive one — both share the sandbox customer
    # id, so both clear this guard. Active-status is M-DIMS-3's concern, NOT this guard's.
    cfg = WriteConfig()  # default: sandbox allow-listed
    active_sku_customer = SANDBOX_CUSTOMER_ID      # e.g. an `s`-prefixed active SKU
    inactive_zz_sku_customer = SANDBOX_CUSTOMER_ID  # e.g. a ZZ* archived legacy SKU

    # Both clear THIS guard — it only proves the customer cleared the boundary.
    assert verify_customer_allowed(active_sku_customer, cfg) is None
    assert verify_customer_allowed(inactive_zz_sku_customer, cfg) is None


# ---------- package export ----------

def test_exported_from_package():
    from cc_client import (
        verify_customer_allowed as pkg_verify,
        CartonCloudCustomerNotAllowed as PkgNotAllowed,
    )

    assert pkg_verify is verify_customer_allowed
    assert PkgNotAllowed is CartonCloudCustomerNotAllowed
