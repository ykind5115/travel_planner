"""Streamlit frontend for the FastAPI-backed travel planner."""

from __future__ import annotations

import os
from datetime import date, timedelta

import httpx
import streamlit as st


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


st.set_page_config(page_title="Travel Planner", page_icon="TP", layout="wide")
st.title("Travel Planner")
st.caption("FastAPI backend + LangGraph multi-agent orchestration + Streamlit frontend")

with st.sidebar:
    st.header("Trip Preferences")
    budget = st.number_input("Budget (CNY)", min_value=1000, max_value=500000, value=10000, step=1000)
    departure_city = st.text_input("Departure City", value="Beijing")
    start_date = st.date_input("Start Date", value=date.today() + timedelta(days=30))
    end_date = st.date_input("End Date", value=date.today() + timedelta(days=35))
    travel_style = st.selectbox(
        "Travel Style",
        ["comfort", "budget", "luxury", "adventure", "cultural", "relaxation"],
    )
    num_travelers = st.number_input("Travelers", min_value=1, max_value=10, value=1)
    interests = st.multiselect("Interests", ["Food", "History", "Art", "Nature", "Shopping", "Photography", "Sports"])
    notes = st.text_area("Notes")
    submit = st.button("Generate Plan", type="primary", use_container_width=True)

if not submit:
    st.info("Fill in the trip preferences on the left, then generate a plan.")
    st.markdown(
        """
```mermaid
flowchart LR
    A[Streamlit Frontend] --> B[FastAPI Backend]
    B --> C[LangGraph Main Graph]
    C --> D[Preference Agent]
    D --> E[Destination Agent]
    E --> F[Parallel Search Subgraph]
    F --> G[Budget Agent]
    G --> H[Plan Result]
```
"""
    )
    st.stop()

payload = {
    "budget": float(budget),
    "departure_city": departure_city,
    "start_date": start_date.strftime("%Y-%m-%d"),
    "end_date": end_date.strftime("%Y-%m-%d"),
    "travel_style": travel_style,
    "num_travelers": int(num_travelers),
    "interests": interests,
    "notes": notes,
}

try:
    with st.spinner("Running LangGraph travel planning workflow..."):
        response = httpx.post(f"{API_BASE_URL}/api/plan/full", json=payload, timeout=180)
        response.raise_for_status()
        state = response.json()
except httpx.ConnectError:
    st.error(f"Cannot reach backend service at {API_BASE_URL}. Start FastAPI first.")
    st.stop()
except httpx.HTTPStatusError as exc:
    st.error(f"Backend returned an error: {exc.response.text}")
    st.stop()
except httpx.HTTPError as exc:
    st.error(f"Request failed: {exc}")
    st.stop()

destination = (state.get("destination_rec") or {}).get("selected") or {}
budget_breakdown = state.get("budget_breakdown") or {}
flight_result = state.get("flight_result") or {}
hotel_result = state.get("hotel_result") or {}
activity_result = state.get("activity_result") or {}

if destination:
    st.subheader(f"{destination.get('city', '')}, {destination.get('country', '')}")
    st.write(destination.get("description", ""))
    highlights = destination.get("highlights") or []
    if highlights:
        st.write("Highlights: " + ", ".join(highlights))

cols = st.columns(4)
cols[0].metric("Flights", f"Y{budget_breakdown.get('flight_cost', 0):.0f}")
cols[1].metric("Hotels", f"Y{budget_breakdown.get('hotel_cost', 0):.0f}")
cols[2].metric("Activities", f"Y{budget_breakdown.get('activity_cost', 0):.0f}")
cols[3].metric("Total", f"Y{budget_breakdown.get('total_cost', 0):.0f}")

if budget_breakdown:
    remaining = budget_breakdown.get("remaining", 0)
    st.write(f"Budget: Y{budget_breakdown.get('budget', 0):.0f} | Remaining: Y{remaining:.0f}")

tab_flight, tab_hotel, tab_activity, tab_debug = st.tabs(["Flights", "Hotels", "Itinerary", "Workflow"])

with tab_flight:
    outbound = flight_result.get("recommended_outbound")
    inbound = flight_result.get("recommended_return")
    if outbound:
        st.write(f"Outbound: {outbound['airline']} {outbound['flight_no']} | Y{outbound['price']:.0f}")
    if inbound:
        st.write(f"Return: {inbound['airline']} {inbound['flight_no']} | Y{inbound['price']:.0f}")

with tab_hotel:
    hotel = hotel_result.get("recommended")
    if hotel:
        st.write(f"{hotel['name']} | {hotel['star_rating']} stars | Y{hotel['price_per_night']:.0f}/night")
        st.write("Amenities: " + ", ".join(hotel.get("amenities") or []))

with tab_activity:
    for day in activity_result.get("day_plans") or []:
        st.markdown(f"#### {day['date']} | Y{day.get('day_cost', 0):.0f}")
        for activity in day.get("activities") or []:
            st.write(
                f"- {activity.get('time_slot', '')}: {activity.get('name', '')} "
                f"({activity.get('duration_hours', 0)}h, Y{activity.get('price', 0):.0f})"
            )

with tab_debug:
    st.write(f"State: {state.get('state')}")
    st.write(f"Adjustment Rounds: {state.get('adjustment_round', 0)}")
    for message in state.get("error_messages") or []:
        st.warning(message)
