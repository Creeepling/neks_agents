"""
LLM Orchestration Layer

Responsibilities:
- Building prompts from conversation history + DB property data.
- Calling the Gemini API for conversational replies.
- Running a separate structured-extraction call (commit step) to convert
  the conversation into typed, validated JSON for the database.

Extraction uses Instructor to guarantee a valid Pydantic model response.
Each step can define its own extraction schema; they are collected in
STEP_EXTRACTION_SCHEMAS at the bottom of this file.
"""

from typing import Any, Dict, List, Optional, Tuple

import instructor
from google import genai
from pydantic import BaseModel, Field

from app.config import settings
from app.database import Conversation, Message

# ---------------------------------------------------------------------------
# Client Setup
# ---------------------------------------------------------------------------

_raw_client = genai.Client(api_key=settings.GEMINI_API_KEY)

# Instructor-patched client for structured extraction calls
_instructor_client = instructor.from_genai(client=_raw_client, use_async=False)


# ---------------------------------------------------------------------------
# Step System Prompts
# These prompts set the agent's role and behaviour for each conversation step.
# Add or modify steps here to extend the pipeline.
# ---------------------------------------------------------------------------

STEP_SYSTEM_PROMPTS: Dict[str, str] = {
    "step_1_lookup": (
        "You are a real estate research assistant. Your task is to help the user gather "
        "key information about a property: its location, type (apartment / house / commercial), "
        "size in square metres, asking price, number of rooms, and any notable features or defects. "
        "Ask targeted questions to fill any gaps. When the user is satisfied, tell them they can "
        "commit the results using the Commit button."
    ),
    "step_2_analysis": (
        "You are a real estate investment analyst. The user has already gathered basic property data "
        "in a previous step. Your task is to help them evaluate the investment potential: market "
        "comparables, estimated rental yield, renovation costs, and a buy / hold / pass recommendation. "
        "Reference the property data that will be provided in the conversation context. "
        "Ask targeted questions to fill any gaps before giving a final assessment."
    ),
}

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful real estate assistant. Answer the user's questions clearly and concisely."
)


# ---------------------------------------------------------------------------
# Extraction Schemas
# Define one Pydantic model per step. The LLM will fill these during the
# commit call. Mark optional fields with Optional so partial data is valid.
# ---------------------------------------------------------------------------

class Step1ExtractionSchema(BaseModel):
    property_type: Optional[str] = Field(None, description="Type of property: apartment, house, commercial, land, etc.")
    location: Optional[str] = Field(None, description="City, neighbourhood, or full address of the property.")
    size_sqm: Optional[float] = Field(None, description="Total size in square metres.")
    price: Optional[float] = Field(None, description="Asking price in the local currency.")
    num_rooms: Optional[int] = Field(None, description="Total number of rooms (bedrooms + living rooms).")
    features: Optional[List[str]] = Field(None, description="Notable positive features (e.g. balcony, parking, new roof).")
    defects: Optional[List[str]] = Field(None, description="Known issues or defects mentioned by the user.")
    notes: Optional[str] = Field(None, description="Any other relevant information from the conversation.")


class Step2ExtractionSchema(BaseModel):
    market_comparables: Optional[str] = Field(None, description="Summary of comparable properties and their prices.")
    estimated_rental_yield_pct: Optional[float] = Field(None, description="Estimated annual rental yield as a percentage.")
    renovation_cost_estimate: Optional[float] = Field(None, description="Estimated renovation costs in the local currency.")
    recommendation: Optional[str] = Field(None, description="Agent recommendation: Buy, Hold, or Pass, with reasoning.")
    risk_notes: Optional[str] = Field(None, description="Key risks or caveats highlighted during analysis.")


STEP_EXTRACTION_SCHEMAS: Dict[str, type[BaseModel]] = {
    "step_1_lookup": Step1ExtractionSchema,
    "step_2_analysis": Step2ExtractionSchema,
}


# ---------------------------------------------------------------------------
# Prompt Building
# ---------------------------------------------------------------------------

def _build_messages(
    conversation: Conversation,
    property_data: Optional[Dict[str, Any]],
    new_user_message: str,
    history_limit: int = 20,
) -> List[Dict[str, str]]:
    """
    Assemble the message list to send to the LLM.

    Strategy:
      1. System prompt (step-specific role + property context injection).
      2. Recent conversation history (capped to avoid context-window bloat).
      3. New user message.
    """
    system_prompt = STEP_SYSTEM_PROMPTS.get(conversation.current_step, DEFAULT_SYSTEM_PROMPT)

    # Inject existing structured property data so the agent knows the context
    if property_data:
        system_prompt += (
            "\n\n--- Current Property Data ---\n"
            f"{property_data}\n"
            "Use this information when answering. Point out missing fields so the user can supply them."
        )
    else:
        system_prompt += "\n\nNo property data has been committed yet for this property."

    messages: List[Dict[str, str]] = [{"role": "user", "parts": [{"text": f"[SYSTEM]\n{system_prompt}"}]}]

    # Add recent history (oldest messages first, capped)
    recent: List[Message] = conversation.messages[-history_limit:] if conversation.messages else []
    for msg in recent:
        if msg.role in ("user", "assistant"):
            role = "user" if msg.role == "user" else "model"
            messages.append({"role": role, "parts": [{"text": msg.content}]})

    # New user turn
    messages.append({"role": "user", "parts": [{"text": new_user_message}]})

    return messages


# ---------------------------------------------------------------------------
# Chat Call
# ---------------------------------------------------------------------------

def get_agent_reply(
    conversation: Conversation,
    property_data: Optional[Dict[str, Any]],
    new_user_message: str,
) -> str:
    """
    Send the assembled prompt to Gemini and return the assistant's reply text.
    Raises RuntimeError if the API key is not configured or the call fails.
    """
    if not settings.GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. "
            "Set it in your .env file or as an environment variable."
        )

    messages = _build_messages(conversation, property_data, new_user_message)

    response = _raw_client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=messages,
    )

    if response and response.text:
        return response.text
    else:
        raise RuntimeError("The LLM returned an empty response. Please try again.")


# ---------------------------------------------------------------------------
# Structured Extraction (Commit Step)
# ---------------------------------------------------------------------------

def extract_structured_data(
    conversation: Conversation,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Run a dedicated extraction LLM call against the full conversation history
    and return a tuple of:
      - extracted: dict of non-null field values to merge into property data
      - missing: list of field names that could not be extracted (remained None)

    Uses Instructor to guarantee a valid Pydantic model response.
    Raises ValueError if no extraction schema is registered for the step.
    """
    schema_class = STEP_EXTRACTION_SCHEMAS.get(conversation.current_step)
    if schema_class is None:
        raise ValueError(
            f"No extraction schema registered for step '{conversation.current_step}'. "
            "Add one to STEP_EXTRACTION_SCHEMAS in llm.py."
        )

    # Build the conversation transcript as a plain text block
    transcript_lines = []
    for msg in conversation.messages:
        if msg.role in ("user", "assistant"):
            label = "User" if msg.role == "user" else "Assistant"
            transcript_lines.append(f"{label}: {msg.content}")
    transcript = "\n".join(transcript_lines)

    extraction_prompt = (
        f"Based on the following conversation transcript, extract the requested structured data.\n\n"
        f"--- Conversation Transcript ---\n{transcript}\n\n"
        "Extract all available information. Leave fields as null if they were not mentioned."
    )

    result: BaseModel = _instructor_client.chat.completions.create(
        model=settings.GEMINI_MODEL,
        response_model=schema_class,
        messages=[{"role": "user", "content": extraction_prompt}],
    )

    result_dict = result.model_dump()
    extracted = {k: v for k, v in result_dict.items() if v is not None}
    missing = [k for k, v in result_dict.items() if v is None]

    return extracted, missing
