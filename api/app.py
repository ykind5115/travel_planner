"""FastAPI backend for the multi-agent travel planner."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config.settings import settings
from models.schemas import TravelPlanState, TravelStyle, UserPreferences
from orchestrator.pipeline import TravelPlanningPipeline

app = FastAPI(
    title="Multi-Agent Travel Planner",
    description="A 6-agent travel planning workflow with LangGraph orchestration.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlanRequest(BaseModel):
    budget: float = Field(10000, gt=0, description="Total budget in CNY")
    departure_city: str = Field("北京", description="Departure city")
    start_date: str = Field("2026-05-01", description="Start date")
    end_date: str = Field("2026-05-05", description="End date")
    travel_style: str = Field("comfort", description="Travel style")
    num_travelers: int = Field(1, ge=1, description="Number of travelers")
    interests: list[str] = Field(default_factory=list)
    notes: str = ""


class PlanSummary(BaseModel):
    destination: str = ""
    country: str = ""
    flight_cost: float = 0
    hotel_cost: float = 0
    activity_cost: float = 0
    total_cost: float = 0
    budget: float = 0
    within_budget: bool = True
    adjustment_rounds: int = 0
    hotel_name: str = ""
    days: int = 0
    highlights: list[str] = []
    warnings: list[str] = []


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "travel-planner", "agents": 6}


def _build_preferences(req: PlanRequest) -> UserPreferences:
    try:
        return UserPreferences(
            budget=req.budget,
            travel_style=TravelStyle(req.travel_style),
            departure_city=req.departure_city,
            start_date=req.start_date,
            end_date=req.end_date,
            num_travelers=req.num_travelers,
            interests=req.interests,
            notes=req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/plan", response_model=PlanSummary)
async def create_plan(req: PlanRequest):
    prefs = _build_preferences(req)
    pipeline = TravelPlanningPipeline()
    state: TravelPlanState = await pipeline.run(prefs)

    dest = state.selected_destination
    budget = state.budget_breakdown

    return PlanSummary(
        destination=dest.city if dest else "",
        country=dest.country if dest else "",
        flight_cost=budget.flight_cost if budget else 0,
        hotel_cost=budget.hotel_cost if budget else 0,
        activity_cost=budget.activity_cost if budget else 0,
        total_cost=budget.total_cost if budget else 0,
        budget=budget.budget if budget else req.budget,
        within_budget=budget.is_within_budget if budget else False,
        adjustment_rounds=state.adjustment_round,
        hotel_name=state.hotel_result.recommended.name
        if state.hotel_result and state.hotel_result.recommended
        else "",
        days=len(state.activity_result.day_plans) if state.activity_result else 0,
        highlights=dest.highlights if dest else [],
        warnings=state.error_messages,
    )


@app.post("/api/plan/full")
async def create_plan_full(req: PlanRequest):
    prefs = _build_preferences(req)
    pipeline = TravelPlanningPipeline()
    state = await pipeline.run(prefs)
    return state.model_dump()


def start():
    import uvicorn

    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)


if __name__ == "__main__":
    start()
