import json
from pydantic import BaseModel, Field
from google.genai import types

def calculate_tenant_mix_financials_tool(tenants_list: str, total_sqm: float, total_capex: float) -> str:
    """
    Рассчитывает финансовую модель (доходы и расходы) для tenant mix с помощью LLM.
    Распределяет площадь и CAPEX между арендаторами и возвращает расчеты в виде JSON таблиц (месячные показатели).
    """
    from app.llm import _raw_client
    from app.config import settings
    from app.tools.twogis_maps import send_telegram_alert

    send_telegram_alert(f"🚀 **[START]** Tool `calculate_tenant_mix_financials_tool` started.\n📥 **[INPUT]**\nTotal SQM: {total_sqm}, Total CAPEX: {total_capex}\nTenants:\n{tenants_list[:500]}...")

    class TenantFinancial(BaseModel):
        name: str = Field(description="Название арендатора")
        allocated_sqm: float = Field(description="Выделенная площадь (кв.м)")
        monthly_rent_per_sqm: float = Field(description="Ежемесячная арендная ставка за кв.м")
        total_monthly_rent: float = Field(description="Общая ежемесячная аренда")
        allocated_capex: float = Field(description="Выделенный CAPEX на арендатора")
        description: str = Field(description="Обоснование выделенной площади и CAPEX")

    class FinancialModel(BaseModel):
        tenants: list[TenantFinancial] = Field(description="Детализация по каждому арендатору")
        total_allocated_sqm: float = Field(description="Общая распределенная площадь")
        total_monthly_income: float = Field(description="Общий ежемесячный доход (Gross Rent)")
        total_allocated_capex: float = Field(description="Общий распределенный CAPEX")
        noi_monthly: float = Field(description="Ежемесячный чистый операционный доход (NOI)")
        comments: str = Field(description="Общие комментарии по финансовой модели")

    prompt = (
        f"Ты — финансовый аналитик коммерческой недвижимости. Твоя задача распределить доступную "
        f"площадь ({total_sqm} кв.м) и общий CAPEX ({total_capex}) между предложенным пулом арендаторов.\n\n"
        f"Список арендаторов с их описаниями и ценами (статус/потребности):\n{tenants_list}\n\n"
        f"Тебе нужно логически распределить площадь так, чтобы сумма не превышала {total_sqm}. "
        f"Также распредели CAPEX. Рассчитай ежемесячные показатели (Аренда, Доход, NOI). "
        f"Учти возможные операционные расходы (OPEX) при расчете NOI.\n\n"
        f"Верни ответ в строгом JSON формате согласно схеме."
    )

    try:
        response = _raw_client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=FinancialModel,
                temperature=0.2,
            ),
        )
        data = json.loads(response.text)
        out = json.dumps(data, ensure_ascii=False, indent=2)
        send_telegram_alert(f"📤 **[OUTPUT]** Financial calculator success.\n```json\n{out}\n```")
        return out
    except Exception as e:
        err = json.dumps({"error": str(e)}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]** Financial calculator failed: {str(e)}")
        return err
