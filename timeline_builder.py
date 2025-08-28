import os
import json
from dataclasses import dataclass, fields
from typing import List, Dict, Any, Optional

# --- Configuration ---
# We will ONLY look in the Main_Events directory.
MAIN_EVENTS_DIR = os.path.join('output', 'Main_Events')
# The output file will be clearly named.
OUTPUT_FILE = 'main_events_timeline.json'

# --- Data Structure ---
# Using the same robust dataclass to load the data cleanly.
@dataclass
class Event:
    event_id: str
    event_title: str
    url: str
    navigation: Dict[str, Optional[str]]
    # Include other fields to load the full object, but they won't be used for sorting.
    event_type: str
    chapter: str
    interactivity: Dict[str, Any]
    progression: Dict[str, Any]
    technical_information: Dict[str, Any]
    primary_character: Optional[str] = None
    secret_information: Optional[Dict[str, Any]] = None 
    timeline_index: Optional[int] = None

# --- Core Functions ---

def load_main_events(directory: str) -> List[Event]:
    """
    Loads all JSON files ONLY from the specified Main_Events directory
    into a list of Event objects.
    """
    print(f"Loading all events from '{directory}'...")
    event_objects = []
    if not os.path.exists(directory):
        print(f"[ERROR] Directory not found: '{directory}'. Please run the crawler first.")
        return []

    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            file_path = os.path.join(directory, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # This logic correctly handles JSONs with extra fields
                    known_keys = {f.name for f in fields(Event) if f.init}
                    filtered_data = {k: v for k, v in data.items() if k in known_keys}
                    event_objects.append(Event(**filtered_data))
            except Exception as e:
                print(f"[WARNING] Could not process file {filename}. Error: {e}")
    
    print(f"Successfully loaded {len(event_objects)} Main Event files.")
    return event_objects

def main():
    """Main execution function."""
    
    # 1. Load ONLY the main events from disk.
    main_events = load_main_events(MAIN_EVENTS_DIR)
    if not main_events:
        return

    # 2. Create a dictionary mapping event titles to the full event object.
    # This allows for instant lookups (e.g., finding the event for "A New You").
    events_by_title = {event.event_title: event for event in main_events}
    all_titles = set(events_by_title.keys())

    # 3. Find the very first event.
    # The first event is the one whose 'previous_event' is either null, empty,
    # or doesn't correspond to any other main event we've loaded.
    start_event = None
    for event in main_events:
        prev_event_title = event.navigation.get('previous_event')
        if not prev_event_title or prev_event_title not in all_titles:
            start_event = event
            print(f"Found the starting event: '{start_event.event_title}'")
            break
    
    if not start_event:
        print("[ERROR] Critical failure: Could not determine the first Main Event. No event has a null or non-matching previous_event. Please check the data.")
        return

    # 4. Build the timeline by following the 'next_event' chain.
    timeline = []
    current_event = start_event
    
    # We use a set to prevent infinite loops in case of bad data (e.g., A -> B -> A)
    processed_titles = set()

    while current_event and current_event.event_title not in processed_titles:
        timeline.append(current_event)
        processed_titles.add(current_event.event_title)
        
        next_title = current_event.navigation.get('next_event')
        
        if not next_title:
            print("Reached the end of the main story chain.")
            break
            
        # Look up the next event object using our dictionary.
        current_event = events_by_title.get(next_title)
        
        if not current_event:
            print(f"[WARNING] The chain is broken. Event '{timeline[-1].event_title}' points to a next event named '{next_title}', which could not be found.")

    # 5. Final Validation and Output
    if len(timeline) < len(main_events):
        print("\n[WARNING] Not all loaded main events were placed in the timeline.")
        placed_titles = {e.event_title for e in timeline}
        missed_events = [title for title in all_titles if title not in placed_titles]
        print(f"Missed {len(missed_events)} events: {missed_events}")
    else:
        print("\nSuccessfully placed all main events into a single chronological chain.")

    # Assign the final timeline index to each event
    for i, event in enumerate(timeline):
        event.timeline_index = i

    # Convert dataclass objects to dictionaries for the final JSON
    output_data = [event.__dict__ for event in timeline]
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
        
    print(f"\nProcess complete. The main event timeline has been saved to '{OUTPUT_FILE}'")

if __name__ == "__main__":
    main()