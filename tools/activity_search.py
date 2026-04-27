"""Activity search tool with Google Places API integration and mock fallback.

API: Google Places (New) — https://console.cloud.google.com
Free tier: $200 monthly credit (roughly 40000 text searches)
Docs: https://developers.google.com/maps/documentation/places/web-service/text-search
"""

from __future__ import annotations

import random

import httpx
from loguru import logger

from config.settings import settings
from models.schemas import Activity

# ━━━━━━━━━━━━━━━━━━ 城市名 → 英文映射 ━━━━━━━━━━━━━━━━━━

CITY_NAME_EN: dict[str, str] = {
    "北京": "Beijing",
    "上海": "Shanghai",
    "广州": "Guangzhou",
    "深圳": "Shenzhen",
    "成都": "Chengdu",
    "杭州": "Hangzhou",
    "东京": "Tokyo",
    "大阪": "Osaka",
    "首尔": "Seoul",
    "曼谷": "Bangkok",
    "清迈": "Chiang Mai",
    "巴黎": "Paris",
    "伦敦": "London",
    "纽约": "New York",
    "新加坡": "Singapore",
    "悉尼": "Sydney",
}

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "sightseeing": ["景点", "landmark", "temple", "museum", "palace", "castle", "park"],
    "food": ["美食", "restaurant", "food", "market", "street food", "cuisine"],
    "experience": ["体验", "experience", "workshop", "spa", "onsen", "massage"],
    "shopping": ["购物", "shopping", "mall", "market", "bazaar"],
    "relaxation": ["休闲", "beach", "spa", "garden", "onsen", "yoga"],
}

CATEGORY_SLOT: dict[str, str] = {
    "sightseeing": "morning",
    "food": "afternoon",
    "experience": "afternoon",
    "shopping": "afternoon",
    "relaxation": "evening",
}

# ━━━━━━━━━━━━━━━━━━ Google Places 真实 API ━━━━━━━━━━━━━━━━━━


async def _google_search_activities(
    city: str,
    interests: list[str] | None = None,
) -> list[Activity]:
    """调用 Google Places Text Search (New) API。"""
    api_key = settings.GOOGLE_PLACES_API_KEY
    if not api_key:
        raise ValueError("GOOGLE_PLACES_API_KEY 未配置")

    city_en = CITY_NAME_EN.get(city, city)
    interests = interests or ["景点", "美食"]
    activities: list[Activity] = []

    queries = [f"tourist attractions in {city_en}"]
    for interest in interests[:3]:
        queries.append(f"{interest} in {city_en}")

    seen_names: set[str] = set()

    async with httpx.AsyncClient(timeout=30) as client:
        for query in queries:
            try:
                resp = await client.post(
                    "https://places.googleapis.com/v1/places:searchText",
                    json={
                        "textQuery": query,
                        "pageSize": 10,
                        "languageCode": "zh-CN",
                    },
                    headers={
                        "X-Goog-Api-Key": api_key,
                        "Content-Type": "application/json",
                        "X-Goog-FieldMask": "places.displayName,places.primaryType,places.rating,places.formattedAddress",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                logger.debug("[GooglePlaces] 查询 '{}' 失败: {}", query, exc)
                continue

            for place in data.get("places", []):
                name = place.get("displayName", {}).get("text", "")
                if not name or name in seen_names:
                    continue
                seen_names.add(name)

                place_type = place.get("primaryType", "")
                category = _classify_category(place_type, interests)
                rating = place.get("rating", 8.0)
                slot = CATEGORY_SLOT.get(category, "morning")

                activities.append(
                    Activity(
                        name=name,
                        category=category,
                        location=city,
                        duration_hours=round(random.uniform(1.5, 3.0), 1),
                        price=round(random.uniform(0, 300), 0) if category != "sightseeing" else 0,
                        rating=min(rating, 10.0) if rating else 8.0,
                        description=f"{city} - {name}",
                        time_slot=slot,
                    )
                )

    logger.info("[GooglePlaces] 找到 {} 个活动 in {}", len(activities), city)
    return activities


def _classify_category(place_type: str, interests: list[str]) -> str:
    """根据 Google Places type 和用户兴趣推断活动类别。"""
    type_lower = place_type.lower()
    if any(kw in type_lower for kw in ["restaurant", "food", "cafe", "bakery"]):
        return "food"
    if any(kw in type_lower for kw in ["museum", "art_gallery", "church", "temple", "mosque", "synagogue", "hindu_temple"]):
        return "sightseeing"
    if any(kw in type_lower for kw in ["spa", "beauty_salon", "gym"]):
        return "relaxation"
    if any(kw in type_lower for kw in ["shopping_mall", "clothing_store", "department_store"]):
        return "shopping"
    if any(kw in type_lower for kw in ["park", "tourist_attraction", "amusement_park", "zoo", "aquarium"]):
        return "sightseeing"
    return "experience"


# ━━━━━━━━━━━━━━━━━━ Mock 回退 ━━━━━━━━━━━━━━━━━━

CITY_ACTIVITIES: dict[str, list[dict]] = {
    "东京": [
        {"name": "浅草寺", "cat": "sightseeing", "price": 0, "hours": 2.0, "slot": "morning"},
        {"name": "筑地市场海鲜早餐", "cat": "food", "price": 200, "hours": 1.5, "slot": "morning"},
        {"name": "明治神宫", "cat": "sightseeing", "price": 0, "hours": 1.5, "slot": "morning"},
        {"name": "涩谷十字路口", "cat": "sightseeing", "price": 0, "hours": 0.5, "slot": "afternoon"},
        {"name": "teamLab 数字艺术馆", "cat": "experience", "price": 250, "hours": 2.5, "slot": "afternoon"},
        {"name": "东京塔", "cat": "sightseeing", "price": 80, "hours": 1.5, "slot": "afternoon"},
        {"name": "新宿歌舞伎町", "cat": "experience", "price": 0, "hours": 2.0, "slot": "evening"},
        {"name": "居酒屋体验", "cat": "food", "price": 300, "hours": 2.0, "slot": "evening"},
    ],
    "曼谷": [
        {"name": "大皇宫", "cat": "sightseeing", "price": 35, "hours": 2.5, "slot": "morning"},
        {"name": "卧佛寺", "cat": "sightseeing", "price": 15, "hours": 1.5, "slot": "morning"},
        {"name": "水上市场", "cat": "experience", "price": 80, "hours": 3.0, "slot": "morning"},
        {"name": "暹罗广场购物", "cat": "shopping", "price": 0, "hours": 2.0, "slot": "afternoon"},
        {"name": "泰式按摩", "cat": "relaxation", "price": 120, "hours": 2.0, "slot": "afternoon"},
        {"name": "考山路小吃", "cat": "food", "price": 60, "hours": 2.0, "slot": "evening"},
        {"name": "湄南河夜游", "cat": "experience", "price": 200, "hours": 2.0, "slot": "evening"},
    ],
    "default": [
        {"name": "城市地标参观", "cat": "sightseeing", "price": 0, "hours": 2.0, "slot": "morning"},
        {"name": "当地博物馆", "cat": "sightseeing", "price": 80, "hours": 2.5, "slot": "morning"},
        {"name": "特色午餐", "cat": "food", "price": 150, "hours": 1.5, "slot": "afternoon"},
        {"name": "老城区漫步", "cat": "sightseeing", "price": 0, "hours": 2.0, "slot": "afternoon"},
        {"name": "日落观景点", "cat": "sightseeing", "price": 50, "hours": 1.0, "slot": "evening"},
        {"name": "当地夜市", "cat": "food", "price": 100, "hours": 2.0, "slot": "evening"},
    ],
}


def _mock_search_activities(city: str, interests: list[str] | None = None) -> list[Activity]:
    """Mock 活动搜索，当 API 不可用时使用。"""
    templates = CITY_ACTIVITIES.get(city, CITY_ACTIVITIES["default"])
    interests = interests or []

    activities: list[Activity] = []
    for template in templates:
        bonus = sum(1 for tag in interests if tag.lower() in template["name"].lower())
        rating = round(random.uniform(7.5, 9.5) + bonus * 0.3, 1)
        activities.append(
            Activity(
                name=template["name"],
                category=template["cat"],
                location=city,
                duration_hours=template["hours"],
                price=float(template["price"]),
                rating=min(rating, 10.0),
                description=f"{city} - {template['name']}",
                time_slot=template["slot"],
            )
        )

    return activities


# ━━━━━━━━━━━━━━━━━━ 统一入口 ━━━━━━━━━━━━━━━━━━


async def search_activities(city: str, interests: list[str] | None = None) -> list[Activity]:
    """搜索活动/景点：真实 API 优先，失败自动降级到 mock。"""
    if settings.ACTIVITY_API_PROVIDER == "mock":
        return _mock_search_activities(city, interests)

    try:
        result = await _google_search_activities(city, interests)
        if result:
            return result
        logger.warning("[ActivitySearch] Google Places 返回空结果，降级到 mock")
    except Exception as exc:
        logger.warning("[ActivitySearch] Google Places API 调用失败，降级到 mock: {}", exc)

    return _mock_search_activities(city, interests)
