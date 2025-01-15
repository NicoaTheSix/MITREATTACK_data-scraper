from bs4 import BeautifulSoup
import requests
import os
import json
"""
This python file scrap the non-detailed infomation of all softwares in MITRE ATT\&CK.
There are four types of info in each software:id,name,associated software,description. 
The result of this file will be saved in [current folder]/data/softwares.json
"""
url_main_page_MIITREATTACK=f'https://attack.mitre.org'
def software_scraper():
    dict_softwares={}
    def description_filter(tr_content):
        p_tag = tr_content.find('p')
        #print(p_tag)
        full_text = ''.join(p_tag.stripped_strings).strip()
        return full_text
    def id_filter(tr_content):
        return tr_content.find('a').text.replace(' ','')
    def name_filter(tr_content):
        return tr_content.findAll('a')[1].text.strip()
    def associatedsoftware_filter(tr_content):
        return tr_content.findAll('td')[2].text.strip()
    def summarize(tr_content):
        id=id_filter(tr_content)
        name=name_filter(tr_content)
        description=description_filter(tr_content)
        associatedsoftware=associatedsoftware_filter(tr_content)
        dict_software={
            "ID":id,
            "name":name,
            "description":description,
            "Associated Software":associatedsoftware
        }
        return dict_software
    url=url_main_page_MIITREATTACK+"software/"
    response=requests.get(url)
    soup=BeautifulSoup(response.text,'html.parser')
    content=soup.find_all("tr")
    #print(content)
    print("Total:",len(content))
    for i in range(1,len(content)):
        #print(content[i].findAll("td"))
        #print(content[i])
        #print(id_filter(content[i]))
        #print(name_filter(content[i]))
        #print(description_filter(content[i]))
        #print(summarize(content[i]))
        dict_softwares[id_filter(content[i])]=summarize(content[i])
    return dict_softwares

with open(os.path.join(os.getcwd(),"data","softwares.json"),"w",encoding='utf-8')as file:
    json.dump(software_scraper(),file,indent=4)