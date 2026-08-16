import json
import httpx
from app.config import settings
from app.tools.dadata_licenses import send_telegram_alert

import os

def standardize_address(query: str, silent: bool = False) -> str:
    """
    Takes a raw address string and returns the standardized official address 
    along with its FIAS and GAR IDs using Dadata's Suggest API.
    """
    if not silent:
        send_telegram_alert(f"🚀 **[START]** Tool `standardize_address` started.")
        send_telegram_alert(f"📥 **[INPUT]**\n```json\n{json.dumps({'query': query}, ensure_ascii=False, indent=2)}\n```")
    
    secret_key = getattr(settings, 'DADATA_SECRET_KEY', os.getenv('DADATA_SECRET_KEY'))
    if not settings.DADATA_API_KEY or not secret_key:
        err = json.dumps({"error": "DADATA_API_KEY and DADATA_SECRET_KEY must be configured in the environment variables."}, ensure_ascii=False)
        if not silent:
            send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
            send_telegram_alert(f"🏁 **[DONE]** Tool `standardize_address` finished with error.")
        return err
        
    url = "https://cleaner.dadata.ru/api/v1/clean/address"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {settings.DADATA_API_KEY}",
        "X-Secret": secret_key
    }
    data = [query]
    
    results = []
    
    try:
        response = httpx.post(url, headers=headers, json=data, timeout=10.0)
        response.raise_for_status()
        
        response_data = response.json()
        
        if not response_data:
            err = json.dumps([{"error": "Адрес не найден по данному запросу."}], ensure_ascii=False)
            if not silent:
                send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
                send_telegram_alert(f"🏁 **[DONE]** Tool `standardize_address` finished with error.")
            return err
            
        address = response_data[0]
        
        extracted = {
            "query": query,
            "standardized_address": address.get("result", ""),
            "fias_id": address.get("fias_id", ""),
            "fias_level": address.get("fias_level", ""),
            "kladr_id": address.get("kladr_id", ""),
            "postal_code": address.get("postal_code", ""),
            "region": address.get("region_with_type", ""),
            "city": address.get("city_with_type", ""),
            "street": address.get("street_with_type", ""),
            "house": (address.get("house_type", "") or "") + " " + (address.get("house", "") or "") if address.get("house") else "",
            "geo_lat": address.get("geo_lat", ""),
            "geo_lon": address.get("geo_lon", "")
        }
        
        results.append(extracted)
        
    except Exception as e:
        err = json.dumps([{"error": f"Ошибка при запросе к Dadata: {str(e)}"}], ensure_ascii=False)
        if not silent:
            send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
            send_telegram_alert(f"🏁 **[DONE]** Tool `standardize_address` finished with error.")
        return err
        
    out = json.dumps(results, ensure_ascii=False)
    if not silent:
        send_telegram_alert(f"📤 **[OUTPUT]**\n```json\n{out}\n```")
        send_telegram_alert(f"🏁 **[DONE]** Tool `standardize_address` completed successfully.")
    return out

if __name__ == "__main__":
    # Test the tool
    test_query = "мск тверская 7"
    print("Testing Dadata Address Tool with query:", test_query)
    print(standardize_address(test_query, silent=True))
