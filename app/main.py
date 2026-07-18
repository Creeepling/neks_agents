"""
FastAPI Application – Real Estate Agent Backend

Endpoints
---------
Auth
  POST /auth/register          - Create a new user account
  POST /auth/token             - Login and receive a JWT access token

Properties
  GET  /properties             - List all properties belonging to the current user
  POST /properties             - Create a new property
  GET  /properties/{id}        - Get a single property with full JSON data
  PUT  /properties/{id}        - Update property name / address
  DELETE /properties/{id}      - Delete a property and all its conversations

Conversations
  GET  /conversations/validate - Pre-flight check: can a step start given current DB data?
  POST /conversations          - Start a new conversation for a property & step
  GET  /conversations/{id}     - Get conversation details + full message history
  POST /conversations/{id}/message  - Send a user message and receive the agent reply
  POST /conversations/{id}/commit   - Extract structured data and write it to the property
  POST /conversations/{id}/complete - Mark a conversation as completed
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import os
from fastapi import Depends, FastAPI, HTTPException, Query, status, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app import auth as auth_utils
from app.config import settings
from app.database import get_repository, init_db
from app.repository import DataRepository
from google.cloud import firestore
from app.models import ConversationModel, MessageModel, RealEstateObjectModel, UserModel, RetailConceptModel
from app.llm import AGENTS_CONFIG, STEP_EXTRACTION_SCHEMAS, STEP_SYSTEM_PROMPTS, extract_structured_data, get_agent_reply
from app.schemas import (
    ChatResponse,
    CommitResponse,
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
    PropertyCreate,
    PropertyResponse,
    PropertyUpdate,
    StepValidationResponse,
    Token,
    UserCreate,
    UserResponse,
    RetailerCreate,
    RetailerUpdate,
    RetailerResponse,
    ConceptCreate,
    ConceptUpdate,
    ConceptResponse,
)

# ---------------------------------------------------------------------------
# App Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app):
    """Initialize the database on startup."""
    init_db()
    yield


# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------

def get_real_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0]
    return request.client.host if request.client else "127.0.0.1"

limiter = Limiter(key_func=get_real_ip, default_limits=["120/minute"])

app = FastAPI(
    title="Real Estate Agent Backend",
    description="Multi-step conversational AI backend for real estate research and analysis.",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


# ---------------------------------------------------------------------------
# Auth Dependencies
# ---------------------------------------------------------------------------

def get_current_user(
    token: str = Depends(oauth2_scheme),
    repo: DataRepository = Depends(get_repository),
) -> UserModel:
    """FastAPI dependency: decode the JWT and return the authenticated User row."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    username = auth_utils.decode_access_token(token)
    if username is None:
        raise credentials_exception

    user = repo.get_user_by_username(username)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive.")

    return user


# ---------------------------------------------------------------------------
# Auth Routes
# ---------------------------------------------------------------------------

@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Auth"])
def register(payload: UserCreate, repo: DataRepository = Depends(get_repository)):
    """Register a new user account."""
    existing = repo.get_user_by_username(payload.username)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{payload.username}' is already taken.",
        )

    user = UserModel(
        username=payload.username,
        hashed_password=auth_utils.hash_password(payload.password),
    )
    user = repo.create_user(user)
    return user


@app.post("/auth/token", response_model=Token, tags=["Auth"])
def login(form: OAuth2PasswordRequestForm = Depends(), repo: DataRepository = Depends(get_repository)):
    """Authenticate with username + password and receive a JWT access token."""
    user = repo.get_user_by_username(form.username)

    if user is None or not auth_utils.verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive.")

    token = auth_utils.create_access_token(data={"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# Properties Routes
# ---------------------------------------------------------------------------

@app.get("/properties", response_model=list[PropertyResponse], tags=["Properties"])
@limiter.limit("10/minute")
def list_properties(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """Return all properties belonging to the authenticated user."""
    return repo.get_properties_for_user(current_user.id)


@app.post("/properties", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED, tags=["Properties"])
def create_property(
    payload: PropertyCreate,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """Create a new real estate object for the authenticated user."""
    prop = RealEstateObjectModel(
        user_id=current_user.id,
        name=payload.name,
        address=payload.address,
        data={
            "city_name": payload.city,
            "exact_location": payload.address,
        },
    )
    if payload.square_meters is not None:
        prop.data["square_meters"] = payload.square_meters
    if payload.floors is not None:
        prop.data["floors"] = payload.floors
    if payload.current_tenants is not None:
        prop.data["current_tenants"] = payload.current_tenants
    prop = repo.create_property(prop)
    return prop


@app.get("/properties/{property_id}", response_model=PropertyResponse, tags=["Properties"])
def get_property(
    property_id: str,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """Get a single property by ID (must belong to the authenticated user)."""
    prop = repo.get_property_by_id_and_user(property_id, current_user.id)

    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

    return prop


@app.put("/properties/{property_id}", response_model=PropertyResponse, tags=["Properties"])
def update_property(
    property_id: str,
    payload: PropertyUpdate,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """Update a property's name, address, or raw data blob."""
    prop = repo.get_property_by_id_and_user(property_id, current_user.id)

    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

    if payload.name is not None:
        prop.name = payload.name
    if payload.address is not None:
        prop.address = payload.address
        
    new_data = dict(prop.data or {})
    if payload.city is not None:
        new_data["city_name"] = payload.city
    if payload.square_meters is not None:
        new_data["square_meters"] = payload.square_meters
    if payload.floors is not None:
        new_data["floors"] = payload.floors
    if payload.current_tenants is not None:
        new_data["current_tenants"] = payload.current_tenants
        
    if payload.data is not None:
        new_data = {**new_data, **payload.data}

    prop.data = new_data

    prop.updated_at = datetime.now(timezone.utc)
    prop = repo.update_property(prop)
    return prop


@app.get("/properties/{property_id}/conversations", response_model=list[ConversationResponse], tags=["Properties"])
def get_property_conversations(
    property_id: str,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """Retrieve all conversations belonging to a property."""
    prop = repo.get_property_by_id_and_user(property_id, current_user.id)
    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")
        
    return repo.get_conversations_for_property(property_id)


@app.post("/properties/{property_id}/fetch_tenants", response_model=PropertyResponse, tags=["Properties"])
def fetch_building_tenants_endpoint(
    property_id: str,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """Fetch current tenants from 2GIS for the property's address and save them."""
    from app.tools.twogis_maps import fetch_building_tenants
    
    prop = repo.get_property_by_id_and_user(property_id, current_user.id)
    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")
        
    if not prop.address:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Property does not have an address set.")
    full_location = prop.address
    city_name = (prop.data or {}).get("city_name", "").strip()
    if city_name and city_name.lower() not in prop.address.lower():
        full_location = f"{city_name}, {prop.address}"
        
    tenants_result = fetch_building_tenants(full_location)
    
    if isinstance(tenants_result, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=tenants_result)
        
    new_data = dict(prop.data or {})
    existing = new_data.get("current_tenants", [])
    
    if isinstance(existing, str):
        existing_list = [{"name": "Старые данные", "categories": "", "floor": existing.strip()}] if existing.strip() else []
    else:
        existing_list = existing
        
    # Merge, keeping existing and appending new ones from 2GIS only if name doesn't match
    existing_names = {t.get("name", "").lower() for t in existing_list}
    for t in tenants_result:
        if t.get("name", "").lower() not in existing_names:
            existing_list.append(t)
            
    new_data["current_tenants"] = existing_list
        
    prop.data = new_data
    prop.updated_at = datetime.now(timezone.utc)
    prop = repo.update_property(prop)
        
    return prop


@app.get("/properties/{property_id}/slides", tags=["Properties"])
def download_presentation(
    property_id: str,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """Generate and download a PPTX presentation for the property."""
    from fastapi.responses import StreamingResponse
    from app.slides import extract_presentation_data, generate_pptx

    prop = repo.get_property_by_id_and_user(property_id, current_user.id)

    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

    # 1. Use LLM to structure presentation data
    presentation_data = extract_presentation_data(prop.data or {})

    # 2. Build PPTX
    pptx_io = generate_pptx(prop.name, prop.address or "", presentation_data)

    # 3. Return as downloadable file
    return StreamingResponse(
        pptx_io,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f'attachment; filename="Presentation_Property_{prop.id}.pptx"'
        }
    )


@app.delete("/properties/{property_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Properties"])
def delete_property(
    property_id: str,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """Delete a property and all its associated conversations and messages."""
    prop = repo.get_property_by_id_and_user(property_id, current_user.id)

    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

    repo.delete_property(property_id, current_user.id)


# ---------------------------------------------------------------------------
# Conversations Routes
# ---------------------------------------------------------------------------

@app.get("/conversations/validate", response_model=StepValidationResponse, tags=["Conversations"])
def validate_step(
    property_id: str = Query(..., description="The property to validate for."),
    step: str = Query(..., description="The step name to validate (e.g. 'step_2_analysis')."),
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """
    Pre-flight check before starting a step.
    Returns which fields required by the step are missing from the property data.
    The UI can display a warning and allow the user to bypass if desired.
    """
    prop = repo.get_property_by_id_and_user(property_id, current_user.id)

    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

    step_config = AGENTS_CONFIG.get(step)
    if step_config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown step '{step}'. Known steps: {list(AGENTS_CONFIG.keys())}",
        )

    existing_data = prop.data or {}
    required_fields = step_config.get("required_fields", [])
    missing = [f for f in required_fields if not existing_data.get(f)]

    if missing:
        return StepValidationResponse(
            can_proceed=True,  # User may still proceed — UI decides
            missing_fields=missing,
            message=(
                f"The property is missing data for {len(missing)} field(s): {', '.join(missing)}. "
                "You may proceed, but the agent will have less context to work with."
            ),
        )

    return StepValidationResponse(
        can_proceed=True,
        missing_fields=[],
        message="All expected fields are present. Ready to proceed.",
    )


@app.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED, tags=["Conversations"])
def start_conversation(
    payload: ConversationCreate,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """Start a new conversation session for a given property and step."""
    prop = repo.get_property_by_id_and_user(payload.property_id, current_user.id)

    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

    if payload.current_step not in STEP_SYSTEM_PROMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown step '{payload.current_step}'. Known steps: {list(STEP_SYSTEM_PROMPTS.keys())}",
        )

    conversation = ConversationModel(
        user_id=current_user.id,
        property_id=payload.property_id,
        current_step=payload.current_step,
        status="active",
    )
    conversation = repo.create_conversation(conversation)

    # Automatically generate the first message from the agent
    try:
        agent_config = AGENTS_CONFIG.get(payload.current_step, {})
        first_message = agent_config.get(
            "first_user_message", 
            "Начни работу над этим этапом. Задай первый вопрос или предложи варианты действий."
        )
        reply_text = get_agent_reply(
            conversation,
            prop,
            repo,
            first_message
        )
        agent_msg = MessageModel(conversation_id=conversation.id, role="assistant", content=reply_text)
        agent_msg = repo.add_message(agent_msg)
        conv = repo.get_conversation_by_id_and_user(conversation.id, current_user.id)
    except Exception as exc:
        # If generation fails, we still return the conversation, just without an initial message
        import traceback
        traceback.print_exc()
        agent_msg = MessageModel(conversation_id=conversation.id, role="assistant", content=f"INTERNAL ERROR: {exc}")
        repo.add_message(agent_msg)
        conv = repo.get_conversation_by_id_and_user(conversation.id, current_user.id)

    return conv


@app.get("/conversations/{conversation_id}", tags=["Conversations"])
def get_conversation(
    conversation_id: str,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """Get a conversation and its full message history."""
    conv = repo.get_conversation_by_id_and_user(conversation_id, current_user.id)

    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    return {
        "id": conv.id,
        "property_id": conv.property_id,
        "current_step": conv.current_step,
        "status": conv.status,
        "created_at": conv.created_at,
        "messages": [
            MessageResponse.model_validate(m) for m in conv.messages
        ],
    }


@app.post("/conversations/{conversation_id}/message", response_model=ChatResponse, tags=["Conversations"])
def send_message(
    conversation_id: str,
    payload: MessageCreate,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """
    Post a user message to the conversation and receive the agent's reply.
    The agent reply is persisted to the database before being returned.
    """
    conv = repo.get_conversation_by_id_and_user(conversation_id, current_user.id)

    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    if conv.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This conversation is already completed. Start a new conversation to continue.",
        )

    # Fetch current property data to inject into the agent's context
    prop = repo.get_property_by_id(conv.property_id)
    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated property not found.")

    # Persist the user message
    user_msg = MessageModel(conversation_id=conv.id, role="user", content=payload.content)
    user_msg = repo.add_message(user_msg)

    # Reload conversation with messages for history building
    conv = repo.get_conversation_by_id_and_user(conv.id, current_user.id)

    # Call the LLM
    try:
        reply_text = get_agent_reply(conv, prop, repo, payload.content)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    # Persist the agent reply
    agent_msg = MessageModel(conversation_id=conv.id, role="assistant", content=reply_text)
    agent_msg = repo.add_message(agent_msg)

    return ChatResponse(
        agent_message=MessageResponse.model_validate(agent_msg),
        conversation_id=conv.id,
    )


@app.post("/conversations/{conversation_id}/commit", response_model=CommitResponse, tags=["Conversations"])
def commit_conversation(
    conversation_id: str,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """
    Run structured extraction on the conversation history and merge the results
    into the property's JSON data blob.
    Does NOT close the conversation — the user can continue chatting after committing.
    """
    conv = repo.get_conversation_by_id_and_user(conversation_id, current_user.id)

    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    prop = repo.get_property_by_id(conv.property_id)
    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated property not found.")

    try:
        extracted, missing = extract_structured_data(conv)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Extraction failed: {type(exc).__name__}: {str(exc)}")

    # Merge extracted fields into the property's existing data blob
    prop.data = {**(prop.data or {}), **extracted}
    prop.updated_at = datetime.now(timezone.utc)
    repo.update_property(prop)

    return CommitResponse(
        property_id=prop.id,
        extracted_fields=extracted,
        missing_fields=missing,
        message=(
            f"Successfully extracted {len(extracted)} field(s) and saved to the property. "
            + (f"The following {len(missing)} field(s) were not found: {', '.join(missing)}." if missing else "")
        ),
    )


@app.post("/conversations/{conversation_id}/complete", response_model=ConversationResponse, tags=["Conversations"])
def complete_conversation(
    conversation_id: str,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """Mark a conversation as completed."""
    conv = repo.get_conversation_by_id_and_user(conversation_id, current_user.id)

    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    conv.status = "completed"
    repo.update_conversation(conv)
    conv = repo.get_conversation_by_id_and_user(conv.id, current_user.id)
    return conv


@app.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Conversations"])
def delete_conversation(
    conversation_id: str,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """Delete a conversation and its messages."""
    conv = repo.get_conversation_by_id_and_user(conversation_id, current_user.id)

    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    repo.delete_conversation(conversation_id, current_user.id)
    return None


# ---------------------------------------------------------------------------
# Retailers Routes
# ---------------------------------------------------------------------------

def get_firestore_db():
    return firestore.Client(project=settings.FIRESTORE_PROJECT_ID, database=settings.FIRESTORE_DATABASE_ID)

@app.get("/retailers", response_model=list[RetailerResponse], tags=["Retailers"])
def list_retailers(
    current_user: UserModel = Depends(get_current_user),
):
    """List all retailer requirements from Firestore."""
    db_fs = get_firestore_db()
    docs = db_fs.collection('retail_property_requirements').stream()
    retailers = []
    for doc in docs:
        data = doc.to_dict()
        data['id'] = doc.id
        retailers.append(data)
    return retailers

@app.post("/retailers", response_model=RetailerResponse, status_code=status.HTTP_201_CREATED, tags=["Retailers"])
def create_retailer(
    payload: RetailerCreate,
    current_user: UserModel = Depends(get_current_user),
):
    """Create a new retailer requirement."""
    db_fs = get_firestore_db()
    data = payload.model_dump(exclude_none=True)
    _, doc_ref = db_fs.collection('retail_property_requirements').add(data)
    data['id'] = doc_ref.id
    return data

@app.put("/retailers/{retailer_id}", response_model=RetailerResponse, tags=["Retailers"])
def update_retailer(
    retailer_id: str,
    payload: RetailerUpdate,
    current_user: UserModel = Depends(get_current_user),
):
    """Update an existing retailer requirement."""
    db_fs = get_firestore_db()
    doc_ref = db_fs.collection('retail_property_requirements').document(retailer_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Retailer not found.")
    
    update_data = payload.model_dump(exclude_unset=True)
    if update_data:
        doc_ref.update(update_data)
    
    updated_doc = doc_ref.get().to_dict()
    updated_doc['id'] = retailer_id
    return updated_doc

@app.delete("/retailers/{retailer_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Retailers"])
def delete_retailer(
    retailer_id: str,
    current_user: UserModel = Depends(get_current_user),
):
    """Delete a retailer requirement."""
    db_fs = get_firestore_db()
    db_fs.collection('retail_property_requirements').document(retailer_id).delete()
    return None


# ---------------------------------------------------------------------------
# System Endpoints
# ---------------------------------------------------------------------------

@app.post("/system/seed-retailers", tags=["System"])
def seed_retailers():
    """Seed the retail property requirements into Firestore."""
    try:
        from app.seed_retail_requirements import seed_database
        seed_database()
        return {"status": "success", "message": "Successfully seeded retail property requirements to Firestore."}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to seed database: {str(e)}")

@app.get("/steps", tags=["System"])
def get_available_steps():
    """Return the list of available agent steps from agents.yaml."""
    steps = []
    for step_id, config in AGENTS_CONFIG.items():
        steps.append({
            "id": step_id,
            "label": config.get("title", step_id),
            "desc": config.get("description", "")
        })
    return steps


# ---------------------------------------------------------------------------
# Retail Object Concepts Routes
# ---------------------------------------------------------------------------

@app.get("/concepts", response_model=list[ConceptResponse], tags=["Concepts"])
def get_all_concepts(
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository)
):
    """Get all global concepts."""
    concepts = repo.get_all_concepts()
    return concepts

@app.post("/concepts", response_model=ConceptResponse, status_code=status.HTTP_201_CREATED, tags=["Concepts"])
def create_concept(
    payload: ConceptCreate,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository)
):
    """Create a new global concept."""
    concept = RetailConceptModel(**payload.model_dump())
    concept = repo.create_concept(concept)
    return concept

@app.put("/concepts/{concept_id}", response_model=ConceptResponse, tags=["Concepts"])
def update_concept(
    concept_id: str,
    payload: ConceptUpdate,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """Update an existing concept."""
    concept = repo.get_concept_by_id(concept_id)
    if not concept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found.")
        
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(concept, key, value)
        
    concept.updated_at = datetime.now(timezone.utc)
    concept = repo.update_concept(concept)
    return concept

@app.delete("/concepts/{concept_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Concepts"])
def delete_concept(
    concept_id: str,
    current_user: UserModel = Depends(get_current_user),
    repo: DataRepository = Depends(get_repository),
):
    """Delete a concept."""
    success = repo.delete_concept(concept_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found.")
    return None

# ---------------------------------------------------------------------------
# Frontend Static Hosting
# ---------------------------------------------------------------------------

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serves the single-page application frontend."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "API is running. Frontend not found locally."}
