"""Go Cold's CartonCloud API client.

Read-only by default. Wraps OAuth2 client credentials, paginated search,
and the few endpoints we actually need: outbound orders, inbound orders,
warehouse products (carton dims), warehouse locations, and stock-on-hand.
"""
from .client import (
    CartonCloudClient,
    CartonCloudError,
    CartonCloudAuthError,
    CartonCloudRateLimited,
    CartonCloudWriteRefused,
    CartonCloudTimeout,
)
from .queries import (
    get_sku_locations,
    get_stock_on_hand,
    search_consignments,
    search_inbound_orders,
    search_outbound_orders,
    search_warehouse_locations,
    search_warehouse_products,
)
from .write_config import (
    WriteConfig,
    SANDBOX_CUSTOMER_ID,
)

__all__ = [
    "CartonCloudClient",
    "CartonCloudError",
    "CartonCloudAuthError",
    "CartonCloudRateLimited",
    "CartonCloudWriteRefused",
    "CartonCloudTimeout",
    "WriteConfig",
    "SANDBOX_CUSTOMER_ID",
    "get_sku_locations",
    "get_stock_on_hand",
    "search_consignments",
    "search_inbound_orders",
    "search_outbound_orders",
    "search_warehouse_locations",
    "search_warehouse_products",
]
