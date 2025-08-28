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

# --- Helper Functions ---

def title_to_url(title: str) -> str:
    """Converts an event title to a full wiki URL."""
    # Replace spaces with underscores and quote special characters for the URL
    return f"{BASE_URL}/index.php?title={quote(title.replace(' ', '_'))}"

def sanitize_filename(name: str) -> str:
    """Sanitizes a string to be used as a valid filename."""
    return re.sub(r'[\\/*?:"<>|]', "", name)

# --- Core Processing Function ---

def process_and_discover(url: str, title_hint: str) -> dict:
    """
    Processes a single event URL to extract its data and discover links to
    the previous and next events.
    Returns a dictionary with processed data and discovered links.
    """
    try:
        time.sleep(1) # Be gentle on the server
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        
        event_data = transform_event_html_to_json(response.text)
        
        event_title = event_data.get("event_title")
        if not event_title:
            print(f"[WARNING] No event_title found for {url}. Using hint: {title_hint}")
            event_title = title_hint

        # All events discovered through graph traversal are considered "Main_Events"
        # for the purpose of folder organization.
        category_folder = "Main_Events"
        output_dir = os.path.join(OUTPUT_BASE_DIR, category_folder)
        os.makedirs(output_dir, exist_ok=True)

        output_filename = f"{sanitize_filename(event_title)}.json"
        output_path = os.path.join(output_dir, output_filename)
        
        if os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            nav = existing_data.get("navigation", {})
            return {
                "status": "skipped", "title": event_title,
                "prev_event": nav.get("previous_event"), "next_event": nav.get("next_event")
            }
            
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(event_data, f, ensure_ascii=False, indent=4)
            
        nav = event_data.get("navigation", {})
        return {
            "status": "success", "path": output_path, "title": event_title,
            "prev_event": nav.get("previous_event"), "next_event": nav.get("next_event")
        }

    except requests.exceptions.RequestException as e:
        return {"status": "error", "title": title_hint, "reason": f"Network error: {e}"}
    except Exception as e:
        return {"status": "error", "title": title_hint, "reason": f"Processing error: {e}"}

# --- Main Graph Traversal Function ---

def main():
    """
    Main execution function. Implements a graph traversal crawler to discover
    and process all connected events, starting from a known seed event.
    """
    print("Starting the Lessons in Love Wiki Crawler (Graph Traversal Mode)...")
    if not os.path.exists(OUTPUT_BASE_DIR):
        os.makedirs(OUTPUT_BASE_DIR)

    # Seed event known to be early in the main timeline
    seed_event_title = "Every Day I Grow Some More"
    
    to_visit = deque([seed_event_title])
    visited_titles = set()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        while to_visit:
            futures = {}
            # Create a batch of tasks from the current queue
            for _ in range(len(to_visit)):
                current_title = to_visit.popleft()
                if not current_title or current_title in visited_titles:
                    continue

                visited_titles.add(current_title)
                url = title_to_url(current_title)
                future = executor.submit(process_and_discover, url, current_title)
                futures[future] = current_title

            if not futures: continue

            print(f"\n--- Processing a batch of {len(futures)} events ---")

            for future in as_completed(futures):
                title = futures[future]
                result = future.result()
                status = result.get("status")

                if status == "success":
                    print(f"[SUCCESS] Saved: {result.get('path')}")
                elif status == "skipped":
                    print(f"[SKIP] Already exists: {result.get('title')}")
                elif status == "error":
                    print(f"[ERROR] Failed to process '{result.get('title')}'. Reason: {result.get('reason')}")

                # Add newly discovered events to the queue for the next batch
                for key in ["prev_event", "next_event"]:
                    discovered_title = result.get(key)
                    if discovered_title and discovered_title not in visited_titles:
                        to_visit.append(discovered_title)
                        print(f"  -> Discovered: {discovered_title}")

    print("\n--- Crawling Process Complete ---")
    print(f"Successfully visited and processed {len(visited_titles)} unique events.")

if __name__ == "__main__":
    main()