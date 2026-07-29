import json
import re
import httpx
from bs4 import BeautifulSoup
from app.tools.twogis_maps import send_telegram_alert

def fetch_cian_commercial_listings(region_id: int = 1) -> str:
    """
    Scrapes a list of commercial real estate listings from CIAN for a given region (default 1 = Moscow).
    Since the app runs on Google Cloud Run, it shares Google's IP infrastructure, which has a higher 
    chance of bypassing CIAN's basic bot protection (similar to Vertex AI Search).
    """
    send_telegram_alert(f"🚀 **[START]** Tool `fetch_cian_commercial_listings` started. Region: `{region_id}`")
    
    url = f"https://www.cian.ru/cat.php?deal_type=rent&engine_version=2&offer_type=offices&region={region_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    try:
        response = httpx.get(url, headers=headers, follow_redirects=True, timeout=15.0)
        response.raise_for_status()
        
        listings = []
        
        # Fallback to BeautifulSoup parsing if config extraction is brittle
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Most CIAN articles have a distinct tag structure, trying to find links to offers
        for link_tag in soup.find_all("a", href=re.compile(r"cian\.ru/rent/commercial/\d+")):
            url = link_tag.get("href")
            title = link_tag.get_text(strip=True)
            if url and title and len(title) > 5:
                # Deduplicate by URL
                if not any(l["url"] == url for l in listings):
                    listings.append({
                        "url": url,
                        "title": title
                    })
                    
        if not listings:
            send_telegram_alert("⚠️ No listings found via HTML parsing. The page structure might have changed or CAPTCHA was triggered.")

        out = json.dumps(listings[:10], ensure_ascii=False, indent=2) # Limit to 10
        send_telegram_alert(f"📤 **[OUTPUT]**\nFound {len(listings)} listings.\n```json\n{out}\n```")
        send_telegram_alert(f"🏁 **[DONE]** Tool `fetch_cian_commercial_listings` completed.")
        return out
        
    except httpx.HTTPStatusError as e:
        err = json.dumps({"error": f"HTTP {e.response.status_code} Error: {e.response.text[:200]}"}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
        return err
    except Exception as e:
        err = json.dumps({"error": str(e)}, ensure_ascii=False)
        send_telegram_alert(f"🛑 **[ERROR]**\n```json\n{err}\n```")
        return err
