"""
Pydantic data models shared by the travel planning API, UI and agents.
"""

from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, Field


class TravelStyle(str, Enum):
    BUDGET = "budget"
    COMFORT = "comfort"
    LUXURY = "luxury"
    ADVENTURE = "adventure"
    CULTURAL = "cultural"
    RELAXATION = "relaxation"


class PlanningState(str, Enum):
    COLLECTING_PREFERENCES = "collecting_preferences"
    RECOMMENDING_DESTINATIONS = "recommending_destinations"
    SEARCHING_PARALLEL = "searching_parallel"
    BUDGET_CHECKING = "budget_checking"
    ADJUSTING = "adjusting"
    COMPLETED = "completed"
    FAILED = "failed"


class UserPreferences(BaseModel):
    budget: float = Field(..., gt=0, description="Total budget in CNY")
    travel_style: TravelStyle = Field(default=TravelStyle.COMFORT)
    departure_city: str = Field(..., description="Departure city")
    start_date: str = Field(..., description="Start date, YYYY-MM-DD")
    end_date: str = Field(..., description="End date, YYYY-MM-DD")
    num_travelers: int = Field(default=1, ge=1)
    interests: list[str] = Field(default_factory=list, description="Interest tags")
    dietary_restrictions: list[str] = Field(default_factory=list)
    accessibility_needs: list[str] = Field(default_factory=list)
    notes: str = Field(default="", description="Additional notes")


class Destination(BaseModel):
    city: str
    country: str
    description: str = ""
    best_season: str = ""
    visa_required: bool = False
    safety_score: float = Field(default=8.0, ge=0, le=10)
    cost_level: str = Field(default="medium", description="low / medium / high")
    highlights: list[str] = Field(default_factory=list)


class DestinationRecommendation(BaseModel):
    destinations: list[Destination]
    selected: Optional[Destination] = None
    reasoning: str = ""


class Flight(BaseModel):
    airline: str
    flight_no: str
    departure_city: str
    arrival_city: str
    departure_time: str
    arrival_time: str
    price: float = Field(ge=0)
    duration_hours: float = Field(ge=0)
    stops: int = Field(default=0, ge=0)
    cabin_class: str = Field(default="economy")


class FlightSearchResult(BaseModel):
    outbound_flights: list[Flight] = Field(default_factory=list)
    return_flights: list[Flight] = Field(default_factory=list)
    recommended_outbound: Optional[Flight] = None
    recommended_return: Optional[Flight] = None
    total_flight_cost: float = 0.0


class Hotel(BaseModel):
    name: str
    city: str
    address: str = ""
    star_rating: float = Field(default=3.0, ge=1, le=5)
    user_rating: float = Field(default=8.0, ge=0, le=10)
    price_per_night: float = Field(ge=0)
    amenities: list[str] = Field(default_factory=list)
    distance_to_center_km: float = Field(default=0.0, ge=0)


class HotelSearchResult(BaseModel):
    hotels: list[Hotel] = Field(default_factory=list)
    recommended: Optional[Hotel] = None
    total_nights: int = 0
    total_hotel_cost: float = 0.0


class Activity(BaseModel):
    name: str
    category: str = Field(default="sightseeing")
    location: str = ""
    duration_hours: float = Field(default=2.0, ge=0)
    price: float = Field(default=0.0, ge=0)
    rating: float = Field(default=8.0, ge=0, le=10)
    description: str = ""
    time_slot: str = Field(default="", description="morning / afternoon / evening")


class DayPlan(BaseModel):
    date: str
    activities: list[Activity] = Field(default_factory=list)
    day_cost: float = 0.0


class ActivitySearchResult(BaseModel):
    day_plans: list[DayPlan] = Field(default_factory=list)
    total_activity_cost: float = 0.0


class BudgetBreakdown(BaseModel):
    flight_cost: float = 0.0
    hotel_cost: float = 0.0
    activity_cost: float = 0.0
    total_cost: float = 0.0
    budget: float = 0.0
    remaining: float = 0.0
    is_within_budget: bool = True
    over_budget_amount: float = 0.0
    suggestions: list[str] = Field(default_factory=list)


class TravelPlanState(BaseModel):
    """Global state passed between LangGraph nodes."""

    state: PlanningState = PlanningState.COLLECTING_PREFERENCES
    preferences: Optional[UserPreferences] = None
    destination_rec: Optional[DestinationRecommendation] = None
    flight_result: Optional[FlightSearchResult] = None
    hotel_result: Optional[HotelSearchResult] = None
    activity_result: Optional[ActivitySearchResult] = None
    budget_breakdown: Optional[BudgetBreakdown] = None
    adjustment_round: int = 0
    max_adjustments: int = 3
    error_messages: Annotated[list[str], operator.add] = Field(default_factory=list)

    @property
    def selected_destination(self) -> Optional[Destination]:
        if self.destination_rec and self.destination_rec.selected:
            return self.destination_rec.selected
        return None
