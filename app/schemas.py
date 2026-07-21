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
    id: str
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
    current_tenants: Optional[Any] = None


class PropertyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256)
    city: Optional[str] = Field(None, max_length=256)
    address: Optional[str] = Field(None, max_length=512)
    square_meters: Optional[float] = None
    floors: Optional[int] = None
    current_tenants: Optional[Any] = None
    data: Optional[Dict[str, Any]] = None


class PropertyResponse(BaseModel):
    id: str
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
    property_id: str
    current_step: str = Field(
        ...,
        description="The step name for this conversation, e.g. 'step_1_lookup' or 'step_2_analysis'.",
    )


class ConversationResponse(BaseModel):
    id: str
    property_id: str
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
    id: str
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
    property_id: str
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


# ---------------------------------------------------------------------------
# Retailer Requirements Schemas
# ---------------------------------------------------------------------------

class RangeSchema(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None

class RentRateSchema(BaseModel):
    min: Optional[float] = None
    avg: Optional[float] = None
    max: Optional[float] = None

class RetailerBase(BaseModel):
    company: str
    brand: str
    format: Optional[str] = None
    is_developing: Optional[bool] = True
    area_sqm: Optional[RangeSchema] = None
    power_kw: Optional[RangeSchema] = None
    ceilings_m: Optional[RangeSchema] = None
    rent_rate: Optional[RentRateSchema] = None
    requirements: Optional[str] = None

class RetailerCreate(RetailerBase):
    pass

class RetailerUpdate(BaseModel):
    company: Optional[str] = None
    brand: Optional[str] = None
    format: Optional[str] = None
    is_developing: Optional[bool] = None
    area_sqm: Optional[RangeSchema] = None
    power_kw: Optional[RangeSchema] = None
    ceilings_m: Optional[RangeSchema] = None
    rent_rate: Optional[RentRateSchema] = None
    requirements: Optional[str] = None

class RetailerResponse(RetailerBase):
    id: str

# ---------------------------------------------------------------------------
# Retail Object Concept Schemas
# ---------------------------------------------------------------------------

class ConceptBase(BaseModel):
    name: str
    format_type: str
    positioning_strategy: str
    target_audience: str
    anchor_strategy: str
    tenant_guidelines: str

class ConceptCreate(ConceptBase):
    pass

class ConceptUpdate(BaseModel):
    name: Optional[str] = None
    format_type: Optional[str] = None
    positioning_strategy: Optional[str] = None
    target_audience: Optional[str] = None
    anchor_strategy: Optional[str] = None
    tenant_guidelines: Optional[str] = None

class ConceptResponse(ConceptBase):
    id: str
    created_at: datetime
    updated_at: datetime
