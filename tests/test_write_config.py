"""W0 — write-config: the config surface for CC write enablement.

This is the first module of the write spine (WRITE_ENABLEMENT_PLAN §2). It holds
NO mutating CC verb — it only decides, from env, whether writes are permitted and
which customers they may target. The non-negotiable property under test: the
defaults are *closed* — write disabled, allow-list = sandbox only, live Forage
absent — so that merely importing/constructing the config can never point a write
at real Forage data.

Fully offline: no network, no CC client.
"""
from __future__ import annotations

import pytest

from cc_client.write_config import WriteConfig, SANDBOX_CUSTOMER_ID


def test_exported_from_package_root():
    # W1+ depend on `from cc_client import WriteConfig`.
    from cc_client import WriteConfig as PkgWriteConfig
    from cc_client import SANDBOX_CUSTOMER_ID as pkg_sandbox_id

    assert PkgWriteConfig is WriteConfig
    assert pkg_sandbox_id == SANDBOX_CUSTOMER_ID

# The live customer id MUST NOT appear in any default. Declared here (not in the
# production module) so a test failure is the alarm if it ever leaks into defaults.
LIVE_FORAGE_CUSTOMER_ID = "d4810e1e-91ab-43ed-b68e-b72bd858b122"

CC_WRITE_VARS = (
    "CC_WRITE_ENABLED", "CC_WRITE_SECRET", "CC_WRITE_CUSTOMER_ALLOWLIST", "CC_LIVE_PROMOTION",
)


@pytest.fixture
def clean_env(monkeypatch):
    """No CC_WRITE_* vars set — exercises the bare defaults."""
    for var in CC_WRITE_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


# ---------- defaults are closed ----------

def test_default_write_disabled():
    assert WriteConfig().write_enabled is False


def test_default_allowlist_is_sandbox_only():
    assert WriteConfig().customer_allowlist == frozenset({SANDBOX_CUSTOMER_ID})


def test_live_forage_absent_from_default_allowlist():
    assert LIVE_FORAGE_CUSTOMER_ID not in WriteConfig().customer_allowlist


def test_default_secret_is_none():
    assert WriteConfig().write_secret is None


def test_sandbox_id_constant_is_the_verified_one():
    assert SANDBOX_CUSTOMER_ID == "a8dab3f2-defa-433e-87a0-01dee48a2286"


# ---------- from_env: empty env stays closed ----------

def test_from_env_empty_is_closed(clean_env):
    cfg = WriteConfig.from_env()
    assert cfg.write_enabled is False
    assert cfg.write_secret is None
    assert cfg.customer_allowlist == frozenset({SANDBOX_CUSTOMER_ID})
    assert LIVE_FORAGE_CUSTOMER_ID not in cfg.customer_allowlist


# ---------- from_env: write_enabled parsing (only literal true opens it) ----------

@pytest.mark.parametrize("value", ["true", "TRUE", "True", " true "])
def test_from_env_enables_write_on_true(clean_env, value):
    clean_env.setenv("CC_WRITE_ENABLED", value)
    assert WriteConfig.from_env().write_enabled is True


@pytest.mark.parametrize("value", ["false", "0", "1", "yes", "", "no", "on"])
def test_from_env_keeps_write_closed_unless_true(clean_env, value):
    clean_env.setenv("CC_WRITE_ENABLED", value)
    assert WriteConfig.from_env().write_enabled is False


# ---------- from_env: secret ----------

def test_from_env_loads_secret(clean_env):
    clean_env.setenv("CC_WRITE_SECRET", "s3cr3t-token")
    assert WriteConfig.from_env().write_secret == "s3cr3t-token"


# ---------- from_env: allow-list parsing ----------

def test_from_env_unset_allowlist_defaults_to_sandbox_only(clean_env):
    assert WriteConfig.from_env().customer_allowlist == frozenset({SANDBOX_CUSTOMER_ID})


def test_from_env_empty_allowlist_defaults_to_sandbox_only(clean_env):
    # An explicitly-empty value must NOT mean "allow everything" — fail closed.
    clean_env.setenv("CC_WRITE_CUSTOMER_ALLOWLIST", "   ")
    assert WriteConfig.from_env().customer_allowlist == frozenset({SANDBOX_CUSTOMER_ID})


def test_from_env_parses_csv_allowlist_trimming_whitespace(clean_env):
    clean_env.setenv(
        "CC_WRITE_CUSTOMER_ALLOWLIST",
        f" {SANDBOX_CUSTOMER_ID} , cust-2 ,, cust-3 ",
    )
    assert WriteConfig.from_env().customer_allowlist == frozenset(
        {SANDBOX_CUSTOMER_ID, "cust-2", "cust-3"}
    )


# ---------- convenience membership predicate ----------

def test_is_customer_allowed_default():
    cfg = WriteConfig()
    assert cfg.is_customer_allowed(SANDBOX_CUSTOMER_ID) is True
    assert cfg.is_customer_allowed(LIVE_FORAGE_CUSTOMER_ID) is False


# ---------- M-DIMS-5a: live-promotion gate (the single flag that arms the live id) ----------

def test_default_live_promotion_is_closed():
    assert WriteConfig().live_promotion is False


def test_live_id_writable_only_when_promotion_armed():
    # The named live gate: the live Forage id is writable IFF CC_LIVE_PROMOTION is armed.
    enabled = dict(write_enabled=True, write_secret="valid")
    assert WriteConfig(**enabled, live_promotion=False).is_customer_allowed(LIVE_FORAGE_CUSTOMER_ID) is False
    assert WriteConfig(**enabled, live_promotion=True).is_customer_allowed(LIVE_FORAGE_CUSTOMER_ID) is True


def test_live_id_in_allowlist_does_NOT_grant_write_without_the_flag():
    # Anti-bypass: the live id is gated SOLELY by the flag, never by allow-list membership.
    # Even smuggled into the allow-list, it stays refused unless CC_LIVE_PROMOTION is armed.
    cfg = WriteConfig(
        write_enabled=True, write_secret="valid",
        customer_allowlist=frozenset({SANDBOX_CUSTOMER_ID, LIVE_FORAGE_CUSTOMER_ID}),
        live_promotion=False,
    )
    assert cfg.is_customer_allowed(LIVE_FORAGE_CUSTOMER_ID) is False, (
        "allow-list membership must NOT make the live id writable — only the flag does"
    )


def test_sandbox_allowed_regardless_of_promotion_flag():
    # The sandbox path is unchanged by promotion: sandbox writes work flag-off and flag-on.
    assert WriteConfig().is_customer_allowed(SANDBOX_CUSTOMER_ID) is True
    assert WriteConfig(live_promotion=True).is_customer_allowed(SANDBOX_CUSTOMER_ID) is True


def test_promotion_is_reversible_a_clear_flag_recloses_the_gate():
    armed = WriteConfig(write_enabled=True, write_secret="valid", live_promotion=True)
    recleared = WriteConfig(write_enabled=True, write_secret="valid", live_promotion=False)
    assert armed.is_customer_allowed(LIVE_FORAGE_CUSTOMER_ID) is True
    assert recleared.is_customer_allowed(LIVE_FORAGE_CUSTOMER_ID) is False


# ---------- from_env: CC_LIVE_PROMOTION parsing (only literal true arms it) ----------

def test_from_env_default_live_promotion_closed(clean_env):
    clean_env.delenv("CC_LIVE_PROMOTION", raising=False)
    assert WriteConfig.from_env().live_promotion is False


@pytest.mark.parametrize("value", ["true", "TRUE", "True", " true "])
def test_from_env_arms_live_promotion_on_true(clean_env, value):
    clean_env.setenv("CC_LIVE_PROMOTION", value)
    assert WriteConfig.from_env().live_promotion is True


@pytest.mark.parametrize("value", ["false", "0", "1", "yes", "", "no", "on"])
def test_from_env_keeps_live_promotion_closed_unless_true(clean_env, value):
    clean_env.setenv("CC_LIVE_PROMOTION", value)
    assert WriteConfig.from_env().live_promotion is False


def test_from_env_arming_flag_makes_live_writable_with_default_allowlist(clean_env):
    # One line of intent: CC_LIVE_PROMOTION=true alone (default sandbox allow-list) makes
    # the live id writable — without ever naming it in CC_WRITE_CUSTOMER_ALLOWLIST.
    clean_env.setenv("CC_WRITE_ENABLED", "true")
    clean_env.setenv("CC_WRITE_SECRET", "valid")
    clean_env.setenv("CC_LIVE_PROMOTION", "true")
    cfg = WriteConfig.from_env()
    assert cfg.customer_allowlist == frozenset({SANDBOX_CUSTOMER_ID})  # allow-list untouched
    assert cfg.is_customer_allowed(LIVE_FORAGE_CUSTOMER_ID) is True
    assert cfg.is_customer_allowed(SANDBOX_CUSTOMER_ID) is True
