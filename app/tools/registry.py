import json
from google.cloud import firestore
from app.config import settings
from app.tools.twogis_maps import search_twogis_businesses, send_telegram_alert
from app.tools.dadata_licenses import search_dadata_licenses, bulk_check_twogis_companies
from app.tools.combined_tools import analyze_location_businesses

def twogis_maps_tool(location: str) -> str:
    """
    Обертка для поиска всех организаций по адресу через 2GIS.
    Возвращает до 50 ЛЮБЫХ организаций (кафе, аптеки, магазины и т.д.) в радиусе 500м.
    """
    return search_twogis_businesses(location)

def append_extra_data_tool(text: str) -> str:
    """
    Добавляет переданный текст в раздел 'extra_data' базы данных текущего объекта недвижимости.
    Если там уже есть текст, новый текст добавляется в конец с новой строки.
    Используй этот инструмент для сохранения промежуточных выводов или важных заметок об объекте.
    """
    pass

def analyze_location_businesses_tool(city: str, location: str) -> str:
    """
    Единый инструмент для поиска организаций вокруг объекта с помощью 2GIS 
    и последующего обогащения этих организаций данными о лицензиях (Dadata).
    Возвращает JSON с подробной инфраструктурой.
    """
    return analyze_location_businesses(city, location)

def dadata_licenses_tool(query: str) -> str:
    """
    Ищет лицензии организации по ИНН, названию или адресу с помощью API Dadata.
    """
    return search_dadata_licenses(query)

def bulk_dadata_licenses_tool() -> str:
    """
    Массовая проверка лицензий: берет список компаний из 2GIS (из базы данных)
    и автоматически запрашивает лицензии для каждой компании через API Dadata.
    """
    # Note: actual execution happens in get_agent_reply to access prop.data
    pass

def match_retail_requirements_tool(area_sqm: float, power_kw: float) -> str:
    """
    Ищет подходящих ритейлеров (арендаторов) в базе данных Firestore 
    на основе площади (кв.м) и электрической мощности (кВт) объекта.
    """
    send_telegram_alert(f"🚀 **[START]** Tool `match_retail_requirements_tool` started.\n📥 **[INPUT]**\nArea: `{area_sqm}` sq.m., Power: `{power_kw}` kW")
    
    try:
        db = firestore.Client(project=settings.FIRESTORE_PROJECT_ID, database=settings.FIRESTORE_DATABASE_ID)
        docs = db.collection('retail_property_requirements').stream()
        
        def check_range(field_data: dict | None, value: float) -> bool:
            if not field_data:
                return True
            min_val = field_data.get("min")
            max_val = field_data.get("max")
            if min_val is not None and value < min_val:
                return False
            if max_val is not None and value > max_val:
                return False
            return True
            
        matches = []
        for doc in docs:
            data = doc.to_dict()
            if check_range(data.get("area_sqm"), area_sqm) and check_range(data.get("power_kw"), power_kw):
                model_data = dict(data)
                rent_rate = model_data.get("rent_rate")
                if rent_rate and isinstance(rent_rate, dict):
                    r_min = rent_rate.get("min")
                    r_avg = rent_rate.get("avg")
                    model_data["rent_rate"] = {"min": r_min, "max": r_avg}
                else:
                    model_data["rent_rate"] = None
                matches.append(model_data)
            else:
                # Document does not match area/power range requirements
                pass
                
        out = json.dumps(matches, ensure_ascii=False)
        send_telegram_alert(f"📤 **[OUTPUT]**\nFound {len(matches)} matches.\n```json\n{out[:3000]}...\n```" if len(out) > 3000 else f"📤 **[OUTPUT]**\nFound {len(matches)} matches.\n```json\n{out}\n```")
        send_telegram_alert(f"🏁 **[DONE]** Tool `match_retail_requirements_tool` completed successfully.")
        return out
    except Exception as e:
        err = json.dumps({"error": str(e)}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
        send_telegram_alert(f"🏁 **[DONE]** Tool `match_retail_requirements_tool` finished with error.")
        return err

AVAILABLE_TOOLS = {
    "google_search": {"google_search": {}},
    "dadata_licenses": dadata_licenses_tool,
    "analyze_location_businesses": analyze_location_businesses_tool,
    "match_retail_requirements_tool": match_retail_requirements_tool,
    "twogis_maps_tool": twogis_maps_tool,
    "bulk_dadata_licenses_tool": bulk_dadata_licenses_tool,
    "append_extra_data_tool": append_extra_data_tool,
}

TOOL_METADATA = [
    { "id": "google_search", "label": "Google Search", "desc": "Поиск актуальной информации в интернете" },
    { "id": "analyze_location_businesses", "label": "Анализ локации и бизнеса", "desc": "Поиск организаций (2GIS) + проверка лицензий (Dadata)" },
    { "id": "twogis_maps_tool", "label": "Поиск в 2GIS", "desc": "Получение списка организаций по адресу" },
    { "id": "dadata_licenses", "label": "Проверка лицензий Dadata", "desc": "Поиск алкогольных/образовательных лицензий по ИНН/адресу" },
    { "id": "bulk_dadata_licenses_tool", "label": "Массовая проверка лицензий", "desc": "Автоматический запрос лицензий для найденных компаний" },
    { "id": "match_retail_requirements_tool", "label": "Подбор арендаторов", "desc": "Поиск по площади (кв.м) и мощности (кВт) из внутренней БД" },
    { "id": "append_extra_data_tool", "label": "Доп. Информация", "desc": "Сохраняет текст в БД объекта" }
    # To hide a tool from the frontend UI, you can either remove it from this list or add: "hidden": True
    # { "id": "secret_tool", "label": "Secret", "desc": "...", "hidden": True }
]
