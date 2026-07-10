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
        
    url = "https://catalog.api.2gis.com/3.0/items"
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
        
        if "meta" in data and data["meta"].get("code") != 200:
            err = json.dumps({"error": f"API Error (meta code {data['meta'].get('code')}): {json.dumps(data, ensure_ascii=False)}"}, ensure_ascii=False)
            send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
            send_telegram_alert(f"🏁 **[DONE]** Tool `search_twogis_businesses` finished with error.")
            return err
        
        if "result" in data and "items" in data["result"]:
            items = data["result"].get("items", [])
            for item in items:
                name = item.get("name", "")
                address = item.get("full_name", item.get("address_name", ""))
                contacts = item.get("contact_groups", [])
                category = ""
                
                if name:
                    results.append({
                        "name": name.strip(),
                        "category": category,
                        "address": address.strip() if address else "",
                        "contacts": contacts
                    })
        else:
            err = json.dumps({"error": f"Unexpected API response structure: {json.dumps(data, ensure_ascii=False)}"}, ensure_ascii=False)
            send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
            send_telegram_alert(f"🏁 **[DONE]** Tool `search_twogis_businesses` finished with error.")
            return err
                    
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
