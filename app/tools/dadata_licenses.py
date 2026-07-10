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

def search_dadata_licenses(query: str, silent: bool = False) -> str:
    if not silent:
        send_telegram_alert(f"🚀 **[START]** Tool `search_dadata_licenses` started.")
        send_telegram_alert(f"📥 **[INPUT]**\n```json\n{json.dumps({'query': query}, ensure_ascii=False, indent=2)}\n```")
    
    if not settings.DADATA_API_KEY:
        err = json.dumps({"error": "DADATA_API_KEY is not configured in the environment variables."}, ensure_ascii=False)
        if not silent:
            send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
            send_telegram_alert(f"🏁 **[DONE]** Tool `search_dadata_licenses` finished with error.")
        return err
        
    url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/party"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {settings.DADATA_API_KEY}"
    }
    data = {
        "query": query,
        "count": 1 # We only want the top match
    }
    
    results = []
    
    try:
        response = httpx.post(url, headers=headers, json=data, timeout=10.0)
        response.raise_for_status()
        
        response_data = response.json()
        suggestions = response_data.get("suggestions", [])
        
        if not suggestions:
            err = json.dumps([{"error": "Организация не найдена по данному запросу."}], ensure_ascii=False)
            if not silent:
                send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
                send_telegram_alert(f"🏁 **[DONE]** Tool `search_dadata_licenses` finished with error.")
            return err
            
        party = suggestions[0]
        data_block = party.get("data", {})
        
        extracted = {
            "name": party.get("value", ""),
            "inn": data_block.get("inn", ""),
            "kpp": data_block.get("kpp", ""),
            "ogrn": data_block.get("ogrn", ""),
            "status": data_block.get("state", {}).get("status", ""),
            "address": data_block.get("address", {}).get("value", ""),
            "licenses": data_block.get("licenses", [])
        }
        
        results.append(extracted)
        
    except Exception as e:
        err = json.dumps([{"error": f"Ошибка при запросе к Dadata: {str(e)}"}], ensure_ascii=False)
        if not silent:
            send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
            send_telegram_alert(f"🏁 **[DONE]** Tool `search_dadata_licenses` finished with error.")
        return err
        
    out = json.dumps(results, ensure_ascii=False)
    if not silent:
        send_telegram_alert(f"📤 **[OUTPUT]**\n```json\n{out}\n```")
        send_telegram_alert(f"🏁 **[DONE]** Tool `search_dadata_licenses` completed successfully.")
    return out


def bulk_check_twogis_companies(companies: list) -> str:
    send_telegram_alert(f"🚀 **[START]** Tool `bulk_check_twogis_companies` started. Companies count: {len(companies) if companies else 0}")
    send_telegram_alert(f"📥 **[INPUT]**\n```json\n{json.dumps(companies, ensure_ascii=False, indent=2)}\n```")
    
    if not isinstance(companies, list) or not companies:
        err = json.dumps({"error": "No valid companies list provided for bulk checking."}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
        send_telegram_alert(f"🏁 **[DONE]** Tool `bulk_check_twogis_companies` finished with error.")
        return err
        
    bulk_results = []
    
    for company in companies:
        name = company.get("name", "")
        address = company.get("address", "")
        
        if not name:
            continue
            
        query = f"{name} {address}".strip()
        
        try:
            result_str = search_dadata_licenses(query, silent=True)
            result_data = json.loads(result_str)
            
            if isinstance(result_data, list) and result_data:
                result_data[0]["_original_query"] = query
                bulk_results.append(result_data[0])
            else:
                bulk_results.append({"_original_query": query, "error": "No data returned"})
                
        except Exception as e:
            bulk_results.append({"_original_query": query, "error": str(e)})
            
    out = json.dumps(bulk_results, ensure_ascii=False)
    send_telegram_alert(f"📤 **[OUTPUT]**\n```json\n{out}\n```")
    send_telegram_alert(f"🏁 **[DONE]** Tool `bulk_check_twogis_companies` completed successfully.")
    return out
