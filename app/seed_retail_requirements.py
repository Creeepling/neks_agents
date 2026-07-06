import os
from google.cloud import firestore

# Initialize Firestore client
# Note: Ensure that the GOOGLE_APPLICATION_CREDENTIALS environment variable 
# is set to your service account key file path, or run this where Application Default Credentials (ADC) are available.
db = firestore.Client()

COLLECTION_NAME = 'retail_property_requirements'

retailers_data = [
    {
        "company": "X5 Group",
        "brand": "Pyaterochka",
        "format": "Convenience",
        "area_sqm": {"min": 250, "max": 600},
        "power_kw": {"min": 50, "max": None},
        "ceilings_m": {"min": 2.5, "max": None},
        "requirements": "1st floor or basement. High residential density (800m radius)."
    },
    {
        "company": "X5 Group",
        "brand": "Perekrestok",
        "format": "Supermarket",
        "area_sqm": {"min": 750, "max": 3000},
        "power_kw": {"min": 180, "max": 350},
        "ceilings_m": {"min": 3.5, "max": None},
        "requirements": "High-traffic areas, shopping centers (anchor), parking >40 cars. Floor load >800 kg/sq.m."
    },
    {
        "company": "X5 Group",
        "brand": "Chizhik",
        "format": "Hard Discounter",
        "area_sqm": {"min": 350, "max": 420},
        "power_kw": {"min": 40, "max": 50},
        "ceilings_m": None,
        "requirements": "Strictly 1st floor, single level. Population >10,000."
    },
    {
        "company": "Magnit",
        "brand": "Magnit",
        "format": "Convenience",
        "area_sqm": {"min": 250, "max": 650},
        "power_kw": None,
        "ceilings_m": None,
        "requirements": "1st floor, street retail, high foot traffic."
    },
    {
        "company": "Dixy",
        "brand": "Dixy",
        "format": "Convenience",
        "area_sqm": {"min": 290, "max": 700},
        "power_kw": {"min": 45, "max": None},
        "ceilings_m": {"min": 3.0, "max": None},
        "requirements": "1st floor only. Cities >3,000 population."
    },
    {
        "company": "Lenta",
        "brand": "Lenta",
        "format": "Supermarket",
        "area_sqm": {"min": 600, "max": 1700},
        "power_kw": None,
        "ceilings_m": None,
        "requirements": "1st floors or TCs, high traffic, dedicated loading zone."
    },
    {
        "company": "Lenta",
        "brand": "Lenta",
        "format": "Hypermarket",
        "area_sqm": {"min": 5500, "max": None},
        "power_kw": {"min": 900, "max": None},
        "ceilings_m": None,
        "requirements": "1st line of transport routes. Floor load >1200 kg/sq.m. Massive parking."
    },
    {
        "company": "VkusVill",
        "brand": "VkusVill",
        "format": "Healthy Food / Conv.",
        "area_sqm": {"min": 100, "max": 300},
        "power_kw": {"min": 30, "max": 50},
        "ceilings_m": {"min": 3.0, "max": None},
        "requirements": "1st floor, glass storefronts preferred."
    },
    {
        "company": "Mercury Retail Group",
        "brand": "Krasnoe & Beloe",
        "format": "Ultra-Convenience / Alcohol",
        "area_sqm": {"min": 80, "max": 400},
        "power_kw": {"min": 15, "max": None},
        "ceilings_m": {"min": 2.5, "max": None},
        "requirements": "MUST be >100m from schools/medical facilities. Open-plan sales floor."
    },
    {
        "company": "Wildberries",
        "brand": "Wildberries",
        "format": "Pick-up Point (PVZ)",
        "area_sqm": {"min": 30, "max": None},
        "power_kw": None,
        "ceilings_m": None,
        "requirements": "1st floor only (no basements). Storage zone must be 70% of total area."
    },
    {
        "company": "Ozon",
        "brand": "Ozon",
        "format": "Pick-up Point (PVZ)",
        "area_sqm": {"min": 20, "max": None},
        "power_kw": None,
        "ceilings_m": {"min": 2.2, "max": 2.4},
        "requirements": "Separate street entrance. No steps or minimal steps (max 5)."
    },
    {
        "company": "Yandex",
        "brand": "Yandex Market",
        "format": "Pick-up Point (PVZ)",
        "area_sqm": {"min": 20, "max": None},
        "power_kw": None,
        "ceilings_m": {"min": 2.3, "max": 2.5},
        "requirements": "Cannot be in residential apartments. Technical ability for branded facade signage."
    },
    {
        "company": "Magnit",
        "brand": "Magnit Cosmetic",
        "format": "Drogerie / Cosmetics",
        "area_sqm": {"min": 180, "max": 300},
        "power_kw": {"min": 30, "max": 60},
        "ceilings_m": {"min": 3.0, "max": None},
        "requirements": "1st floor, separate entrance, proximity to grocery anchors."
    },
    {
        "company": "DNS",
        "brand": "DNS",
        "format": "Electronics",
        "area_sqm": {"min": 150, "max": 1100},
        "power_kw": None,
        "ceilings_m": None,
        "requirements": "Free layout, rectangular shape. Freight elevator mandatory if not on 1st floor."
    },
    {
        "company": "DNS",
        "brand": "DNS Hypermarket",
        "format": "Electronics",
        "area_sqm": {"min": 700, "max": None},
        "power_kw": None,
        "ceilings_m": None,
        "requirements": "Free layout, rectangular shape. Freight elevator mandatory if not on 1st floor."
    },
    {
        "company": "M.Video",
        "brand": "M.Video",
        "format": "Electronics",
        "area_sqm": {"min": 350, "max": 1000},
        "power_kw": None,
        "ceilings_m": {"min": 3.6, "max": None},
        "requirements": "Major intersections, large residential arrays, mandatory customer parking."
    },
    {
        "company": "Lemana PRO",
        "brand": "Leroy Merlin / Lemana PRO",
        "format": "DIY / Home Improvement",
        "area_sqm": {"min": 8000, "max": 20000},
        "power_kw": None,
        "ceilings_m": {"min": 5.0, "max": None},
        "requirements": "High visibility, proximity to highways. Land plots of 2.5 – 30 hectares."
    },
    {
        "company": "Detsky Mir",
        "brand": "Detsky Mir",
        "format": "Kids & Toys",
        "area_sqm": {"min": 700, "max": 1200},
        "power_kw": {"min": 35, "max": None}, 
        "ceilings_m": {"min": 3.5, "max": None},
        "requirements": "Cities >80k population. Levels -1 to 3 with freight elevators & escalators."
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
