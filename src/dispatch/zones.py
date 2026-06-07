"""Zone fallback for delivery addresses with no run history (TOML config)."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ZoneRule:
    name: str
    state: str | None
    postcode_ranges: list[tuple[int, int]]   # inclusive; exact = (n, n)


@dataclass(frozen=True)
class ZoneConfig:
    zones: list[ZoneRule]
    fallback: str


def _parse_range(token: str) -> tuple[int, int]:
    token = str(token).strip()
    if "-" in token:
        lo, hi = token.split("-", 1)
        return (int(lo), int(hi))
    return (int(token), int(token))


def load_zone_config(path: Path) -> ZoneConfig:
    """Load zone rules from a TOML file (stdlib tomllib)."""
    data = tomllib.loads(Path(path).read_text())
    zones: list[ZoneRule] = []
    for z in data.get("zone", []):
        ranges = [_parse_range(t) for t in z.get("postcodes", [])]
        zones.append(ZoneRule(name=z["name"], state=z.get("state"),
                              postcode_ranges=ranges))
    return ZoneConfig(zones=zones, fallback=data.get("fallback", "Unzoned"))


def assign_zone(state: str | None, postcode: str | None,
                config: ZoneConfig) -> str:
    """First matching zone name, else the fallback.

    A zone with postcode ranges requires the postcode to fall in one range
    AND (if the zone sets a state) the state to match. A zone with no ranges
    matches on state alone.
    """
    try:
        pc = int(str(postcode).strip()) if postcode else None
    except ValueError:
        pc = None
    for z in config.zones:
        if z.state and state and z.state != state:
            continue
        if z.postcode_ranges:
            if pc is not None and any(lo <= pc <= hi
                                      for lo, hi in z.postcode_ranges):
                return z.name
            continue
        if z.state and state == z.state:
            return z.name
    return config.fallback
