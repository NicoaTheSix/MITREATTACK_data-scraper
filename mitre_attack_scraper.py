import requests
from bs4 import BeautifulSoup
import os
import json
import re

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

def scrape_all(base_url):
    """
    Scrapes all categories from the MITRE ATT&CK website.
    """
    all_data = {}
    
    # Scrape simple tables
    categories = {
        "groups": ("Associated Groups", None),
        "software": ("Software", None),
        "campaigns": ("Campaigns", None),
        "assets": ("Assets", "platforms"),
        "datasources": ("Data Sources", "platforms")
    }
    
    for category, (name, third_col) in categories.items():
        url = f"{base_url}/{category}/"
        all_data[category] = scrape_simple_table(url, name, third_col)
        
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