import os
import json
from dataclasses import dataclass, fields
from typing import List, Dict, Any, Optional

# --- Configuration ---
MAIN_EVENTS_DIR = os.path.join('output', 'Main_Events')
OUTPUT_FILE = 'main_events_timeline.json'

# --- Data Structure ---
@dataclass
class Event:
    event_id: str
    event_title: str
    url: str
    navigation: Dict[str, Optional[str]]
    # All other fields are loaded to prevent crashes but are not used for sorting.
    event_type: Optional[str] = None
    chapter: Optional[str] = None
    interactivity: Optional[Dict[str, Any]] = None
    progression: Optional[Dict[str, Any]] = None
    technical_information: Optional[Dict[str, Any]] = None
    primary_character: Optional[str] = None
    secret_information: Optional[Dict[str, Any]] = None
    timeline_index: Optional[int] = None

# --- Core Functions ---

def load_main_events(directory: str) -> List[Event]:
    """Loads all JSON files from the Main_Events directory."""
    print(f"Loading all events from '{directory}'...")
    event_objects = []
    if not os.path.exists(directory):
        print(f"[ERROR] Directory not found: '{directory}'.")
        return []

    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            file_path = os.path.join(directory, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    known_keys = {f.name for f in fields(Event)}
                    filtered_data = {k: v for k, v in data.items() if k in known_keys}
                    event_objects.append(Event(**filtered_data))
            except Exception as e:
                print(f"[WARNING] Could not process file {filename}. Error: {e}")

    print(f"Successfully loaded {len(event_objects)} Main Event files.")
    return event_objects

def main():
    """Main execution function with corrected logic."""
    main_events = load_main_events(MAIN_EVENTS_DIR)
    if not main_events:
        return

    events_by_title = {event.event_title: event for event in main_events}
    all_main_event_titles = set(events_by_title.keys())

    # --- NEW AND ROBUST LOGIC TO FIND THE STARTING EVENT ---
    start_event = None
    for event in main_events:
        prev_event_title = event.navigation.get('previous_event')
        # The start event is the one whose predecessor is NOT another main event.
        if prev_event_title not in all_main_event_titles:
            start_event = event
            break

    if not start_event:
        print("[ERROR] Critical failure: Could not determine the starting event.")
        print("No event was found whose 'previous_event' points to something outside the main event list.")
        return

    print(f"Correctly identified starting event: '{start_event.event_title}'")

    # --- Build the timeline by following the 'next_event' chain ---
    timeline = []
    current_event = start_event
    processed_titles = set()

    while current_event and current_event.event_title not in processed_titles:
        timeline.append(current_event)
        processed_titles.add(current_event.event_title)

        next_title = current_event.navigation.get('next_event')

        if not next_title:
            print("Reached the logical end of the known main story chain.")
            break

        current_event = events_by_title.get(next_title)

        if not current_event:
            print(f"[INFO] The chain ends here. Event '{timeline[-1].event_title}' points to a next event named '{next_title}', which could not be found in the loaded files. This is expected if it's a new/unreleased event.")

    # --- Final Validation ---
    placed_count = len(timeline)
    total_count = len(main_events)
    print(f"\nTimeline construction complete. Placed {placed_count} out of {total_count} events in the chain.")

    if placed_count < total_count:
        missed_events = all_main_event_titles - processed_titles
        print(f"[WARNING] {len(missed_events)} events were loaded but not placed in the timeline. This may indicate a broken link in the wiki data or orphan events.")
        # print(f"Orphaned Events: {list(missed_events)}") # Uncomment for debugging if needed

    # Assign the final timeline index to each event
    for i, event in enumerate(timeline):
        event.timeline_index = i

    output_data = [event.__dict__ for event in timeline]

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)

    print(f"\nProcess complete. The main event timeline has been saved to '{OUTPUT_FILE}'")

if __name__ == "__main__":
    main()