import requests
import os
import re
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urldefrag
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import the core transformation function from your existing script
from transformer import transform_event_html_to_json

# --- Configuration ---

# This dictionary now maps a broad category to a list page URL.
# The category is used as a fallback if a more specific one isn't found.
SEED_URLS = {
   # 'Main_Events': 'https://lessonsinlove.wiki/index.php?title=Main_Events',
    'Character_Events': 'https://lessonsinlove.wiki/index.php?title=Character_Events_(Side)',
    # You can add the other character pages here; they will all be sorted correctly
    # 'Character_Events_F2': 'https://lessonsinlove.wiki/index.php?title=Character_Events_(Floor_Two)',
    # 'Character_Events_F1': 'https://lessonsinlove.wiki/index.php?title=Character_Events_(Floor_One)',
}

OUTPUT_BASE_DIR = 'output'
MAX_WORKERS = 10

# --- Helper Functions ---

def get_event_urls(list_page_url: str) -> set[str]:
    """Scrapes a list page to find all unique, clean event URLs."""
    # This function remains largely the same and is effective.
    print(f"Discovering event URLs from: {list_page_url}")
    urls = set()
    try:
        response = requests.get(list_page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        content_area = soup.find(id='mw-content-text')
        if not content_area: return set()
        for link in content_area.find_all('a', href=True):
            clean_url, _ = urldefrag(link['href'])
            full_url = urljoin(list_page_url, clean_url)
            if 'index.php?title=' in full_url and 'action=edit' not in full_url and 'Category:' not in full_url:
                urls.add(full_url)
        print(f"Found {len(urls)} unique event URLs.")
        return urls
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching the list page: {e}")
        return set()

def sanitize_filename(name: str) -> str:
    """Removes invalid characters from a string to make it a valid folder name."""
    return re.sub(r'[\\/*?:"<>|]', "", name)

# --- 2. Processing Logic (Upgraded) ---

def process_url(url: str, default_category: str):
    """
    Fetches, transforms, determines the correct directory, and saves data for a URL.
    """
    try:
        # 1. Scrape and Transform
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        event_data = transform_event_html_to_json(response.text)
        event_id = event_data.get("event_id")

        if not event_id:
            return f"[WARNING] No event_id found for {url}. Skipping."

        # 2. Determine Output Directory Dynamically
        primary_char = event_data.get("primary_character")
        
        if primary_char:
            # If a character is identified, create a specific folder for them.
            char_folder_name = sanitize_filename(primary_char)
            output_dir = os.path.join(OUTPUT_BASE_DIR, 'Character_Events', char_folder_name)
        else:
            # Otherwise, use the default category (e.g., 'Main_Events').
            output_dir = os.path.join(OUTPUT_BASE_DIR, default_category)
            
        # Create the directory if it doesn't exist. This is thread-safe.
        os.makedirs(output_dir, exist_ok=True)

        # 3. Check Cache / Save Output
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

# --- 3. Main Execution Loop ---

def main():
    """Main execution function to orchestrate the concurrent scraping process."""
    print("Starting the Lessons in Love Wiki Crawler (V3).")
    if not os.path.exists(OUTPUT_BASE_DIR):
        os.makedirs(OUTPUT_BASE_DIR)

    all_urls_to_process = {}
    for category, list_page_url in SEED_URLS.items():
        urls = get_event_urls(list_page_url)
        for url in urls:
            # Store the URL with its default category, avoiding duplicates
            if url not in all_urls_to_process:
                all_urls_to_process[url] = category
    
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