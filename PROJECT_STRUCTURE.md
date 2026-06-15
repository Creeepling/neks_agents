# Neks Agents — Project Structure and Logic

This document provides a high-level overview of the architecture, database schema, and logical flow of the Neks real estate conversational agent system.

## High-Level Architecture

The project is built as a monolithic **FastAPI** backend that also serves a vanilla **HTML/CSS/JS** single-page application frontend. It is designed to be easily deployable to Google Cloud Run via a single Docker container.

### Core Technologies
- **Backend:** Python 3.12, FastAPI, SQLAlchemy
- **Frontend:** Vanilla JavaScript, HTML5, CSS3 (No build step)
- **AI / LLM:** Google Gemini API integrated via `instructor` for strict JSON structured data extraction.
- **Database:** SQLite (local development) / PostgreSQL (production via Cloud SQL)
- **Authentication:** JWT (JSON Web Tokens) with `bcrypt` password hashing.

---

## Directory Structure

```text
Neks_clean/
├── app/
│   ├── __init__.py
│   ├── auth.py         # JWT generation, validation, and password hashing (bcrypt)
│   ├── config.py       # Pydantic BaseSettings for environment variables (.env)
│   ├── database.py     # SQLAlchemy engine, session management, and ORM Models
│   ├── llm.py          # Gemini API integration, System Prompts, and Extraction Schemas
│   ├── main.py         # FastAPI app, API route definitions, static file serving
│   └── schemas.py      # Pydantic models for API request/response validation
├── frontend/
│   └── index.html      # Complete Single-Page Application (UI + logic)
├── scratch/
│   └── test_api.py     # End-to-end Python test script using FastAPI TestClient
├── .env.example        # Template for local environment variables
├── Dockerfile          # Multi-stage Dockerfile for Cloud Run deployment
├── requirements.txt    # Core dependencies (FastAPI, SQLAlchemy, google-genai, etc.)
└── requirements.prod.txt # Production-only dependencies (psycopg2-binary)
```

---

## Database Schema

The database uses SQLAlchemy ORM and consists of four main tables. All data is scoped to the `User` who created it.

1. **`users`**
   - `id`, `username`, `hashed_password`, `created_at`
2. **`properties`**
   - `id`, `user_id`, `name`, `address`
   - `data` (JSON/JSONB): A flexible schemaless column. As the AI extracts data during conversations, the structured JSON is merged into this column.
3. **`conversations`**
   - `id` (UUID), `property_id`, `user_id`
   - `current_step` (String): e.g., `step_1_lookup`, `step_2_analysis`. Determines which system prompt and extraction schema the AI uses.
   - `status` (String): `active` or `completed`.
4. **`messages`**
   - `id`, `conversation_id`, `role` (user/assistant/system), `content` (Text)

---

## Logical Flow

### 1. Multi-Step Conversation Lifecycle
Instead of a single continuous chat, the system is broken into distinct **Steps**. Each step is essentially an isolated agent designed to achieve a specific goal (e.g., gathering financial data, assessing risk).

1. **Start Step:** The user selects a step from the UI. The backend calls `/conversations/validate` to ensure the property's JSON `data` column contains the prerequisite information for that step. If prerequisites are missing, the user is warned.
2. **Chat:** A new `Conversation` is created. Every message sent by the user triggers a call to Gemini. The backend pulls the full history of the current conversation and prepends the **System Prompt** specific to the current step (defined in `llm.py`).
3. **Commit Extraction:** When the user is satisfied, they click "Commit". The backend uses the `instructor` library to ask Gemini to review the entire conversation history and extract data matching a strict **Pydantic Schema** specific to the step.
4. **Data Merge:** The extracted fields are merged into the `properties.data` JSON column, making that data available for future steps. The conversation is marked `completed`.

### 2. Authentication Flow
- User submits credentials to `/auth/token`.
- Backend verifies against hashed passwords in DB.
- Returns a JWT string.
- Frontend stores JWT in `localStorage` and attaches it to the `Authorization: Bearer <token>` header for all subsequent API calls.
- `get_current_user` dependency in FastAPI decodes the token and attaches the `User` object to the request.

### 3. Production Deployment
- The app is containerized using `Dockerfile`.
- Deployed on **Google Cloud Run**.
- Connects securely to **Google Cloud SQL (PostgreSQL)** via Unix sockets.
- The `app/main.py` explicitly serves the `frontend/index.html` on the root `/` path, unifying the API and the UI on a single domain to avoid CORS issues.
