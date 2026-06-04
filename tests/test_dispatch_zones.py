from __future__ import annotations

from pathlib import Path

from dispatch.zones import assign_zone, load_zone_config

_TOML = """
fallback = "Unzoned"

[[zone]]
name = "Metro Melbourne"
state = "VIC"
postcodes = ["3000-3207"]

[[zone]]
name = "Geelong"
state = "VIC"
postcodes = ["3211-3242"]

[[zone]]
name = "Interstate NSW"
state = "NSW"
"""


def _cfg(tmp_path: Path):
    p = tmp_path / "z.toml"
    p.write_text(_TOML)
    return load_zone_config(p)


def test_postcode_range_match(tmp_path):
    cfg = _cfg(tmp_path)
    assert assign_zone("VIC", "3179", cfg) == "Metro Melbourne"
    assert assign_zone("VIC", "3220", cfg) == "Geelong"


def test_state_only_zone_matches_without_postcode(tmp_path):
    cfg = _cfg(tmp_path)
    assert assign_zone("NSW", "2000", cfg) == "Interstate NSW"


def test_no_match_returns_fallback(tmp_path):
    cfg = _cfg(tmp_path)
    assert assign_zone("QLD", "4000", cfg) == "Unzoned"
    assert assign_zone("VIC", "3999", cfg) == "Unzoned"
