from bs4 import BeautifulSoup, Tag, NavigableString
import json
import re

def get_section_content(start_node: Tag, stop_at: list = ['h2', 'h3']):
    """
    Collects all sibling nodes after a starting header node until a stopping tag is found.
    (FIXED to handle NavigableString nodes correctly).
    """
    content = []
    if not start_node or not hasattr(start_node, 'find_parent'):
        return content
    header_tag = start_node.find_parent(stop_at)
    if not header_tag:
        return content
    for sibling in header_tag.find_next_siblings():
        # A NavigableString doesn't have a .name, so we check hasattr first.
        if hasattr(sibling, 'name') and sibling.name in stop_at:
            break
        content.append(sibling)
    return content

def parse_interactivity(tab: Tag) -> dict:
    # This function is correct and requires no changes.
    data = {
        "requirements": None, "to_get_this_event": None, "to_miss_this_event": None,
        "choices": [], "effects": [],
    }
    if not tab: return data
    req_header = tab.find("span", id="Requirements")
    if req_header:
        next_content = req_header.find_parent('h3').find_next_sibling(['p', 'div', 'ul'])
        if next_content: data["requirements"] = next_content.get_text(" ", strip=True)
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
        context_text = None
        for node in content_nodes:
            if hasattr(node, 'name') and node.name == 'p': context_text = node.get_text(" ", strip=True)
            elif hasattr(node, 'name') and node.name == 'dl':
                options = [dt.get_text(strip=True) for dt in node.find_all('dt')]
                effect_tag = node.find('dd')
                effect = effect_tag.get_text(" ", strip=True) if effect_tag else None
                data["choices"].append({"context": context_text, "options": options, "effect": effect})
                context_text = None
    effects_header = tab.find("span", id="Effects")
    if effects_header:
        for element in get_section_content(effects_header):
            if hasattr(element, 'name') and element.name == 'ul':
                data["effects"].extend([li.get_text(" ", strip=True) for li in element.find_all('li') if li.get_text(strip=True)])
    return data

def parse_progression(tab: Tag) -> dict:
    """
    Parses the 'Event Progression (Spoilers!)' tab.
    Corrected to find and extract plain text trivia.
    """
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
    
    # --- FIXED TRIVIA PARSING LOGIC ---
    trivia_header = tab.find("span", id="Trivia")
    if trivia_header and trivia_header.parent:
        h2_tag = trivia_header.parent
        # Iterate through all siblings after the h2 tag
        for sibling in h2_tag.next_siblings:
            # Check if the sibling is a tag and is a new header, then stop
            if isinstance(sibling, Tag) and sibling.name in ['h2', 'h3']:
                break
            # Handle plain text (NavigableString)
            elif isinstance(sibling, NavigableString):
                text = sibling.strip()
                if text:
                    data["trivia"].append(text)
            # Handle list tags (ul or dl)
            elif isinstance(sibling, Tag) and sibling.name in ['ul', 'dl']:
                if sibling.name == 'ul':
                    data["trivia"].extend([li.get_text(" ", strip=True) for li in sibling.find_all('li')])
                elif sibling.name == 'dl':
                    dt = sibling.find("dt")
                    dd = sibling.find("dd")
                    if dt and dd: data["trivia"].append(f"{dt.get_text(strip=True)}: {dd.get_text(strip=True)}")
    # --- END OF FIXED LOGIC ---

    return data


def parse_technical_info(tab: Tag) -> dict:
    """Parses the 'Technical Information' tab. (FIXED to handle multiple list types)."""
    data = {"event_references": {}, "backgrounds": [], "music_tracks": [], "changelog": []}
    if not tab: return data

    # --- FIXED EVENT REFERENCES LOGIC ---
    ref_header = tab.find("span", id="Event_References")
    if ref_header and ref_header.parent:
        h2_tag = ref_header.parent
        # Iterate over all siblings after the h2 tag
        for sibling in h2_tag.next_siblings:
            # Stop if we hit a new major header
            if isinstance(sibling, Tag) and sibling.name in ['h2', 'h3']:
                break
            
            # Look for li tags either directly or within a ul
            if isinstance(sibling, Tag) and (sibling.name == 'ul' or sibling.name == 'li'):
                # Handle ul with li children
                if sibling.name == 'ul':
                    nodes_to_parse = sibling.find_all('li')
                else:
                    # Handle direct li tag
                    nodes_to_parse = [sibling]

                for node in nodes_to_parse:
                    text = node.get_text(strip=True)
                    parts = text.split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].strip().lower().replace(' ', '_').replace('(s)', 's')
                        value = parts[1].strip()
                        if key == "event_script_names":
                            data["event_references"][key] = [v.strip() for v in value.split(',')]
                        else:
                            data["event_references"][key] = value
    # --- END OF FIXED LOGIC ---

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
    # This function is correct and requires no changes.
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

def transform_event_html_to_json(html_content: str) -> dict:
    """Main function to transform HTML content to the structured JSON."""
    soup = BeautifulSoup(html_content, "html.parser")
    
    event_title_tag = soup.find("span", class_="mw-page-title-main")
    event_title = event_title_tag.get_text(strip=True) if event_title_tag else "Unknown Event"
    event_id = re.sub(r"\W+", "_", event_title).lower()
    
    url_tag = soup.find("meta", {"property": "og:url"})
    canonical_url = url_tag['content'] if url_tag else None

    event_type = None
    primary_character = None
    intro_p = soup.select_one(".mw-parser-output > p")
    if intro_p:
        intro_text = intro_p.get_text(" ", strip=True)
        event_type_span = intro_p.find("span", class_=re.compile(r'.*Event$'))
        if event_type_span and event_type_span.find('a'):
            event_type = event_type_span.find('a').get_text(strip=True)
        elif "Main Event" in intro_text:
            event_type = "Main Event"
        elif "is an Event for" in intro_text:
            event_type = "Event"
        char_link = intro_p.find("a", attrs={"title": re.compile(r'^Characters/')})
        if char_link:
            primary_character = char_link.get_text(strip=True)

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
        "event_type": event_type, "primary_character": primary_character,
        "chapter": find_chapter(soup, event_title), "interactivity": interactivity_data,
        "progression": progression_data, "technical_information": technical_data,
        "navigation": nav
    }
    