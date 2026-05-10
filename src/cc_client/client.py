"""CartonCloud API client.

Handles OAuth2 client_credentials auth with automatic token refresh,
exponential backoff on 429/5xx, and helpers for paginated endpoints.

Usage:
    client = CartonCloudClient.from_env()
    me = client.get("/uaa/userinfo", tenant_scoped=False)
    orders = list(client.search_outbound_orders(condition))
"""
from __future__ import annotations

import base64
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Iterator
from urllib.parse import urljoin

import httpx

log = logging.getLogger(__name__)


class CartonCloudError(Exception):
    """Base exception for CC client failures."""


class CartonCloudAuthError(CartonCloudError):
    """OAuth / 401 issues."""


class CartonCloudRateLimited(CartonCloudError):
    """429 received after retries exhausted."""


@dataclass
class _Token:
    access_token: str
    expires_at: float  # epoch seconds

    @property
    def is_expired(self) -> bool:
        # refresh 60s before actual expiry to be safe
        return time.time() >= (self.expires_at - 60)


class CartonCloudClient:
    """Thin sync client over CartonCloud REST API v1.

    Read-only by default for safety: pass write_enabled=True to allow
    POST/PUT/PATCH/DELETE. This is a deliberate seatbelt during early
    development so we can't accidentally mutate production data.
    """

    DEFAULT_BASE_URL = "https://api.cartoncloud.com"
    ACCEPT_VERSION = "1"
    MAX_RETRIES = 4

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        base_url: str = DEFAULT_BASE_URL,
        write_enabled: bool = False,
        timeout: float = 30.0,
    ) -> None:
        if not client_id or not client_secret or not tenant_id:
            raise ValueError("client_id, client_secret and tenant_id are required")
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.base_url = base_url.rstrip("/")
        self.write_enabled = write_enabled
        self._http = httpx.Client(timeout=timeout)
        self._token: _Token | None = None

    @classmethod
    def from_env(cls, **overrides: Any) -> "CartonCloudClient":
        """Build a client from CC_* environment variables.

        Required: CC_CLIENT_ID, CC_CLIENT_SECRET, CC_TENANT_ID.
        Optional: CC_BASE_URL, CC_WRITE_ENABLED ("true" to enable writes).
        """
        kwargs = {
            "client_id": os.environ.get("CC_CLIENT_ID", ""),
            "client_secret": os.environ.get("CC_CLIENT_SECRET", ""),
            "tenant_id": os.environ.get("CC_TENANT_ID", ""),
            "base_url": os.environ.get("CC_BASE_URL", cls.DEFAULT_BASE_URL),
            "write_enabled": os.environ.get("CC_WRITE_ENABLED", "").lower() == "true",
        }
        kwargs.update(overrides)
        return cls(**kwargs)

    # ---------- auth ----------

    def _fetch_token(self) -> _Token:
        creds = f"{self.client_id}:{self.client_secret}".encode()
        basic = base64.b64encode(creds).decode()
        log.debug("requesting new access token")
        r = self._http.post(
            urljoin(self.base_url + "/", "uaa/oauth/token"),
            headers={
                "Authorization": f"Basic {basic}",
                "Accept-Version": self.ACCEPT_VERSION,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
        )
        if r.status_code != 200:
            raise CartonCloudAuthError(
                f"token endpoint returned {r.status_code}: {r.text[:200]}"
            )
        data = r.json()
        return _Token(
            access_token=data["access_token"],
            expires_at=time.time() + int(data.get("expires_in", 3600)),
        )

    def _ensure_token(self) -> str:
        if self._token is None or self._token.is_expired:
            self._token = self._fetch_token()
        return self._token.access_token

    # ---------- request core ----------

    def _request(
        self,
        method: str,
        path: str,
        *,
        tenant_scoped: bool = True,
        params: dict[str, Any] | None = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        if method.upper() not in {"GET"} and not self.write_enabled:
            raise CartonCloudError(
                f"write operations disabled (method={method}); "
                "set write_enabled=True or CC_WRITE_ENABLED=true to allow"
            )

        if tenant_scoped:
            url = urljoin(
                self.base_url + "/", f"tenants/{self.tenant_id}{path}"
            )
        else:
            url = urljoin(self.base_url + "/", path.lstrip("/"))

        merged_headers = {
            "Accept-Version": self.ACCEPT_VERSION,
            "Authorization": f"Bearer {self._ensure_token()}",
        }
        if json is not None:
            merged_headers["Content-Type"] = "application/json"
        if headers:
            merged_headers.update(headers)

        backoff = 1.0
        last_exc: Exception | None = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                r = self._http.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=merged_headers,
                )
            except httpx.HTTPError as e:
                last_exc = e
                log.warning("network error on attempt %d: %s", attempt, e)
                if attempt == self.MAX_RETRIES:
                    raise CartonCloudError(f"network failure after retries: {e}")
                time.sleep(backoff)
                backoff *= 2
                continue

            if r.status_code == 401 and attempt == 0:
                # token might've been revoked mid-flight; refresh once and retry
                log.info("got 401, refreshing token")
                self._token = None
                merged_headers["Authorization"] = f"Bearer {self._ensure_token()}"
                continue

            if r.status_code == 429 or 500 <= r.status_code < 600:
                if attempt == self.MAX_RETRIES:
                    if r.status_code == 429:
                        raise CartonCloudRateLimited(
                            f"rate limited after {self.MAX_RETRIES} retries"
                        )
                    raise CartonCloudError(
                        f"server error {r.status_code} after retries: {r.text[:200]}"
                    )
                retry_after = float(r.headers.get("Retry-After", backoff))
                log.warning(
                    "got %d on %s %s, sleeping %.1fs (attempt %d)",
                    r.status_code, method, path, retry_after, attempt,
                )
                time.sleep(retry_after)
                backoff *= 2
                continue

            if not r.is_success:
                raise CartonCloudError(
                    f"{method} {path} failed: {r.status_code} {r.text[:300]}"
                )
            return r

        # should be unreachable
        raise CartonCloudError(f"exhausted retries: {last_exc}")

    # ---------- public read helpers ----------

    def get(
        self,
        path: str,
        *,
        tenant_scoped: bool = True,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        return self._request(
            "GET", path, tenant_scoped=tenant_scoped, params=params, headers=headers
        ).json()

    def me(self) -> dict[str, Any]:
        """Return the authenticated user's info incl. accessible tenants."""
        return self.get("/uaa/userinfo", tenant_scoped=False)

    def paginated_post_search(
        self,
        path: str,
        body: dict[str, Any],
        *,
        page_size: int = 100,
        minimal: bool = False,
        max_pages: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield items across all pages of a POST /search endpoint.

        CC paginates via ?page=&size=, with Total-Pages in response headers.
        """
        page = 1
        headers = {"Prefer": "return=minimal"} if minimal else None
        while True:
            r = self._request(
                "GET",  # method override below
                path,
                params={"page": page, "size": page_size},
                headers=headers,
            )
            # Hmm: search is POST. Override:
            raise NotImplementedError("use post_search instead")  # pragma: no cover

    def post_search(
        self,
        path: str,
        body: dict[str, Any],
        *,
        page_size: int = 100,
        minimal: bool = False,
        max_pages: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield items from a paginated POST /search endpoint.

        Note: search endpoints are POST despite reading data; CC chose this
        so complex query bodies don't have to be URL-encoded.
        """
        # Search endpoints are reads even though method is POST.
        # Temporarily allow them regardless of write_enabled flag.
        original_write = self.write_enabled
        self.write_enabled = True
        try:
            page = 1
            headers = {"Prefer": "return=minimal"} if minimal else None
            while True:
                r = self._request(
                    "POST",
                    path,
                    params={"page": page, "size": page_size},
                    json=body,
                    headers=headers,
                )
                items = r.json()
                if not items:
                    return
                for item in items:
                    yield item

                total_pages_h = r.headers.get("Total-Pages")
                if total_pages_h:
                    try:
                        total_pages = int(total_pages_h)
                        if page >= total_pages:
                            return
                    except ValueError:
                        pass
                if max_pages is not None and page >= max_pages:
                    return
                if len(items) < page_size:
                    # short page = last page even if header missing
                    return
                page += 1
        finally:
            self.write_enabled = original_write

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "CartonCloudClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
