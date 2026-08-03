import json
import httpx
from app.config import settings
from app.tools.twogis_maps import send_telegram_alert

def fetch_ads_api_listings(address: str, city: str = "Москва") -> str:
    """
    Fetches real estate listings from ads-api.ru (Avito, Cian, etc.) based on address.
    """
    send_telegram_alert(f"🚀 **[START]** Tool `fetch_ads_api_listings` started. City: `{city}`, Address: `{address}`")
    
    if not settings.ADS_API_KEY:
        error_msg = "ADS_API_KEY is not configured in environment variables."
        send_telegram_alert(f"🛑 **[ERROR]** {error_msg}")
        return json.dumps({"error": error_msg}, ensure_ascii=False)

    # Note: ADS-API uses token-based or user/token GET parameters. 
    # Usually it's ?user=LOGIN&token=TOKEN or just ?token=TOKEN
    # Since the exact parameter format depends on the user's dashboard, we use a generic structure.
    # The 'q' parameter is typically used for text search, and 'city' for region.
    
    url = "https://ads-api.ru/main/api"
    params = {
        "token": settings.ADS_API_KEY,
        "q": address,
        "city": city,
        "limit": 10 # Limit results
    }
    
    try:
        response = httpx.get(url, params=params, follow_redirects=True, timeout=15.0)
        
        # Some APIs return 200 with an error in JSON, some return 4xx
        if response.status_code != 200:
            err = json.dumps({"error": f"HTTP {response.status_code} Error: {response.text[:200]}"}, ensure_ascii=False)
            send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
            return err
            
        data = response.json()
        
        # Normalize output for LLM (take top 10 to save context window)
        # We assume data is a dict with a 'data' array or just a list.
        listings = data.get("data", data) if isinstance(data, dict) else data
        
        if not isinstance(listings, list):
            listings = [listings]
            
        out = json.dumps(listings[:10], ensure_ascii=False, indent=2)
        send_telegram_alert(f"📤 **[OUTPUT]**\nFound {len(listings)} listings for {address}.\n```json\n{out[:3000]}...\n```" if len(out) > 3000 else f"📤 **[OUTPUT]**\nFound {len(listings)} listings for {address}.\n```json\n{out}\n```")
        send_telegram_alert(f"🏁 **[DONE]** Tool `fetch_ads_api_listings` completed.")
        return out
        
    except httpx.HTTPStatusError as e:
        err = json.dumps({"error": f"HTTP {e.response.status_code} Error: {e.response.text[:200]}"}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
        return err
    except Exception as e:
        err = json.dumps({"error": str(e)}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
        return err
