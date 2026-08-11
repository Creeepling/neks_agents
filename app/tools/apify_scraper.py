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
    try:
        from apify_client import ApifyClient
    except ImportError:
        err = json.dumps({"error": "apify-client is not installed. Run pip install apify-client"}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
        return err

    import urllib.parse
    
    actor_id = "km2oo0mCahDBKPOa6" 
    
    client = ApifyClient(settings.APIFY_API_TOKEN)
    
    # URL encode the address for the Avito query string
    quoted_address = urllib.parse.quote_plus(address)
    
    # Map city to a basic slug (Avito usually uses transliteration, defaulting to moskva for testing)
    city_slug = "moskva" if "москва" in city.lower() else city.lower()
    search_url = f"https://www.avito.ru/{city_slug}/kommercheskaya_nedvizhimost?q={quoted_address}"

    payload = {
        "mode": "search",
        "regions": [city_slug],
        "category": "kommercheskaya_nedvizhimost",
        "dealType": "sdam", # "sdam" = rent, "prodam" = sale
        "sortBy": "default",
        "ownerOnly": False,
        "urls": [
            search_url
        ],
        "maxListings": 10,
        "fetchDetails": False,
        "incrementalMode": False,
        "emitUnchanged": False,
        "emitExpired": False,
        "proxy": {
            "useApifyProxy": True,
            "apifyProxyGroups": [
                "RESIDENTIAL"
            ]
        },
        "maxNotifyListings": 50
    }
    
    try:
        # call() blocks and waits for the run to finish (handles long-polling automatically)
        run = client.actor(actor_id).call(run_input=payload)
        
        # Fetch the results from the dataset
        items = client.dataset(run["defaultDatasetId"] if isinstance(run, dict) else run["id"] if isinstance(run, dict) else getattr(run, "defaultDatasetId", getattr(run, "id", None))).list_items().items
        
        out = json.dumps(items[:10], ensure_ascii=False, indent=2)
        send_telegram_alert(f"📤 **[OUTPUT]**\nFound {len(items)} listings.\n```json\n{out[:3000]}...\n```" if len(out) > 3000 else f"📤 **[OUTPUT]**\nFound {len(items)} listings.\n```json\n{out}\n```")
        send_telegram_alert(f"🏁 **[DONE]** Tool `fetch_market_listings` completed.")
        return out
        
    except Exception as e:
        err = json.dumps({"error": str(e)}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
        return err
