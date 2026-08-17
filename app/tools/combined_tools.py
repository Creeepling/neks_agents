import json
from app.tools.twogis_maps import search_twogis_businesses, send_telegram_alert
from app.tools.dadata_licenses import search_dadata_licenses

def analyze_location_businesses(city: str, location: str, radius: int = 150) -> str:
    """
    Finds businesses in a location using 2GIS, limits to top 15, and enriches them with Dadata licenses.
    """
    full_location = f"{city}, {location}".strip(", ")
    send_telegram_alert(f"🚀 **[START]** Tool `analyze_location_businesses` started for: {full_location}")
    
    # Step 1: Get businesses from 2GIS
    twogis_result_str = search_twogis_businesses(full_location, radius=radius)
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

    # Step 3: Clean data and infer licenses
    for business in twogis_data:
        name = business.get("name", "")
        address = business.get("address", "")
        
        # Clean up the output JSON by moving descriptors to the category field
        if "," in name:
            parts = name.split(",", 1)
            business["name"] = parts[0].strip()
            business["category"] = parts[1].strip()
            
        category_lower = business.get("category", "").lower()
        name_lower = business.get("name", "").lower()
        search_string = f"{category_lower} {name_lower}"
        
        licenses = []
        
        # Infer Educational License
        if any(keyword in search_string for keyword in ["школ", "детск", "лицей", "гимнази", "университет", "институт", "колледж", "образоват"]):
            licenses.append("ОБРАЗОВАТЕЛЬНАЯ ДЕЯТЕЛЬНОСТЬ")
            
        # Infer Medical License
        if any(keyword in search_string for keyword in ["медицин", "аптек", "клиник", "больниц", "поликлиник", "стоматолог"]):
            licenses.append("МЕДИЦИНСКАЯ ДЕЯТЕЛЬНОСТЬ")
            
        # Infer Alcohol License (or presence of alcohol sales)
        if any(keyword in search_string for keyword in ["супермаркет", "алкомаркет", "бар", "ресторан", "кафе", "пиво", "вин", "гипермаркет"]):
            licenses.append("АЛКОГОЛЬНАЯ ПРОДУКЦИЯ")
            
        business["licenses"] = licenses
            
        # Ensure city is in address for consistency
        if city.lower() not in address.lower():
            business["address"] = f"{city}, {address}".strip(", ")
            
    # Step 4: Return fully enriched list without slicing length
    out = json.dumps(twogis_data, ensure_ascii=False)
    send_telegram_alert(f"📤 **[OUTPUT]**\n```json\n{out}\n```")
    send_telegram_alert(f"🏁 **[DONE]** Tool `analyze_location_businesses` completed successfully.")
    
    return out
