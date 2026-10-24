from datetime import date

from app import inventory as inv
from app.planner import build_plan, check_connections, rank_destinations
from app.state import TripRequest


def test_deterministic_inventory():
    a = inv.search_flights("MOW", "antalya", date(2026, 11, 12))
    b = inv.search_flights("MOW", "antalya", date(2026, 11, 12))
    assert a == b and len(a) >= 3


def test_rank_respects_flight_limit_and_explains_exclusions():
    req = TripRequest(origin="MOW", month=11, adults=2, children_ages=[5], prefs=["sea", "warm"], max_flight_h=5.5)
    opts, excluded = rank_destinations(req)
    assert opts and all(o["travel"]["minutes"] <= 5.5 * 60 * 1.05 for o in opts)
    assert any(e["dest_id"] == "phuket" for e in excluded)
    assert all(o["why"] for o in opts)


def test_pets_exclude_banned_destinations():
    req = TripRequest(origin="MOW", month=12, adults=2, prefs=["sea", "warm"], pets="dog")
    opts, excluded = rank_destinations(req, limit=8)
    assert all(o["dest_id"] not in ("bali", "maldives") for o in opts)


def test_plan_has_bundles_without_connection_errors():
    req = TripRequest(origin="MOW", month=12, adults=2, children_ages=[6], prefs=["sea"])
    plan = build_plan(req, "phuket")
    assert 1 <= len(plan["bundles"]) <= 3
    for b in plan["bundles"]:
        assert not [i for i in b["issues"] if i["level"] == "error"]
        # отель заселяется в день прибытия (или с ночи накануне при раннем прилёте)
        arr = b["out"]["arr"][:10]
        assert b["stay"]["check_in"] <= arr
        assert b["explain"]["why"]


def test_checker_finds_broken_dates():
    req = TripRequest(origin="MOW", month=12, adults=2)
    plan = build_plan(req, "phuket")
    b = dict(plan["bundles"][0])
    b["stay"] = dict(b["stay"], check_in="2026-12-01", check_out="2026-12-30")
    codes = {i["code"] for i in check_connections(b, req) if i["level"] == "error"}
    assert codes & {"checkin_before_arrival", "checkin_after_arrival", "checkout_after_departure", "checkout_gap"}


def test_pets_plan_only_pet_friendly():
    req = TripRequest(origin="MOW", month=8, adults=2, pets="dog")
    plan = build_plan(req, "sochi")
    assert all(b["hotel"]["pets_allowed"] for b in plan["bundles"])
    assert all(b["out"]["pet_cabin"] for b in plan["bundles"])


def test_train_only():
    req = TripRequest(origin="MOW", month=9, adults=2, transport="train", prefs=["sea"])
    plan = build_plan(req, "sochi")
    assert all(b["out"]["mode"] == "train" for b in plan["bundles"])
