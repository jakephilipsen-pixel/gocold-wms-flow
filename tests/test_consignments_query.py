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
