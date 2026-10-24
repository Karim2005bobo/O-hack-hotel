"""Опциональная LLM через OpenAI-совместимый API.

LLM используется для двух вещей:
1) извлечение слотов и намерения из свободного текста (поверх правил nlu.py);
2) ответы на свободные вопросы о направлении («что посмотреть», «что взять»).

Все цены, наличие и проверки делает детерминированный планировщик — LLM не
может «придумать» отель или цену. Без ключа агент полностью работает на правилах.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time

import httpx

from .data.destinations import DESTINATIONS
from .data.geo import ORIGINS

log = logging.getLogger("agent.llm")

INTENTS = ["reset", "greet", "choose", "choose_book", "book", "pay", "shift_dates", "extend", "cheaper", "pricier",
           "show_hotels", "show_flights", "show_destinations", "why", "info", "skip", "early_checkin", "late_checkout",
           "reminders", "cancel_booking", "change_booking", "add_transfer", "add_insurance"]
PREFS = ["sea", "warm", "mild", "culture", "food", "party", "quiet", "romantic", "nature", "mountains", "ski", "shopping",
         "wellness", "diving", "northern_lights", "kids_fun", "city", "surf", "adventure", "pool", "kitchen"]


def enabled() -> bool:
    return bool(os.getenv("LLM_API_KEY")) and os.getenv("LLM_ENABLED", "true").lower() not in ("0", "false", "no")


def _chat(messages: list[dict], max_tokens: int = 600, json_mode: bool = True) -> str | None:
    base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    timeout = float(os.getenv("LLM_TIMEOUT", "20"))
    body = {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {os.getenv('LLM_API_KEY')}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(f"{base}/chat/completions", json=body, headers=headers)
            if r.status_code == 400 and json_mode:  # сервер не поддерживает response_format
                body.pop("response_format")
                r = c.post(f"{base}/chat/completions", json=body, headers=headers)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    except Exception as e:  # noqa: BLE001 — сеть/формат: тихо откатываемся на правила
        log.warning("LLM недоступна: %s", e)
        return None


def _system_prompt(today_iso: str) -> str:
    dests = ", ".join(f"{d.id}={d.name} ({d.country})" for d in DESTINATIONS)
    origins = ", ".join(f"{o.code}={o.name}" for o in ORIGINS)
    return f"""Ты — модуль понимания запросов тревел-агента. Сегодня {today_iso}.
Верни ТОЛЬКО JSON-объект с полями, которые явно следуют из последнего сообщения пользователя (остальные не включай):
origin: код города вылета из [{origins}]
destination: id направления из [{dests}]
country: страна, если названа страна, а не город (например "Турция", "Россия")
avoid: список стран/id направлений, которые пользователь исключил
date_from, date_to: YYYY-MM-DD; month: 1-12; year; nights: число ночей
adults: взрослых; children_ages: список возрастов детей; children_pending: число детей без возраста
pets: "dog" | "cat" | "pet" | null (null — если сказал, что питомец не едет)
budget: общий бюджет в рублях (если «на человека» — поставь _budget_per_person: true)
budget_level: "low" | "high"
prefs: подмножество {PREFS}
meal: "RO"|"BB"|"HB"|"AI"; free_cancel: bool; direct_only: bool; max_flight_h: число часов; transport: "plane"|"train"
stars_min: 2-5; beach_close: bool; center_close: bool; visa_free: bool; priority: "price"|"balance"|"comfort"|"time"
flight_time_pref: "morning"|"day"|"evening"
_intent: одно из {INTENTS} или не указывай. shift_dates → _shift: дни (+позже/−раньше); extend → _extend: ±ночей.
choose → _choice_idx (0-based) или _choice_code ("optimal"|"economy"|"comfort").
_unknown_place: название места, если пользователь назвал страну/город, которых нет в списке направлений.
«без долгих перелётов» → max_flight_h 5.5. Не выдумывай значения."""


def extract(text: str, stage: str, context: str, today_iso: str) -> dict | None:
    if not enabled():
        return None
    t0 = time.time()
    raw = _chat([
        {"role": "system", "content": _system_prompt(today_iso)},
        {"role": "user", "content": f"Этап диалога: {stage}. Что уже известно: {context}\nСообщение: {text}"},
    ])
    if not raw:
        return None
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    log.info("LLM extract %.2fs: %s", time.time() - t0, data)
    return _validate(data)


def _validate(d: dict) -> dict:
    ok: dict = {}
    ids = {x.id for x in DESTINATIONS}
    codes = {o.code for o in ORIGINS}
    for k, v in d.items():
        if v is None and k != "pets":
            continue
        if k == "origin" and v in codes:
            ok[k] = v
        elif k == "destination" and v in ids:
            ok[k] = v
        elif k in ("country",) and isinstance(v, str):
            ok[k] = v
        elif k == "avoid" and isinstance(v, list):
            ok[k] = [str(x) for x in v]
        elif k in ("date_from", "date_to") and isinstance(v, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            ok[k] = v
        elif k in ("month", "year", "nights", "adults", "children_pending", "budget", "stars_min", "_shift", "_extend",
                   "_choice_idx") and isinstance(v, (int, float)):
            ok[k] = int(v)
        elif k == "children_ages" and isinstance(v, list):
            ok[k] = [int(x) for x in v if isinstance(x, (int, float)) and 0 <= x < 18]
        elif k == "pets" and v in ("dog", "cat", "pet", None):
            ok[k] = v
        elif k == "budget_level" and v in ("low", "mid", "high"):
            ok[k] = v
        elif k == "prefs" and isinstance(v, list):
            ok[k] = [p for p in v if p in PREFS]
        elif k == "meal" and v in ("RO", "BB", "HB", "AI"):
            ok[k] = v
        elif k in ("free_cancel", "direct_only", "beach_close", "center_close", "visa_free", "_budget_per_person") and isinstance(v, bool):
            ok[k] = v
        elif k == "max_flight_h" and isinstance(v, (int, float)) and 1 <= v <= 30:
            ok[k] = float(v)
        elif k == "transport" and v in ("plane", "train", "any"):
            ok[k] = v
        elif k == "priority" and v in ("price", "balance", "comfort", "time"):
            ok[k] = v
        elif k == "flight_time_pref" and v in ("morning", "day", "evening"):
            ok[k] = v
        elif k == "_intent" and v in INTENTS:
            ok[k] = v
        elif k == "_unknown_place" and isinstance(v, str) and v.strip():
            ok[k] = v.strip()[:60]
        elif k == "_choice_code" and v in ("optimal", "economy", "comfort"):
            ok[k] = v
    return ok


def answer(question: str, facts: str) -> str | None:
    if not enabled():
        return None
    raw = _chat([
        {"role": "system", "content": "Ты — дружелюбный тревел-агент Островка. Отвечай по-русски, кратко (3–6 предложений), "
                                      "опирайся на факты ниже, не выдумывай цены и наличие. Факты:\n" + facts},
        {"role": "user", "content": question},
    ], max_tokens=400, json_mode=False)
    return raw.strip() if raw else None
