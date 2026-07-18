from datetime import datetime, timezone
from typing import Any, Optional, List
from pydantic import BaseModel, Field
import uuid

class MessageModel(BaseModel):
    id: Optional[str] = None
    conversation_id: str
    role: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ConversationModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    property_id: str
    current_step: str
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    messages: List[MessageModel] = Field(default_factory=list)

class RealEstateObjectModel(BaseModel):
    id: Optional[str] = None
    user_id: str
    name: str
    address: Optional[str] = None
    data: Optional[Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserModel(BaseModel):
    id: Optional[str] = None
    username: str
    hashed_password: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RetailConceptModel(BaseModel):
    id: Optional[str] = None
    name: str
    format_type: str
    positioning_strategy: str
    target_audience: str
    anchor_strategy: str
    tenant_guidelines: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
