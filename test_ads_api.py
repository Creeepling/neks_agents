import os
import sys
import codecs
sys.stdout.reconfigure(encoding='utf-8')

# Add the project root to sys.path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.tools.ads_api_scraper import fetch_ads_api_listings
from app.config import settings

def main():
    print(f"ADS API KEY config check: {'Present' if settings.ADS_API_KEY else 'Missing'}")
    
    # We test with a sample address
    address = "Тверская улица"
    city = "Москва"
    
    print(f"Testing ADS-API fetch for: {city}, {address}")
    
    # Normally this would return 'missing api key' if it's not set
    result = fetch_ads_api_listings(address, city)
    print("Result:")
    print(result)

if __name__ == "__main__":
    main()
