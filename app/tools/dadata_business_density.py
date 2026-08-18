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

def get_legal_entity_density(address: str, silent: bool = False) -> str:
    """
    Takes an address and returns the number of registered legal entities at that address
    (up to a max of 20) using Dadata's Suggest Party API. This helps determine if the 
    building is a business center (mass registration) or standalone.
    """
    if not silent:
        send_telegram_alert(f"🚀 **[START]** Tool `get_legal_entity_density` started.")
        send_telegram_alert(f"📥 **[INPUT]**\n```json\n{json.dumps({'address': address}, ensure_ascii=False, indent=2)}\n```")
    
    if not settings.DADATA_API_KEY:
        err = json.dumps({"error": "DADATA_API_KEY is not configured in the environment variables."}, ensure_ascii=False)
        if not silent:
            send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
            send_telegram_alert(f"🏁 **[DONE]** Tool `get_legal_entity_density` finished with error.")
        return err
        
    url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/party"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {settings.DADATA_API_KEY}"
    }
    
    # We use Dadata's max count limit of 20 to determine density.
    data = {
        "query": address,
        "count": 20 
    }
    
    try:
        response = httpx.post(url, headers=headers, json=data, timeout=10.0)
        response.raise_for_status()
        
        response_data = response.json()
        suggestions = response_data.get("suggestions", [])
        
        count = len(suggestions)
        businesses = []
        
        for party in suggestions:
            data_block = party.get("data", {})
            businesses.append({
                "name": party.get("value", ""),
                "inn": data_block.get("inn", ""),
                "status": data_block.get("state", {}).get("status", "")
            })
            
        density_label = f"{count}"
        if count == 20:
            density_label = "20+ (High Density - likely a Business Center or mass registration address)"
            
        extracted = {
            "query_address": address,
            "registered_entities_count": density_label,
            "sample_businesses": businesses
        }
        
        out = json.dumps(extracted, ensure_ascii=False)
        if not silent:
            send_telegram_alert(f"📤 **[OUTPUT]**\n```json\n{out}\n```")
            send_telegram_alert(f"🏁 **[DONE]** Tool `get_legal_entity_density` completed successfully.")
        return out
        
    except Exception as e:
        err = json.dumps({"error": f"Ошибка при запросе к Dadata: {str(e)}"}, ensure_ascii=False)
        if not silent:
            send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
            send_telegram_alert(f"🏁 **[DONE]** Tool `get_legal_entity_density` finished with error.")
        return err

if __name__ == "__main__":
    print(get_legal_entity_density("мск тверская 7", silent=True))
