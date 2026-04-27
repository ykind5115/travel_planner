# Travel Planner

A multi-agent travel planning project built with `LangGraph`, `FastAPI`, and `Streamlit`.

This project models travel planning as a graph-based workflow:

- `PreferenceAgent` enriches user preferences
- `DestinationAgent` recommends destinations
- `FlightAgent`, `HotelAgent`, and `ActivityAgent` run in parallel inside a LangGraph subgraph
- `BudgetAgent` validates cost and triggers bounded adjustment loops

The result is a portfolio-style AI engineering project that demonstrates:

- graph-based orchestration with `LangGraph`
- multi-agent task decomposition
- parallel search as a subgraph
- backend/frontend separation with `FastAPI` + `Streamlit`
- structured state management with `Pydantic`

## Architecture

```text
Streamlit UI
   |
   v
FastAPI API
   |
   v
LangGraph Main Graph
   |
   +--> Preference Agent
   +--> Destination Agent
   +--> Parallel Search Subgraph
   |      +--> Flight Agent
   |      +--> Hotel Agent
   |      +--> Activity Agent
   |
   +--> Budget Agent
   |
   +--> Final Travel Plan
```

## Tech Stack

- Python 3.12+
- LangGraph
- FastAPI
- Streamlit
- Pydantic
- httpx
- python-dotenv
- loguru

## Project Structure

```text
agents/         Agent implementations
api/            FastAPI backend
config/         Runtime config and prompt templates
models/         Pydantic schemas and workflow state
orchestrator/   LangGraph orchestration
tools/          Mock search/data tools
ui/             Streamlit frontend
```

## Features

- End-to-end multi-agent travel planning
- Graph-based orchestration instead of ad hoc async control flow
- Parallel flight/hotel/activity search
- Budget guardrail with retry loop
- Mock-friendly local demo mode
- API-driven frontend

## Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the backend:

```bash
python -m api.app
```

Start the frontend in another terminal:

```bash
streamlit run ui/streamlit_app.py
```

## Environment Variables

Create a local `.env` file with values like:

```env
LLM_PROVIDER=mock
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096
BUDGET_MAX_RETRIES=3
PARALLEL_TIMEOUT=120
API_HOST=0.0.0.0
API_PORT=8000
API_BASE_URL=http://localhost:8000
LOG_LEVEL=INFO
```

## API Endpoints

- `GET /api/health`
- `POST /api/plan`
- `POST /api/plan/full`

## Why This Project Matters

This repository is designed as a strong interview and portfolio project for AI engineering and backend roles. It highlights practical orchestration design, modular agent boundaries, stateful workflow control, and a clean frontend/backend split.
