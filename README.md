# Real Estate Agent Backend

A multi-step conversational AI backend for real estate research and analysis. Built with FastAPI, SQLAlchemy, and Google Gemini.

## Features
- **JWT Authentication**: Secure user registration and login.
- **Property Management**: Create, list, update, and delete real estate objects with a flexible JSON data store.
- **Multi-step Conversations**: Each property can have multiple conversation sessions, one per analysis step.
- **Agent Replies**: Gemini-powered conversational responses with step-specific system prompts and property context injection.
- **Structured Extraction (Commit)**: At any point, trigger a commit to extract structured data from the conversation and write it to the property record.
- **Step Validation**: Pre-flight check endpoint to warn the UI about missing fields before starting a new step.
- **Cloud Run Ready**: Dockerfile with multi-stage build and dynamic `$PORT` configuration.

---

## Local Development Setup

### 1. Create a virtual environment
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
Copy the example below into a `.env` file in the project root:

```env
# Required: Get from Google AI Studio (https://aistudio.google.com/)
GEMINI_API_KEY=your-gemini-api-key

# Required: Change to a long random string in production
# Generate: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=change-me-in-production

# Optional: defaults to local SQLite
DATABASE_URL=sqlite:///./app.db

# Optional: defaults shown
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
GEMINI_MODEL=gemini-2.5-flash
ENVIRONMENT=local
```

### 4. Run the development server
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`

---

## API Overview

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Create a new user account |
| POST | `/auth/token` | Login and receive a JWT token |

### Properties
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/properties` | List all properties |
| POST | `/properties` | Create a property |
| GET | `/properties/{id}` | Get property + JSON data |
| PUT | `/properties/{id}` | Update name/address/data |
| DELETE | `/properties/{id}` | Delete property + conversations |

### Conversations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/conversations/validate` | Pre-flight check for a step |
| POST | `/conversations` | Start a new conversation |
| GET | `/conversations/{id}` | Get conversation + messages |
| POST | `/conversations/{id}/message` | Send user message, get agent reply |
| POST | `/conversations/{id}/commit` | Extract and save structured data |
| POST | `/conversations/{id}/complete` | Mark conversation as done |

---

## Extending the Pipeline

To add a new step (e.g. `step_3_negotiation`):

1. **Add a system prompt** in `app/llm.py` → `STEP_SYSTEM_PROMPTS`:
   ```python
   "step_3_negotiation": "You are a real estate negotiation coach..."
   ```

2. **Add an extraction schema** in `app/llm.py` → `STEP_EXTRACTION_SCHEMAS`:
   ```python
   class Step3ExtractionSchema(BaseModel):
       offer_price: Optional[float] = Field(None, description="...")
       ...

   STEP_EXTRACTION_SCHEMAS["step_3_negotiation"] = Step3ExtractionSchema
   ```

That's it. No other changes needed.

---

## Google Cloud Run Deployment

### Build and push the container
```bash
# Set your project and region
export PROJECT_ID=your-gcp-project-id
export REGION=europe-west1

# Build the image
gcloud builds submit --tag gcr.io/$PROJECT_ID/realestate-agent

# Deploy to Cloud Run
gcloud run deploy realestate-agent \
  --image gcr.io/$PROJECT_ID/realestate-agent \
  --region $REGION \
  --allow-unauthenticated \
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,SECRET_KEY=SECRET_KEY:latest,DATABASE_URL=DATABASE_URL:latest"
```

> **Note**: Store `GEMINI_API_KEY`, `SECRET_KEY`, and `DATABASE_URL` in **Google Secret Manager** before deploying.
> For the database, use **Cloud SQL (PostgreSQL)** or an external managed service like **Neon** or **Supabase**.
