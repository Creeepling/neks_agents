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
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import auth as auth_utils
from app.config import settings
from app.database import (
    Conversation,
    Message,
    RealEstateObject,
    User,
    get_db,
    init_db,
)
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

app = FastAPI(
    title="Real Estate Agent Backend",
    description="Multi-step conversational AI backend for real estate research and analysis.",
    version="1.0.0",
    lifespan=lifespan,
)

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
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: decode the JWT and return the authenticated User row."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    username = auth_utils.decode_access_token(token)
    if username is None:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive.")

    return user


# ---------------------------------------------------------------------------
# Auth Routes
# ---------------------------------------------------------------------------

@app.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Auth"])
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Register a new user account."""
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{payload.username}' is already taken.",
        )

    user = User(
        username=payload.username,
        hashed_password=auth_utils.hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/token", response_model=Token, tags=["Auth"])
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate with username + password and receive a JWT access token."""
    user = db.query(User).filter(User.username == form.username).first()

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
def list_properties(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all properties belonging to the authenticated user."""
    return db.query(RealEstateObject).filter(RealEstateObject.user_id == current_user.id).all()


@app.post("/properties", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED, tags=["Properties"])
def create_property(
    payload: PropertyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new real estate object for the authenticated user."""
    prop = RealEstateObject(
        user_id=current_user.id,
        name=payload.name,
        address=payload.address,
        data={
            "city_name": payload.city,
            "exact_location": payload.address
        },
    )
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop


@app.get("/properties/{property_id}", response_model=PropertyResponse, tags=["Properties"])
def get_property(
    property_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single property by ID (must belong to the authenticated user)."""
    prop = db.query(RealEstateObject).filter(
        RealEstateObject.id == property_id,
        RealEstateObject.user_id == current_user.id,
    ).first()

    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

    return prop


@app.put("/properties/{property_id}", response_model=PropertyResponse, tags=["Properties"])
def update_property(
    property_id: int,
    payload: PropertyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a property's name, address, or raw data blob."""
    prop = db.query(RealEstateObject).filter(
        RealEstateObject.id == property_id,
        RealEstateObject.user_id == current_user.id,
    ).first()

    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

    if payload.name is not None:
        prop.name = payload.name
    if payload.address is not None:
        prop.address = payload.address
    if payload.data is not None:
        prop.data = {**(prop.data or {}), **payload.data}

    prop.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(prop)
    return prop


@app.delete("/properties/{property_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Properties"])
def delete_property(
    property_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a property and all its associated conversations and messages."""
    prop = db.query(RealEstateObject).filter(
        RealEstateObject.id == property_id,
        RealEstateObject.user_id == current_user.id,
    ).first()

    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

    db.delete(prop)
    db.commit()


# ---------------------------------------------------------------------------
# Conversations Routes
# ---------------------------------------------------------------------------

@app.get("/conversations/validate", response_model=StepValidationResponse, tags=["Conversations"])
def validate_step(
    property_id: int = Query(..., description="The property to validate for."),
    step: str = Query(..., description="The step name to validate (e.g. 'step_2_analysis')."),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Pre-flight check before starting a step.
    Returns which fields required by the step are missing from the property data.
    The UI can display a warning and allow the user to bypass if desired.
    """
    prop = db.query(RealEstateObject).filter(
        RealEstateObject.id == property_id,
        RealEstateObject.user_id == current_user.id,
    ).first()

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a new conversation session for a given property and step."""
    prop = db.query(RealEstateObject).filter(
        RealEstateObject.id == payload.property_id,
        RealEstateObject.user_id == current_user.id,
    ).first()

    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found.")

    if payload.current_step not in STEP_SYSTEM_PROMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown step '{payload.current_step}'. Known steps: {list(STEP_SYSTEM_PROMPTS.keys())}",
        )

    conversation = Conversation(
        user_id=current_user.id,
        property_id=payload.property_id,
        current_step=payload.current_step,
        status="active",
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@app.get("/conversations/{conversation_id}", tags=["Conversations"])
def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a conversation and its full message history."""
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Post a user message to the conversation and receive the agent's reply.
    The agent reply is persisted to the database before being returned.
    """
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()

    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    if conv.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This conversation is already completed. Start a new conversation to continue.",
        )

    # Fetch current property data to inject into the agent's context
    prop = db.query(RealEstateObject).filter(RealEstateObject.id == conv.property_id).first()
    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated property not found.")

    # Persist the user message
    user_msg = Message(conversation_id=conv.id, role="user", content=payload.content)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # Reload conversation with messages for history building
    db.refresh(conv)

    # Call the LLM
    try:
        reply_text = get_agent_reply(conv, prop.data, payload.content)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    # Persist the agent reply
    agent_msg = Message(conversation_id=conv.id, role="assistant", content=reply_text)
    db.add(agent_msg)
    db.commit()
    db.refresh(agent_msg)

    return ChatResponse(
        agent_message=MessageResponse.model_validate(agent_msg),
        conversation_id=conv.id,
    )


@app.post("/conversations/{conversation_id}/commit", response_model=CommitResponse, tags=["Conversations"])
def commit_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run structured extraction on the conversation history and merge the results
    into the property's JSON data blob.
    Does NOT close the conversation — the user can continue chatting after committing.
    """
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()

    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    prop = db.query(RealEstateObject).filter(RealEstateObject.id == conv.property_id).first()
    if prop is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated property not found.")

    try:
        extracted, missing = extract_structured_data(conv)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    # Merge extracted fields into the property's existing data blob
    prop.data = {**(prop.data or {}), **extracted}
    prop.updated_at = datetime.now(timezone.utc)
    db.commit()

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a conversation as completed. No further messages can be sent after this."""
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()

    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    conv.status = "completed"
    db.commit()
    db.refresh(conv)
    return conv


# ---------------------------------------------------------------------------
# System Endpoints
# ---------------------------------------------------------------------------

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
