# validator.py
import os
import json

OUTPUT_BASE_DIR = 'output'

def validate_data():
    """
    Scans all scraped JSON files and checks for common errors or missing data.
    """
    print(f"--- Starting Validation of data in '{OUTPUT_BASE_DIR}' folder ---")
    
    files_to_review = {}
    total_files_scanned = 0
    
    # Recursively find all .json files in the output directory
    for root, _, files in os.walk(OUTPUT_BASE_DIR):
        for file in files:
            if file.endswith('.json'):
                total_files_scanned += 1
                filepath = os.path.join(root, file)
                
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # --- List of Checks ---
                    
                    # 1. Critical fields should never be empty
                    if not data.get('event_title') or not data.get('event_id'):
                        add_to_review(files_to_review, filepath, "Critical field (event_title or event_id) is missing.")
                        
                    # 2. Key metadata fields that are commonly missing
                    if not data.get('event_type'):
                        add_to_review(files_to_review, filepath, "Event Type is null.")
                        
                    if not data.get('chapter'):
                        add_to_review(files_to_review, filepath, "Chapter is null.")
                        
                    if not data.get('progression', {}).get('synopsis'):
                         add_to_review(files_to_review, filepath, "Synopsis is empty.")
                         
                    # 3. Logical Consistency Checks
                    event_type = data.get('event_type', '')
                    if event_type and 'Event' in event_type and event_type != 'Main Event':
                        if not data.get('primary_character'):
                            add_to_review(files_to_review, filepath, "Character Event is missing a primary_character.")
                    
                except json.JSONDecodeError:
                    add_to_review(files_to_review, filepath, "Invalid JSON format (file is corrupted).")
                except Exception as e:
                    add_to_review(files_to_review, filepath, f"An unexpected error occurred: {e}")

    # --- Print Summary Report ---
    print(f"\nValidation Complete. Scanned {total_files_scanned} files.\n")
    
    if not files_to_review:
        print("✅ All checks passed! No immediate issues found.")
    else:
        print(f"⚠️ Found {len(files_to_review)} file(s) with potential issues. Please review them manually:\n")
        for filepath, reasons in files_to_review.items():
            print(f"- File: {filepath}")
            for reason in reasons:
                print(f"  - Reason: {reason}")
            print() # Newline for readability

def add_to_review(review_dict, filepath, reason):
    """Helper function to add a file and reason to the review list."""
    if filepath not in review_dict:
        review_dict[filepath] = []
    review_dict[filepath].append(reason)

if __name__ == "__main__":
    validate_data()