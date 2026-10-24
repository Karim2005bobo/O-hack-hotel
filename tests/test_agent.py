from app import agent, store
from app.state import SessionState


def run(state, *steps):
    out = None
    for s in steps:
        out = agent.handle(state, None, s) if isinstance(s, dict) else agent.handle(state, s)
    return out


def test_single_clarification_then_destinations():
    store.reset_for_tests()
    s = SessionState(user_id="t-a")
    out = run(s, "хочу к тёплому морю в ноябре с ребёнком")
    assert s.stage == "clarify" and "лет" in out["text"]
    out = run(s, "ребенку 4 года")
    assert s.stage == "destinations" and out["blocks"][0]["type"] == "destinations"
    assert s.clarifications == 1


def test_full_path_to_booking_and_postsale():
    store.reset_for_tests()
    s = SessionState(user_id="t-b")
    run(s, "Хургада в декабре на неделю вдвоём")
    assert s.stage == "bundles"
    out = run(s, "а если на два дня позже?")
    assert any(b["type"] == "diff" for b in out["blocks"])
    run(s, "беру оптимальный")
    assert s.stage == "cart"
    run(s, {"type": "checkout"})
    out = run(s, "Иван Петров, Мария Петрова")
    assert s.stage == "booked" and s.active_booking
    bk = store.get_booking(s.active_booking)
    assert bk["status"] == "confirmed" and len(bk["travelers"]) == 2
    out = run(s, {"type": "change_booking", "days": 1})
    assert "Итого" in out["text"]
    out = run(s, {"type": "confirm_change", "days": 1})
    assert store.get_booking(s.active_booking)["history"][-1]["text"].startswith("Даты изменены")
    out = run(s, {"type": "reminders"})
    assert out["blocks"][0]["type"] == "reminders"


def test_memory_between_sessions():
    store.reset_for_tests()
    s = SessionState(user_id="t-mem")
    run(s, "из Казани в Сочи в августе, едем с женой и сыном 6 лет", {"type": "choose_bundle", "idx": 0},
        {"type": "checkout"}, "Иван Петров, Анна Петрова, Миша Петров")
    assert s.stage == "booked"
    s2 = SessionState(user_id="t-mem")
    w = agent.welcome(s2)
    assert "Помню" in w["text"] and s2.req.origin == "KZN"
    run(s2, "хотим на море в июне с ребенком")
    # возраст ребёнка взят из памяти — уточнять не нужно
    assert s2.req.children_ages == [6] and s2.stage == "destinations"


def test_dog_on_banned_destination_replans():
    store.reset_for_tests()
    s = SessionState(user_id="t-dog")
    run(s, "Бали в декабре на 10 ночей вдвоём")
    assert s.req.destination == "bali"
    out = run(s, "с нами едет собака")
    assert s.req.destination is None and s.stage == "destinations"
    assert "запрещён" in out["text"]
