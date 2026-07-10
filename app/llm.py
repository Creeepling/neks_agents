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
import asyncio
from typing import Any, Dict, List, Optional, Tuple

import instructor
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, create_model

from app.config import settings
from app.models import ConversationModel as Conversation, MessageModel as Message
from app.tools.twogis_maps import search_twogis_businesses
from app.tools.dadata_licenses import search_dadata_licenses, bulk_check_twogis_companies

def twogis_maps_tool(location: str) -> str:
    """
    Обертка для поиска всех организаций по адресу через 2GIS.
    Возвращает до 50 ЛЮБЫХ организаций (кафе, аптеки, магазины и т.д.) в радиусе 500м.
    """
    return search_twogis_businesses(location)

def dadata_licenses_tool(query: str) -> str:
    """
    Ищет лицензии организации по ИНН, названию или адресу с помощью API Dadata.
    """
    return search_dadata_licenses(query)

def bulk_dadata_licenses_tool() -> str:
    """
    Массовая проверка лицензий: берет список компаний из 2GIS (из базы данных)
    и автоматически запрашивает лицензии для каждой компании через API Dadata.
    """
    # Note: actual execution happens in get_agent_reply to access prop.data
    pass

def match_retail_requirements_tool(area_sqm: float, power_kw: float) -> str:
    """
    Ищет подходящих ритейлеров (арендаторов) в базе данных Firestore 
    на основе площади (кв.м) и электрической мощности (кВт) объекта.
    """
    import json
    from google.cloud import firestore
    
    db = firestore.Client(project=settings.FIRESTORE_PROJECT_ID, database=settings.FIRESTORE_DATABASE_ID)
    docs = db.collection('retail_property_requirements').stream()
    
    def check_range(field_data: dict | None, value: float) -> bool:
        if not field_data:
            return True
        min_val = field_data.get("min")
        max_val = field_data.get("max")
        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False
        return True
        
    matches = []
    for doc in docs:
        data = doc.to_dict()
        if check_range(data.get("area_sqm"), area_sqm) and check_range(data.get("power_kw"), power_kw):
            matches.append(data)
            
    return json.dumps(matches, ensure_ascii=False)

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

def _build_model(name: str, schema_def: dict) -> type[BaseModel]:
    fields = {}
    for field_name, field_info in schema_def.items():
        field_type_str = field_info.get("type", "string")
        description = field_info.get("description", "")
        
        if field_type_str == "string":
            py_type = Optional[str]
        elif field_type_str == "integer":
            py_type = Optional[int]
        elif field_type_str == "float":
            py_type = Optional[float]
        elif field_type_str == "object":
            sub_schema = field_info.get("properties", {})
            sub_model = _build_model(f"{name}_{field_name}", sub_schema)
            py_type = Optional[sub_model]
        elif field_type_str == "list":
            items_def = field_info.get("items", "string")
            
            if isinstance(items_def, dict):
                item_type_str = items_def.get("type", "string")
                if item_type_str == "object":
                    sub_schema = items_def.get("properties", {})
                    sub_model = _build_model(f"{name}_{field_name}_item", sub_schema)
                    py_type = Optional[List[sub_model]]
                else:
                    py_type = Optional[List[str]]
            else:
                item_type = items_def
                if item_type == "object":
                    sub_schema = field_info.get("properties", {})
                    sub_model = _build_model(f"{name}_{field_name}_item", sub_schema)
                    py_type = Optional[List[sub_model]]
                else:
                    py_type = Optional[List[str]] if item_type == "string" else Optional[List[Any]]
        else:
            py_type = Optional[str]
            
        fields[field_name] = (py_type, Field(None, description=description))
    return create_model(name, **fields)

for step_id, config in AGENTS_CONFIG.items():
    STEP_SYSTEM_PROMPTS[step_id] = config.get("system_prompt", "")
    schema_def = config.get("extraction_schema", {})
    model_name = "".join(word.capitalize() for word in step_id.split("_")) + "Schema"
    STEP_EXTRACTION_SCHEMAS[step_id] = _build_model(model_name, schema_def)

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
        system_prompt += (
            "\n\nТвой ответ должен быть написан удобно читаемым текстом. "
            "Отвечай на русском, не пиши названия системных полей или переменных."
        )

    # Inject existing structured property data so the agent knows the context
    if property_data:
        system_prompt += (
            "\n\n--- Текущие данные об объекте ---\n"
            f"{property_data}\n"
            "Используй эти данные для контекста."
        )

    messages: List[Dict[str, Any]] = [{"role": "user", "parts": [{"text": f"[SYSTEM]\n{system_prompt}"}]}]

    # Add recent history (oldest messages first, capped)
    recent: List[Message] = conversation.messages[-history_limit:] if conversation.messages else []
    for msg in recent:
        if msg.role in ("user", "assistant"):
            role = "user" if msg.role == "user" else "model"
            if messages[-1]["role"] == role:
                messages[-1]["parts"][0]["text"] += f"\n\n{msg.content}"
            else:
                messages.append({"role": role, "parts": [{"text": msg.content}]})

    # New user turn
    if messages[-1]["role"] == "user":
        messages[-1]["parts"][0]["text"] += f"\n\n{new_user_message}"
    else:
        messages.append({"role": "user", "parts": [{"text": new_user_message}]})

    return messages


# ---------------------------------------------------------------------------
# Chat Call
# ---------------------------------------------------------------------------

def get_agent_reply(
    conversation: Conversation,
    prop: Any,
    repo: Any,
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

    messages = _build_messages(conversation, prop.data, new_user_message)

    agent_config = AGENTS_CONFIG.get(conversation.current_step, {})
    use_thinking = agent_config.get("use_thinking", False)
    
    AVAILABLE_TOOLS = {
        "google_search": {"google_search": {}},
        "twogis_maps": twogis_maps_tool,
        "dadata_licenses": dadata_licenses_tool,
        "bulk_dadata_licenses": bulk_dadata_licenses_tool,
        "match_retail_requirements_tool": match_retail_requirements_tool
    }
    
    # Available tools for the current step (configured in agents.yaml)
    step_tools_names = agent_config.get("available_tools", ["google_search", "twogis_maps", "dadata_licenses", "bulk_dadata_licenses", "match_retail_requirements_tool"])
    step_tools = [AVAILABLE_TOOLS[name] for name in step_tools_names if name in AVAILABLE_TOOLS]
    
    config_kwargs = {}
    if step_tools:
        config_kwargs["tools"] = step_tools
        config_kwargs["tool_config"] = types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="AUTO"),
            include_server_side_tool_invocations=True
        )
        
    if use_thinking:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=4096)

    for _ in range(5):
        try:
            response = _raw_client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=messages,
                config=types.GenerateContentConfig(**config_kwargs)
            )
        except Exception as e:
            # If the current model rejects the thinking_config, fallback without it
            if use_thinking and "thinking_config" in config_kwargs:
                del config_kwargs["thinking_config"]
                response = _raw_client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=messages,
                    config=types.GenerateContentConfig(**config_kwargs)
                )
            else:
                raise e

        if response.function_calls:
            # Append the model's tool call request
            messages.append(response.candidates[0].content)
            
            # Execute the requested functions and append their results
            parts = []
            for fc in response.function_calls:
                if fc.name == "twogis_maps":
                    args = fc.args
                    try:
                        result = twogis_maps_tool(**args)
                        parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
                        
                        # Save result to DB
                        import json
                        from app.tools.twogis_maps import send_telegram_alert
                        try:
                            send_telegram_alert("[DB-SAVE-STEP 1] Parsing JSON result from twogis_maps_tool...")
                            parsed_result = json.loads(result)
                            send_telegram_alert(f"[DB-SAVE-STEP 2] JSON parsed successfully. Is list: {isinstance(parsed_result, list)}. Length: {len(parsed_result) if isinstance(parsed_result, list) else 'N/A'}")
                            
                            if isinstance(parsed_result, list):
                                send_telegram_alert("[DB-SAVE-STEP 3] Fetching existing property data...")
                                new_data = dict(prop.data or {})
                                send_telegram_alert(f"[DB-SAVE-STEP 4] Current keys in prop.data: {list(new_data.keys())}")
                                
                                existing = new_data.get("twogis_maps_results", [])
                                send_telegram_alert(f"[DB-SAVE-STEP 5] Retrieved existing 'twogis_maps_results'. Type: {type(existing)}, Length: {len(existing) if isinstance(existing, list) else 'N/A'}")
                                
                                if isinstance(existing, list):
                                    existing.extend(parsed_result)
                                    new_data["twogis_maps_results"] = existing
                                    send_telegram_alert(f"[DB-SAVE-STEP 6A] Appended results. New length: {len(existing)}")
                                else:
                                    new_data["twogis_maps_results"] = parsed_result
                                    send_telegram_alert(f"[DB-SAVE-STEP 6B] Overwrote with new results. Length: {len(parsed_result)}")
                                
                                prop.data = new_data
                                send_telegram_alert("[DB-SAVE-STEP 7] Reassigned updated dictionary back to prop.data.")
                                
                                from datetime import datetime, timezone
                                prop.updated_at = datetime.now(timezone.utc)
                                send_telegram_alert("[DB-SAVE-STEP 8] Committing to Firestore via repo.update_property(prop)...")
                                repo.update_property(prop)
                                send_telegram_alert("[DB-SAVE-STEP 9] SUCCESS! Property updated in Firestore.")
                            elif isinstance(parsed_result, dict) and "error" in parsed_result:
                                new_data = dict(prop.data or {})
                                new_data["twogis_maps_error"] = parsed_result["error"]
                                prop.data = new_data
                                from datetime import datetime, timezone
                                prop.updated_at = datetime.now(timezone.utc)
                                repo.update_property(prop)
                        except Exception as db_err:
                            send_telegram_alert(f"Failed to save 2gis maps results to DB: {db_err}")
                            
                    except Exception as e:
                        parts.append(types.Part.from_function_response(name=fc.name, response={"error": str(e)}))
                        
                elif fc.name == "dadata_licenses_tool":
                    args = fc.args
                    try:
                        result = dadata_licenses_tool(**args)
                        parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
                        
                        import json
                        try:
                            parsed_result = json.loads(result)
                            if isinstance(parsed_result, list):
                                new_data = dict(prop.data or {})
                                new_data["dadata_licenses_results"] = parsed_result
                                prop.data = new_data
                                from datetime import datetime, timezone
                                prop.updated_at = datetime.now(timezone.utc)
                                repo.update_property(prop)
                            elif isinstance(parsed_result, dict) and "error" in parsed_result:
                                new_data = dict(prop.data or {})
                                new_data["dadata_licenses_error"] = parsed_result["error"]
                                prop.data = new_data
                                from datetime import datetime, timezone
                                prop.updated_at = datetime.now(timezone.utc)
                                repo.update_property(prop)
                        except Exception as db_err:
                            print(f"Failed to save dadata licenses results to DB: {db_err}")
                            
                    except Exception as e:
                        parts.append(types.Part.from_function_response(name=fc.name, response={"error": str(e)}))
                        
                elif fc.name == "bulk_dadata_licenses_tool":
                    try:
                        twogis_results = prop.data.get("twogis_maps_results", [])
                        if not twogis_results:
                            parts.append(types.Part.from_function_response(name=fc.name, response={"error": "No 2GIS maps results found in the database. Run the Maps tool first."}))
                            continue
                            
                        result = bulk_check_twogis_companies(twogis_results)
                        parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
                        
                        import json
                        try:
                            parsed_result = json.loads(result)
                            if isinstance(parsed_result, list):
                                new_data = dict(prop.data or {})
                                new_data["dadata_licenses_results"] = parsed_result
                                prop.data = new_data
                                from datetime import datetime, timezone
                                prop.updated_at = datetime.now(timezone.utc)
                                repo.update_property(prop)
                            elif isinstance(parsed_result, dict) and "error" in parsed_result:
                                new_data = dict(prop.data or {})
                                new_data["bulk_dadata_licenses_error"] = parsed_result["error"]
                                prop.data = new_data
                                from datetime import datetime, timezone
                                prop.updated_at = datetime.now(timezone.utc)
                                repo.update_property(prop)
                        except Exception as db_err:
                            print(f"Failed to save bulk dadata licenses results to DB: {db_err}")
                            
                    except Exception as e:
                        parts.append(types.Part.from_function_response(name=fc.name, response={"error": str(e)}))
                        
                elif fc.name == "match_retail_requirements_tool":
                    args = fc.args
                    try:
                        result = match_retail_requirements_tool(**args)
                        parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
                    except Exception as e:
                        parts.append(types.Part.from_function_response(name=fc.name, response={"error": str(e)}))
            
            messages.append({"role": "user", "parts": parts})
            continue
        break

    if response and response.text:
        text = response.text
        # Extract grounding sources if available
        sources = []
        if response.candidates and response.candidates[0].grounding_metadata:
            metadata = response.candidates[0].grounding_metadata
            if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                for chunk in metadata.grounding_chunks:
                    if hasattr(chunk, 'web') and chunk.web and chunk.web.uri:
                        title = chunk.web.title if hasattr(chunk.web, 'title') and chunk.web.title else chunk.web.uri
                        sources.append((title, chunk.web.uri))
        
        if sources:
            unique_sources = {}
            for title, url in sources:
                if url not in unique_sources:
                    unique_sources[url] = title
            sources_list = "\n".join([f"- [{title}]({url})" for url, title in unique_sources.items()])
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
