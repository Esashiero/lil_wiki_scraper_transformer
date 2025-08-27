import requests
import os
import time
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Import the core transformation function from your existing script
from transformer import transform_event_html_to_json

# --- 1. URL Discovery ---

def get_event_urls(list_page_url: str) -> list[str]:
    """
    Scrapes a list page (like the Main Events page) to find and return a list
    of all individual event page URLs.
    """
    print(f"Discovering event URLs from: {list_page_url}")
    urls = []
    try:
        response = requests.get(list_page_url)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        soup = BeautifulSoup(response.text, 'html.parser')

        # The main content area contains the list of events
        # We target the `<li>` elements that contain a link to an event
        content_div = soup.find('div', class_='mw-parser-output')
        if not content_div:
            print("Error: Could not find the main content div '.mw-parser-output'.")
            return []

        # Find all list items, which typically contain the event links
        list_items = content_div.find_all('li')

        for item in list_items:
            link = item.find('a')
            if link and link.has_attr('href'):
                # Construct the full, absolute URL from the relative path
                relative_path = link['href']
                full_url = urljoin(list_page_url, relative_path)
                if full_url not in urls:
                    urls.append(full_url)

        print(f"Found {len(urls)} unique event URLs.")
        return urls

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching the list page: {e}")
        return []

# --- 2. Main Execution Loop ---

def main():
    """
    Main execution function to orchestrate the scraping process.
    """
    # The starting point for our scrape
    seed_urls = ['https://lessonsinlove.wiki/index.php?title=Main_Events']
    output_dir = 'output'
    
    print("Starting the Lessons in Love Wiki Crawler.")

    # Create the output directory if it doesn't already exist
    if not os.path.exists(output_dir):
        print(f"Creating output directory: '{output_dir}/'")
        os.makedirs(output_dir)

    # Build a master list of all event URLs from our seed(s)
    master_url_list = []
    for url in seed_urls:
        master_url_list.extend(get_event_urls(url))

    if not master_url_list:
        print("No event URLs found. Exiting.")
        return

    print(f"\nBeginning scrape of {len(master_url_list)} total events...")

    # Loop through every URL, scrape it, transform it, and save it
    for i, url in enumerate(master_url_list):
        try:
            # --- Implement a Politeness Delay ---
            time.sleep(0.3) # Wait 1 second before each new request

            print(f"\n[{i+1}/{len(master_url_list)}] Processing: {url}")

            # --- Scrape and Transform ---
            response = requests.get(url)
            response.raise_for_status()
            
            event_data = transform_event_html_to_json(response.text)
            event_id = event_data.get("event_id", None)

            if not event_id:
                print(f"  [WARNING] Could not determine event_id for {url}. Skipping.")
                continue

            # --- Implement Caching ---
            output_filename = f"{event_id}.json"
            output_path = os.path.join(output_dir, output_filename)

            if os.path.exists(output_path):
                print(f"  [SKIP] JSON file '{output_filename}' already exists.")
                continue

            # --- Save the Output ---
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(event_data, f, ensure_ascii=False, indent=4)
            print(f"  [SUCCESS] Saved data to '{output_path}'")

        # --- Robust Error Handling ---
        except requests.exceptions.RequestException as e:
            print(f"  [ERROR] Failed to download {url}. Reason: {e}")
        except Exception as e:
            # Catch any other exceptions that might occur during parsing
            print(f"  [ERROR] An unexpected error occurred while processing {url}. Reason: {e}")

    print("\nCrawling process complete.")


if __name__ == "__main__":
    main()