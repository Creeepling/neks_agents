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

class AnalyzedOfferSchema(BaseModel):
    url: str = Field(description="Ссылка на объявление")
    title: str = Field(description="Заголовок объявления")
    offer_type: str = Field(description="Тип сделки: Аренда или Продажа")
    price: float = Field(description="Общая стоимость (в месяц для аренды, полная для продажи)")
    price_per_sqm: float = Field(description="Стоимость за квадратный метр")
    area_sqm: float = Field(description="Общая площадь в квадратных метрах")
    floor: Optional[str] = Field(None, description="Этаж или этажность")
    condition: Optional[str] = Field(None, description="Состояние отделки (например: 'shell and core', 'типовая отделка', 'требует ремонта')")
    power_kw: Optional[float] = Field(None, description="Электрическая мощность в кВт (важно для коммерции)")
    key_advantages: List[str] = Field(description="Список из 2-3 главных преимуществ объекта из описания")
    key_disadvantages: List[str] = Field(description="Список из 2-3 главных недостатков или рисков из описания")
    summary: str = Field(description="Краткое резюме описания (не более 3 предложений)")

class MarketOfferModel(BaseModel):
    id: Optional[str] = None
    property_id: str
    data: AnalyzedOfferSchema
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
