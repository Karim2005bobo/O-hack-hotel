"""Telegram-адаптер: тот же агент в мессенджере (long polling, без вебхуков).

Включается переменной TELEGRAM_BOT_TOKEN. Карточки агента превращаются
в компактный текст, а подсказки (чипы) — в inline-кнопки.
"""
from __future__ import annotations

import html
import logging
import os
import re
import threading
import time
import uuid

import httpx

from . import agent, store
from .planner import dt, hours, rub
from .state import SessionState

log = logging.getLogger("telegram")
API = "https://api.telegram.org/bot{token}/{method}"

_sessions: dict[int, str] = {}
_callbacks: dict[str, dict] = {}


def _md_to_html(text: str) -> str:
    t = html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(^|\s)_(.+?)_(?=$|\s|[.,])", r"\1<i>\2</i>", t)
    return t


def render_blocks(blocks: list[dict]) -> str:
    parts = []
    for b in blocks:
        if b["type"] == "destinations":
            for i, d in enumerate(b["items"], 1):
                w = d["weather"]
                parts.append(f"{i}. {d['flag']} <b>{html.escape(d['name'])}</b> — {rub(d['est']['total'])} под ключ, "
                             f"{d['dates']['text']}\n   +{w['air']}°" + (f", море +{w['sea']}°" if w["sea"] is not None else "") +
                             f", в пути {html.escape(d['travel']['text'])}\n   ✓ " + html.escape("; ".join(d["why"][:3])))
        elif b["type"] == "plan":
            for i, x in enumerate(b["plan"]["bundles"], 1):
                parts.append(f"{i}. <b>{x['title']}</b> — {rub(x['total'])}\n"
                             f"   ✈️ {x['out']['number']} {dt(x['out']['dep']):%d.%m %H:%M}, {hours(x['out']['duration_min'])}\n"
                             f"   🏨 {html.escape(x['hotel']['name'])} {x['hotel']['stars']}★, {x['stay']['nights']} ноч., {x['stay']['meal_name']}\n"
                             f"   ✓ {html.escape('; '.join(x['explain']['why'][:3]))}")
        elif b["type"] == "diff":
            parts.append("<b>Что изменилось:</b>\n" + "\n".join("• " + html.escape(x) for x in b["items"]))
        elif b["type"] == "cart":
            c = b["cart"]
            parts.append("\n".join(f"• {html.escape(i['title'])} — {rub(i['price'])}" for i in c["items"]) +
                         f"\n<b>Итого: {rub(c['total'])}</b>")
        elif b["type"] == "booking":
            bk = b["booking"]
            parts.append(f"<b>{bk['id']}</b> · {html.escape(bk['dest_name'])}, {bk['dates_text']} · {rub(bk['total'])}\n"
                         f"✈️ {html.escape(bk['out'])}\n🏨 {html.escape(bk['hotel'])}")
        elif b["type"] == "reminders":
            parts.append("\n".join(f"• {r['at'][8:10]}.{r['at'][5:7]} {r['at'][11:16]} — {html.escape(r['text'])}" for r in b["items"]))
        elif b["type"] == "hotels":
            parts.append("\n".join(f"• {html.escape(r['name'])} {r['stars']}★ — {rub(r['price'])}, совпадение {r['fit']}%"
                                   for r in b["rows"][:6]))
    return "\n\n".join(parts)


def keyboard(chips: list[dict]) -> dict | None:
    if not chips:
        return None
    rows = []
    for c in chips[:8]:
        key = uuid.uuid4().hex[:16]
        _callbacks[key] = c
        rows.append([{"text": c["label"][:60], "callback_data": key}])
    return {"inline_keyboard": rows}


class Bot:
    def __init__(self, token: str):
        self.token = token
        self.client = httpx.Client(timeout=40)
        self.offset = 0

    def call(self, method: str, **params):
        r = self.client.post(API.format(token=self.token, method=method), json=params)
        return r.json()

    def send(self, chat_id: int, out: dict):
        text = _md_to_html(out["text"])
        extra = render_blocks(out.get("blocks", []))
        if extra:
            text += "\n\n" + extra
        if out.get("blocks") and any(b["type"] == "checkout" for b in out["blocks"]):
            text += "\n\nНапишите имена путешественников через запятую (как в паспорте)."
        for i in range(0, len(text), 3900):
            chunk = text[i:i + 3900]
            last = i + 3900 >= len(text)
            self.call("sendMessage", chat_id=chat_id, text=chunk, parse_mode="HTML",
                      reply_markup=keyboard(out.get("chips", [])) if last else None)

    def session(self, chat_id: int) -> SessionState:
        sid = _sessions.get(chat_id)
        s = store.load_session(sid) if sid else None
        if not s:
            s = SessionState(user_id=f"tg-{chat_id}")
            _sessions[chat_id] = s.id
        return s

    def handle_update(self, u: dict):
        if "message" in u and u["message"].get("text"):
            chat_id = u["message"]["chat"]["id"]
            text = u["message"]["text"]
            s = self.session(chat_id)
            if text.startswith("/start"):
                out = agent.welcome(s)
            else:
                out = agent.handle(s, text)
            store.save_session(s)
            self.send(chat_id, out)
        elif "callback_query" in u:
            q = u["callback_query"]
            chat_id = q["message"]["chat"]["id"]
            self.call("answerCallbackQuery", callback_query_id=q["id"])
            c = _callbacks.get(q.get("data", ""))
            if not c:
                return
            s = self.session(chat_id)
            out = agent.handle(s, c.get("message"), c.get("action"))
            store.save_session(s)
            self.send(chat_id, out)

    def loop(self):
        log.info("Telegram bot started")
        while True:
            try:
                r = self.call("getUpdates", offset=self.offset, timeout=30)
                for u in r.get("result", []):
                    self.offset = u["update_id"] + 1
                    try:
                        self.handle_update(u)
                    except Exception:  # noqa: BLE001
                        log.exception("update failed")
            except Exception as e:  # noqa: BLE001
                log.warning("telegram polling error: %s", e)
                time.sleep(5)


def start_in_background():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return
    threading.Thread(target=Bot(token).loop, daemon=True, name="telegram").start()
