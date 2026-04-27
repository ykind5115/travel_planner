"""Hotel search tool with Amadeus Hotel API integration and mock fallback.

API: Amadeus Hotel Search (https://developers.amadeus.com)
Free sandbox: 10000 requests/month
Docs: https://developers.amadeus.com/self-service/category/hotel/api-doc/api-docs-v2
"""

from __future__ import annotations

import random
from datetime import datetime

import httpx
from loguru import logger

from config.settings import settings
from models.schemas import Hotel

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
        return _amadeus_token


# ━━━━━━━━━━━━━━━━━━ Amadeus 真实 API ━━━━━━━━━━━━━━━━━━


async def _amadeus_search_hotels(
    city: str,
    check_in: str,
    check_out: str,
    style: str = "comfort",
) -> list[Hotel]:
    """调用 Amadeus Hotel Search API。"""
    city_code = CITY_TO_IATA.get(city)
    if not city_code:
        logger.warning("[Amadeus] 城市 {} 无 IATA 映射，降级到 mock", city)
        return _mock_search_hotels(city, check_in, check_out, style)

    token = await _get_amadeus_token()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{settings.amadeus_base_url}/v1/shopping/hotel-offers",
            params={
                "cityCode": city_code,
                "checkInDate": check_in,
                "checkOutDate": check_out,
                "adults": 1,
                "roomQuantity": 1,
                "currency": "CNY",
                "bestRateOnly": "false",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        data = resp.json()

    hotels: list[Hotel] = []
    for offer in data.get("data", []):
        try:
            hotel_info = offer.get("hotel", {})
            price_info = offer.get("offers", [{}])[0] if offer.get("offers") else {}
            price = float(price_info.get("price", {}).get("total", 0))

            name = hotel_info.get("name", "未知酒店")
            rating_str = hotel_info.get("rating", "3")
            star_rating = min(5.0, max(1.0, float(rating_str)))
            amenities = [a.get("description", "") for a in hotel_info.get("amenities", []) if a.get("description")]

            hotels.append(
                Hotel(
                    name=name,
                    city=city,
                    address=hotel_info.get("address", {}).get("lines", [""])[0] if hotel_info.get("address") else "",
                    star_rating=star_rating,
                    user_rating=round(star_rating * 1.8, 1),
                    price_per_night=price,
                    amenities=amenities[:6] if amenities else ["WiFi"],
                    distance_to_center_km=round(random.uniform(0.3, 5.0), 1),
                )
            )
        except (KeyError, IndexError, ValueError) as exc:
            logger.debug("[Amadeus] 跳过无法解析的酒店: {}", exc)
            continue

    logger.info("[Amadeus] 找到 {} 家酒店 in {}", len(hotels), city)
    return hotels


# ━━━━━━━━━━━━━━━━━━ Mock 回退 ━━━━━━━━━━━━━━━━━━

CITY_HOTEL_DATA: dict[str, list[dict]] = {
    "东京": [
        {"name": "东京帝国酒店", "star": 5.0, "base_price": 1500, "amenities": ["WiFi", "温泉", "米其林餐厅", "管家服务"]},
        {"name": "新宿华盛顿酒店", "star": 4.0, "base_price": 650, "amenities": ["WiFi", "早餐", "健身房"]},
        {"name": "东京胶囊旅馆", "star": 2.0, "base_price": 120, "amenities": ["WiFi", "公共浴室"]},
        {"name": "涩谷精品酒店", "star": 4.5, "base_price": 900, "amenities": ["WiFi", "酒吧", "屋顶花园"]},
    ],
    "曼谷": [
        {"name": "曼谷文华东方酒店", "star": 5.0, "base_price": 800, "amenities": ["WiFi", "SPA", "泳池", "河景"]},
        {"name": "考山路精品旅舍", "star": 3.0, "base_price": 100, "amenities": ["WiFi", "酒吧", "公共区域"]},
        {"name": "素坤逸万豪酒店", "star": 4.5, "base_price": 500, "amenities": ["WiFi", "泳池", "健身房", "早餐"]},
        {"name": "暹罗经济酒店", "star": 3.0, "base_price": 150, "amenities": ["WiFi", "空调"]},
    ],
    "default": [
        {"name": "城市中心大酒店", "star": 4.0, "base_price": 500, "amenities": ["WiFi", "早餐", "健身房"]},
        {"name": "豪华五星酒店", "star": 5.0, "base_price": 1000, "amenities": ["WiFi", "SPA", "泳池", "管家服务"]},
        {"name": "经济连锁酒店", "star": 3.0, "base_price": 200, "amenities": ["WiFi", "空调"]},
        {"name": "青年旅舍", "star": 2.0, "base_price": 80, "amenities": ["WiFi", "公共厨房"]},
    ],
}


def _mock_search_hotels(
    city: str,
    check_in: str,
    check_out: str,
    style: str = "comfort",
) -> list[Hotel]:
    """Mock 酒店搜索，当 API 不可用时使用。"""
    templates = CITY_HOTEL_DATA.get(city, CITY_HOTEL_DATA["default"])
    style_multiplier = {
        "budget": 0.7,
        "comfort": 1.0,
        "luxury": 1.5,
        "adventure": 0.6,
        "cultural": 0.9,
        "relaxation": 1.2,
    }
    multiplier = style_multiplier.get(style, 1.0)

    hotels: list[Hotel] = []
    for template in templates:
        noise = random.uniform(0.85, 1.15)
        hotels.append(
            Hotel(
                name=template["name"],
                city=city,
                address=f"{city}市中心区域",
                star_rating=template["star"],
                user_rating=round(random.uniform(7.0, 9.8), 1),
                price_per_night=round(template["base_price"] * multiplier * noise),
                amenities=template["amenities"],
                distance_to_center_km=round(random.uniform(0.3, 5.0), 1),
            )
        )

    return sorted(hotels, key=lambda h: h.price_per_night)


# ━━━━━━━━━━━━━━━━━━ 统一入口 ━━━━━━━━━━━━━━━━━━


async def search_hotels(
    city: str,
    check_in: str,
    check_out: str,
    style: str = "comfort",
) -> list[Hotel]:
    """搜索酒店：真实 API 优先，失败自动降级到 mock。"""
    if settings.HOTEL_API_PROVIDER == "mock":
        return _mock_search_hotels(city, check_in, check_out, style)

    try:
        return await _amadeus_search_hotels(city, check_in, check_out, style)
    except Exception as exc:
        logger.warning("[HotelSearch] Amadeus API 调用失败，降级到 mock: {}", exc)
        return _mock_search_hotels(city, check_in, check_out, style)
