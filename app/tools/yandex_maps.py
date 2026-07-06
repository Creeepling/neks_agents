import json
import asyncio
from typing import List, Dict
from playwright.async_api import async_playwright

async def search_yandex_maps_businesses(location: str, query: str = "организации") -> str:
    """
    Ищет организации на Яндекс.Картах по заданному местоположению.
    
    Args:
        location: Местоположение или адрес (например, "Москва, Тверская улица")
        query: Поисковый запрос (например, "кафе", "магазины", "коммерческая недвижимость")
        
    Returns:
        Строка в формате JSON со списком найденных организаций (название и категория).
    """
    results: List[Dict[str, str]] = []
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Go to Yandex Maps
            await page.goto("https://yandex.ru/maps/", wait_until="domcontentloaded")
            
            # Find the search input
            search_input = page.locator(".search-form-view__input input")
            if await search_input.count() == 0:
                # Try generic input if specific class fails
                search_input = page.locator("input.input__control")
                
            await search_input.wait_for(state="visible", timeout=10000)
            
            # Fill the search bar
            search_query = f"{query} {location}"
            await search_input.fill(search_query)
            await search_input.press("Enter")
            
            # Wait for results panel to load
            await page.wait_for_selector(".search-list-view__list", timeout=15000)
            
            # Wait a bit for elements to populate
            await page.wait_for_timeout(3000)
            
            # Scroll down to load more results if needed
            result_items = page.locator(".search-snippet-view")
            
            count = await result_items.count()
            
            for i in range(min(count, 15)):
                try:
                    item = result_items.nth(i)
                    
                    name_locator = item.locator(".search-business-snippet-view__title")
                    category_locator = item.locator(".search-business-snippet-view__category")
                    address_locator = item.locator(".search-business-snippet-view__address")
                    
                    name = ""
                    if await name_locator.count() > 0:
                        name = await name_locator.first.text_content()
                        
                    category = ""
                    if await category_locator.count() > 0:
                        category = await category_locator.first.text_content()
                        
                    address = ""
                    if await address_locator.count() > 0:
                        address = await address_locator.first.text_content()
                        
                    if name:
                        results.append({
                            "name": name.strip() if name else "",
                            "category": category.strip() if category else "",
                            "address": address.strip() if address else ""
                        })
                except Exception as item_err:
                    print(f"Error parsing item: {item_err}")
                    continue
                    
            await browser.close()
            
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
        
    return json.dumps(results, ensure_ascii=False)
