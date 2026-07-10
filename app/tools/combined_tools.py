import json
from app.tools.twogis_maps import search_twogis_businesses, send_telegram_alert
from app.tools.dadata_licenses import search_dadata_licenses

def analyze_location_businesses(location: str) -> str:
    """
    Finds businesses in a location using 2GIS, limits to top 15, and enriches them with Dadata licenses.
    """
    send_telegram_alert(f"🚀 **[START]** Tool `analyze_location_businesses` started for: {location}")
    
    # Step 1: Get businesses from 2GIS
    twogis_result_str = search_twogis_businesses(location)
    try:
        twogis_data = json.loads(twogis_result_str)
    except Exception as e:
        err = json.dumps({"error": f"Failed to parse 2GIS results: {str(e)}"}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
        send_telegram_alert(f"🏁 **[DONE]** Tool `analyze_location_businesses` finished with error.")
        return err

    # Check if we got an error dictionary back from search_twogis_businesses
    if isinstance(twogis_data, dict) and "error" in twogis_data:
        err = json.dumps(twogis_data, ensure_ascii=False)
        send_telegram_alert(f"🏁 **[DONE]** Tool `analyze_location_businesses` finished with error.")
        return err

    if not isinstance(twogis_data, list):
        twogis_data = []

    # Step 2: Slice to top 15
    top_businesses = twogis_data[:15]
    send_telegram_alert(f"ℹ️ **[INFO]** Found {len(twogis_data)} businesses, slicing to top {len(top_businesses)} for license enrichment.")

    # Step 3: Enrich with Dadata licenses
    for business in top_businesses:
        name = business.get("name", "")
        address = business.get("address", "")
        query = f"{name} {address}".strip()
        
        if not query:
            business["licenses"] = []
            continue
            
        try:
            dadata_result_str = search_dadata_licenses(query, silent=True)
            dadata_result = json.loads(dadata_result_str)
            
            if isinstance(dadata_result, list) and dadata_result:
                business["licenses"] = dadata_result[0].get("licenses", [])
            else:
                business["licenses"] = []
        except Exception as e:
            business["licenses"] = []
            
    # Step 4: Return enriched list
    out = json.dumps(top_businesses, ensure_ascii=False)
    send_telegram_alert(f"📤 **[OUTPUT]**\n```json\n{out}\n```")
    send_telegram_alert(f"🏁 **[DONE]** Tool `analyze_location_businesses` completed successfully.")
    
    return out
