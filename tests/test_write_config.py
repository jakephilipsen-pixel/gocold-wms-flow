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

CC_WRITE_VARS = ("CC_WRITE_ENABLED", "CC_WRITE_SECRET", "CC_WRITE_CUSTOMER_ALLOWLIST")


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


def test_from_env_allowlist_can_be_promoted_to_include_live(clean_env):
    # The live-promotion path (M-DIMS-5): adding the live id via env is the ONLY
    # way it enters the allow-list. Default never contains it (asserted above).
    clean_env.setenv(
        "CC_WRITE_CUSTOMER_ALLOWLIST",
        f"{SANDBOX_CUSTOMER_ID},{LIVE_FORAGE_CUSTOMER_ID}",
    )
    assert LIVE_FORAGE_CUSTOMER_ID in WriteConfig.from_env().customer_allowlist


# ---------- convenience membership predicate ----------

def test_is_customer_allowed_default():
    cfg = WriteConfig()
    assert cfg.is_customer_allowed(SANDBOX_CUSTOMER_ID) is True
    assert cfg.is_customer_allowed(LIVE_FORAGE_CUSTOMER_ID) is False
