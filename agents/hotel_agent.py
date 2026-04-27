"""Hotel agent: searches and ranks accommodation options."""

from __future__ import annotations

from datetime import datetime

from loguru import logger

from models.schemas import Hotel, HotelSearchResult, TravelPlanState
from tools.hotel_search import search_hotels

from .base_agent import BaseAgent


class HotelAgent(BaseAgent):
    name = "HotelAgent"

    async def execute(self, state: TravelPlanState) -> TravelPlanState:
        pref = state.preferences
        dest = state.selected_destination
        if pref is None or dest is None:
            raise ValueError("Preferences and destination are required.")

        nights = self._calc_nights(pref.start_date, pref.end_date)
        hotels = await search_hotels(dest.city, pref.start_date, pref.end_date, pref.travel_style.value)
        rec = self._best_hotel(hotels, pref.budget * 0.4 / max(nights, 1), pref.travel_style.value)
        room_count = max(1, (pref.num_travelers + 1) // 2)
        total = rec.price_per_night * nights * room_count if rec else 0

        state.hotel_result = HotelSearchResult(
            hotels=hotels,
            recommended=rec,
            total_nights=nights,
            total_hotel_cost=total,
        )
        logger.info("[{}] selected hotel: {}, total cost: {:.0f}", self.name, rec.name if rec else "N/A", total)
        return state

    @staticmethod
    def _calc_nights(start: str, end: str) -> int:
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.strptime(end, "%Y-%m-%d")
            return max((end_date - start_date).days, 1)
        except (ValueError, TypeError):
            return 3

    @staticmethod
    def _best_hotel(hotels: list[Hotel], nightly_budget: float, style: str) -> Hotel | None:
        if not hotels:
            return None

        star_pref = {
            "budget": 2.5,
            "comfort": 3.5,
            "luxury": 4.5,
            "adventure": 2.5,
            "cultural": 3.5,
            "relaxation": 4.0,
        }
        target_star = star_pref.get(style, 3.5)

        def score(hotel: Hotel) -> float:
            price_score = 20 if hotel.price_per_night <= nightly_budget else 0
            star_score = 30 - abs(hotel.star_rating - target_star) * 10
            rating_score = hotel.user_rating * 3
            location_score = max(0, 10 - hotel.distance_to_center_km * 3)
            return price_score + star_score + rating_score + location_score

        return max(hotels, key=score)
