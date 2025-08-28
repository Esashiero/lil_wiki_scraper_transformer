import os
import json

# --- Configuration ---
MAIN_EVENTS_DIR = os.path.join('output', 'Main_Events')

def main():
    """
    A simple diagnostic script to inspect the event links and find the true starting point.
    """
    if not os.path.exists(MAIN_EVENTS_DIR):
        print(f"[ERROR] Directory not found: '{MAIN_EVENTS_DIR}'. Please ensure the crawler has run.")
        return

    event_links = []
    
    print(f"Reading all {len(os.listdir(MAIN_EVENTS_DIR))} files from '{MAIN_EVENTS_DIR}'...")

    for filename in os.listdir(MAIN_EVENTS_DIR):
        if not filename.endswith('.json'):
            continue

        file_path = os.path.join(MAIN_EVENTS_DIR, filename)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                title = data.get('event_title', 'TITLE NOT FOUND')
                navigation = data.get('navigation', {})
                prev_event = navigation.get('previous_event', 'PREVIOUS EVENT NOT FOUND')
                event_links.append({'title': title, 'prev': prev_event})
        except Exception as e:
            print(f"[WARNING] Could not process file {filename}. Error: {e}")

    # Sort the list alphabetically by title for easier reading
    event_links.sort(key=lambda x: x['title'])

    print("\n--- Main Event Link Analysis ---")
    print("This list shows each event and its direct predecessor.")
    print("Look for the event with a 'null', empty, or non-event predecessor.\n")

    for link in event_links:
        # Using repr() for 'prev' to clearly show if it's None (null) or an empty string ""
        print(f"Event: \"{link['title']}\"  <--  Previous: {repr(link['prev'])}")

    print(f"\n--- End of Analysis ---")
    print("Please copy and paste this output so we can identify the true starting event.")


if __name__ == "__main__":
    main()