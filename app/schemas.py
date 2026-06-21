from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Auth Schemas
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=128)
    password: str = Field(..., min_length=6)


class UserResponse(BaseModel):
    id: int
    username: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


# ---------------------------------------------------------------------------
# Property Schemas
# ---------------------------------------------------------------------------

class PropertyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    city: str = Field(..., min_length=1, max_length=256)
    address: str = Field(..., min_length=1, max_length=512)
    square_meters: Optional[float] = None
    floors: Optional[int] = None


class PropertyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256)
    address: Optional[str] = Field(None, max_length=512)
    square_meters: Optional[float] = None
    floors: Optional[int] = None
    data: Optional[Dict[str, Any]] = None


class PropertyResponse(BaseModel):
    id: int
    name: str
    address: Optional[str]
    data: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Conversation Schemas
# ---------------------------------------------------------------------------

class ConversationCreate(BaseModel):
    property_id: int
    current_step: str = Field(
        ...,
        description="The step name for this conversation, e.g. 'step_1_lookup' or 'step_2_analysis'.",
    )


class ConversationResponse(BaseModel):
    id: str
    property_id: int
    current_step: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Message Schemas
# ---------------------------------------------------------------------------

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)


class MessageResponse(BaseModel):
    id: int
    conversation_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Chat Response Schema
# ---------------------------------------------------------------------------

class ChatResponse(BaseModel):
    """Returned after the agent replies to a user message."""
    agent_message: MessageResponse
    conversation_id: str


# ---------------------------------------------------------------------------
# Commit / Structured Extraction Schemas
# ---------------------------------------------------------------------------

class CommitResponse(BaseModel):
    """
    Returned after a commit action triggers LLM extraction and DB write.
    Contains the fields that were written into the property's JSON data blob.
    """
    property_id: int
    extracted_fields: Dict[str, Any]
    missing_fields: List[str]
    message: str


# ---------------------------------------------------------------------------
# Validation / Pre-flight Check Schemas
# ---------------------------------------------------------------------------

class StepValidationResponse(BaseModel):
    """
    Returned by the pre-flight check before starting a new step.
    The UI should present warnings to the user and optionally allow bypass.
    """
    can_proceed: bool
    missing_fields: List[str]
    message: str
