"""Метрики качества агента по живым сессиям и тестовому прогону."""
from __future__ import annotations

from statistics import mean, median

from . import store


def aggregate(prefix: str | None = None, exclude_prefix: str | None = "eval") -> dict:
    sessions = store.all_sessions()
    if prefix:
        sessions = [s for s in sessions if s["user_id"].startswith(prefix)]
    elif exclude_prefix:
        sessions = [s for s in sessions if not s["user_id"].startswith(exclude_prefix)]
    active = [s for s in sessions if s.get("first_user_at")]
    booked = [s for s in active if s.get("booking_ids")]
    reco = [s for s in active if s.get("first_reco_at")]
    ttfr = [(s["first_reco_at"] - s["first_user_at"]) for s in reco]
    clar = [s.get("clarifications", 0) for s in active]
    turns_to_book = [s.get("turns", 0) for s in booked]
    bookings = [b for s in booked for b in (store.get_booking(x) for x in s["booking_ids"]) if b]
    conn_err = 0
    from .planner import check_connections
    from .state import TripRequest
    for b in bookings:
        req = TripRequest(pets=b.get("pets"))
        conn_err += sum(1 for i in check_connections(b["bundle"], req) if i["level"] == "error")
    return {
        "sessions": len(active),
        "completed": len(booked),
        "completion_rate": round(len(booked) / len(active), 3) if active else None,
        "avg_clarifications": round(mean(clar), 2) if clar else None,
        "median_time_to_first_reco_s": round(median(ttfr), 3) if ttfr else None,
        "avg_turns_to_booking": round(mean(turns_to_book), 1) if turns_to_book else None,
        "replans": sum(s.get("replans", 0) for s in active),
        "connection_errors_in_bookings": conn_err,
        "avg_check": round(mean(b["total"] for b in bookings)) if bookings else None,
    }
