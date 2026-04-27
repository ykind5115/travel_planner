"""Flight agent: searches and ranks outbound and return flights."""

from __future__ import annotations

from loguru import logger

from models.schemas import Flight, FlightSearchResult, TravelPlanState
from tools.flight_search import search_flights

from .base_agent import BaseAgent


class FlightAgent(BaseAgent):
    name = "FlightAgent"

    async def execute(self, state: TravelPlanState) -> TravelPlanState:
        pref = state.preferences
        dest = state.selected_destination
        if pref is None or dest is None:
            raise ValueError("Preferences and destination are required.")

        outbound = await search_flights(pref.departure_city, dest.city, pref.start_date)
        returns = await search_flights(dest.city, pref.departure_city, pref.end_date)

        rec_out = self._best_flight(outbound, pref.budget * 0.3)
        rec_ret = self._best_flight(returns, pref.budget * 0.3)
        total = ((rec_out.price if rec_out else 0) + (rec_ret.price if rec_ret else 0)) * pref.num_travelers

        state.flight_result = FlightSearchResult(
            outbound_flights=outbound,
            return_flights=returns,
            recommended_outbound=rec_out,
            recommended_return=rec_ret,
            total_flight_cost=total,
        )
        logger.info("[{}] selected flights, total cost: {:.0f}", self.name, total)
        return state

    @staticmethod
    def _best_flight(flights: list[Flight], budget_share: float) -> Flight | None:
        if not flights:
            return None

        max_price = max(f.price for f in flights) or 1
        max_duration = max(f.duration_hours for f in flights) or 1

        def score(flight: Flight) -> float:
            price_score = 1 - (flight.price / max_price)
            duration_score = 1 - (flight.duration_hours / max_duration)
            stop_score = 1 - (flight.stops / 3)
            budget_bonus = 10 if flight.price <= budget_share else 0
            return price_score * 50 + duration_score * 30 + stop_score * 20 + budget_bonus

        return max(flights, key=score)
