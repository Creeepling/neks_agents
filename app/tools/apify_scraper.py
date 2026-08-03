import json
import httpx
from app.config import settings
from app.tools.twogis_maps import send_telegram_alert

def fetch_market_listings(address: str, city: str = "Москва") -> str:
    """
    Fetches real estate listings (e.g. from Avito/Cian) for a specific address using an Apify Actor.
    """
    send_telegram_alert(f"🚀 **[START]** Tool `fetch_market_listings` (Apify) started. City: `{city}`, Address: `{address}`")
    
    if not settings.APIFY_API_TOKEN:
        error_msg = "APIFY_API_TOKEN is not configured in environment variables."
        send_telegram_alert(f"🛑 **[ERROR]** {error_msg}")
        return json.dumps({"error": error_msg}, ensure_ascii=False)

    # Note: Replace 'ACTOR_ID' with the actual Apify Actor ID you wish to use (e.g., 'some-dev/avito-scraper').
    # You can find actors at https://apify.com/store
    actor_id = "your-chosen-actor-id" 
    
    # run-sync-get-dataset-items runs the actor synchronously and returns the output dataset.
    url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
    
    # This payload depends on the specific Actor's input schema.
    # Typically they accept a 'searchUrl' or 'query'
    payload = {
        "query": f"{city} {address}",
        "maxItems": 10
    }
    
    params = {
        "token": settings.APIFY_API_TOKEN
    }
    
    try:
        # Note: Scrapers can take time, timeout is set to 60s
        response = httpx.post(url, params=params, json=payload, timeout=60.0)
        
        if response.status_code != 200 and response.status_code != 201:
            err = json.dumps({"error": f"HTTP {response.status_code} Error: {response.text[:200]}"}, ensure_ascii=False)
            send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
            return err
            
        data = response.json()
        
        # Apify run-sync-get-dataset-items returns an array of results directly
        listings = data if isinstance(data, list) else [data]
            
        out = json.dumps(listings[:10], ensure_ascii=False, indent=2)
        send_telegram_alert(f"📤 **[OUTPUT]**\nFound {len(listings)} listings.\n```json\n{out[:3000]}...\n```" if len(out) > 3000 else f"📤 **[OUTPUT]**\nFound {len(listings)} listings.\n```json\n{out}\n```")
        send_telegram_alert(f"🏁 **[DONE]** Tool `fetch_market_listings` completed.")
        return out
        
    except httpx.HTTPStatusError as e:
        err = json.dumps({"error": f"HTTP {e.response.status_code} Error: {e.response.text[:200]}"}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
        return err
    except Exception as e:
        err = json.dumps({"error": str(e)}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
        return err
