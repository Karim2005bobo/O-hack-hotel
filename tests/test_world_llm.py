"""Любое место мира через LLM (ответы модели подменены)."""
import json
import re

from conftest import llm_env

from app import agent, llm, store
from app.data.destinations import DEST_BY_ID
from app.state import SessionState

AIR = [2, 3, 3, 6, 9, 12, 14, 13, 11, 7, 4, 2]


def card(name, cc, lat, lon, kind="place", suggest=(), sea=None, types=("city",)):
    return {"kind": kind, "name": name, "name_loc": f"в {name}е", "name_acc": f"в {name}", "country": "", "cc": cc,
            "lat": lat, "lon": lon, "iata": "XXX", "airport_km": 40, "tz": 0, "types": list(types), "tags": ["culture", "nature"],
            "air_max": AIR, "sea": sea, "rain_days": [10] * 12, "best_months": [6, 7, 8],
            "areas": [{"name": "Центр", "airport_km": 45, "beach_m": None, "center_km": 0.5, "vibe": ["city"]}],
            "highlights": ["Голубая лагуна", "Гейзер Строккюр"], "hotel_price_rub": 15000, "daily_spend_rub": 6000,
            "direct_flights_from_moscow": False, "visa_note": "нужна виза", "risks": {"12": "очень короткий день"},
            "suggest": list(suggest), "note": "пояснение"}


CARDS = {
    "Рейкьявик": card("Рейкьявик", "IS", 64.15, -21.94),
    "Италия": card("Италия", "IT", 42, 12, kind="region", suggest=["Рим", "Венеция"]),
    "Рим": card("Рим", "IT", 41.9, 12.5, sea=[14] * 12),
    "Венеция": card("Венеция", "IT", 45.44, 12.33),
    "Антарктида": card("Антарктида", "AQ", -75, 0, kind="unreachable", suggest=["Ушуая", "Мурманск"]),
    "Ушуая": card("Ушуая", "AR", -54.8, -68.3),
}


def fake_llm(monkeypatch, extract):
    llm_env(monkeypatch)

    def chat(messages, **_):
        text = messages[-1]["content"]
        m = re.search(r"назвал место: «(.+?)»", text)
        if m:
            return json.dumps(CARDS[m.group(1)], ensure_ascii=False)
        return json.dumps(extract, ensure_ascii=False)
    monkeypatch.setattr(llm, "_chat", chat)


def test_any_city_becomes_full_trip(monkeypatch):
    store.reset_for_tests()
    fake_llm(monkeypatch, {"_unknown_place": "Рейкьявик", "month": 2, "adults": 2})
    s = SessionState(user_id="w1")
    out = agent.handle(s, "Хочу в Рейкьявик в феврале вдвоём")
    assert s.stage == "bundles", out["text"]
    d = DEST_BY_ID[s.req.destination]
    assert d.name == "Рейкьявик" and d.source == "llm" and d.visa == "visa"
    b = s.plan["bundles"][0]
    assert b["out"]["stops"] == 1 and b["out"]["via"] in ("Стамбул", "Белград", "Дубай")  # прямых рейсов нет
    assert not [i for i in b["issues"] if i["level"] == "error"]
    assert any(t.get("tool") == "llm_place_card" for t in out["trace"])
    # кэш: при повторе LLM за карточкой не ходим
    monkeypatch.setattr(llm, "place_card", lambda q: (_ for _ in ()).throw(AssertionError("кэш не сработал")))
    s2 = SessionState(user_id="w2")
    agent.handle(s2, "Хочу в Рейкьявик в феврале вдвоём")
    assert s2.req.destination == s.req.destination


def test_region_gives_concrete_places(monkeypatch):
    store.reset_for_tests()
    fake_llm(monkeypatch, {"_unknown_place": "Италия", "month": 6, "adults": 2})
    s = SessionState(user_id="w3")
    out = agent.handle(s, "хочу в Италию в июне вдвоём")
    assert s.stage == "destinations"
    names = [d["name"] for d in out["blocks"][0]["items"]]
    assert set(names) == {"Рим", "Венеция"}
    assert "Италия" in out["text"]


def test_unreachable_place_is_honest(monkeypatch):
    store.reset_for_tests()
    fake_llm(monkeypatch, {"_unknown_place": "Антарктида", "month": 1, "adults": 2})
    s = SessionState(user_id="w4")
    out = agent.handle(s, "хочу в антарктиду в январе вдвоём")
    names = [d["name"] for d in out["blocks"][0]["items"]]
    assert "Ушуая" in names and "Мурманск и Териберка" in names
    assert "Антарктида" in out["text"]


def test_without_llm_falls_back_to_catalog(monkeypatch):
    store.reset_for_tests()
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    s = SessionState(user_id="w5")
    out = agent.handle(s, "Хочу поехать в антарктиду летом вдвоём")
    assert "нет" in out["text"] and s.stage == "destinations"
