import requests
import os
import re
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urldefrag
from concurrent.futures import ThreadPoolExecutor, as_completed

from transformer import transform_event_html_to_json

# --- Configuration ---
SEED_URLS = {
    'Main_Events': 'https://lessonsinlove.wiki/index.php?title=Main_Events',
    'Character_Events_Side': 'https://lessonsinlove.wiki/index.php?title=Character_Events_(Side)',
    'Character_Events_F2': 'https://lessonsinlove.wiki/index.php?title=Character_Events_(Floor_Two)',
    'Character_Events_F1': 'https://lessonsinlove.wiki/index.php?title=Character_Events_(Floor_One)',
    'Secret_Events': 'https://lessonsinlove.wiki/index.php?title=Secret_Events'
}

OUTPUT_BASE_DIR = 'output'
MAX_WORKERS = 10

# --- THIS IS THE UPDATED FUNCTION ---
def get_event_urls(list_page_url: str) -> set[str]:
    """
    Scrapes a list page to find all unique, clean event URLs, now with
    a stricter filter to exclude non-event pages.
    """
    print(f"Discovering event URLs from: {list_page_url}")
    urls = set()
    
    # Prefixes in the 'title' part of a URL that should be ignored.
    # This prevents scraping character pages, list pages, etc.
    EXCLUDED_PREFIXES = ('Characters/', 'Generic_Events', 'Character_Events')

    try:
        response = requests.get(list_page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        content_area = soup.find(id='mw-content-text')
        if not content_area: return set()
        
        for link in content_area.find_all('a', href=True):
            clean_url, _ = urldefrag(link['href'])
            full_url = urljoin(list_page_url, clean_url)
            
            # --- UPDATED FILTER LOGIC ---
            # Basic structural check
            if 'index.php?title=' not in full_url:
                continue
                
            # Extract the part of the URL after 'title='
            title_part = full_url.split('title=', 1)[-1]

            # Exclude non-event pages more robustly
            if ('action=edit' in full_url or 
                'Category:' in title_part or 
                'Template:' in title_part or
                title_part.startswith(EXCLUDED_PREFIXES)):
                continue # Skip this URL
                
            urls.add(full_url)
                
        print(f"Found {len(urls)} valid event URLs.")
        return urls
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching the list page: {e}")
        return set()

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name)

def process_url(url: str, default_category: str):
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        event_data = transform_event_html_to_json(response.text)
        event_id = event_data.get("event_id")
        if not event_id:
            return f"[WARNING] No event_id found for {url}. Skipping."
        primary_char = event_data.get("primary_character")
        if primary_char:
            char_folder_name = sanitize_filename(primary_char)
            output_dir = os.path.join(OUTPUT_BASE_DIR, 'Character_Events', char_folder_name)
        else:
            output_dir = os.path.join(OUTPUT_BASE_DIR, default_category)
        os.makedirs(output_dir, exist_ok=True)
        output_filename = f"{event_id}.json"
        output_path = os.path.join(output_dir, output_filename)
        if os.path.exists(output_path):
            return f"[SKIP] Already exists: {output_path}"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(event_data, f, ensure_ascii=False, indent=4)
        return f"[SUCCESS] Saved to: {output_path}"
    except requests.exceptions.RequestException as e:
        return f"[ERROR] Network error for {url}. Reason: {e}"
    except Exception as e:
        return f"[ERROR] Parsing/processing error for {url}. Reason: {e}"

def main():
    """Main execution function to orchestrate the concurrent scraping process."""
    print("Starting the Lessons in Love Wiki Crawler (Final Version).")
    if not os.path.exists(OUTPUT_BASE_DIR):
        os.makedirs(OUTPUT_BASE_DIR)
    all_urls_to_process = {}
    for category, list_page_url in SEED_URLS.items():
        urls = get_event_urls(list_page_url)
        for url in urls:
            if url not in all_urls_to_process:
                # Sanitize the category name for the folder
                folder_category = category.replace('_Side', '').replace('_F1', '').replace('_F2', '')
                all_urls_to_process[url] = folder_category
    total_urls = len(all_urls_to_process)
    print(f"\nFound a total of {total_urls} unique events to process across all categories.")
    if not total_urls: return
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(process_url, url, category): url for url, category in all_urls_to_process.items()}
        for future in as_completed(future_to_url):
            result = future.result()
            print(result)
    print("\nCrawling process complete.")

if __name__ == "__main__":
    main()