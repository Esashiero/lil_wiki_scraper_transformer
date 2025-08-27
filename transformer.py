from bs4 import BeautifulSoup, Tag
import json
import re

def get_section_content(start_node: Tag, stop_at: list = ['h2', 'h3']):
    """
    Collects all sibling nodes after a starting header node until a stopping tag is found.
    """
    content = []
    if not start_node or not hasattr(start_node, 'find_parent'):
        return content
    header_tag = start_node.find_parent(stop_at)
    if not header_tag:
        return content
    for sibling in header_tag.find_next_siblings():
        if sibling.name in stop_at:
            break
        content.append(sibling)
    return content

def parse_interactivity(tab: Tag) -> dict:
    """Parses the 'Event Interactivity' tab."""
    data = {
        "requirements": None, "to_get_this_event": None, "choices": [], "effects": [],
    }
    if not tab: return data

    req_header = tab.find("span", id="Requirements")
    if req_header:
        req_p = req_header.find_parent('h3').find_next_sibling('p')
        if req_p: data["requirements"] = req_p.get_text(" ", strip=True)

    get_event_header = tab.find("span", id="To_get_this_event")
    if get_event_header:
        get_event_p = get_event_header.find_parent('h3').find_next_sibling('p')
        if get_event_p: data["to_get_this_event"] = get_event_p.get_text(" ", strip=True)

    miss_event_header = tab.find("span", id="To_miss_this_event")
    if miss_event_header:
        current_element = miss_event_header.find_parent('h3')
        while True:
            current_element = current_element.find_next_sibling()
            if not current_element or current_element.name != 'dl': break
            children = [child for child in current_element.children if isinstance(child, Tag)]
            if all(c.name == 'dt' for c in children[:-1]) and children[-1].name == 'dd':
                data["choices"].append({"options": [dt.get_text(strip=True) for dt in children[:-1]], "effect": children[-1].get_text(" ", strip=True)})
            else:
                temp_dt = None
                for child in children:
                    if child.name == 'dt': temp_dt = child
                    elif child.name == 'dd' and temp_dt:
                        data["choices"].append({"options": [temp_dt.get_text(strip=True)], "effect": child.get_text(" ", strip=True)})
                        temp_dt = None

    effects_header = tab.find("span", id="Effects")
    if effects_header:
        ul = effects_header.find_parent('h2').find_next_sibling('ul')
        if ul: data["effects"] = [li.get_text(" ", strip=True) for li in ul.find_all('li') if li.get_text(strip=True)]

    return data

def parse_progression(tab: Tag) -> dict:
    """Parses the 'Event Progression (Spoilers!)' tab."""
    # --- FIXED: Trivia is now a list to handle multiple formats ---
    data = {"locations": [], "synopsis": None, "participating_characters": [], "trivia": []}
    if not tab: return data

    loc_header = tab.find("span", id="Locations")
    if loc_header:
        ul = next((n for n in get_section_content(loc_header) if n.name == 'ul'), None)
        if ul: data["locations"] = [li.get_text(" ", strip=True) for li in ul.find_all('li')]

    synopsis_header = tab.find("span", id="Synopsis")
    if synopsis_header:
        data["synopsis"] = " ".join([p.get_text(" ", strip=True) for p in get_section_content(synopsis_header) if p.name == 'p'])

    chars_header = tab.find("span", id="Participating_Characters")
    if chars_header:
        div = next((n for n in get_section_content(chars_header) if n.name == 'div' and 'plainlist' in n.get('class', [])), None)
        if div: data["participating_characters"] = [a.get_text(strip=True) for a in div.find_all("a") if a.get_text(strip=True)]

    # --- FIXED: Logic to handle both <dl> and <ul> for Trivia ---
    trivia_header = tab.find("span", id="Trivia")
    if trivia_header:
        content = get_section_content(trivia_header)
        dl_node = next((node for node in content if node.name == 'dl'), None)
        ul_node = next((node for node in content if node.name == 'ul'), None)

        if dl_node: # Handles the key: value format
            dt = dl_node.find("dt")
            dd = dl_node.find("dd")
            if dt and dd:
                data["trivia"].append(f"{dt.get_text(strip=True)}: {dd.get_text(strip=True)}")
        elif ul_node: # Handles the simple list format
            for li in ul_node.find_all('li'):
                text = li.get_text(" ", strip=True)
                if text: data["trivia"].append(text)

    return data

def parse_technical_info(tab: Tag) -> dict:
    """Parses the 'Technical Information' tab."""
    data = {"event_references": {}, "backgrounds": [], "music_tracks": [], "changelog": []}
    if not tab: return data

    # --- FIXED: Logic to find <li> tags directly, without needing a <ul> ---
    ref_header = tab.find("span", id="Event_References")
    if ref_header:
        content = get_section_content(ref_header)
        li_tags = [node for node in content if node.name == 'li'] # Get all li tags in the section
        for li in li_tags:
            parts = li.get_text(strip=True).split('=', 1)
            if len(parts) == 2:
                key = parts[0].strip().lower().replace(' ', '_').replace('(s)', 's')
                value = parts[1].strip()
                data["event_references"][key] = [v.strip() for v in value.split(',')] if key == "event_script_names" else value

    bg_header = tab.find("span", id="Backgrounds")
    if bg_header:
        ul = next((n for n in get_section_content(bg_header) if n.name == 'ul'), None)
        if ul: data["backgrounds"] = [li.get_text(strip=True) for li in ul.find_all('li')]

    music_header = tab.find("span", id="Music_Tracks")
    if music_header:
        ul = next((n for n in get_section_content(music_header) if n.name == 'ul'), None)
        if ul: data["music_tracks"] = [li.get_text(strip=True) for li in ul.find_all('li')]

    cl_header = tab.find("span", id="Event_Changelog")
    if cl_header:
        data["changelog"] = [p.get_text(" ", strip=True) for p in get_section_content(cl_header) if p.name == 'p']

    return data

def find_chapter(soup: BeautifulSoup, event_title: str) -> str:
    """Finds the specific chapter version (e.g., v0.1.1)."""
    navbox = soup.find("div", class_="navbox")
    if not navbox: return None
    event_tag = navbox.find(lambda tag: tag.name in ('a', 'b') and tag.get_text(strip=True) == event_title and 'selflink' in tag.get('class', []))
    if not event_tag: return None
    row = event_tag.find_parent("tr")
    if not row: return None
    header, list_cell = row.find("th"), row.find("td")
    if not header or not list_cell: return None
    base_version_text = header.get_text(strip=True)
    all_events_in_row = list_cell.find_all("a")
    try:
        event_index = [a.get_text(strip=True) for a in all_events_in_row].index(event_title)
        event_position = event_index + 1
        version_parts = base_version_text.lstrip('v').split('.')
        if len(version_parts) >= 2:
            return f"v{version_parts[0]}.{version_parts[1]}.{event_position}"
        return base_version_text
    except (ValueError, IndexError):
        return base_version_text

def transform_event_html_to_json(html_content: str) -> dict:
    """Main function to transform HTML content to the structured JSON."""
    soup = BeautifulSoup(html_content, "html.parser")
    event_title_tag = soup.find("span", class_="mw-page-title-main")
    event_title = event_title_tag.get_text(strip=True) if event_title_tag else "Unknown Event"
    event_id = re.sub(r"\W+", "_", event_title).lower()
    url_tag = soup.find("meta", {"property": "og:url"})
    canonical_url = url_tag['content'] if url_tag else None
    intro_p = soup.select_one(".mw-parser-output > p")
    event_type = "Main Event" if intro_p and "Main Event" in intro_p.get_text() else None
    interactivity_tab = soup.find("article", {"data-title": "Event Interactivity"})
    progression_tab = soup.find("article", {"data-title": "Event Progression (Spoilers!)"})
    technical_tab = soup.find("article", {"data-title": "Technical Information"})
    interactivity_data = parse_interactivity(interactivity_tab)
    progression_data = parse_progression(progression_tab)
    technical_data = parse_technical_info(technical_tab)
    nav = {"previous_event": None, "next_event": None}
    prev_div = soup.find("div", class_="LArrow")
    if prev_div:
        prev_text = prev_div.get_text(strip=True).replace("Previous Event:", "").strip()
        nav["previous_event"] = prev_text if prev_text.lower() != "none" else None
    next_div = soup.find("div", class_="RArrow")
    if next_div and next_div.find("a"):
        nav["next_event"] = next_div.find("a").get_text(strip=True)
    return {
        "event_id": event_id, "event_title": event_title, "url": canonical_url,
        "event_type": event_type, "chapter": find_chapter(soup, event_title),
        "interactivity": interactivity_data, "progression": progression_data,
        "technical_information": technical_data, "navigation": nav
    }

if __name__ == "__main__":
    # Change this to the name of the file you are processing
    file_to_parse = "2.html" #<-- CHANGE THIS FILENAME
    html_content = ""
    try:
        with open(file_to_parse, 'r', encoding="utf-8") as f:
            html_content = f.read()
    except UnicodeDecodeError:
        print(f"Warning: Could not read '{file_to_parse}' as UTF-8. Falling back to 'latin-1' encoding.")
        with open(file_to_parse, 'r', encoding="latin-1") as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"Error: The file '{file_to_parse}' was not found.")
        exit()
    if html_content:
        event_json = transform_event_html_to_json(html_content)
        print(json.dumps(event_json, indent=2, ensure_ascii=False))