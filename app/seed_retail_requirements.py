import os
from google.cloud import firestore

# Initialize Firestore client
# Note: Ensure that the GOOGLE_APPLICATION_CREDENTIALS environment variable 
# is set to your service account key file path, or run this where Application Default Credentials (ADC) are available.
from app.config import settings
db = firestore.Client(project=settings.FIRESTORE_PROJECT_ID, database=settings.FIRESTORE_DATABASE_ID)

COLLECTION_NAME = 'retail_property_requirements'

retailers_data = [
    {
        "company": "X5 Group",
        "brand": "Пятерочка",
        "format": "Магазин у дома",
        "area_sqm": {"min": 250, "max": 600},
        "power_kw": {"min": 50, "max": None},
        "ceilings_m": {"min": 2.5, "max": None},
        "requirements": "1 этаж или цоколь. Высокая плотность населения (радиус 800м)."
    },
    {
        "company": "X5 Group",
        "brand": "Перекресток",
        "format": "Супермаркет",
        "area_sqm": {"min": 750, "max": 3000},
        "power_kw": {"min": 180, "max": 350},
        "ceilings_m": {"min": 3.5, "max": None},
        "requirements": "Места с высоким трафиком, ТЦ (якорный арендатор), парковка >40 мест. Нагрузка на пол >800 кг/кв.м."
    },
    {
        "company": "X5 Group",
        "brand": "Чижик",
        "format": "Жесткий дискаунтер",
        "area_sqm": {"min": 350, "max": 420},
        "power_kw": {"min": 40, "max": 50},
        "ceilings_m": None,
        "requirements": "Строго 1 этаж, один уровень. Население >10,000."
    },
    {
        "company": "Магнит",
        "brand": "Магнит",
        "format": "Магазин у дома",
        "area_sqm": {"min": 250, "max": 650},
        "power_kw": None,
        "ceilings_m": None,
        "requirements": "1 этаж, стрит-ритейл, высокий пешеходный трафик."
    },
    {
        "company": "Дикси",
        "brand": "Дикси",
        "format": "Магазин у дома",
        "area_sqm": {"min": 290, "max": 700},
        "power_kw": {"min": 45, "max": None},
        "ceilings_m": {"min": 3.0, "max": None},
        "requirements": "Только 1 этаж. Города с населением >3,000."
    },
    {
        "company": "Лента",
        "brand": "Лента",
        "format": "Супермаркет",
        "area_sqm": {"min": 600, "max": 1700},
        "power_kw": None,
        "ceilings_m": None,
        "requirements": "1 этаж или ТЦ, высокий трафик, выделенная зона погрузки."
    },
    {
        "company": "Лента",
        "brand": "Лента",
        "format": "Гипермаркет",
        "area_sqm": {"min": 5500, "max": None},
        "power_kw": {"min": 900, "max": None},
        "ceilings_m": None,
        "requirements": "1 линия транспортных магистралей. Нагрузка на пол >1200 кг/кв.м. Большая парковка."
    },
    {
        "company": "ВкусВилл",
        "brand": "ВкусВилл",
        "format": "Здоровое питание / У дома",
        "area_sqm": {"min": 100, "max": 300},
        "power_kw": {"min": 30, "max": 50},
        "ceilings_m": {"min": 3.0, "max": None},
        "requirements": "1 этаж, предпочтительны стеклянные витрины."
    },
    {
        "company": "Mercury Retail Group",
        "brand": "Красное & Белое",
        "format": "Ультра-у дома / Алкомаркет",
        "area_sqm": {"min": 80, "max": 400},
        "power_kw": {"min": 15, "max": None},
        "ceilings_m": {"min": 2.5, "max": None},
        "requirements": "ОБЯЗАТЕЛЬНО >100м от школ/мед.учреждений. Свободная планировка торгового зала."
    },
    {
        "company": "Wildberries",
        "brand": "Wildberries",
        "format": "Пункт выдачи заказов (ПВЗ)",
        "area_sqm": {"min": 30, "max": None},
        "power_kw": None,
        "ceilings_m": None,
        "requirements": "Только 1 этаж (без цоколей). Складская зона должна занимать 70% общей площади."
    },
    {
        "company": "Ozon",
        "brand": "Ozon",
        "format": "Пункт выдачи заказов (ПВЗ)",
        "area_sqm": {"min": 20, "max": None},
        "power_kw": None,
        "ceilings_m": {"min": 2.2, "max": 2.4},
        "requirements": "Отдельный вход с улицы. Отсутствие ступенек или минимум (до 5)."
    },
    {
        "company": "Яндекс",
        "brand": "Яндекс Маркет",
        "format": "Пункт выдачи заказов (ПВЗ)",
        "area_sqm": {"min": 20, "max": None},
        "power_kw": None,
        "ceilings_m": {"min": 2.3, "max": 2.5},
        "requirements": "Не допускается размещение в жилых квартирах. Техническая возможность для брендированной вывески."
    },
    {
        "company": "Магнит",
        "brand": "Магнит Косметик",
        "format": "Дрогери / Косметика",
        "area_sqm": {"min": 180, "max": 300},
        "power_kw": {"min": 30, "max": 60},
        "ceilings_m": {"min": 3.0, "max": None},
        "requirements": "1 этаж, отдельный вход, близость к продуктовым якорям."
    },
    {
        "company": "ДНС",
        "brand": "ДНС",
        "format": "Электроника",
        "area_sqm": {"min": 150, "max": 1100},
        "power_kw": None,
        "ceilings_m": None,
        "requirements": "Свободная планировка, прямоугольная форма. Грузовой лифт обязателен, если не 1 этаж."
    },
    {
        "company": "ДНС",
        "brand": "ДНС Гипер",
        "format": "Электроника",
        "area_sqm": {"min": 700, "max": None},
        "power_kw": None,
        "ceilings_m": None,
        "requirements": "Свободная планировка, прямоугольная форма. Грузовой лифт обязателен, если не 1 этаж."
    },
    {
        "company": "М.Видео",
        "brand": "М.Видео",
        "format": "Электроника",
        "area_sqm": {"min": 350, "max": 1000},
        "power_kw": None,
        "ceilings_m": {"min": 3.6, "max": None},
        "requirements": "Крупные перекрестки, большие жилые массивы, обязательна парковка для клиентов."
    },
    {
        "company": "Лемана ПРО",
        "brand": "Леруа Мерлен / Лемана ПРО",
        "format": "DIY / Товары для дома",
        "area_sqm": {"min": 8000, "max": 20000},
        "power_kw": None,
        "ceilings_m": {"min": 5.0, "max": None},
        "requirements": "Высокая видимость, близость к шоссе. Земельные участки от 2,5 до 30 гектаров."
    },
    {
        "company": "Детский мир",
        "brand": "Детский мир",
        "format": "Товары для детей",
        "area_sqm": {"min": 700, "max": 1200},
        "power_kw": {"min": 35, "max": None}, 
        "ceilings_m": {"min": 3.5, "max": None},
        "requirements": "Города с населением >80 тыс. Уровни от -1 до 3 с грузовыми лифтами и эскалаторами."
    }
]

def seed_database():
    print(f"Seeding {len(retailers_data)} documents into '{COLLECTION_NAME}' collection...")
    batch = db.batch()
    collection_ref = db.collection(COLLECTION_NAME)
    
    for item in retailers_data:
        # Create a new document with an auto-generated ID
        doc_ref = collection_ref.document()
        batch.set(doc_ref, item)
    
    # Commit the batch operation
    batch.commit()
    print("Successfully seeded Firestore!")

if __name__ == "__main__":
    seed_database()
