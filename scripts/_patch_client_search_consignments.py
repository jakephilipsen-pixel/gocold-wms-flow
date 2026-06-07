"""Patch for src/cc_client/client.py — add search_consignments().

If your CartonCloudClient already has search_consignments, skip this.
Otherwise, append this method to the CartonCloudClient class. Mirrors
the pattern of search_outbound_orders.

This script is here for reference only — it is not imported. The lines
below should be pasted into the CartonCloudClient class body.
"""

# --- BEGIN paste into CartonCloudClient ---

def search_consignments(self, condition: dict, page_size: int = 100):
    """Iterate consignments matching the given search condition.

    POSTs to /tenants/{tenantId}/consignments/search and yields each
    consignment dict. Pagination is handled via the page/size query
    params per the CC pagination spec.

    Args:
        condition: A dict shaped like {"condition": {...}} per the
            CC search condition spec. See API docs § Consignments §
            Search Consignment for available fields (runSheetId,
            runSheetDate, deliveryRunName, etc.).
        page_size: Items per page (CC default varies; 100 is fine).
    """
    page = 1
    while True:
        params = {"page": page, "size": page_size}
        resp = self._post_json(
            "/consignments/search",
            json=condition,
            params=params,
            tenant_scoped=True,
        )
        # CC search returns a JSON array in the body; headers carry pagination
        data = resp.json()
        if not isinstance(data, list):
            raise CartonCloudError(
                f"Unexpected consignment search response shape: {type(data).__name__}"
            )
        for item in data:
            yield item

        total_pages = int(resp.headers.get("Total-Pages", "1") or "1")
        if page >= total_pages or not data:
            break
        page += 1

# --- END paste ---


# If your existing client uses a different request helper name
# (e.g. self._request_json or self.post), adapt the _post_json call
# accordingly. The key bits are:
#   - POST to /consignments/search (tenant-scoped)
#   - Body is the condition dict as-is
#   - Query params: page=N, size=100
#   - Follow Total-Pages header for pagination
