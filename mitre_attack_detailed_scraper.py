

import requests
from bs4 import BeautifulSoup
import json
import re

def scrape_technique_details(url):
    """
    Scrapes detailed information for a single technique, including sub-techniques and procedure examples.
    """
    print(f"Scraping details from: {url}")
    details = {
        "name": "N/A",
        "description": "N/A",
        "metadata": {},
        "sub_techniques": [],
        "procedure_examples": []
    }
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        soup = BeautifulSoup(response.text, 'html.parser')

        # --- Basic Info ---
        h1 = soup.find('h1')
        if h1:
            details['name'] = h1.text.strip()

        desc_div = soup.find('div', class_='description-body')
        if desc_div:
            details['description'] = desc_div.get_text(separator="\n").strip()

        # --- Metadata (from the side card) ---
        card = soup.find('div', class_='card')
        if card:
            card_body = card.find('div', class_='card-body')
            if card_body:
                for row in card_body.find_all('div', class_='row'):
                    span = row.find('span', class_='h5')
                    if span:
                        key = span.text.split(':')[0].strip().lower().replace(' ', '_')
                        links = row.find_all('a')
                        if links:
                            value = [a.text.strip() for a in links]
                        else:
                            value_node = span.next_sibling
                            value = value_node.strip() if value_node and isinstance(value_node, str) else ''
                        details['metadata'][key] = value

        # --- Sub-techniques (for Techniques) ---
        parent_id = details.get('metadata', {}).get('id', 'TXXXX')
        sub_h2 = soup.find('h2', id='sub-techniques')
        if sub_h2:
            sub_table = sub_h2.find_next('table')
            if sub_table and sub_table.find('tbody'):
                for row in sub_table.find('tbody').find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        id_cell, name_cell = cols[0], cols[1]
                        id_link = id_cell.find('a')
                        name_link = name_cell.find('a')
                        if id_link and name_link:
                            sub_id_part = id_link.text.strip()
                            full_sub_id = f"{parent_id}{sub_id_part}"
                            sub_name = name_link.text.strip()
                            details['sub_techniques'].append({'id': full_sub_id, 'name': sub_name})

        # --- Procedure Examples ---
        proc_h2 = soup.find('h2', id='procedure-examples')
        if proc_h2:
            proc_table = proc_h2.find_next('table')
            if proc_table and proc_table.find('tbody'):
                for row in proc_table.find('tbody').find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) >= 3:
                        id_link, name_link, desc_cell = cols[0].find('a'), cols[1].find('a'), cols[2]
                        if id_link and name_link and desc_cell:
                            proc_id = id_link.text.strip()
                            proc_name = name_link.text.strip()
                            proc_desc = desc_cell.get_text(separator="\n").strip()
                            details['procedure_examples'].append({'id': proc_id, 'name': proc_name, 'description': proc_desc})

    except Exception as e:
        print(f"An error occurred while scraping {url}: {e}")

    return details

if __name__ == '__main__':
    technique_url = "https://attack.mitre.org/techniques/T1548/"
    technique_details = scrape_technique_details(technique_url)
    print(json.dumps(technique_details, indent=4))

