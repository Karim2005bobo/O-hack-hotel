"""Прогон тестового набора сценариев и подсчёт метрик качества.

Запуск:  python -m eval.run_eval            (таблица в консоль)
         python -m eval.run_eval --json     (JSON)
Симулятор пользователя отвечает на уточнения, вносит изменения из сценария,
выбирает первый вариант и оплачивает. Затем независимо проверяем бронь.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from statistics import mean, median

from app import agent, store
from app.data.destinations import DEST_BY_ID
from app.planner import check_connections, dt
from app.state import SessionState

from .scenarios import SCENARIOS


def run_scenario(sc: dict) -> dict:
    st = SessionState(user_id=f"eval-{uuid.uuid4().hex[:8]}")
    msgs = list(sc["messages"])
    answers = list(sc.get("answers", []))
    changes = list(sc.get("changes", []))
    totals_seen, log = [], []
    replanned = False
    t_start = time.time()
    turns = 0
    out = agent.handle(st, msgs.pop(0))
    turns += 1
    log.append(out["text"][:120])
    first_reco_ms = None
    while turns < 18 and st.stage != "booked":
        if st.first_reco_at and first_reco_ms is None:
            first_reco_ms = int((st.first_reco_at - st.first_user_at) * 1000)
        if st.plan and st.plan.get("bundles"):
            totals_seen.append(st.plan["bundles"][0]["total"])
        if msgs:
            out = agent.handle(st, msgs.pop(0))
        elif st.stage == "clarify":
            out = agent.handle(st, answers.pop(0) if answers else "неважно, подбери сам")
        elif st.stage == "destinations":
            out = agent.handle(st, None, {"type": "choose_destination", "dest_id": st.dest_options[0]["dest_id"]})
        elif st.stage == "bundles" and changes:
            out = agent.handle(st, changes.pop(0))
            replanned = replanned or any(b["type"] == "diff" for b in out["blocks"])
        elif st.stage == "bundles":
            out = agent.handle(st, None, {"type": "choose_bundle", "idx": 0})
        elif st.stage == "cart":
            out = agent.handle(st, None, {"type": "checkout"})
        elif st.stage == "checkout":
            n = st.cart["bundle"]["party"]["adults"] + len(st.cart["bundle"]["party"]["children"])
            out = agent.handle(st, None, {"type": "pay", "travelers": [{"name": f"Test Person{i}"} for i in range(n)],
                                          "email": "test@example.com"})
        else:
            out = agent.handle(st, "начать заново")
        turns += 1
        log.append(out["text"][:120])
    if st.first_reco_at and first_reco_ms is None:
        first_reco_ms = int((st.first_reco_at - st.first_user_at) * 1000)
    store.save_session(st)
    booking = store.get_booking(st.active_booking) if st.active_booking else None
    checks = evaluate(sc, st, booking, replanned, totals_seen)
    conn_errors = 0
    if booking:
        conn_errors = sum(1 for i in check_connections(booking["bundle"], st.req) if i["level"] == "error")
    passed = bool(booking) and all(c["ok"] for c in checks)
    return {
        "name": sc["name"], "first_message": sc["messages"][0], "passed": passed,
        "result": (f"{booking['dest_name']}, {booking['dates_text']}, {booking['total']:,} ₽".replace(",", " ") if booking else f"не дошёл: {st.stage}"),
        "completed": bool(booking), "clarifications": st.clarifications, "turns": turns, "ttfr_ms": first_reco_ms,
        "connection_errors": conn_errors, "checks": checks, "elapsed_ms": int((time.time() - t_start) * 1000), "log": log,
    }


def evaluate(sc: dict, st: SessionState, bk: dict | None, replanned: bool, totals: list[int]) -> list[dict]:
    exp = sc.get("expect", {})
    res = []
    def add(name, ok):
        res.append({"name": name, "ok": bool(ok)})
    if not bk:
        add("бронь оформлена", False)
        return res
    b = bk["bundle"]
    for c in sc.get("checks", []):
        if c == "no_conn_errors":
            add("нет ошибок состыковки", not any(i["level"] == "error" for i in check_connections(b, st.req)))
        elif c == "max_flight":
            add(f"в пути ≤ {exp['max_flight_h']} ч", b["out"]["duration_min"] <= exp["max_flight_h"] * 60)
        elif c == "kids_ok":
            add("отель подходит детям", not b["hotel"]["adults_only"] and b["party"]["children"])
        elif c == "month":
            add("нужный месяц", dt(b["out"]["dep"]).month == exp["month"])
        elif c == "origin":
            add("верный город вылета", st.req.origin == exp["origin"])
        elif c == "budget":
            add(f"в бюджете {exp['budget']:,}".replace(",", " "), bk["total"] <= exp["budget"] * 1.05)
        elif c == "dest":
            add("верное направление", bk["dest_id"] in exp["dest"])
        elif c == "pets":
            add("отель и транспорт с питомцем", b["hotel"]["pets_allowed"] and b["out"]["pet_cabin"] and b["back"]["pet_cabin"])
        elif c == "train":
            add("поезд", b["out"]["mode"] == "train")
        elif c == "meal_ai":
            add("всё включено", b["stay"]["meal"] in ("AI", "UAI"))
        elif c == "country_tr":
            add("Турция", DEST_BY_ID[bk["dest_id"]].country == "Турция")
        elif c == "replanned":
            add("план пересобран с диффом", replanned)
        elif c == "cheaper":
            add("после «дешевле» итог ниже", len(totals) >= 2 and min(totals[1:]) < totals[0])
        elif c == "visa_free":
            add("без визы", DEST_BY_ID[bk["dest_id"]].visa == "none")
        elif c == "not_egypt":
            add("не Египет", DEST_BY_ID[bk["dest_id"]].country != "Египет")
        elif c == "direct":
            add("прямой рейс", b["out"]["stops"] == 0 and b["back"]["stops"] == 0)
        elif c == "free_cancel":
            add("бесплатная отмена", b["stay"]["rate"]["refundable"])
    return res


def run_all(verbose: bool = True) -> dict:
    results = [run_scenario(sc) for sc in SCENARIOS]
    ttfr = [r["ttfr_ms"] for r in results if r["ttfr_ms"] is not None]
    summary = {
        "total": len(results),
        "passed": sum(r["passed"] for r in results),
        "completion_rate": round(sum(r["completed"] for r in results) / len(results), 3),
        "avg_clarifications": round(mean(r["clarifications"] for r in results), 2),
        "avg_turns": round(mean(r["turns"] for r in results), 1),
        "median_ttfr_ms": int(median(ttfr)) if ttfr else None,
        "connection_errors": sum(r["connection_errors"] for r in results),
        "constraint_violations": sum(1 for r in results for c in r["checks"] if not c["ok"]),
    }
    if verbose:
        print(f"{'Сценарий':<48} {'Итог':<6} {'Уточн':>5} {'Ходов':>5} {'TTFR,мс':>8}  Результат")
        for r in results:
            print(f"{r['name'][:47]:<48} {'OK' if r['passed'] else 'FAIL':<6} {r['clarifications']:>5} {r['turns']:>5} "
                  f"{str(r['ttfr_ms']):>8}  {r['result']}")
            for c in r["checks"]:
                if not c["ok"]:
                    print(f"{'':<50}✕ {c['name']}")
        print("\nИтого:", json.dumps(summary, ensure_ascii=False))
    for r in results:
        r.pop("log", None)
    return {"summary": summary, "scenarios": results}


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(run_all(verbose=False), ensure_ascii=False, indent=2))
    else:
        run_all()
