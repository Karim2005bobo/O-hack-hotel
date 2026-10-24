"""Города вылета и геометрия."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Origin:
    code: str
    name: str
    name_gen: str  # «из Москвы»
    lat: float
    lon: float
    tz: float
    aliases: tuple[str, ...]
    airport: str


ORIGINS: list[Origin] = [
    Origin("MOW", "Москва", "Москвы", 55.75, 37.62, 3, ("москв", "мск", "подмосков"), "Шереметьево"),
    Origin("LED", "Санкт-Петербург", "Санкт-Петербурга", 59.94, 30.31, 3,
           ("петербург", "питер", "спб", "санкт", "ленинград"), "Пулково"),
    Origin("SVX", "Екатеринбург", "Екатеринбурга", 56.84, 60.6, 5, ("екатеринбург", "екб", "ебург"), "Кольцово"),
    Origin("KZN", "Казань", "Казани", 55.79, 49.12, 3, ("казан",), "Казань"),
    Origin("OVB", "Новосибирск", "Новосибирска", 55.03, 82.92, 7, ("новосиб", "нск"), "Толмачёво"),
    Origin("KUF", "Самара", "Самары", 53.2, 50.15, 4, ("самар",), "Курумоч"),
    Origin("UFA", "Уфа", "Уфы", 54.74, 55.97, 5, ("уфа", "уфы", "уфе"), "Уфа"),
    Origin("GOJ", "Нижний Новгород", "Нижнего Новгорода", 56.33, 44.0, 3, ("нижн", "нижегород"), "Стригино"),
    Origin("PEE", "Пермь", "Перми", 58.01, 56.25, 5, ("перм",), "Большое Савино"),
    Origin("VVO", "Владивосток", "Владивостока", 43.12, 131.89, 10, ("владивосток", "владик"), "Кневичи"),
]

ORIGIN_BY_CODE = {o.code: o for o in ORIGINS}

# Город вылета, который совпадает с направлением (не предлагаем «из Москвы в Москву»)
ORIGIN_SAME_DEST = {"MOW": "moscow", "LED": "spb", "KZN": "kazan"}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def flight_minutes(dist_km: float) -> int:
    """Чистое время в воздухе прямого рейса с учётом обходных маршрутов."""
    return int(dist_km / 800 * 60 + 40)
