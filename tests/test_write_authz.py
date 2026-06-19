"""W2 — cc-write-authz: the write-auth secret check in front of any mutate.

Python analogue of dim-capture-app's `requireSyncKey` (module 12). Fail-closed:
a server with no write secret configured refuses (503 analogue); a caller that
presents no token, or the wrong token, refuses (401 analogue). The compare is
constant-time (`hmac.compare_digest`) so a wrong token can't be brute-forced by
timing.

Mirrors dim-capture-app module 12's four-ways rigour:
  1. refuse on unset secret   2. refuse on empty secret
  3. refuse on missing token   4. proceed on correct
plus wrong-token, empty-token, precedence, and the constant-time guarantee.

Fully offline — no client, no network, no CC write.
"""
from __future__ import annotations

import hmac

import pytest

from cc_client.write_authz import (
    verify_write_auth,
    CartonCloudWriteAuthNotConfigured,
    CartonCloudWriteAuthFailed,
)
from cc_client.write_config import WriteConfig

SECRET = "correct-horse-battery-staple"


# ---------- the four ways (dim-capture-app module 12 rigour) ----------

def test_refuse_when_secret_unset():
    # 503 analogue: server has no write secret configured.
    with pytest.raises(CartonCloudWriteAuthNotConfigured):
        verify_write_auth(None, SECRET)


def test_refuse_when_secret_empty():
    with pytest.raises(CartonCloudWriteAuthNotConfigured):
        verify_write_auth("", SECRET)


def test_refuse_when_token_missing():
    # 401 analogue: caller presents no token.
    with pytest.raises(CartonCloudWriteAuthFailed):
        verify_write_auth(SECRET, None)


def test_proceed_when_correct():
    # No exception, returns None.
    assert verify_write_auth(SECRET, SECRET) is None


# ---------- extra rigour ----------

def test_refuse_when_token_empty():
    with pytest.raises(CartonCloudWriteAuthFailed):
        verify_write_auth(SECRET, "")


def test_refuse_when_token_wrong():
    with pytest.raises(CartonCloudWriteAuthFailed):
        verify_write_auth(SECRET, "not-the-secret")


def test_not_configured_takes_precedence_over_missing_token():
    # Server misconfig is the more fundamental refusal: 503 wins over 401.
    with pytest.raises(CartonCloudWriteAuthNotConfigured):
        verify_write_auth(None, None)


def test_wrong_length_token_does_not_leak_via_exception_type():
    # A shorter/longer wrong token is still just a 401-analogue failure.
    with pytest.raises(CartonCloudWriteAuthFailed):
        verify_write_auth(SECRET, "x")


def test_uses_constant_time_compare(monkeypatch):
    # Prove the compare goes through hmac.compare_digest (not ==).
    calls: list[tuple] = []
    real = hmac.compare_digest

    def spy(a, b):
        calls.append((a, b))
        return real(a, b)

    monkeypatch.setattr("cc_client.write_authz.hmac.compare_digest", spy)
    verify_write_auth(SECRET, SECRET)
    assert calls, "expected hmac.compare_digest to be used for the token compare"


# ---------- integration with W0 config ----------

def test_integrates_with_writeconfig_secret(monkeypatch):
    monkeypatch.setenv("CC_WRITE_SECRET", SECRET)
    cfg = WriteConfig.from_env()
    assert verify_write_auth(cfg.write_secret, SECRET) is None
    with pytest.raises(CartonCloudWriteAuthFailed):
        verify_write_auth(cfg.write_secret, "wrong")


def test_writeconfig_default_secret_refuses_as_unconfigured():
    # W0 default: no secret -> any write attempt is 503-analogue refused.
    cfg = WriteConfig()
    with pytest.raises(CartonCloudWriteAuthNotConfigured):
        verify_write_auth(cfg.write_secret, "anything")


# ---------- package export ----------

def test_exported_from_package():
    from cc_client import (
        verify_write_auth as pkg_verify,
        CartonCloudWriteAuthNotConfigured as PkgNotConfigured,
        CartonCloudWriteAuthFailed as PkgFailed,
    )

    assert pkg_verify is verify_write_auth
    assert PkgNotConfigured is CartonCloudWriteAuthNotConfigured
    assert PkgFailed is CartonCloudWriteAuthFailed
