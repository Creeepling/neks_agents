import os
import sys
# Add the project root to sys.path so we can import app modules
sys.path.insert(0, r"c:\Users\ejlha\Desktop\NeedThis\Brilliance\Neks_clean")

from app.tools.twogis_maps import search_twogis_businesses
from app.config import settings

print(f"API KEY: {settings.TWOGIS_API_KEY}")
result = search_twogis_businesses("Москва, Тверская улица", "кафе")
print(result)
