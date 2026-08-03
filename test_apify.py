import os
import sys
import codecs

sys.stdout.reconfigure(encoding='utf-8')

# Add the project root to sys.path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.tools.apify_scraper import fetch_market_listings
from app.config import settings

def main():
    print(f"APIFY API TOKEN config check: {'Present' if settings.APIFY_API_TOKEN else 'Missing'}")
    
    address = "Тверская улица"
    city = "Москва"
    
    print(f"Testing Apify fetch for: {city}, {address}")
    
    result = fetch_market_listings(address, city)
    print("Result:")
    print(result)

if __name__ == "__main__":
    main()
