import os
from google.cloud import firestore

# Determine the environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# In production, we use a different collection to avoid messing with dev data
COLLECTION_NAME = "retail_concepts"

concepts_data = [
    {
        "name": "Районный торговый центр «ЭкоЛайф»",
        "format_type": "Районный ТЦ",
        "positioning_strategy": "Удобный торговый центр для ежедневных покупок с упором на экологичные и фермерские продукты.",
        "target_audience": "Жители близлежащих спальных районов, семьи с детьми, ценящие качество и экономию времени.",
        "anchor_strategy": "Крупный продуктовый супермаркет формата «у дома» (например, «ВкусВилл» или «Перекресток»), аптека и дрогери.",
        "tenant_guidelines": "Приоритет отдается пекарням, фермерским лавкам, услугам повседневного спроса (химчистка, ремонт обуви) и небольшим кофейням.",
    },
    {
        "name": "Ритейл-парк «МегаМолл»",
        "format_type": "Ритейл-парк",
        "positioning_strategy": "Крупный загородный торговый комплекс, предлагающий широкий ассортимент товаров для дома, ремонта и активного отдыха по выгодным ценам.",
        "target_audience": "Автовладельцы, жители пригорода и горожане, совершающие крупные покупки на выходных.",
        "anchor_strategy": "Гипермаркет DIY (например, Leroy Merlin), крупный продуктовый гипермаркет и гипермаркет электроники.",
        "tenant_guidelines": "Крупноформатные арендаторы (категории «big-box»), мебельные салоны, спортивные гипермаркеты; минимум развлекательной зоны, большая парковка.",
    },
    {
        "name": "Торгово-развлекательный центр «Галактика»",
        "format_type": "Региональный ТРЦ",
        "positioning_strategy": "Главный центр притяжения региона для шопинга и развлечений выходного дня, предлагающий уникальный опыт для всей семьи.",
        "target_audience": "Широкий охват населения всего города и прилегающих районов; люди со средним и выше среднего уровнем дохода.",
        "anchor_strategy": "Многозальный кинотеатр, крупный семейный развлекательный центр, универмаги одежды международных брендов.",
        "tenant_guidelines": "Обязательно наличие обширного фуд-корта, ресторанов, фэшн-галереи (mass-market и middle-up), а также зон для проведения мероприятий.",
    },
    {
        "name": "Аутлет-центр «Премиум Вилладж»",
        "format_type": "Аутлет",
        "positioning_strategy": "Торговый комплекс в формате открытой деревни, специализирующийся на распродажах коллекций премиальных и известных брендов с постоянными скидками.",
        "target_audience": "Любители брендовых вещей, экономные шопоголики и туристы.",
        "anchor_strategy": "Флагманские дисконт-магазины ведущих мировых фэшн-брендов и спортивных марок.",
        "tenant_guidelines": "Единый архитектурный стиль, отсутствие классических продуктовых гипермаркетов, наличие уютных кафе и ресторанов для отдыха между покупками.",
    },
    {
        "name": "Стрит-ритейл кластер «Гурман Стрит»",
        "format_type": "Лайфстайл-центр",
        "positioning_strategy": "Атмосферное городское пространство, объединяющее авторскую гастрономию, бутики локальных дизайнеров и бьюти-коворкинги.",
        "target_audience": "Молодежь, креативный класс, офисные работники близлежащих бизнес-центров и любители гастрономических открытий.",
        "anchor_strategy": "Гастромаркет (фуд-холл) с разнообразными корнерами, модный фитнес-клуб или арт-пространство.",
        "tenant_guidelines": "Уникальные концепции (без масс-маркета), крафтовые бары, спешелти-кофейни, барбершопы и шоурумы; акцент на эстетику и комьюнити.",
    }
]

def seed_database():
    try:
        db = firestore.Client()
        collection = db.collection(COLLECTION_NAME)

        print(f"Clearing existing documents in '{COLLECTION_NAME}' collection...")
        existing_docs = collection.stream()
        delete_batch = db.batch()
        delete_count = 0
        for doc in existing_docs:
            delete_batch.delete(doc.reference)
            delete_count += 1
        if delete_count > 0:
            delete_batch.commit()
            print(f"Deleted {delete_count} existing documents.")

        print(f"Seeding {len(concepts_data)} concepts into '{COLLECTION_NAME}' collection...")

        count = 0
        for item in concepts_data:
            # We don't specify an ID to let Firestore auto-generate one
            doc_ref = collection.document()
            
            # Add timestamp like the model does
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            item["created_at"] = now
            item["updated_at"] = now

            doc_ref.set(item)
            print(f"Created concept: {item['name']} with ID: {doc_ref.id}")
            count += 1

        print(f"Successfully created {count} concept documents.")

    except Exception as e:
        print(f"Error seeding database: {e}")

if __name__ == "__main__":
    # If FIRESTORE_PROJECT_ID isn't set but we are running locally with gcloud auth,
    # the firestore client will still pick it up from ADC.
    seed_database()
