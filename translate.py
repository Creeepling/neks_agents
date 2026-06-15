import os

file_path = r"c:\Users\ejlha\Desktop\NeedThis\Brilliance\Neks_clean\frontend\index.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.content = f.read()

replacements = {
    "Neks — Real Estate Agent": "Neks — Агент по недвижимости",
    "Internal real estate research and analysis agent dashboard.": "Внутренняя панель агента по исследованию и анализу недвижимости.",
    "Real estate research &amp; analysis agent": "Агент по исследованию и анализу недвижимости",
    "Sign In": "Войти",
    "Register": "Регистрация",
    "Create Account": "Создать аккаунт",
    "your_username": "ваше_имя",
    ">Username<": ">Имя пользователя<",
    ">Password<": ">Пароль<",
    ">Properties<": ">Объекты<",
    "'Properties'": "'Объекты'",
    ">Navigation<": ">Навигация<",
    "Sign Out": "Выйти",
    "+ New Property": "+ Новый объект",
    "Loading…": "Загрузка…",
    "No properties yet": "Пока нет объектов",
    "Create your first property to start researching.": "Создайте первый объект для начала исследования.",
    "No address set": "Адрес не указан",
    "fields</span>": "полей</span>",
    "never": "никогда",
    "Add a real estate object to start researching": "Добавьте объект недвижимости для начала исследования",
    ">Property Name<": ">Название объекта<",
    ">Address (optional)<": ">Адрес (необязательно)<",
    "e.g. Sunset Apartment": "напр., Квартира на закате",
    "e.g. Calle del Sol 1, Madrid": "напр., Тверская 1, Москва",
    ">Cancel<": ">Отмена<",
    "Create Property": "Создать объект",
    ">Edit<": ">Изменить<",
    "+ Start Step": "+ Начать этап",
    "Committed Data": "Сохраненные данные",
    "Property Data": "Данные объекта",
    "Conversations": "Диалоги",
    "+ New": "+ Новый",
    "No data committed yet. Start a conversation to begin researching.": "Данные еще не сохранены. Начните диалог, чтобы начать исследование.",
    "No conversations yet": "Пока нет диалогов",
    "Start a step to begin the research process.": "Начните этап, чтобы запустить процесс исследования.",
    "Edit Property": "Редактировать объект",
    ">Address<": ">Адрес<",
    "Delete Property": "Удалить объект",
    "Delete this property and all its conversations? This cannot be undone.": "Удалить этот объект и все его диалоги? Это действие нельзя отменить.",
    "Save Changes": "Сохранить изменения",
    "Start a New Step": "Начать новый этап",
    "Choose which analysis step to run for this property": "Выберите этап анализа для этого объекта",
    "Continue →": "Продолжить →",
    "⚠ Missing Data": "⚠ Отсутствуют данные",
    "may produce incomplete results": "может дать неполные результаты",
    "The following fields from a previous step are missing from this property's data.": "Следующие поля из предыдущего этапа отсутствуют в данных этого объекта.",
    "You can still proceed — the agent will make assumptions for any missing context.": "Вы можете продолжить — агент сделает предположения для недостающего контекста.",
    "Proceed Anyway": "Все равно продолжить",
    "📋 Commit Results": "📋 Сохранить результаты",
    "✓ Mark Complete": "✓ Завершить",
    "✓ Completed": "✓ Завершено",
    "← Back to Property": "← Назад к объекту",
    "Start the conversation": "Начните диалог",
    "Send a message to begin.": "Отправьте сообщение, чтобы начать.",
    ">You<": ">Вы<",
    ">Agent<": ">Агент<",
    "Type your message…": "Введите ваше сообщение…",
    "This conversation is completed.": "Этот диалог завершен.",
    ">Send<": ">Отправить<",
    "Extraction Results": "Результаты извлечения",
    "fields saved": "полей сохранено",
    "not found": "не найдено",
    "Mark this conversation as completed? You will no longer be able to send messages.": "Пометить диалог как завершенный? Вы больше не сможете отправлять сообщения.",
    
    # JS Strings
    "Step 1: Research & Lookup": "Этап 1: Поиск и исследование",
    "Gather basic property details — location, type, size, price, rooms, features.": "Сбор основных данных об объекте — расположение, тип, площадь, цена, комнаты, особенности.",
    "Step 2: Investment Analysis": "Этап 2: Инвестиционный анализ",
    "Evaluate investment potential — comparables, rental yield, renovation costs, recommendation.": "Оценка инвестиционного потенциала — аналоги, доходность аренды, стоимость ремонта, рекомендации.",
    
    # Toast Messages
    "Failed to load properties:": "Не удалось загрузить объекты:",
    "Property created": "Объект создан",
    "Failed to create property": "Не удалось создать объект",
    "Failed to load property:": "Не удалось загрузить объект:",
    "Property updated": "Объект обновлен",
    "Update failed": "Не удалось обновить",
    "Property deleted": "Объект удален",
    "Failed to start conversation": "Не удалось начать диалог",
    "Conversation started": "Диалог начат",
    "Could not load messages.": "Не удалось загрузить сообщения.",
    "No response from agent": "Нет ответа от агента",
    "Send failed:": "Ошибка отправки:",
    "Commit returned no data": "Сохранение не вернуло данных",
    "Results committed to property": "Результаты сохранены в объекте",
    "Commit failed:": "Ошибка сохранения:",
    "Conversation completed": "Диалог завершен",
    "Could not complete conversation": "Не удалось завершить диалог",
    
    # Dates
    "just now": "только что",
    "m ago": "м назад",
    "h ago": "ч назад",
    "d ago": "д назад",
    
    # Interpolation
    "${props.length} propert${props.length === 1 ? 'y' : 'ies'} tracked": "${props.length} ${props.length === 1 ? 'объект отслеживается' : 'объектов отслеживается'}"
}

for eng, rus in replacements.items():
    content = content.replace(eng, rus)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Translation completed.")
