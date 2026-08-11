import httpx
import json

token = "apify_api_BTlLyDrrCKfKakc22S0haRi2009nJp3gMhIb"
actor_id = "km2oo0mCahDBKPOa6"
url = f"https://api.apify.com/v2/actors/{actor_id}/run-sync-get-dataset-items"
params = {"token": token}

payload = {
    "mode": "search",
    "regions": ["moskva"],
    "category": "kvartiry",
    "dealType": "prodam",
    "sortBy": "default",
    "ownerOnly": False,
    "urls": [
        "https://www.avito.ru/moskva/kvartiry/prodam"
    ],
    "maxListings": 5,
    "fetchDetails": False,
    "incrementalMode": False,
    "emitUnchanged": False,
    "emitExpired": False,
    "proxy": {
        "useApifyProxy": True,
        "apifyProxyGroups": ["RESIDENTIAL"]
    },
    "maxNotifyListings": 50
}

print("Running exact user snippet payload...")
try:
    response = httpx.post(url, params=params, json=payload, timeout=300.0)
    print("Status:", response.status_code)
    data = response.json()
    print("Result length:", len(data) if isinstance(data, list) else 1)
    if isinstance(data, list) and len(data) > 0:
        print(json.dumps(data[0], ensure_ascii=False, indent=2)[:500])
except Exception as e:
    print("Error:", e)
