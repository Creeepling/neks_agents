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
from app.tools.registry import AVAILABLE_TOOLS, analyze_location_businesses_tool, match_retail_requirements_tool

# ---------------------------------------------------------------------------
# Client Setup
# ---------------------------------------------------------------------------

_raw_client = genai.Client(api_key=settings.GEMINI_API_KEY or "DUMMY_KEY_FOR_IMPORT")

# Instructor-patched client for structured extraction calls
_instructor_client = instructor.from_genai(client=_raw_client, use_async=False)


# ---------------------------------------------------------------------------
# Dynamic Agent Configuration (Loaded from agents.yaml)
# ---------------------------------------------------------------------------

import shutil

def _load_agents_config() -> dict:
    base_dir = os.path.dirname(os.path.dirname(__file__))
    config_path = os.path.join(base_dir, "agents.yaml")
    example_path = os.path.join(base_dir, "agents.example.yaml")
    
    if not os.path.exists(config_path) and os.path.exists(example_path):
        try:
            shutil.copy(example_path, config_path)
            print(f"Created default configuration at {config_path}")
        except Exception as e:
            print(f"Warning: Could not create default configuration: {e}")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Warning: Could not load agents.yaml: {e}")
        return {}

AGENTS_CONFIG = _load_agents_config()

STEP_SYSTEM_PROMPTS: Dict[str, str] = {}
STEP_EXTRACTION_SCHEMAS: Dict[str, type[BaseModel]] = {}

def reload_agents_config():
    global AGENTS_CONFIG, STEP_SYSTEM_PROMPTS, STEP_EXTRACTION_SCHEMAS
    AGENTS_CONFIG.clear()
    AGENTS_CONFIG.update(_load_agents_config())
    
    STEP_SYSTEM_PROMPTS.clear()
    STEP_EXTRACTION_SCHEMAS.clear()
    
    for step_id, config in AGENTS_CONFIG.items():
        STEP_SYSTEM_PROMPTS[step_id] = config.get("system_prompt", "")
        schema_def = config.get("extraction_schema", {})
        model_name = "".join(word.capitalize() for word in step_id.split("_")) + "Schema"
        STEP_EXTRACTION_SCHEMAS[step_id] = _build_model(model_name, schema_def)

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
# Context Fetchers Registry
# ---------------------------------------------------------------------------

def fetch_concepts_context(repo: Any, property_id: str) -> str:
    if not repo:
        return ""
    concepts = repo.get_all_concepts()
    if not concepts: 
        return ""
    
    lines = ["--- Глобальные Концепции ---"]
    for c in concepts:
        lines.append(f"Название: {c.name}")
        lines.append(f"Формат: {c.format_type}")
        lines.append(f"Стратегия: {c.positioning_strategy}")
        lines.append(f"Аудитория: {c.target_audience}")
        lines.append(f"Якоря: {c.anchor_strategy}")
        lines.append(f"Гайдлайны по арендаторам: {c.tenant_guidelines}\n")
    return "\n".join(lines)

CONTEXT_FETCHERS = {
    "retail_concepts": fetch_concepts_context,
}


# ---------------------------------------------------------------------------
# Prompt Building
# ---------------------------------------------------------------------------

def _build_messages(
    conversation: Conversation,
    property_data: Optional[Dict[str, Any]],
    new_user_message: str,
    repo: Any = None,
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

    # Inject requested auxiliary databases (e.g. retail_concepts)
    step_config = AGENTS_CONFIG.get(conversation.current_step, {})
    requested_context_keys = step_config.get("injected_context", [])
    
    context_variables = {}
    for key in requested_context_keys:
        fetcher = CONTEXT_FETCHERS.get(key)
        if fetcher:
            context_variables[key] = fetcher(repo, conversation.property_id)
            
    for key, val in context_variables.items():
        if not val:
            continue
        placeholder = f"{{{key}}}"
        if placeholder in system_prompt:
            system_prompt = system_prompt.replace(placeholder, val)
        else:
            system_prompt += f"\n\n{val}"

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

    messages = _build_messages(conversation, prop.data, new_user_message, repo=repo)

    agent_config = AGENTS_CONFIG.get(conversation.current_step, {})
    use_thinking = agent_config.get("use_thinking", False)
    
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
        config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
        
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
                if fc.name in ("analyze_location_businesses", "analyze_location_businesses_tool"):
                    args = fc.args
                    try:
                        result = analyze_location_businesses_tool(**args)
                        parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
                        
                        # Save result to DB
                        import json
                        from app.tools.twogis_maps import send_telegram_alert
                        try:
                            send_telegram_alert("[DB-SAVE-STEP 1] Parsing JSON result from analyze_location_businesses_tool...")
                            parsed_result = json.loads(result)
                            send_telegram_alert(f"[DB-SAVE-STEP 2] JSON parsed successfully. Is list: {isinstance(parsed_result, list)}. Length: {len(parsed_result) if isinstance(parsed_result, list) else 'N/A'}")
                            
                            if isinstance(parsed_result, list):
                                send_telegram_alert("[DB-SAVE-STEP 3] Fetching existing property data...")
                                new_data = dict(prop.data or {})
                                send_telegram_alert(f"[DB-SAVE-STEP 4] Current keys in prop.data: {list(new_data.keys())}")
                                
                                # Saving to twogis_maps_results to maintain UI compatibility
                                new_data["twogis_maps_results"] = parsed_result
                                send_telegram_alert(f"[DB-SAVE-STEP 6] Saved enriched results. Length: {len(parsed_result)}")
                                
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
                            send_telegram_alert(f"Failed to save combined tools results to DB: {db_err}")
                            
                    except Exception as e:
                        from app.tools.twogis_maps import send_telegram_alert
                        send_telegram_alert(f"🛑 **[FATAL CRASH]** Exception between tool execution and DB save for analyze_location_businesses: {type(e).__name__}: {str(e)}")
                        parts.append(types.Part.from_function_response(name=fc.name, response={"error": str(e)}))
                        
                elif fc.name == "dadata_licenses_tool":
                    from app.tools.dadata_licenses import search_dadata_licenses
                    args = fc.args
                    try:
                        result = search_dadata_licenses(**args)
                        parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
                    except Exception as e:
                        parts.append(types.Part.from_function_response(name=fc.name, response={"error": str(e)}))
                        
                elif fc.name == "match_retail_requirements_tool":
                    args = fc.args
                    try:
                        result = match_retail_requirements_tool(**args)
                        parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
                    except Exception as e:
                        parts.append(types.Part.from_function_response(name=fc.name, response={"error": str(e)}))
                        
                elif fc.name == "fetch_market_listings_tool":
                    from app.tools.apify_scraper import fetch_market_listings
                    args = fc.args
                    try:
                        result = fetch_market_listings(**args)
                        parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
                    except Exception as e:
                        parts.append(types.Part.from_function_response(name=fc.name, response={"error": str(e)}))
                        
                elif fc.name == "append_extra_data_tool":
                    from app.tools.twogis_maps import send_telegram_alert
                    args = fc.args
                    text_to_append = args.get("text", "")
                    send_telegram_alert(f"🚀 **[START]** Tool `append_extra_data_tool` started.\n📥 **[INPUT]**\n```\n{text_to_append}\n```")
                    try:
                        new_data = dict(prop.data or {})
                        existing_extra_data = new_data.get("extra_data", "")
                        if existing_extra_data:
                            new_data["extra_data"] = existing_extra_data + "\n" + text_to_append
                        else:
                            new_data["extra_data"] = text_to_append
                        prop.data = new_data
                        
                        from datetime import datetime, timezone
                        prop.updated_at = datetime.now(timezone.utc)
                        repo.update_property(prop)
                        send_telegram_alert(f"🏁 **[DONE]** Tool `append_extra_data_tool` completed successfully.")
                        parts.append(types.Part.from_function_response(name=fc.name, response={"result": "Successfully appended text to extra_data."}))
                    except Exception as e:
                        send_telegram_alert(f"🛑 **[ERROR]** Tool `append_extra_data_tool` failed: {str(e)}")
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

# ---------------------------------------------------------------------------
# AI Tenant Search
# ---------------------------------------------------------------------------

def fetch_tenants_with_ai(location: str) -> list[dict]:
    """Use Gemini with Google Search to find current tenants for a given property location."""
    class TenantItem(BaseModel):
        name: str = Field(description="Название компании или бренда (например, Пятерочка, Zara, Cofix)")
        categories: str = Field(default="", description="Категория или сфера деятельности (например, Супермаркет, Одежда, Кофейня)")
        floor: str = Field(default="", description="Этаж, если известен (иначе пустая строка)")

    class TenantsList(BaseModel):
        tenants: list[TenantItem]

    prompt = f"Найди текущих действующих коммерческих арендаторов (магазины, рестораны, услуги) по адресу: {location}. Используй встроенный Google Search, чтобы найти информацию на 2GIS, Яндекс.Картах, официальных сайтах или новостных порталах. Верни список арендаторов в строгом структурированном виде."

    response = _raw_client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            response_mime_type="application/json",
            response_schema=TenantsList,
            temperature=0.2,
        ),
    )
    
    import json
    try:
        data = json.loads(response.text)
        return data.get("tenants", [])
    except Exception as e:
        print(f"Error parsing AI tenants response: {e}")
        return []

# ---------------------------------------------------------------------------
# Document Summarization
# ---------------------------------------------------------------------------

def summarize_document(file_path: str, mime_type: str, display_name: str) -> str:
    """Uploads a file to Gemini, generates a summary in Russian, and cleans up."""
    # Upload to Gemini
    uploaded_file = _raw_client.files.upload(
        file=file_path,
        config={'mime_type': mime_type, 'display_name': display_name}
    )
    
    import time
    # Wait for processing if necessary
    while getattr(uploaded_file, 'state', None) and getattr(uploaded_file.state, 'name', '') == 'PROCESSING':
        time.sleep(2)
        uploaded_file = _raw_client.files.get(name=uploaded_file.name)
        
    default_prompt = (
        "Проанализируй этот документ. Сделай подробное резюме "
        "самой важной информации, которая может быть полезна для "
        "анализа объекта недвижимости или коммерческой деятельности. "
        "Ответ должен быть на русском языке."
    )
    prompt = AGENTS_CONFIG.get("document_summarizer", {}).get("system_prompt") or default_prompt
    
    try:
        response = _raw_client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[uploaded_file, prompt]
        )
        return response.text
    finally:
        # Cleanup
        try:
            _raw_client.files.delete(name=uploaded_file.name)
        except Exception as e:
            print(f"Failed to delete file from Gemini: {e}")
