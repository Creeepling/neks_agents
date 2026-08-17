from typing import List, Dict, Any
import instructor
from google import genai
from app.config import settings
from app.models import AnalyzedOfferSchema, MarketOfferModel
from datetime import datetime, timezone
import json
from app.tools.twogis_maps import send_telegram_alert

MAX_OFFERS = 10

def process_and_summarize_offers(property_id: str, repo: Any, raw_offers: List[Dict[str, Any]]) -> None:
    """
    Background worker to process raw excel offers.
    It passes the raw data to Gemini to clean it and extract into a structured schema,
    and saves them to the DB. Processes at most MAX_OFFERS rows. Respects a cancel flag
    stored in cian_processing_status.cancel in the DB.
    """
    if not settings.GEMINI_API_KEY:
        send_telegram_alert("GEMINI_API_KEY is not configured for offers_processor.")
        return

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    instructor_client = instructor.from_genai(client=client, use_async=False)

    capped_offers = raw_offers[:MAX_OFFERS]
    total = len(capped_offers)
    completed = 0

    for i, raw_offer in enumerate(capped_offers):
        # --- Cooperative cancellation check ---
        prop = repo.get_property_by_id(property_id)
        if prop:
            status_obj = (prop.data or {}).get("cian_processing_status", {})
            if status_obj.get("cancel"):
                current_data = dict(prop.data or {})
                current_data["cian_processing_status"] = {
                    **status_obj,
                    "status": "cancelled",
                    "cancel": False,
                }
                prop.data = current_data
                prop.updated_at = datetime.now(timezone.utc)
                repo.update_property(prop)
                return
        else:
            return  # property deleted, stop silently

        try:
            prompt = (
                f"You are a real estate data analyst. Please read the following raw row data "
                f"from a real estate scraping tool (like CIAN or Avito). Clean and extract the data "
                f"into the requested structured format.\n\n"
                f"--- RAW DATA ---\n"
                f"{json.dumps(raw_offer, ensure_ascii=False, default=str)}\n\n"
                f"If any requested fields are missing, make your best guess or leave them empty. "
                f"Always respond with the JSON schema."
            )

            analyzed_data: AnalyzedOfferSchema = instructor_client.chat.completions.create(
                model=settings.GEMINI_MODEL,
                response_model=AnalyzedOfferSchema,
                messages=[{"role": "user", "content": prompt}],
            )

            offer_model = MarketOfferModel(
                property_id=property_id,
                data=analyzed_data
            )
            repo.create_offer(offer_model)

        except Exception as e:
            send_telegram_alert(f"Error processing offer {i} for property {property_id}: {str(e)}")

        finally:
            completed += 1
            prop = repo.get_property_by_id(property_id)
            if prop:
                current_data = dict(prop.data or {})
                status_obj = current_data.get("cian_processing_status", {})
                if status_obj:
                    status_obj["completed"] = completed
                    if completed >= total:
                        status_obj["status"] = "completed"
                    current_data["cian_processing_status"] = status_obj
                    prop.data = current_data
                    prop.updated_at = datetime.now(timezone.utc)
                    repo.update_property(prop)
