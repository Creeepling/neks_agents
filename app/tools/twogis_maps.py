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
            try:
                resp = httpx.post(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "Markdown"},
                    timeout=5.0
                )
                resp.raise_for_status()
            except Exception:
                # Fallback to raw text if Markdown parsing fails (e.g., due to unclosed code blocks after splitting)
                httpx.post(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": chunk},
                    timeout=5.0
                )
    except Exception as e:
        pass

def search_twogis_businesses(location: str) -> str:
    send_telegram_alert(f"🚀 **[START]** Tool `search_twogis_businesses` started.")
    send_telegram_alert(f"📥 **[INPUT]**\n```json\n{json.dumps({'location': location}, ensure_ascii=False, indent=2)}\n```")
    
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
        
        send_telegram_alert(f"📍 **[GEOCODE SUCCESS]**\nFound coordinates for `{location}`: **Lon:** `{lon}`, **Lat:** `{lat}`\nStarting 150m radius search for all organizations...")
        
    except Exception as e:
        err = json.dumps({"error": f"Ошибка геокодирования адреса: {str(e)}"}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
        send_telegram_alert(f"🏁 **[DONE]** Tool `search_twogis_businesses` finished with error.")
        return err

    # STEP 2: Radius search around the coordinates
    url = "https://catalog.api.2gis.com/3.0/items"
    
    results = []
    seen = set()
    
    for page in range(1, 6): # Fetch up to 50 items using 5 pages of 10
        params = {
            "key": settings.TWOGIS_API_KEY,
            "point": f"{lon},{lat}",
            "radius": 150,
            "type": "branch",
            "fields": "items.point,items.contact_groups",
            "page_size": 10,
            "page": page
        }
        
        try:
            response = httpx.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            
            if "meta" in data and data["meta"].get("code") != 200:
                if data["meta"].get("code") == 404 and data["meta"].get("error", {}).get("type") == "itemNotFound":
                    break # No more results
                else:
                    err = json.dumps({"error": f"API Error (meta code {data['meta'].get('code')}): {json.dumps(data, ensure_ascii=False)}"}, ensure_ascii=False)
                    send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
                    send_telegram_alert(f"🏁 **[DONE]** Tool `search_twogis_businesses` finished with error.")
                    return err
            
            if "result" in data and "items" in data["result"]:
                items = data["result"].get("items", [])
                if not items:
                    break
                    
                for item in items:
                    name = item.get("name", "")
                    address = item.get("full_name", item.get("address_name", ""))
                    contacts = item.get("contact_groups", [])
                    category = ""
                    
                    if name:
                        name_stripped = name.strip()
                        addr_stripped = address.strip() if address else ""
                        
                        # Only include if address contains at least one digit
                        if not any(char.isdigit() for char in addr_stripped):
                            continue
                            
                        unique_key = (name_stripped, addr_stripped)
                        
                        if unique_key not in seen:
                            seen.add(unique_key)
                            results.append({
                                "name": name_stripped,
                                "category": category,
                                "address": addr_stripped
                            })
            else:
                break # No items found
                        
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

def fetch_building_tenants(location: str):
    """
    Geocodes the location to find the building_id, then fetches all businesses located inside that specific building.
    Returns a formatted string of tenants.
    """
    send_telegram_alert(f"🚀 **[START]** Tool `fetch_building_tenants` started for location: `{location}`")
    
    if not settings.TWOGIS_API_KEY:
        err = "TWOGIS_API_KEY is not configured in the environment variables."
        send_telegram_alert(f"🛑 **[ERROR]** {err}")
        return err
        
    # STEP 1: Search for the building using intelligent full-text search
    search_url = "https://catalog.api.2gis.com/3.0/items"
    search_params = {
        "q": location,
        "type": "building",
        "key": settings.TWOGIS_API_KEY
    }
    
    try:
        search_response = httpx.get(search_url, params=search_params, timeout=10.0)
        search_response.raise_for_status()
        search_data = search_response.json()
        
        if "meta" in search_data and search_data["meta"].get("code") != 200:
            raise Exception(f"Building Search API Error: {search_data['meta'].get('error', 'Unknown')}")
            
        items = search_data.get("result", {}).get("items", [])
        if not items:
            err = f"Не удалось найти здание по адресу: {location}. Попробуйте уточнить адрес в формате 'Город, Улица, Дом'."
            send_telegram_alert(f"🛑 **[ERROR]** {err}")
            return err
            
        building_id = items[0].get("id")
        building_name = items[0].get("full_name") or items[0].get("address_name") or location
        
        # STEP 2: Fetch businesses by building_id
        items_url = "https://catalog.api.2gis.com/3.0/items"
        items_params = {
            "building_id": building_id,
            "type": "branch",
            "key": settings.TWOGIS_API_KEY,
            "fields": "items.rubrics"
        }
        
        items_response = httpx.get(items_url, params=items_params, timeout=10.0)
        items_response.raise_for_status()
        items_data = items_response.json()
        
        if "meta" in items_data and items_data["meta"].get("code") != 200:
            if items_data["meta"].get("code") == 404:
                return "В данном здании не найдено зарегистрированных организаций."
            raise Exception(f"Items API Error: {items_data['meta'].get('error', 'Unknown')}")
            
        branches = items_data.get("result", {}).get("items", [])
        if not branches:
            return "В данном здании не найдено зарегистрированных организаций."
            
        formatted_tenants = []
        for b in branches:
            name = b.get("name", "Неизвестно")
            rubrics = b.get("rubrics", [])
            categories = ", ".join([r.get("name", "") for r in rubrics if r.get("name")])
            address_comment = b.get("address_comment", "")
            
            formatted_tenants.append({
                "name": name,
                "categories": categories,
                "floor": address_comment
            })
            
        send_telegram_alert(f"🏁 **[DONE]** `fetch_building_tenants` found {len(branches)} tenants.")
        return formatted_tenants
        
    except Exception as e:
        send_telegram_alert(f"🛑 **[ERROR]** Exception in fetch_building_tenants: {str(e)}")
        return f"Ошибка при получении арендаторов: {str(e)}"
