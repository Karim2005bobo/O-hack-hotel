import json

from app import agent, llm, store
from app.state import SessionState


def test_llm_extract_validates_and_merges(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test")
    fake = {"destination": "antalya", "adults": 3, "children_ages": [7], "prefs": ["sea", "unknown_pref"],
            "budget": "много", "_intent": "bogus", "month": 6}
    monkeypatch.setattr(llm, "_chat", lambda *a, **k: "Вот JSON: " + json.dumps(fake))
    data = llm.extract("какой-то текст", "start", "", "2026-10-24")
    assert data == {"destination": "antalya", "adults": 3, "children_ages": [7], "prefs": ["sea"], "month": 6}


def test_agent_survives_llm_failure(monkeypatch):
    store.reset_for_tests()
    monkeypatch.setenv("LLM_API_KEY", "test")
    monkeypatch.setattr(llm, "_chat", lambda *a, **k: None)
    s = SessionState(user_id="t-llm")
    out = agent.handle(s, "Стамбул в декабре вдвоём на 4 ночи")
    assert s.stage == "bundles" and out["blocks"]


def test_llm_overrides_rules(monkeypatch):
    store.reset_for_tests()
    monkeypatch.setenv("LLM_API_KEY", "test")
    # правила не поймут «Кёнигсберг-стайл», а LLM — да
    monkeypatch.setattr(llm, "_chat", lambda *a, **k: json.dumps({"destination": "kaliningrad", "month": 7, "adults": 2}))
    s = SessionState(user_id="t-llm2")
    agent.handle(s, "хочу туда, где янтарь и Куршская коса, летом, вдвоём")
    assert s.req.destination == "kaliningrad" and s.stage == "bundles"
