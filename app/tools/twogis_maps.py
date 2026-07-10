import json
import httpx
from app.config import settings

def search_twogis_businesses(location: str, query: str = "организации") -> str:
    """
    Ищет организации через 2GIS API (Places API) по заданному местоположению.
    
    Args:
        location: Местоположение или адрес (например, "Москва, Тверская улица")
        query: Поисковый запрос (например, "кафе", "аптека", "супермаркет")
        
    Returns:
        Строка в формате JSON со списком найденных организаций (название и адрес).
    """
    if not settings.TWOGIS_API_KEY:
        return json.dumps({"error": "TWOGIS_API_KEY is not configured in the environment variables."}, ensure_ascii=False)
        
    url = "https://catalog.api.2gis.com/3.0/items"
    
    # Combine query and location for 2GIS
    search_q = f"{query} {location}".strip()
    
    params = {
        "q": search_q,
        "key": settings.TWOGIS_API_KEY,
        "fields": "items.point,items.contact_groups",
        "page_size": 10
    }
    
    results = []
    
    try:
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        
        data = response.json()
        
        # 2GIS sometimes returns errors with HTTP 200 OK, encapsulated in the 'meta' block
        if "meta" in data and data["meta"].get("code") != 200:
            return json.dumps({"error": f"API Error (meta code {data['meta'].get('code')}): {json.dumps(data, ensure_ascii=False)}"}, ensure_ascii=False)
        
        if "result" in data and "items" in data["result"]:
            items = data["result"].get("items", [])
            for item in items:
                name = item.get("name", "")
                # Use full_name to get city context, fallback to address_name
                address = item.get("full_name", item.get("address_name", ""))
                contacts = item.get("contact_groups", [])
                
                # 2GIS puts categories in deep objects, so we skip it to keep it simple and backwards compatible
                category = ""
                
                if name:
                    results.append({
                        "name": name.strip(),
                        "category": category,
                        "address": address.strip() if address else "",
                        "contacts": contacts
                    })
        else:
            # If there's no result and no meta error, return the raw data so we can debug it
            return json.dumps({"error": f"Unexpected API response structure: {json.dumps(data, ensure_ascii=False)}"}, ensure_ascii=False)
                    
    except httpx.HTTPStatusError as e:
        error_msg = f"Ошибка API 2GIS (статус {e.response.status_code}): {e.response.text}"
        return json.dumps({"error": error_msg}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Ошибка при запросе к 2GIS: {str(e)}"}, ensure_ascii=False)
        
    return json.dumps(results, ensure_ascii=False)
