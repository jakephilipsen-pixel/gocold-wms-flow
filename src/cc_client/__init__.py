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
from .write_authz import (
    verify_write_auth,
    CartonCloudWriteAuthNotConfigured,
    CartonCloudWriteAuthFailed,
)
from .write_customer_guard import (
    verify_customer_allowed,
    CartonCloudCustomerNotAllowed,
)
from .write_idempotency import (
    compute_diff,
    serialise_object,
    ObjectLockRegistry,
    idempotent_mutate,
    IdempotentWriteResult,
)
from .write_rate_limit import (
    TokenBucket,
    MutateRateLimiter,
    CartonCloudWriteRateLimited,
    DEFAULT_CEILING_PER_MIN,
)

__all__ = [
    "CartonCloudClient",
    "CartonCloudError",
    "CartonCloudAuthError",
    "CartonCloudRateLimited",
    "CartonCloudWriteRefused",
    "CartonCloudTimeout",
    "CartonCloudWriteAuthNotConfigured",
    "CartonCloudWriteAuthFailed",
    "CartonCloudCustomerNotAllowed",
    "WriteConfig",
    "SANDBOX_CUSTOMER_ID",
    "verify_write_auth",
    "verify_customer_allowed",
    "compute_diff",
    "serialise_object",
    "ObjectLockRegistry",
    "idempotent_mutate",
    "IdempotentWriteResult",
    "TokenBucket",
    "MutateRateLimiter",
    "CartonCloudWriteRateLimited",
    "DEFAULT_CEILING_PER_MIN",
    "get_sku_locations",
    "get_stock_on_hand",
    "search_consignments",
    "search_inbound_orders",
    "search_outbound_orders",
    "search_warehouse_locations",
    "search_warehouse_products",
]
