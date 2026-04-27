"""Flight search tool with Amadeus API integration and mock fallback.

API: Amadeus for Developers (https://developers.amadeus.com)
Free sandbox: 10000 requests/month
Docs: https://developers.amadeus.com/self-service/category/air/api-doc/api-docs-v2
"""

from __future__ import annotations

import random
from datetime import datetime

import httpx
from loguru import logger

from config.settings import settings
from models.schemas import Flight

# ━━━━━━━━━━━━━━━━━━ IATA 代码映射 ━━━━━━━━━━━━━━━━━━

CITY_TO_IATA: dict[str, str] = {
    "北京": "PEK",
    "上海": "PVG",
    "广州": "CAN",
    "深圳": "SZX",
    "成都": "CTU",
    "杭州": "HGH",
    "东京": "TYO",
    "大阪": "OSA",
    "首尔": "ICN",
    "曼谷": "BKK",
    "清迈": "CNX",
    "巴黎": "PAR",
    "伦敦": "LON",
    "纽约": "NYC",
    "新加坡": "SIN",
    "悉尼": "SYD",
}

AIRLINES = {
    "domestic": [
        ("中国国航", "CA"),
        ("东方航空", "MU"),
        ("南方航空", "CZ"),
        ("海南航空", "HU"),
        ("春秋航空", "9C"),
        ("吉祥航空", "HO"),
    ],
    "international": [
        ("全日空", "NH"),
        ("日本航空", "JL"),
        ("大韩航空", "KE"),
        ("新加坡航空", "SQ"),
        ("泰国航空", "TG"),
        ("国泰航空", "CX"),
        ("阿联酋航空", "EK"),
        ("法国航空", "AF"),
    ],
}

ROUTE_DURATIONS = {
    ("北京", "东京"): (3.5, 4.5),
    ("上海", "东京"): (2.5, 3.5),
    ("北京", "首尔"): (2.0, 3.0),
    ("上海", "首尔"): (1.5, 2.5),
    ("北京", "曼谷"): (4.5, 6.0),
    ("上海", "曼谷"): (4.0, 5.5),
    ("北京", "巴黎"): (10.0, 13.0),
    ("上海", "巴黎"): (11.0, 14.0),
    ("北京", "大阪"): (3.0, 4.0),
    ("上海", "大阪"): (2.0, 3.0),
    ("北京", "清迈"): (5.0, 7.0),
    ("上海", "清迈"): (4.5, 6.5),
}

# ━━━━━━━━━━━━━━━━━━ Amadeus Token 管理 ━━━━━━━━━━━━━━━━━━

_amadeus_token: str = ""
_amadeus_token_expiry: float = 0.0


async def _get_amadeus_token() -> str:
    """获取 Amadeus OAuth2 access token，带缓存复用。"""
    global _amadeus_token, _amadeus_token_expiry

    import time

    if _amadeus_token and time.time() < _amadeus_token_expiry - 60:
        return _amadeus_token

    if not settings.AMADEUS_CLIENT_ID or not settings.AMADEUS_CLIENT_SECRET:
        raise ValueError("AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET 未配置")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.amadeus_base_url}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.AMADEUS_CLIENT_ID,
                "client_secret": settings.AMADEUS_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        _amadeus_token = data["access_token"]
        _amadeus_token_expiry = time.time() + data.get("expires_in", 1800)
        logger.info("[Amadeus] token refreshed, expires in {}s", data.get("expires_in"))
        return _amadeus_token


# ━━━━━━━━━━━━━━━━━━ Amadeus 真实 API ━━━━━━━━━━━━━━━━━━


def _parse_duration_to_hours(duration: str) -> float:
    """将 ISO 8601 时长 (PT2H30M) 转换为小时数。"""
    import re

    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", duration)
    if not match:
        return 3.0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return round(hours + minutes / 60, 1)


async def _amadeus_search_flights(
    departure_city: str,
    arrival_city: str,
    date: str,
    cabin_class: str = "economy",
    count: int = 6,
) -> list[Flight]:
    """调用 Amadeus Flight Offers Search API。"""
    origin = CITY_TO_IATA.get(departure_city)
    destination = CITY_TO_IATA.get(arrival_city)

    if not origin or not destination:
        logger.warning("[Amadeus] 城市 {} 或 {} 无 IATA 映射，降级到 mock", departure_city, arrival_city)
        return _mock_search_flights(departure_city, arrival_city, date, cabin_class, count)

    token = await _get_amadeus_token()

    travel_class_map = {"economy": "ECONOMY", "business": "BUSINESS", "first": "FIRST"}
    params: dict[str, str | int] = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": date,
        "adults": 1,
        "currencyCode": "CNY",
        "max": count,
    }
    if cabin_class in travel_class_map:
        params["travelClass"] = travel_class_map[cabin_class]

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{settings.amadeus_base_url}/v2/shopping/flight-offers",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        data = resp.json()

    flights: list[Flight] = []
    for offer in data.get("data", []):
        try:
            itinerary = offer["itineraries"][0]
            segment = itinerary["segments"][0]
            price = float(offer["price"]["total"])
            duration = _parse_duration_to_hours(itinerary.get("duration", "PT3H"))
            dep_time = segment["departure"]["at"]
            arr_time = segment["arrival"]["at"]
            carrier = segment.get("carrierCode", "XX")
            flight_no = f"{carrier}{segment.get('number', '000')}"

            flights.append(
                Flight(
                    airline=carrier,
                    flight_no=flight_no,
                    departure_city=departure_city,
                    arrival_city=arrival_city,
                    departure_time=dep_time,
                    arrival_time=arr_time,
                    price=price,
                    duration_hours=duration,
                    stops=len(itinerary["segments"]) - 1,
                    cabin_class=cabin_class,
                )
            )
        except (KeyError, IndexError, ValueError) as exc:
            logger.debug("[Amadeus] 跳过无法解析的航班: {}", exc)
            continue

    logger.info("[Amadeus] 找到 {} 个航班 {}→{}", len(flights), departure_city, arrival_city)
    return flights


# ━━━━━━━━━━━━━━━━━━ Mock 回退 ━━━━━━━━━━━━━━━━━━


def _mock_search_flights(
    departure_city: str,
    arrival_city: str,
    date: str,
    cabin_class: str = "economy",
    count: int = 6,
) -> list[Flight]:
    """Mock 航班搜索，当 API 不可用时使用。"""
    key = (departure_city, arrival_city)
    reverse_key = (arrival_city, departure_city)
    duration_range = ROUTE_DURATIONS.get(key) or ROUTE_DURATIONS.get(reverse_key) or (3.0, 8.0)

    international_cities = {"东京", "首尔", "曼谷", "巴黎", "大阪", "清迈"}
    airline_pool = AIRLINES["international"] if arrival_city in international_cities else AIRLINES["domestic"]

    cabin_multiplier = {"economy": 1.0, "business": 2.5, "first": 5.0}
    multiplier = cabin_multiplier.get(cabin_class, 1.0)

    flights: list[Flight] = []
    for index in range(count):
        airline_name, airline_code = airline_pool[index % len(airline_pool)]
        duration = round(random.uniform(*duration_range), 1)
        stops = random.choices([0, 1, 2], weights=[60, 30, 10])[0]
        base_price = 500 + duration * random.randint(200, 500) - stops * 200
        price = max(300, round(base_price * multiplier))
        dep_hour = random.randint(6, 20)

        flights.append(
            Flight(
                airline=airline_name,
                flight_no=f"{airline_code}{random.randint(100, 9999)}",
                departure_city=departure_city,
                arrival_city=arrival_city,
                departure_time=f"{date}T{dep_hour:02d}:{random.choice(['00', '30'])}:00",
                arrival_time=f"{date}T到达",
                price=float(price),
                duration_hours=duration,
                stops=stops,
                cabin_class=cabin_class,
            )
        )

    return sorted(flights, key=lambda f: f.price)


# ━━━━━━━━━━━━━━━━━━ 统一入口 ━━━━━━━━━━━━━━━━━━


async def search_flights(
    departure_city: str,
    arrival_city: str,
    date: str,
    cabin_class: str = "economy",
    count: int = 6,
) -> list[Flight]:
    """搜索航班：真实 API 优先，失败自动降级到 mock。"""
    if settings.FLIGHT_API_PROVIDER == "mock":
        return _mock_search_flights(departure_city, arrival_city, date, cabin_class, count)

    try:
        return await _amadeus_search_flights(departure_city, arrival_city, date, cabin_class, count)
    except Exception as exc:
        logger.warning("[FlightSearch] Amadeus API 调用失败，降级到 mock: {}", exc)
        return _mock_search_flights(departure_city, arrival_city, date, cabin_class, count)
