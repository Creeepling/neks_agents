# Neks Agents — Real Estate AI Intelligence Platform

A multi-agent conversational AI backend and single-page platform for commercial real estate research, due diligence, retail tenant matching, and investment analysis. Built with **FastAPI**, **Google Cloud Firestore**, **Google Gemini**, and integrated geospatial/market data tools.

---

## Key Features

- **Dynamic Multi-Agent Pipeline**: Configurable multi-step workflow defined in `agents.yaml` and manageable directly via Firestore (`/system/agents-config/json`).
- **Tool-Calling Ecosystem**:
  - **DaData Integration**: Address normalization, geocoding, cadastral validation, and alcohol/business license checks.
  - **2GIS Integration**: Surrounding infrastructure discovery, competitor mapping, rubric densities, and foot-traffic indicators.
  - **CIAN / Apify Scraper**: Real-time automated scraping of nearby market lease and sale offers.
  - **Financial Calculator**: Automated calculation of rental yields, payback periods, Capex/Opex, and unit economics.
- **Multimodal Document & EGRN Analysis**: Automated parsing of Rosreestr EGRN statements and project documents with Gemini Multimodal.
- **Tenant Matching & Retail Concepts**: Comprehensive commercial concepts and retailer requirement database with AI-assisted autofill.
- **Structured Data Extraction (Commit)**: Schema-enforced structured extraction at the end of each conversation step to merge insights into property records.
- **Presentation Deck Generator**: Automatic HTML/presentation slide deck generator tailored for investor and tenant teasers.
- **Built-in Web Interface**: Lightweight, responsive Single-Page Application (SPA) served directly by FastAPI.
- **Enterprise Security & Reliability**: JWT authentication, bcrypt password hashing, and API rate limiting (`slowapi`).

---

## Local Development Setup

### 1. Create and Activate Virtual Environment
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Google Cloud Credentials
Authenticate your local environment to access Firestore:
```bash
gcloud auth application-default login
```
*(Or set `GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"` in your environment)*

### 4. Configure Environment Variables
Copy the template `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

Example `.env`:
```env
# Required: Google Gemini API Key (https://aistudio.google.com/)
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-3-flash-preview

# Required: Firestore Configuration
FIRESTORE_PROJECT_ID=your-gcp-project-id
FIRESTORE_DATABASE_ID=neksagents

# Required: Secret Key for JWT Authentication
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-secure-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Optional / Tool Integrations:
DADATA_API_KEY=your-dadata-api-key
TWOGIS_API_KEY=your-2gis-api-key
APIFY_API_TOKEN=your-apify-token

# Optional: Telegram Diagnostics Notifications
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id

ENVIRONMENT=local
```

### 5. Run the Development Server
```bash
uvicorn app.main:app --reload
```

- Web UI: `http://localhost:8000/`
- Interactive Swagger Docs: `http://localhost:8000/docs`
- OpenAPI Specification: `http://localhost:8000/openapi.json`

---

## API Overview

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/register` | Register a new user |
| `POST` | `/auth/token` | Login and obtain JWT access token |

### Properties & Real Estate Objects
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/properties` | List all properties for current user |
| `POST` | `/properties` | Create a new property |
| `GET` | `/properties/{id}` | Get property details and accumulated JSON data |
| `PUT` | `/properties/{id}` | Update property details |
| `DELETE` | `/properties/{id}` | Delete property and associated data |
| `POST` | `/properties/{id}/documents` | Upload and summarize property document |
| `DELETE` | `/properties/{id}/documents/{doc_id}` | Remove document from property |
| `POST` | `/properties/{id}/egrn_extracts` | Upload and parse EGRN (Rosreestr) extract |
| `DELETE` | `/properties/{id}/egrn_extracts/{doc_id}` | Remove EGRN extract |
| `POST` | `/properties/{id}/cian_offers` | Trigger CIAN market offers scraping |
| `GET` | `/properties/{id}/cian_offers` | Retrieve saved CIAN market offers |
| `POST` | `/properties/{id}/cian_offers/clear` | Clear saved market offers |
| `POST` | `/properties/{id}/fetch_tenants` | Pull tenant infrastructure via 2GIS |
| `POST` | `/properties/{id}/fetch_tenants_ai` | AI-assisted tenant and foot-traffic discovery |
| `GET` | `/properties/{id}/slides` | Generate presentation deck data |

### Conversations & Agents
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/conversations/validate` | Pre-flight validation of prerequisite data for a step |
| `POST` | `/conversations` | Initialize a conversation for a property & agent step |
| `GET` | `/conversations/{id}` | Get conversation metadata and full message history |
| `POST` | `/conversations/{id}/message` | Send user message and get agent response (with tool execution) |
| `POST` | `/conversations/{id}/commit` | Extract structured schema data and merge into property |
| `POST` | `/conversations/{id}/complete` | Mark conversation as completed |
| `DELETE` | `/conversations/{id}` | Delete conversation |

### Retailers & Concepts
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/retailers` | List retail tenant requirement profiles |
| `POST` | `/retailers` | Create a retailer requirement profile |
| `PUT` | `/retailers/{id}` | Update retailer profile |
| `DELETE` | `/retailers/{id}` | Delete retailer profile |
| `POST` | `/retailers/auto-fill` | Auto-fill retailer profile data using AI |
| `GET` | `/concepts` | List commercial property concepts |
| `POST` | `/concepts` | Create a commercial concept |
| `PUT` | `/concepts/{id}` | Update commercial concept |
| `DELETE` | `/concepts/{id}` | Delete commercial concept |

### System & Pipeline Configuration
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/steps` | List active agent steps and metadata |
| `GET` | `/system/tools` | List available agent tools and descriptions |
| `GET` | `/system/agents-config/json` | Retrieve current agent pipeline configuration |
| `PUT` | `/system/agents-config/json` | Update pipeline configuration dynamically in Firestore |
| `POST` | `/system/agents-config/reset` | Reset pipeline configuration to default `agents.yaml` |
| `POST` | `/system/seed-retailers` | Seed default retail tenant profiles |
| `POST` | `/system/seed-concepts` | Seed default commercial concept profiles |

---

## Agent Pipeline Configuration

Agent steps are declared in `agents.yaml` (or customized at runtime in Firestore). Each step defines:
- **`name`** & **`role`**: Descriptive title and system identity.
- **`system_prompt`**: Specialized instructions and analytical guidelines.
- **`tools`**: Bound capabilities (e.g. `twogis_maps`, `dadata_licenses`, `financial_calculator`).
- **`input_requirements`**: Prerequisite property fields checked before starting.
- **`output_schema`**: JSON Schema extracted upon `/commit` and merged into the property store.

---

## Deployment (Google Cloud Run)

The application is containerized and optimized for Google Cloud Run with Firestore.

### 1. Build and Submit Container Image
```bash
export PROJECT_ID=your-gcp-project-id
export REGION=europe-west1

gcloud builds submit --tag gcr.io/$PROJECT_ID/neks-agents
```

### 2. Deploy to Cloud Run
```bash
gcloud run deploy neks-agents \
  --image gcr.io/$PROJECT_ID/neks-agents \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars "FIRESTORE_PROJECT_ID=$PROJECT_ID,FIRESTORE_DATABASE_ID=neksagents,GEMINI_MODEL=gemini-3-flash-preview,ENVIRONMENT=production" \
  --set-secrets "GEMINI_API_KEY=GEMINI_API_KEY:latest,SECRET_KEY=SECRET_KEY:latest,DADATA_API_KEY=DADATA_API_KEY:latest,TWOGIS_API_KEY=TWOGIS_API_KEY:latest,APIFY_API_TOKEN=APIFY_API_TOKEN:latest"
```

> **Note**: Ensure the Cloud Run service account has the **Cloud Datastore User** (`roles/datastore.user`) role to access Firestore Native databases.
