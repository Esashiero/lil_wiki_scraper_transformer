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
    # Find the header tag (h2, h3, etc.) that the start_node (a span) is inside
    header_tag = start_node.find_parent(stop_at)
    if not header_tag:
        return content
    for sibling in header_tag.find_next_siblings():
        if sibling.name in stop_at:
            break
        content.append(sibling)
    return content

def parse_interactivity(tab: Tag) -> dict:
    """Parses the 'Event Interactivity' tab with improved logic."""
    data = {
        "requirements": None,
        "to_get_this_event": None,
        "to_miss_this_event": None, # Added this field
        "choices": [],
        "effects": [],
    }
    if not tab: return data

    # --- Requirements ---
    req_header = tab.find("span", id="Requirements")
    if req_header:
        # The content can be in a <p>, <div>, or <ul> tag immediately following the <h3>
        next_content = req_header.find_parent('h3').find_next_sibling(['p', 'div', 'ul'])
        if next_content:
            data["requirements"] = next_content.get_text(" ", strip=True)

    # --- To get this event ---
    get_event_header = tab.find("span", id="To_get_this_event")
    if get_event_header:
        get_event_p = get_event_header.find_parent('h3').find_next_sibling('p')
        if get_event_p:
            data["to_get_this_event"] = get_event_p.get_text(" ", strip=True)

    # --- To miss this event (NEW) ---
    miss_event_header = tab.find("span", id="To_miss_this_event")
    if miss_event_header:
        miss_event_p = miss_event_header.find_parent('h3').find_next_sibling('p')
        if miss_event_p:
            data["to_miss_this_event"] = miss_event_p.get_text(" ", strip=True)

    # --- Choices (Overhauled) ---
    choices_header = tab.find("span", id="Choices")
    if choices_header:
        # Get all sibling elements between the "Choices" h2 and the next h2
        content_nodes = get_section_content(choices_header, stop_at=['h2'])
        
        context_text = None
        for node in content_nodes:
            if node.name == 'p':
                # This <p> tag provides context for the next choice <dl>
                context_text = node.get_text(" ", strip=True)
            elif node.name == 'dl':
                # This is a choice block
                options = []
                effect = None
                
                # Extract all dt (options) and the final dd (effect)
                dt_tags = node.find_all('dt')
                dd_tag = node.find('dd')

                if dt_tags:
                    options = [dt.get_text(strip=True) for dt in dt_tags]
                if dd_tag:
                    effect = dd_tag.get_text(" ", strip=True)
                
                data["choices"].append({
                    "context": context_text,
                    "options": options,
                    "effect": effect
                })
                context_text = None # Reset context after it's been used

    # --- Effects ---
    effects_header = tab.find("span", id="Effects")
    if effects_header:
        # Effects can be in a <ul> or be described in a <p> before a <ul>
        content = get_section_content(effects_header)
        for element in content:
             if element.name == 'ul':
                 data["effects"].extend([li.get_text(" ", strip=True) for li in element.find_all('li') if li.get_text(strip=True)])

    return data


def parse_progression(tab: Tag) -> dict:
    """Parses the 'Event Progression (Spoilers!)' tab."""
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

    trivia_header = tab.find("span", id="Trivia")
    if trivia_header:
        content = get_section_content(trivia_header)
        dl_node = next((node for node in content if node.name == 'dl'), None)
        ul_node = next((node for node in content if node.name == 'ul'), None)

        if dl_node:
            dt = dl_node.find("dt")
            dd = dl_node.find("dd")
            if dt and dd:
                data["trivia"].append(f"{dt.get_text(strip=True)}: {dd.get_text(strip=True)}")
        elif ul_node:
            for li in ul_node.find_all('li'):
                text = li.get_text(" ", strip=True)
                if text: data["trivia"].append(text)

    return data

def parse_technical_info(tab: Tag) -> dict:
    """Parses the 'Technical Information' tab."""
    data = {"event_references": {}, "backgrounds": [], "music_tracks": [], "changelog": []}
    if not tab: return data

    ref_header = tab.find("span", id="Event_References")
    if ref_header:
        content = get_section_content(ref_header)
        li_tags = [node for node in content if isinstance(node, Tag) and node.name == 'li']
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
    """
    Finds the chapter or version number.
    Handles both 'v0.X.Y' format (Main Events) and 'Chapter X' format (Character Events).
    """
    navbox = soup.find("div", class_="navbox")
    if not navbox: return None
    event_tag = navbox.find(lambda tag: tag.name in ('a', 'b') and tag.get_text(strip=True) == event_title)
    if not event_tag: return None
    row = event_tag.find_parent("tr")
    if not row: return None
    header = row.find("th")
    if not header: return None
    base_text = header.get_text(strip=True)
    if 'Chapter' in base_text:
        return base_text
    list_cell = row.find("td")
    if not list_cell: return base_text
    all_events_in_row = list_cell.find_all("a")
    try:
        event_index = [a.get_text(strip=True) for a in all_events_in_row].index(event_title)
        event_position = event_index + 1
        version_parts = base_text.lstrip('v').split('.')
        if len(version_parts) >= 2:
            return f"v{version_parts[0]}.{version_parts[1]}.{event_position}"
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

    # --- Improved Event Type and Character Parsing ---
    event_type = None
    primary_character = None
    intro_p = soup.select_one(".mw-parser-output > p")
    if intro_p:
        # Find event type from a styled span, e.g., <span class="InviteEvent">
        event_type_span = intro_p.find("span", class_=re.compile(r'.*Event$'))
        if event_type_span and event_type_span.find('a'):
            event_type = event_type_span.find('a').get_text(strip=True)
        elif "Main Event" in intro_p.get_text():
            event_type = "Main Event"
        
        # Find the primary character this event is for
        # It's usually a link with a title attribute starting with "Characters/"
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
        "event_type": event_type,
        "primary_character": primary_character, # Added for categorization
        "chapter": find_chapter(soup, event_title),
        "interactivity": interactivity_data,
        "progression": progression_data,
        "technical_information": technical_data,
        "navigation": nav
    }