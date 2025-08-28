from bs4 import BeautifulSoup, Tag, NavigableString
import json
import re

# All other parsing functions (get_section_content, parse_interactivity, etc.)
# are correct from the previous version and remain unchanged.

def get_section_content(start_node: Tag, stop_at: list = ['h2', 'h3']):
    content = []
    if not start_node or not hasattr(start_node, 'find_parent'): return content
    header_tag = start_node.find_parent(stop_at)
    if not header_tag: return content
    for sibling in header_tag.find_next_siblings():
        if hasattr(sibling, 'name') and sibling.name in stop_at: break
        content.append(sibling)
    return content

def parse_interactivity(tab: Tag) -> dict:
    """
    Parses the 'Event Interactivity' tab with corrected logic for multi-element requirements.
    """
    data = {
        "requirements": None, "to_get_this_event": None, "to_miss_this_event": None,
        "choices": [], "effects": [],
    }
    if not tab: return data

    # --- REQUIREMENTS PARSING LOGIC REWRITTEN ---
    req_header = tab.find("span", id="Requirements")
    if req_header and req_header.parent:
        h3_tag = req_header.parent
        requirements_content = []
        # Find all sibling tags between this h3 and the next one
        for sibling in h3_tag.find_next_siblings():
            if hasattr(sibling, 'name') and sibling.name == 'h3':
                break # Stop when we hit the next header (e.g., "To get this event")
            # Collect text from any relevant tags in this section
            if hasattr(sibling, 'name') and sibling.name in ['p', 'ul', 'div']:
                requirements_content.append(sibling.get_text(" ", strip=True))
        
        if requirements_content:
            data["requirements"] = " ".join(requirements_content)
    # --- END OF REWRITTEN LOGIC ---

    get_event_header = tab.find("span", id="To_get_this_event")
    if get_event_header:
        get_event_p = get_event_header.find_parent('h3').find_next_sibling('p')
        if get_event_p: data["to_get_this_event"] = get_event_p.get_text(" ", strip=True)
    
    miss_event_header = tab.find("span", id="To_miss_this_event")
    if miss_event_header:
        miss_event_p = miss_event_header.find_parent('h3').find_next_sibling('p')
        if miss_event_p: data["to_miss_this_event"] = miss_event_p.get_text(" ", strip=True)

    choices_header = tab.find("span", id="Choices")
    if choices_header:
        content_nodes = get_section_content(choices_header, stop_at=['h2'])
        block_context = None
        for node in content_nodes:
            if hasattr(node, 'name') and node.name == 'p':
                block_context = node.get_text(" ", strip=True)
            elif hasattr(node, 'name') and node.name == 'dl':
                current_option = None
                for child in node.children:
                    if isinstance(child, Tag):
                        if child.name == 'dt':
                            current_option = child.get_text(strip=True)
                        elif child.name == 'dd' and current_option:
                            effect = child.get_text(" ", strip=True)
                            choice_object = {
                                "context": block_context, "option": current_option, "effect": effect
                            }
                            data["choices"].append(choice_object)
                            current_option = None
                block_context = None

    effects_header = tab.find("span", id="Effects")
    if effects_header:
        for element in get_section_content(effects_header):
            if hasattr(element, 'name') and element.name == 'ul':
                data["effects"].extend([li.get_text(" ", strip=True) for li in element.find_all('li') if li.get_text(strip=True)])
    
    return data

def parse_progression(tab: Tag) -> dict:
    data = {"locations": [], "synopsis": None, "participating_characters": [], "trivia": []}
    if not tab: return data
    loc_header = tab.find("span", id="Locations")
    if loc_header:
        ul = next((n for n in get_section_content(loc_header) if hasattr(n, 'name') and n.name == 'ul'), None)
        if ul: data["locations"] = [li.get_text(" ", strip=True) for li in ul.find_all('li')]
    synopsis_header = tab.find("span", id="Synopsis")
    if synopsis_header:
        data["synopsis"] = " ".join([p.get_text(" ", strip=True) for p in get_section_content(synopsis_header) if hasattr(p, 'name') and p.name == 'p'])
    chars_header = tab.find("span", id="Participating_Characters")
    if chars_header:
        div = next((n for n in get_section_content(chars_header) if hasattr(n, 'name') and n.name == 'div' and 'plainlist' in n.get('class', [])), None)
        if div: data["participating_characters"] = [a.get_text(strip=True) for a in div.find_all("a") if a.get_text(strip=True)]
    trivia_header = tab.find("span", id="Trivia")
    if trivia_header and trivia_header.parent:
        h2_tag = trivia_header.parent
        for sibling in h2_tag.next_siblings:
            if isinstance(sibling, Tag) and sibling.name in ['h2', 'h3']: break
            elif isinstance(sibling, NavigableString):
                text = sibling.strip()
                if text: data["trivia"].append(text)
            elif isinstance(sibling, Tag) and sibling.name in ['ul', 'dl']:
                if sibling.name == 'ul': data["trivia"].extend([li.get_text(" ", strip=True) for li in sibling.find_all('li')])
                elif sibling.name == 'dl':
                    dt, dd = sibling.find("dt"), sibling.find("dd")
                    if dt and dd: data["trivia"].append(f"{dt.get_text(strip=True)}: {dd.get_text(strip=True)}")
    return data

def parse_technical_info(tab: Tag) -> dict:
    """Parses technical info, now saving event_script_names as a plain string."""
    data = {"event_references": {}, "backgrounds": [], "music_tracks": [], "changelog": []}
    if not tab: return data
    ref_header = tab.find("span", id="Event_References")
    if ref_header and ref_header.parent:
        h2_tag = ref_header.parent
        for sibling in h2_tag.next_siblings:
            if isinstance(sibling, Tag) and sibling.name in ['h2', 'h3']: break
            if isinstance(sibling, Tag) and (sibling.name == 'ul' or sibling.name == 'li'):
                nodes_to_parse = sibling.find_all('li') if sibling.name == 'ul' else [sibling]
                for node in nodes_to_parse:
                    text = node.get_text(strip=True)
                    parts = text.split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].strip().lower().replace(' ', '_').replace('(s)', 's')
                        value = parts[1].strip()
                        # REMOVED: Special handling for event_script_names. It's now treated as a standard string.
                        data["event_references"][key] = value
    bg_header = tab.find("span", id="Backgrounds")
    if bg_header:
        ul = next((n for n in get_section_content(bg_header) if hasattr(n, 'name') and n.name == 'ul'), None)
        if ul: data["backgrounds"] = [li.get_text(strip=True) for li in ul.find_all('li')]
    music_header = tab.find("span", id="Music_Tracks")
    if music_header:
        ul = next((n for n in get_section_content(music_header) if hasattr(n, 'name') and n.name == 'ul'), None)
        if ul: data["music_tracks"] = [li.get_text(strip=True) for li in ul.find_all('li')]
    cl_header = tab.find("span", id="Event_Changelog")
    if cl_header:
        data["changelog"] = [p.get_text(" ", strip=True) for p in get_section_content(cl_header) if hasattr(p, 'name') and p.name == 'p']
    return data

def find_chapter(soup: BeautifulSoup, event_title: str) -> str:
    navbox = soup.find("div", class_="navbox")
    if not navbox: return None
    event_tag = navbox.find(lambda tag: tag.name in ('a', 'b') and tag.get_text(strip=True) == event_title)
    if not event_tag: return None
    row = event_tag.find_parent("tr")
    if not row: return None
    header = row.find("th")
    if not header: return None
    base_text = header.get_text(strip=True)
    if 'Chapter' in base_text: return base_text
    list_cell = row.find("td")
    if not list_cell: return base_text
    all_events_in_row = list_cell.find_all("a")
    try:
        event_index = [a.get_text(strip=True) for a in all_events_in_row].index(event_title)
        version_parts = base_text.lstrip('v').split('.')
        if len(version_parts) >= 2: return f"v{version_parts[0]}.{version_parts[1]}.{event_index + 1}"
        return base_text
    except (ValueError, IndexError):
        return base_text

def parse_secret_tab(tab: Tag) -> dict:
    data = {"description": None, "translations": []}
    if not tab: return data
    description_p = tab.find('p')
    if description_p:
        data["description"] = description_p.get_text(" ", strip=True)
    table = tab.find('table', class_='wikitable')
    if table and table.find('tbody'):
        rows = table.tbody.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) == 4:
                translation_entry = {
                    "value": cells[0].get_text(" ", strip=True), "type": cells[1].get_text(" ", strip=True),
                    "translation": cells[2].get_text(" ", strip=True), "appearance": cells[3].get_text(" ", strip=True)
                }
                data["translations"].append(translation_entry)
    return data

def transform_event_html_to_json(html_content: str) -> dict:
    """Main function to transform HTML content to the structured JSON with fixed key order."""
    soup = BeautifulSoup(html_content, "html.parser")
    
    # --- Data Extraction (remains the same) ---
    event_title_tag = soup.find("span", class_="mw-page-title-main")
    event_title = event_title_tag.get_text(strip=True) if event_title_tag else "Unknown Event"
    event_id = re.sub(r"\W+", "_", event_title).lower()
    url_tag = soup.find("meta", {"property": "og:url"})
    canonical_url = url_tag['content'] if url_tag else None
    event_type, primary_character = None, None
    intro_p = soup.select_one(".mw-parser-output > p")
    if intro_p:
        intro_text = intro_p.get_text(" ", strip=True)
        event_type_span = intro_p.find("span", class_=re.compile(r'.*Event$'))
        event_type_link = intro_p.find("a", href=re.compile(r'#.*_Event$'))
        if event_type_span and event_type_span.find('a'): event_type = event_type_span.find('a').get_text(strip=True)
        elif event_type_link: event_type = event_type_link.get_text(strip=True)
        elif "Main Event" in intro_text: event_type = "Main Event"
        elif "is an Event for" in intro_text: event_type = "Event"
        char_link = intro_p.find("a", attrs={"title": re.compile(r'^Characters/')})
        if char_link: primary_character = char_link.get_text(strip=True)
    chapter = find_chapter(soup, event_title)
    if not chapter and intro_p:
        intro_text_lower = intro_p.get_text().lower()
        ordinal_words = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth', 'eleventh', 'twelfth', 'thirteenth', 'fourteenth', 'fifteenth', 'sixteenth', 'seventeenth', 'eighteenth', 'nineteenth', 'twentieth', 'twenty-first', 'twenty-second', 'twenty-third', 'twenty-fourth', 'twenty-fifth', 'thirtieth', 'fortieth', 'fiftieth']
        for word in ordinal_words:
            if re.search(rf'\b{word}\b', intro_text_lower):
                chapter = word.capitalize()
                break
    interactivity_data = parse_interactivity(soup.find("article", {"data-title": "Event Interactivity"}))
    progression_data = parse_progression(soup.find("article", {"data-title": "Event Progression (Spoilers!)"}))
    technical_data = parse_technical_info(soup.find("article", {"data-title": "Technical Information"}))
    secret_data = parse_secret_tab(soup.find("article", {"data-title": "Secret"}))
    nav = {"previous_event": None, "next_event": None}
    prev_div, next_div = soup.find("div", class_="LArrow"), soup.find("div", class_="RArrow")
    if prev_div:
        prev_text = prev_div.get_text(strip=True).replace("Previous Event:", "").strip()
        nav["previous_event"] = prev_text if prev_text.lower() != "none" else None
    if next_div and next_div.find("a"):
        nav["next_event"] = next_div.find("a").get_text(strip=True)

    # --- Final Dictionary Assembly with specific key order ---
    final_json = {
        "event_id": event_id,
        "event_title": event_title,
        "url": canonical_url,
        "event_type": event_type,
        "primary_character": primary_character,
        "chapter": chapter,
        "interactivity": interactivity_data,
        "progression": progression_data,
        "technical_information": technical_data
    }
    if secret_data and (secret_data["description"] or secret_data["translations"]):
        final_json["secret_information"] = secret_data

    # Ensure the nav dictionary is clean before adding it
    final_nav = {
        "previous_event": nav.get("previous_event"),
        "next_event": nav.get("next_event")
    }
    final_json["navigation"] = final_nav
    
    return final_json