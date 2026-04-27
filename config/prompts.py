"""Centralized prompt templates for LLM-enabled agents."""

from __future__ import annotations


DESTINATION_SYSTEM_PROMPT = (
    "You are a travel destination recommendation expert. "
    "Return JSON only and do not include extra explanation."
)

DESTINATION_USER_TEMPLATE = (
    "Budget: {budget}\n"
    "Departure city: {departure_city}\n"
    "Dates: {start_date} to {end_date}\n"
    "Travel style: {travel_style}\n"
    "Travelers: {num_travelers}\n"
    "Interests: {interests}\n\n"
    "Recommend 3 destinations and return a JSON array in this format:\n"
    '[{{"city":"City","country":"Country","description":"Short description",'
    '"cost_level":"low/medium/high","highlights":["Highlight 1","Highlight 2"]}}]'
)

ACTIVITY_SYSTEM_PROMPT = (
    "You are a travel itinerary planner. "
    "Return JSON only and do not include extra explanation."
)

ACTIVITY_USER_TEMPLATE = (
    "Destination: {city}, {country}\n"
    "Travel style: {travel_style}\n"
    "Daily budget: {daily_budget}\n"
    "Days: {num_days}\n"
    "Interests: {interests}\n\n"
    "Generate one morning, one afternoon, and one evening activity per day. "
    "Return a JSON array in this format:\n"
    '[{{"date":"YYYY-MM-DD","activities":[{{"name":"Activity","time_slot":"morning",'
    '"duration_hours":2,"price":100,"category":"sightseeing"}}]}}]'
)
