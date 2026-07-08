import httpx
url = "https://catalog.api.2gis.com/3.0/items"
params = {
    "q": "кафе Москва",
    "key": "test_key",
    "fields": "items.point",
    "page_size": 15
}
try:
    response = httpx.get(url, params=params)
    print("STATUS:", response.status_code)
    print("BODY:", response.text)
except Exception as e:
    print("ERROR:", e)
