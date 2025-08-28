import os
import json
from dataclasses import dataclass, fields
from typing import List, Dict, Any, Optional
from thefuzz import process as fuzz_process

# --- Configuration ---
MAIN_EVENTS_DIR = os.path.join('output', 'Main_Events')
OUTPUT_FILE = 'main_events_timeline.json'

# --- Data Structure (NEW VERSION) ---
@dataclass
class Event:
    event_id: str
    event_title: str
    url: str
    event_type: Optional[str]
    chapter: Optional[str]
    synopsis: Optional[str]
    characters: List[str]
    locations: List[str]
    requirements: Optional[str]
    choices: List[Dict[str, Any]]
    effects: List[str]
    navigation: Dict[str, Optional[str]]
    trivia: List[str]
    changelog: List[str]
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

# --- Utility to normalize titles ---
def normalize_title(title: str) -> str:
    """Normalize event titles for consistent lookup."""
    if not title:
        return ""
    return "".join(c for c in title.strip() if c.isprintable())


def main():
    """Main execution function with logic to handle multiple independent event chains."""
    main_events = load_main_events(MAIN_EVENTS_DIR)
    if not main_events:
        return

    # --- DEBUG: find missing references ---
    for event in main_events:
        prev = event.navigation.get("previous_event")
        nxt = event.navigation.get("next_event")
        if prev == "The Sakakibara Diet" or nxt == "The Sakakibara Diet":
            print(f"Reference issue found in: {event.event_title} (prev: {prev}, next: {nxt})")
    # --- End debug ---

    events_by_title = {event.event_title: event for event in main_events}
    all_main_event_titles = set(events_by_title.keys())


    # --- Find all starting points ---
    starting_events = []
    for event in main_events:
        prev_event_title = event.navigation.get('previous_event')
        if prev_event_title not in all_main_event_titles:
            starting_events.append(event)

    if not starting_events:
        print("[ERROR] Critical failure: Could not determine any starting event.")
        return

    print(f"Found {len(starting_events)} potential starting points for event chains.")

    # --- Timeline-building loop goes here ---
    full_timeline = []
    processed_titles = set()
    chain_count = 0

    for start_event in starting_events:
        norm_start_title = normalize_title(start_event.event_title)
        if norm_start_title in processed_titles:
            continue

        chain_count += 1
        current_chain = []
        current_event = start_event

        print(f"\nBuilding chain #{chain_count} starting with: '{start_event.event_title}'")

        while current_event:
            norm_current_title = normalize_title(current_event.event_title)
            if norm_current_title in processed_titles:
                break

            current_chain.append(current_event)
            processed_titles.add(norm_current_title)

            next_title_raw = current_event.navigation.get('next_event')
            next_title = normalize_title(next_title_raw)

            if not next_title:
                print(f"  -> Chain reached a logical end at '{current_event.event_title}' (no 'next_event').")
                break

            next_event = events_by_title.get(next_title)

            if not next_event and next_title:
                best_match = fuzz_process.extractOne(next_title, all_main_event_titles)
                if best_match and best_match[1] > 90:
                    print(f"  -> Fuzzy-matched '{next_title}' to '{best_match[0]}' (Confidence: {best_match[1]}%)")
                    next_event = events_by_title.get(best_match[0])
                else:
                    print(f"  -> Chain broken: Event '{current_event.event_title}' points to '{next_title}', which was not found.")
                    next_event = None

            current_event = next_event

        full_timeline.extend(current_chain)

    # --- Save timeline ---
    placed_count = len(full_timeline)
    total_count = len(main_events)
    print(f"\nTimeline construction complete. Placed {placed_count} out of {total_count} events across {chain_count} chains.")

    missed_events = all_main_event_titles - processed_titles
    if missed_events:
        print(f"[WARNING] {len(missed_events)} events were loaded but not placed in any timeline.")
        # print(f"  -> Orphaned Events: {sorted(list(missed_events))}")

    for i, event in enumerate(full_timeline):
        event.timeline_index = i

    output_data = [event.__dict__ for event in full_timeline]
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)

    print(f"\nProcess complete. The main event timeline has been saved to '{OUTPUT_FILE}'")

if __name__ == "__main__":
    main()