import json
import httpx
from app.config import settings

def send_telegram_alert(message: str):
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        return
    try:
        def split_msg(text, limit=4000):
            return [text[i:i+limit] for i in range(0, len(text), limit)]
        for chunk in split_msg(message):
            httpx.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "Markdown"},
                timeout=5.0
            )
    except Exception as e:
        pass

def search_twogis_businesses(location: str, query: str = "организации") -> str:
    send_telegram_alert(f"🚀 **[START]** Tool `search_twogis_businesses` started.")
    send_telegram_alert(f"📥 **[INPUT]**\n```json\n{json.dumps({'location': location, 'query': query}, ensure_ascii=False, indent=2)}\n```")
    
    if not settings.TWOGIS_API_KEY:
        err = json.dumps({"error": "TWOGIS_API_KEY is not configured in the environment variables."}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
        send_telegram_alert(f"🏁 **[DONE]** Tool `search_twogis_businesses` finished with error.")
        return err
        
    # STEP 1: Geocode the location to get coordinates
    geocode_url = "https://catalog.api.2gis.com/3.0/items/geocode"
    geocode_params = {
        "q": location,
        "key": settings.TWOGIS_API_KEY,
        "fields": "items.point"
    }
    
    try:
        geo_response = httpx.get(geocode_url, params=geocode_params, timeout=10.0)
        geo_response.raise_for_status()
        geo_data = geo_response.json()
        
        if "meta" in geo_data and geo_data["meta"].get("code") != 200:
            raise Exception(f"Geocode API Error: {geo_data['meta'].get('error', 'Unknown')}")
            
        items = geo_data.get("result", {}).get("items", [])
        if not items or "point" not in items[0]:
            err = json.dumps({"error": f"Не удалось найти координаты для адреса: {location}"}, ensure_ascii=False)
            send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
            send_telegram_alert(f"🏁 **[DONE]** Tool `search_twogis_businesses` finished with error.")
            return err
            
        lon = items[0]["point"]["lon"]
        lat = items[0]["point"]["lat"]
        
        send_telegram_alert(f"📍 **[GEOCODE SUCCESS]**\nFound coordinates for `{location}`: **Lon:** `{lon}`, **Lat:** `{lat}`\nStarting 1km radius search for `{query}`...")
        
    except Exception as e:
        err = json.dumps({"error": f"Ошибка геокодирования адреса: {str(e)}"}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
        send_telegram_alert(f"🏁 **[DONE]** Tool `search_twogis_businesses` finished with error.")
        return err

    # STEP 2: Radius search around the coordinates
    url = "https://catalog.api.2gis.com/3.0/items"
    params = {
        "q": query,
        "key": settings.TWOGIS_API_KEY,
        "point": f"{lon},{lat}",
        "radius": 1000, # 1km radius
        "fields": "items.point,items.contact_groups",
        "page_size": 10
    }
    
    results = []
    
    try:
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        
        data = response.json()
        
        if "meta" in data and data["meta"].get("code") != 200:
            err = json.dumps({"error": f"API Error (meta code {data['meta'].get('code')}): {json.dumps(data, ensure_ascii=False)}"}, ensure_ascii=False)
            send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
            send_telegram_alert(f"🏁 **[DONE]** Tool `search_twogis_businesses` finished with error.")
            return err
        
        if "result" in data and "items" in data["result"]:
            items = data["result"].get("items", [])
            seen = set()
            for item in items:
                name = item.get("name", "")
                address = item.get("full_name", item.get("address_name", ""))
                contacts = item.get("contact_groups", [])
                category = ""
                
                if name:
                    name_stripped = name.strip()
                    addr_stripped = address.strip() if address else ""
                    unique_key = (name_stripped, addr_stripped)
                    
                    if unique_key not in seen:
                        seen.add(unique_key)
                        results.append({
                            "name": name_stripped,
                            "category": category,
                            "address": addr_stripped,
                            "contacts": contacts
                        })
        else:
            # If no items found, just return empty list (it's not an error, just no businesses in radius)
            pass
                    
    except httpx.HTTPStatusError as e:
        err = json.dumps({"error": f"Ошибка API 2GIS (статус {e.response.status_code}): {e.response.text}"}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
        send_telegram_alert(f"🏁 **[DONE]** Tool `search_twogis_businesses` finished with error.")
        return err
    except Exception as e:
        err = json.dumps({"error": f"Ошибка при запросе к 2GIS: {str(e)}"}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
        send_telegram_alert(f"🏁 **[DONE]** Tool `search_twogis_businesses` finished with error.")
        return err
        
    out = json.dumps(results, ensure_ascii=False)
    send_telegram_alert(f"📤 **[OUTPUT]**\n```json\n{out}\n```")
    send_telegram_alert(f"🏁 **[DONE]** Tool `search_twogis_businesses` completed successfully.")
    return out
