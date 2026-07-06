import json
import httpx
from app.config import settings

def search_dadata_licenses(query: str) -> str:
    """
    Ищет лицензии организации по ИНН, названию или адресу с помощью API Dadata.
    
    Args:
        query: Строка поиска (ИНН, название организации, адрес).
        
    Returns:
        JSON строка с лицензиями и базовой информацией об организации.
    """
    if not settings.DADATA_API_KEY:
        return json.dumps({"error": "DADATA_API_KEY is not configured in the environment variables."}, ensure_ascii=False)
        
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
            return json.dumps([{"error": "Организация не найдена по данному запросу."}], ensure_ascii=False)
            
        party = suggestions[0]
        data_block = party.get("data", {})
        
        # Extract basic info
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
        return json.dumps([{"error": f"Ошибка при запросе к Dadata: {str(e)}"}], ensure_ascii=False)
        
    return json.dumps(results, ensure_ascii=False)


def bulk_check_yandex_companies(companies: list) -> str:
    """
    Автоматически перебирает список компаний (полученных из Яндекс карт),
    формирует запрос на основе названия и адреса, и запрашивает лицензии через Dadata API.
    """
    if not isinstance(companies, list) or not companies:
        return json.dumps({"error": "No valid companies list provided for bulk checking."}, ensure_ascii=False)
        
    bulk_results = []
    
    for company in companies:
        name = company.get("name", "")
        address = company.get("address", "")
        
        if not name:
            continue
            
        # Create a combined query string "Name Address"
        query = f"{name} {address}".strip()
        
        # We parse the result of the single-check tool
        try:
            # search_dadata_licenses returns a JSON string, we need to parse it to append
            result_str = search_dadata_licenses(query)
            result_data = json.loads(result_str)
            
            # Since result_data is a list of results (usually 1 item), we extend or append
            if isinstance(result_data, list) and result_data:
                # Add context of what original company we queried
                result_data[0]["_original_query"] = query
                bulk_results.append(result_data[0])
            else:
                bulk_results.append({"_original_query": query, "error": "No data returned"})
                
        except Exception as e:
            bulk_results.append({"_original_query": query, "error": str(e)})
            
    return json.dumps(bulk_results, ensure_ascii=False)
