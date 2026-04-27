"""Weather tool with OpenWeatherMap API integration and mock fallback.

API: OpenWeatherMap (https://openweathermap.org/api)
Free tier: 60 calls/minute, 1000 calls/day
Docs: https://openweathermap.org/forecast5
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import httpx
from loguru import logger

from config.settings import settings

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


@dataclass
class WeatherInfo:
    city: str
    date: str
    temperature_high: int
    temperature_low: int
    condition: str
    humidity: int
    rain_probability: int
    suggestion: str


# ━━━━━━━━━━━━━━━━━━ OpenWeatherMap 真实 API ━━━━━━━━━━━━━━━━━━

CONDITION_MAP: dict[int, str] = {
    2: "雷阵雨",
    3: "小雨",
    5: "雨",
    6: "雪",
    7: "雾",
    800: "晴",
    801: "多云",
    802: "多云",
    803: "阴",
    804: "阴",
}


def _weather_code_to_condition(code: int) -> str:
    if code in CONDITION_MAP:
        return CONDITION_MAP[code]
    prefix = code // 100
    if prefix in CONDITION_MAP:
        return CONDITION_MAP[prefix]
    return "多云"


def _generate_suggestion(high: int, low: int, rain_prob: int) -> str:
    if rain_prob > 50:
        return "建议携带雨具，穿防水鞋。"
    if high > 30:
        return "天气较热，注意防晒和补水。"
    if low < 5:
        return "天气偏冷，注意保暖。"
    return "天气适宜，适合户外活动。"


async def _openweather_get_weather(city: str, date: str) -> WeatherInfo:
    """调用 OpenWeatherMap 5-day/3-hour forecast API。"""
    city_en = CITY_NAME_EN.get(city, city)
    api_key = settings.OPENWEATHER_API_KEY

    if not api_key:
        raise ValueError("OPENWEATHER_API_KEY 未配置")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={
                "q": city_en,
                "appid": api_key,
                "units": "metric",
                "cnt": 40,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    target_date = date[:10]
    matching: list[dict] = []
    for item in data.get("list", []):
        if item.get("dt_txt", "").startswith(target_date):
            matching.append(item)

    if not matching:
        logger.warning("[OpenWeather] 未找到 {} 的 {} 天气数据，降级到 mock", city, date)
        return _mock_get_weather(city, date)

    temps = [m["main"]["temp"] for m in matching]
    humidities = [m["main"]["humidity"] for m in matching]
    conditions = [m["weather"][0]["id"] for m in matching if m.get("weather")]

    high = round(max(temps))
    low = round(min(temps))
    humidity = round(sum(humidities) / len(humidities))
    condition = _weather_code_to_condition(conditions[0]) if conditions else "多云"
    rain_prob = sum(1 for m in matching if m.get("pop", 0) > 0.3) / max(len(matching), 1) * 100

    logger.info("[OpenWeather] {} {} 天气: {} {}°C/{}°C", city, date, condition, high, low)
    return WeatherInfo(
        city=city,
        date=date,
        temperature_high=high,
        temperature_low=low,
        condition=condition,
        humidity=humidity,
        rain_probability=round(rain_prob),
        suggestion=_generate_suggestion(high, low, round(rain_prob)),
    )


# ━━━━━━━━━━━━━━━━━━ Mock 回退 ━━━━━━━━━━━━━━━━━━

DEFAULT_PROFILE = {
    "spring": {"high": (15, 25), "low": (8, 15), "conditions": ["晴", "多云", "小雨"], "humidity": (40, 70), "rain": 25},
    "summer": {"high": (25, 35), "low": (18, 25), "conditions": ["晴", "多云", "雷阵雨"], "humidity": (60, 85), "rain": 45},
    "autumn": {"high": (15, 25), "low": (8, 18), "conditions": ["晴", "多云"], "humidity": (40, 65), "rain": 20},
    "winter": {"high": (0, 12), "low": (-5, 5), "conditions": ["晴", "多云", "阴", "小雪"], "humidity": (30, 55), "rain": 15},
}


def _month_to_season(month: int) -> str:
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    if month in (9, 10, 11):
        return "autumn"
    return "winter"


def _mock_get_weather(city: str, date: str) -> WeatherInfo:
    """Mock 天气查询，当 API 不可用时使用。"""
    try:
        month = int(date.split("-")[1])
    except (IndexError, ValueError):
        month = 6

    profile = DEFAULT_PROFILE[_month_to_season(month)]
    high = random.randint(*profile["high"])
    low = random.randint(*profile["low"])
    condition = random.choice(profile["conditions"])
    humidity = random.randint(*profile["humidity"])
    rain = profile["rain"]

    return WeatherInfo(
        city=city,
        date=date,
        temperature_high=high,
        temperature_low=low,
        condition=condition,
        humidity=humidity,
        rain_probability=rain,
        suggestion=_generate_suggestion(high, low, rain),
    )


# ━━━━━━━━━━━━━━━━━━ 统一入口 ━━━━━━━━━━━━━━━━━━


async def get_weather(city: str, date: str) -> WeatherInfo:
    """查询天气：真实 API 优先，失败自动降级到 mock。"""
    if settings.WEATHER_API_PROVIDER == "mock":
        return _mock_get_weather(city, date)

    try:
        return await _openweather_get_weather(city, date)
    except Exception as exc:
        logger.warning("[WeatherAPI] OpenWeatherMap 调用失败，降级到 mock: {}", exc)
        return _mock_get_weather(city, date)
