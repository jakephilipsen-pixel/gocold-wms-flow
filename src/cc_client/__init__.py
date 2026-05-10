"""Go Cold's CartonCloud API client.

Read-only by default. Wraps OAuth2 client credentials, paginated search,
and the few endpoints we actually need: outbound orders, inbound orders,
warehouse products (carton dims), and stock-on-hand reports.
"""
from .client import (
    CartonCloudClient,
    CartonCloudError,
    CartonCloudAuthError,
    CartonCloudRateLimited,
)
from .queries import (
    get_stock_on_hand,
    search_inbound_orders,
    search_outbound_orders,
    search_warehouse_products,
)

__all__ = [
    "CartonCloudClient",
    "CartonCloudError",
    "CartonCloudAuthError",
    "CartonCloudRateLimited",
    "get_stock_on_hand",
    "search_inbound_orders",
    "search_outbound_orders",
    "search_warehouse_products",
]
