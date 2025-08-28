import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urldefrag
from crawler import get_all_event_urls_from_category, SEED_URLS

print("Starting test...")

for category_name, start_url in SEED_URLS['DIRECT_CATEGORIES'].items():
    print(f"\n--- Testing Category: {category_name} ---")
    urls = get_all_event_urls_from_category(start_url)
    print(f"Found {len(urls)} URLs for {category_name}.")

print("\nTest finished.")
