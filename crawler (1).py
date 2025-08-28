import requests
import os
import re
import json
import time
from collections import deque
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urldefrag, unquote, quote
from concurrent.futures import ThreadPoolExecutor, as_completed
from transformer import transform_event_html_to_json

# --- Configuration ---
OUTPUT_BASE_DIR = 'output'
MAX_WORKERS = 10
BASE_URL = 'https://lessonsinlove.wiki'
SEED_CATEGORY_URL = 'https://www.lessonsinlove.wiki/index.php?title=Normal_Office_Visit'

# --- Data Cleaning and Manual Patches ---
JUNK_TITLES = {'update xx.xx.xx'}
TITLE_MAPPINGS = {
    'Fireworks etc...': 'Fireworks, Chicken, and the Innate Fear of Death',
    'The Legacy of Thuam Pt. IV': 'The Legacy of Thaum Pt. IV',
    'The Sakakibara Diet': None, # This link is a known dead end
}

# --- Helper Functions ---

def title_to_url(title: str) -> str:
    """Converts an event title to a full wiki URL."""
    return f"{BASE_URL}/index.php?title={quote(title.replace(' ', '_'))}"

def url_to_title(url: str) -> str:
    """Extracts the event title from a wiki URL."""
    try:
        title_part = url.split('title=', 1)[1]
        return unquote(title_part).replace('_', ' ')
    except IndexError:
        return None

def sanitize_filename(name: str) -> str:
    """Sanitizes a string to be used as a valid filename."""
    return re.sub(r'[\\/*?:"<>|]', "", name)

# --- Seeding Function ---

def get_seed_urls_from_category_page(start_url: str) -> set[str]:
    """
    Scrapes a category page and all its subsequent pages to get a large
    initial seed of event URLs.
    """
    urls = set()
    current_page_url = start_url
    page_count = 0
    while current_page_url:
        page_count += 1
        print(f"  Scraping seed page {page_count}: {current_page_url}")
        try:
            time.sleep(0.2)
            response = requests.get(current_page_url, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            content_div = soup.find('div', id='mw-pages')
            if not content_div: break
            links = content_div.find_all('a', href=True)
            for link in links:
                if '/index.php?title=' in link['href'] and 'action=edit' not in link['href']:
                    title_part = link['href'].split('title=', 1)[-1]
                    if 'Category:' not in title_part:
                        urls.add(urldefrag(urljoin(BASE_URL, link['href']))[0])
            next_page_link = content_div.find('a', string='next page')
            current_page_url = urljoin(BASE_URL, next_page_link['href']) if next_page_link else None
        except requests.exceptions.RequestException as e:
            print(f"  [ERROR] Could not fetch seed page {current_page_url}: {e}")
            current_page_url = None
    return urls

# --- Core Processing Function ---

def process_and_discover(url: str, title_hint: str) -> dict:
    """
    Processes a single event URL, cleans its navigation data, saves it,
    and discovers links to the previous and next events.
    """
    try:
        time.sleep(0.2)
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        event_data = transform_event_html_to_json(response.text)
        event_title = event_data.get("event_title", title_hint)

        # --- Clean navigation data before saving ---
        nav = event_data.get("navigation", {})
        for key in ["prev_event", "next_event"]:
            title = nav.get(key)
            if not title or title in JUNK_TITLES:
                nav[key] = None
            elif title in TITLE_MAPPINGS:
                nav[key] = TITLE_MAPPINGS[title]
        event_data["navigation"] = nav
        
        output_dir = os.path.join(OUTPUT_BASE_DIR, "Main_Events")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{sanitize_filename(event_title)}.json")
        
        if os.path.exists(output_path):
            # Even if it exists, overwrite it with the cleaned data
            pass

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(event_data, f, ensure_ascii=False, indent=4)
        
        return {
            "status": "success", "path": output_path, "title": event_title,
            "prev_event": nav.get("previous_event"), "next_event": nav.get("next_event")
        }
    except Exception as e:
        return {"status": "error", "title": title_hint, "reason": str(e)}

# --- Main Hybrid Crawler Function ---

def main():
    """
    Main execution function. Implements a hybrid crawler that uses a seed
    list from a category page and then performs graph traversal.
    """
    print("Starting the Lessons in Love Wiki Crawler (Hybrid Mode)...")
    if not os.path.exists(OUTPUT_BASE_DIR):
        os.makedirs(OUTPUT_BASE_DIR)

    print("\n--- Phase 1: Seeding initial events from Main Events category ---")
    seed_urls = get_seed_urls_from_category_page(SEED_CATEGORY_URL)
    initial_titles = {url_to_title(url) for url in seed_urls if url_to_title(url)}
    print(f"--> Found {len(initial_titles)} unique event titles from category pages.")

    print("\n--- Phase 2: Traversing event graph to find all connected events ---")
    to_visit = deque(initial_titles)
    visited_titles = set()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        while to_visit:
            futures = {}
            batch_size = len(to_visit)
            
            for _ in range(batch_size):
                if not to_visit: break
                current_title = to_visit.popleft()
                if not current_title or current_title in visited_titles:
                    continue
                
                visited_titles.add(current_title)
                url = title_to_url(current_title)
                futures[executor.submit(process_and_discover, url, current_title)] = current_title
            
            if not futures: continue
            
            print(f"\n--- Processing a batch of {len(futures)} events ---")
            for future in as_completed(futures):
                title = futures[future]
                result = future.result()
                status = result.get("status")

                if status == "success":
                    print(f"[SUCCESS] Saved: {result.get('path')}")
                elif status == "error":
                    print(f"[ERROR] Failed '{result.get('title')}'. Reason: {result.get('reason')}")
                
                for key in ["prev_event", "next_event"]:
                    discovered_title = result.get(key)
                    if discovered_title and discovered_title not in visited_titles and discovered_title not in to_visit:
                        to_visit.append(discovered_title)
                        print(f"  -> Discovered: {discovered_title}")

    print("\n--- Crawling Process Complete ---")
    print(f"Successfully visited and processed {len(visited_titles)} unique events.")

if __name__ == "__main__":
    main()