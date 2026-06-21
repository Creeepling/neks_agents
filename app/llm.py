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

import os
import yaml
from typing import Any, Dict, List, Optional, Tuple

import instructor
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, create_model

from app.config import settings
from app.database import Conversation, Message

# ---------------------------------------------------------------------------
# Client Setup
# ---------------------------------------------------------------------------

_raw_client = genai.Client(api_key=settings.GEMINI_API_KEY or "DUMMY_KEY_FOR_IMPORT")

# Instructor-patched client for structured extraction calls
_instructor_client = instructor.from_genai(client=_raw_client, use_async=False)


# ---------------------------------------------------------------------------
# Dynamic Agent Configuration (Loaded from agents.yaml)
# ---------------------------------------------------------------------------

def _load_agents_config() -> dict:
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "agents.yaml")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Warning: Could not load agents.yaml: {e}")
        return {}

AGENTS_CONFIG = _load_agents_config()

STEP_SYSTEM_PROMPTS: Dict[str, str] = {}
STEP_EXTRACTION_SCHEMAS: Dict[str, type[BaseModel]] = {}

for step_id, config in AGENTS_CONFIG.items():
    STEP_SYSTEM_PROMPTS[step_id] = config.get("system_prompt", "")
    
    fields = {}
    schema_def = config.get("extraction_schema", {})
    for field_name, field_info in schema_def.items():
        field_type_str = field_info.get("type", "string")
        
        if field_type_str == "string":
            py_type = Optional[str]
        elif field_type_str == "integer":
            py_type = Optional[int]
        elif field_type_str == "float":
            py_type = Optional[float]
        elif field_type_str == "list":
            item_type = field_info.get("items", "string")
            py_type = Optional[List[str]] if item_type == "string" else Optional[List[Any]]
        else:
            py_type = Optional[str]
            
        description = field_info.get("description", "")
        fields[field_name] = (py_type, Field(None, description=description))
    
    model_name = "".join(word.capitalize() for word in step_id.split("_")) + "Schema"
    STEP_EXTRACTION_SCHEMAS[step_id] = create_model(model_name, **fields)

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful real estate assistant. Answer the user's questions clearly and concisely."
)


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

    # Determine which fields this step is responsible for
    schema_class = STEP_EXTRACTION_SCHEMAS.get(conversation.current_step)
    if schema_class:
        target_fields = ", ".join(schema_class.model_fields.keys())
        system_prompt += (
            f"\n\nТвоя цель в этом диалоге — собрать информацию для следующих полей: {target_fields}. "
            "Задавай вопросы по одному, чтобы собрать недостающие данные."
        )

    # Inject existing structured property data so the agent knows the context
    if property_data:
        system_prompt += (
            "\n\n--- Текущие данные об объекте ---\n"
            f"{property_data}\n"
            "Используй эти данные для контекста."
        )

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
        config=types.GenerateContentConfig(
            tools=[{"google_search": {}}],
        )
    )

    if response and response.text:
        text = response.text
        # Extract grounding sources if available
        sources = []
        if response.candidates and response.candidates[0].grounding_metadata:
            metadata = response.candidates[0].grounding_metadata
            if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                for chunk in metadata.grounding_chunks:
                    if hasattr(chunk, 'web') and chunk.web and chunk.web.uri:
                        sources.append(chunk.web.uri)
        
        if sources:
            unique_sources = list(dict.fromkeys(sources))
            sources_list = "\n".join([f"- {url}" for url in unique_sources])
            text += f"\n\n**Источники:**\n{sources_list}"

        return text
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
