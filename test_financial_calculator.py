import os
import sys

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.tools.financial_calculator import calculate_tenant_mix_financials_tool

tenants_list = '''
1. "Супермаркет Пятерочка": Якорный арендатор, требует около 400-500 кв.м. Готовы платить 1500 руб/кв.м в месяц.
2. "Аптека Горздрав": Требует 50-70 кв.м. Готовы платить 3000 руб/кв.м в месяц.
3. "Кофейня Cofix": Требует 20-30 кв.м. Аренда 5000 руб/кв.м. Ожидают ремонт (CAPEX нужен).
'''
total_sqm = 600.0
total_capex = 5000000.0

print("Running test for calculate_tenant_mix_financials_tool...")
result = calculate_tenant_mix_financials_tool(tenants_list, total_sqm, total_capex)
print("\nResult written to result.json")
with open("result.json", "w", encoding="utf-8") as f:
    f.write(result)

