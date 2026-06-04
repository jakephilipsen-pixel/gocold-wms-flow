from __future__ import annotations

from dispatch.addresses import address_key, normalise_address
from dispatch.consignments import extract_run_info, parse_consignment


def test_normalise_handles_list_lines_and_dict_state():
    addr = {"lines": ["12 Cold St ", "Unit 3"], "suburb": "Scoresby",
            "state": {"code": "VIC"}, "postcode": "3179"}
    key, full, street, suburb, state, postcode = normalise_address(addr)
    assert street == "12 Cold St, Unit 3"
    assert suburb == "Scoresby"
    assert state == "VIC"
    assert postcode == "3179"
    assert key == "12 cold st, unit 3 scoresby vic 3179"


def test_normalise_none_address_is_empty_key():
    assert address_key(None) == ""


def test_address_key_collapses_case_and_whitespace():
    a = {"lines": ["12  COLD  St"], "suburb": "Scoresby",
         "state": "VIC", "postcode": "3179"}
    b = {"lines": ["12 cold st"], "suburb": "scoresby",
         "state": "VIC", "postcode": "3179"}
    assert address_key(a) == address_key(b)


def test_extract_run_info_prefers_delivery_run():
    cons = {"details": {"runsheet": {"name": "RS-12", "date": "2026-06-03"},
                        "deliveryRun": {"name": "West-Tue"}},
            "customer": {"name": "Forage"}}
    rs_label, rs_date, dr_name, cust = extract_run_info(cons)
    assert rs_label == "RS-12 (2026-06-03)"
    assert rs_date == "2026-06-03"
    assert dr_name == "West-Tue"
    assert cust == "Forage"


def test_parse_consignment_run_is_delivery_run_then_runsheet():
    cons = {"details": {"deliver": {"address": {"lines": ["1 A St"],
            "suburb": "Geelong", "state": "VIC", "postcode": "3220"}},
            "runsheet": {"name": "RS-9", "date": "2026-06-02"},
            "deliveryRun": {"name": "Geelong-Mon"}}}
    rec = parse_consignment(cons)
    assert rec["run"] == "Geelong-Mon"
    assert rec["run_date"] == "2026-06-02"
    assert rec["address_key"] == "1 a st geelong vic 3220"
