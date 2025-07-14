import requests
from bs4 import BeautifulSoup
import os
import json
import re

# ---------------------------------------------------------------------------
# Helper functions for scraping additional details from ATT&CK object pages
# ---------------------------------------------------------------------------

def _get_soup(url):
    """Fetches a URL and returns a BeautifulSoup object."""
    try:
        r = requests.get(url)
        r.raise_for_status()
        return BeautifulSoup(r.text, 'html.parser')
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return BeautifulSoup('', 'html.parser')


def _parse_card_metadata(soup):
    """Parses metadata from the side card."""
    metadata = {}
    card = soup.find('div', class_='card-body')
    if not card:
        return metadata
    for div in card.find_all('div', class_='card-data'):
        title = div.find('span', class_='h5') or div.find('span', class_='h5 card-title')
        if title:
            key = title.text.replace(':', '').strip().lower().replace(' ', '_')
            text = div.get_text(separator=' ', strip=True)
            value = text.split(':', 1)[1].strip() if ':' in text else ''
            metadata[key] = value
    return metadata


def _parse_references(soup):
    """Extracts reference list items."""
    refs = []
    ref_h2 = soup.find('h2', id='references')
    if ref_h2:
        ref_div = ref_h2.find_next('div', class_='row')
        if ref_div:
            for li in ref_div.find_all('li'):
                refs.append(li.get_text(separator=' ', strip=True))
    return refs


def _parse_table_section(soup, section_id):
    """Returns a list of dictionaries for rows in the table following the h2."""
    results = []
    h2 = soup.find('h2', id=section_id)
    if not h2:
        return results
    table = h2.find_next('table')
    if not table or not table.find('tbody'):
        return results
    headers = [th.text.strip().lower().replace(' ', '_') for th in table.find_all('th')]
    for row in table.find('tbody').find_all('tr'):
        cols = [td.get_text(separator=' ', strip=True) for td in row.find_all('td')]
        if len(cols) == len(headers) + 1:
            cols[1] = cols[1] + cols[2]
            cols.pop(2)
        entry = {k: cols[i] if i < len(cols) else '' for i, k in enumerate(headers)}
        results.append(entry)
    return results

def get_attack_version(url):
    """
    Tries to get the ATT&CK version from the main page.
    """
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        # Find the version string. This is a bit of a guess, and might need adjustment.
        # Looking for a pattern like "ATT&CK v17.1"
        version_element = soup.find(string=re.compile(r"ATT&CK v\d+\.\d+"))
        if version_element:
            match = re.search(r"v(\d+\.\d+)", version_element)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"Could not determine ATT&CK version automatically: {e}")
    return "unknown"


def id_filter(tr_content):
    a_tag = tr_content.find('a')
    if a_tag:
        return a_tag.text.replace(' ', '')
    return None

def name_filter(tr_content):
    a_tags = tr_content.find_all('a')
    if len(a_tags) > 1:
        return a_tags[1].text.strip()
    return None

def description_filter(tr_content):
    p_tag = tr_content.find('p')
    if p_tag:
        return ''.join(p_tag.stripped_strings).strip()
    # Fallback for pages where description is not in a <p> tag
    td_tags = tr_content.find_all('td')
    if len(td_tags) > 2:
        return ''.join(td_tags[2].stripped_strings).strip()
    return ""


def thirdColumn_filter(tr_content):
    tds = tr_content.find_all('td')
    if len(tds) > 2:
        text = tds[2].text.strip().replace(' ', '')
        if "\n" in text:
            return [j for j in text.split("\n") if j]
        else:
            return [j for j in text.split(",") if j]
    return []

def scrape_simple_table(url, category_name, third_column_name=None):
    """
    Scrapes a simple table with ID, Name, and Description.
    """
    print(f"Scraping {category_name} from {url}")
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    data = {}
    table = soup.find("table")
    if not table:
        return data
        
    for row in table.find("tbody").find_all("tr"):
        item_id = id_filter(row)
        if not item_id:
            continue
        
        item_name = name_filter(row)
        item_description = description_filter(row)
        
        entry = {
            "ID": item_id,
            "name": item_name,
            "description": item_description
        }
        
        if third_column_name:
            entry[third_column_name] = thirdColumn_filter(row)
            
        data[item_id] = entry
        
    return data


def scrape_table_with_details(url, category_name, third_column_name=None, detail_fn=None, base_url="https://attack.mitre.org"):
    """Scrapes a table and optionally augments each entry with page details."""
    data = scrape_simple_table(url, category_name, third_column_name)
    if not detail_fn:
        return data
    for item_id, entry in data.items():
        link = f"{base_url}/{category_name.lower()}/{item_id}/"
        detail = detail_fn(link)
        entry.update(detail)
    return data

def scrape_techniques(url):
    print(f"Scraping techniques from {url}")
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    techniques = {}
    
    table = soup.find("table")
    if not table:
        return techniques

    last_technique_id = None
    for row in table.find("tbody").find_all("tr"):
        if 'technique' in row.get('class', []):
            technique_id = id_filter(row)
            if not technique_id:
                continue
            
            name = name_filter(row)
            description = ''.join(row.find_all('td')[2].stripped_strings).strip()
            
            techniques[technique_id] = {
                "ID": technique_id,
                "name": name,
                "description": description,
                "subtechniques": {}
            }
            last_technique_id = technique_id
        elif 'sub' in row.get('class', []) and last_technique_id:
            sub_technique_id_raw = row.find('a').text.replace(' ', '') if row.find('a') else None
            if not sub_technique_id_raw:
                continue

            # The sub-technique ID is usually in the format .001, we need the full ID
            sub_technique_id = f"{last_technique_id}{sub_technique_id_raw}"

            name = row.find_all('a')[1].text.strip()
            description = ''.join(row.find_all('td')[3].stripped_strings).strip()

            if last_technique_id in techniques:
                 techniques[last_technique_id]["subtechniques"][sub_technique_id] = {
                    "ID": sub_technique_id,
                    "name": name,
                    "description": description
                }

    return techniques


# ---------------------------------------------------------------------------
# Detailed scrapers for various ATT&CK object types
# ---------------------------------------------------------------------------

def scrape_mitigation_details(url):
    soup = _get_soup(url)
    details = {
        "metadata": _parse_card_metadata(soup),
        "techniques": _parse_table_section(soup, "techniques"),
        "references": _parse_references(soup)
    }
    return details


def scrape_datasource_details(url):
    soup = _get_soup(url)
    details = {
        "metadata": _parse_card_metadata(soup),
        "data_components": _parse_table_section(soup, "datacomponents"),
        "references": _parse_references(soup)
    }
    return details


def scrape_asset_details(url):
    soup = _get_soup(url)
    details = {
        "metadata": _parse_card_metadata(soup),
        "techniques": _parse_table_section(soup, "techniques")
    }
    return details


def scrape_group_details(url):
    soup = _get_soup(url)
    details = {
        "metadata": _parse_card_metadata(soup),
        "techniques": _parse_table_section(soup, "techniques"),
        "software": _parse_table_section(soup, "software"),
        "references": _parse_references(soup)
    }
    return details


def scrape_software_details(url):
    soup = _get_soup(url)
    details = {
        "metadata": _parse_card_metadata(soup),
        "techniques": _parse_table_section(soup, "techniques"),
        "groups": _parse_table_section(soup, "groups"),
        "references": _parse_references(soup)
    }
    return details


def scrape_campaign_details(url):
    soup = _get_soup(url)
    details = {
        "metadata": _parse_card_metadata(soup),
        "groups": _parse_table_section(soup, "groups"),
        "techniques": _parse_table_section(soup, "techniques"),
        "software": _parse_table_section(soup, "software"),
        "references": _parse_references(soup)
    }
    return details

def scrape_all(base_url):
    """
    Scrapes all categories from the MITRE ATT&CK website.
    """
    all_data = {}
    
    # Scrape simple tables with details
    categories = {
        "groups": ("Associated Groups", None, scrape_group_details),
        "software": ("Software", None, scrape_software_details),
        "campaigns": ("Campaigns", None, scrape_campaign_details),
        "assets": ("Assets", "platforms", scrape_asset_details),
        "datasources": ("Data Sources", "platforms", scrape_datasource_details),
        "mitigations": ("Mitigations", None, scrape_mitigation_details)
    }
    
    for category, (name, third_col, detail_fn) in categories.items():
        url = f"{base_url}/{category}/"
        all_data[category] = scrape_table_with_details(url, category, third_col, detail_fn, base_url)
        
    # Scrape tactics (has sub-pages)
    all_data["tactics"] = {}
    for domain in ["enterprise", "mobile", "ics"]:
        url = f"{base_url}/tactics/{domain}/"
        all_data["tactics"][domain] = scrape_simple_table(url, f"Tactics ({domain})")

    # Scrape techniques (has sub-techniques and sub-pages)
    all_data["techniques"] = {}
    for domain in ["enterprise", "mobile", "ics"]:
        url = f"{base_url}/techniques/{domain}/"
        all_data["techniques"][domain] = scrape_techniques(url)
        
    return all_data

if __name__ == "__main__":
    BASE_URL = "https://attack.mitre.org"
    
    print("Starting MITRE ATT&CK scraper...")
    
    version = get_attack_version(BASE_URL)
    print(f"Detected ATT&CK version: {version}")
    
    mitre_data = scrape_all(BASE_URL)
    
    output_filename = f"mitre_attack_data_v{version}.json"
    output_path = os.path.join(os.getcwd(), "data", output_filename)
    
    print(f"Scraping finished. Saving data to {output_path}")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mitre_data, f, indent=4, ensure_ascii=False)
        
    print("Done.")