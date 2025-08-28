import requests
import os
import re
import json
import time
import argparse
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urldefrag, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed

# Assuming transform_event_html_to_json is in a file named transformer.py
from transformer import transform_event_html_to_json

# --- Configuration ---
SEED_URLS = {
    'DIRECT_CATEGORIES': {
        'Main_Events': 'https://lessonsinlove.wiki/index.php?title=Category:Main_Events',
        'Happy_Events': 'https://lessonsinlove.wiki/index.php?title=Category:Happy_events'
    },
    'INDEX_CATEGORIES': {
        'Side_Characters': 'https://lessonsinlove.wiki/index.php?title=Category:Side_character_events',
        'Main_Characters': 'https://lessonsinlove.wiki/index.php?title=Category:Main_character_events'
    }
}

OUTPUT_BASE_DIR = 'output'
MAX_WORKERS = 10

# --- URL Discovery Functions (Unchanged) ---

def get_all_event_urls_from_category(start_url: str) -> set[str]:
    """
    Scrapes a category page and all its subsequent pages ("next page") to find
    all unique event URLs. This version is more robust.
    """
    urls = set()
    current_page_url = start_url
    page_count = 0

    while current_page_url:
        page_count += 1
        print(f"  Scraping category page {page_count}: {current_page_url}")

        try:
            time.sleep(1)
            response = requests.get(current_page_url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # MediaWiki category pages place the list of pages and pagination links within this div.
            content_div = soup.find('div', id='mw-pages')
            if not content_div:
                # Fallback to the original container if mw-pages is not found
                content_div = soup.find('div', class_='mw-category-generated')
                if not content_div:
                    print(f"  [WARNING] Could not find a suitable content container on {current_page_url}. Stopping scrape for this category.")
                    break

            # Find all links within this container.
            links = content_div.find_all('a', href=True)
            found_on_page = 0
            for link in links:
                full_url = urljoin(current_page_url, link['href'])

                # Filter out non-event links like 'next page', 'edit', or sub-categories.
                if '/index.php?title=' in full_url and 'action=edit' not in full_url:
                    title_part = full_url.split('title=', 1)[-1]
                    if 'Category:' not in title_part:
                        clean_url = urldefrag(full_url)[0]
                        if clean_url not in urls:
                            urls.add(clean_url)
                            found_on_page += 1

            if found_on_page > 0:
                print(f"    -> Found {found_on_page} new event URLs.")

            # Find the 'next page' link specifically within the same content div.
            next_page_link = content_div.find('a', string='next page')

            if next_page_link and next_page_link.get('href'):
                # The href is relative, so we join it with the base start_url.
                current_page_url = urljoin(start_url, next_page_link['href'])
            else:
                current_page_url = None # End of pagination

        except requests.exceptions.RequestException as e:
            print(f"  [ERROR] An error occurred while fetching {current_page_url}: {e}")
            current_page_url = None

    return urls

def get_character_category_urls(index_page_url: str) -> set[str]:
    """
    Scrapes an index page to find the URLs for each individual
    character's event category page.
    """
    category_urls = set()
    print(f"Scraping character category index: {index_page_url}")
    try:
        response = requests.get(index_page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        category_items = soup.find_all('div', class_='CategoryTreeItem')
        for item in category_items:
            link = item.find('a', href=True)
            if link:
                full_url = urljoin(index_page_url, link['href'])
                category_urls.add(full_url)
        
        return category_urls

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] An error occurred while fetching the index page {index_page_url}: {e}")
        return set()

# --- Processing and Saving Functions (Unchanged) ---

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name)

def process_url(url: str, category_folder: str):
    try:
        time.sleep(1)
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        event_data = transform_event_html_to_json(response.text)
        
        event_id = event_data.get("event_id")
        if not event_id:
            return f"[WARNING] No event_id found for {url}. Skipping."

        output_dir = os.path.join(OUTPUT_BASE_DIR, category_folder)
        
        primary_char = event_data.get("primary_character")
        if primary_char and category_folder == 'Character_Events':
            char_folder_name = sanitize_filename(primary_char)
            output_dir = os.path.join(output_dir, char_folder_name)

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

# --- MAIN FUNCTION (Updated with new logging) ---

def main():
    """Main execution function with summary logging and category filtering."""
    parser = argparse.ArgumentParser(description="Crawl the Lessons in Love wiki for event data.")
    parser.add_argument(
        '--category',
        type=str,
        help='A specific category to crawl (e.g., "Main_Events", "Happy_Events", "Side_Characters"). If not provided, all categories will be crawled.'
    )
    args = parser.parse_args()

    print("Starting the Lessons in Love Wiki Crawler...")
    if not os.path.exists(OUTPUT_BASE_DIR):
        os.makedirs(OUTPUT_BASE_DIR)
        
    final_url_map = {}

    # --- URL Discovery Phase ---
    print("\n--- Phase 1: Discovering Event URLs ---")
    
    categories_to_process = []
    if args.category:
        print(f"Targeting specific category: {args.category}")
        if args.category in SEED_URLS['DIRECT_CATEGORIES'] or args.category in SEED_URLS['INDEX_CATEGORIES']:
            categories_to_process.append(args.category)
        else:
            print(f"[ERROR] Category '{args.category}' not found in SEED_URLS.")
            return
    else:
        print("Processing all categories...")
        categories_to_process.extend(SEED_URLS['DIRECT_CATEGORIES'].keys())
        categories_to_process.extend(SEED_URLS['INDEX_CATEGORIES'].keys())

    for category_name in categories_to_process:
        # Handle DIRECT categories
        if category_name in SEED_URLS['DIRECT_CATEGORIES']:
            start_url = SEED_URLS['DIRECT_CATEGORIES'][category_name]
            event_urls = get_all_event_urls_from_category(start_url)
            print(f"--> Found {len(event_urls)} URLs for category '{category_name}'.")
            for url in event_urls:
                if url not in final_url_map:
                    final_url_map[url] = category_name

        # Handle INDEX categories
        elif category_name in SEED_URLS['INDEX_CATEGORIES']:
            index_url = SEED_URLS['INDEX_CATEGORIES'][category_name]
            print(f"\nProcessing Index: {category_name}")
            char_category_urls = get_character_category_urls(index_url)
            print(f"Found {len(char_category_urls)} sub-categories. Discovering events for each...")
            for char_url in sorted(list(char_category_urls)):
                char_name_log = unquote(char_url.split('Category:')[1].replace('_events', ''))
                event_urls = get_all_event_urls_from_category(char_url)
                print(f"  --> Found {len(event_urls)} URLs for '{char_name_log}'.")
                for url in event_urls:
                    if url not in final_url_map:
                        # All sub-events from an index are stored under one parent folder
                        final_url_map[url] = 'Character_Events'

    # --- Processing Phase ---
    total_urls = len(final_url_map)
    print(f"\n--- Phase 2: Processing and Saving {total_urls} Total Unique Events ---")
    if not total_urls:
        print("No URLs discovered. Exiting.")
        return

    success_count, skip_count, error_count = 0, 0, 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(process_url, url, category): (url, category) for url, category in final_url_map.items()}
        for future in as_completed(future_to_url):
            url, category = future_to_url[future]
            try:
                result = future.result()
                if "[SUCCESS]" in result: success_count += 1
                elif "[SKIP]" in result: skip_count += 1
                else:
                    error_count += 1
                    print(result)
            except Exception as exc:
                error_count += 1
                print(f'[ERROR] Processing {url} in category {category} generated an exception: {exc}')

    print("\n--- Crawling Process Complete ---")
    print(f"Successfully created: {success_count} files.")
    print(f"Skipped (already exist): {skip_count} files.")
    print(f"Errors/Warnings: {error_count} files.")

if __name__ == "__main__":
    main()