from flask import Flask, render_template, request, Response
import csv
import io
import requests
from bs4 import BeautifulSoup
import re
import time  # Ajoutez 
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse, urlunparse

app = Flask(__name__)

def get_site_name(url):
    match = re.search(r'www\.(.*?)\.(com|fr)', url)
    if match:
        return match.group(1)
    else:
        return "Nom du site non trouvé"
    
#GESTION DES SITES A EXCLURE

def read_excluded_sites(file_path):
    with open(file_path, "r") as file:
        return [line.strip() for line in file]

def add_site_to_exclude_list(site_url):
    excluded_sites = read_excluded_sites("siteaexclure.txt")
    if site_url not in excluded_sites:
        with open("siteaexclure.txt", "a") as file:
            file.write(site_url + "\n")
    else:
        print("Le site est déjà dans la liste d'exclusion.")

@app.route('/add_sites', methods=['POST'])
def add_site():
    if request.method == 'POST':
        site_url = request.json.get('site_url')
        add_site_to_exclude_list(site_url)
        return "Site ajouté avec succès !", 200
    else:
        return "Erreur : Méthode non autorisée", 405

    



#SCRAPING DES ADRESSES EMAILS

excluded_sites = read_excluded_sites("siteaexclure.txt")

def scrape_emails(urls, lieu):
    unique_results = {}
    for url in urls:
        try:
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            # Exclure les sites présents dans siteaexclure.txt
            if base_url in excluded_sites:
                continue
            
            legal_url = f"{base_url}/mentions-legales"
            response = requests.get(legal_url, verify=False, timeout=2)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            emails = extract_emails_from_soup(soup)
            unique_emails = list(set(emails))
            
            filtered_emails = [email for email in unique_emails if not (email.endswith('.png') or email.endswith('.webp'))]
            site_name = get_site_name(url)
            if site_name not in unique_results:
                unique_results[site_name] = {
                    "site_name": site_name,
                    "site_url": legal_url,
                    "email": ", ".join(filtered_emails) if filtered_emails else "Aucune adresse e-mail trouvée"
                }
        except requests.exceptions.RequestException as e:
            print("Une erreur s'est produite lors de la connexion à", legal_url, ":", e)

    return list(unique_results.values())


def extract_emails_from_soup(soup):
    
    email_pattern = re.compile(r'[\w\.-]+@[a-zA-Z0-9\.-]+\.[a-zA-Z]+')
    email_list = []
    
    for tag in soup.find_all(text=True):
      
        matches = email_pattern.findall(tag)
       
        email_list.extend(matches)
        
        matches = re.findall(r'[\w\.-]+ ?\[(?:\s)?at(?:\s)?\] ?[\w\.-]+|[\w\.-]+ ?\((?:\s)?at(?:\s)?\) ?[\w\.-]+', tag)
        for match in matches:
            match = match.replace('[ at]', '@').replace('(at)', '@')
            email_list.append(match)
    return email_list


def scrape_Qwant_search_results(query, lieu):
    search_results = []
    driver = webdriver.Chrome()  

    driver.get(f"https://www.qwant.com/?l=fr&q={query} {lieu}") 
    try:

        button = driver.find_element(By.XPATH, "//button[contains(text(),'Plus de résultats')]")

        button.click()
        time.sleep(1)
        button.click()
        time.sleep(1)
        button.click()
        time.sleep(1)
        button.click()
        time.sleep(1)

        page_content = driver.page_source
        soup = BeautifulSoup(page_content, 'html.parser')
        search_result_links = soup.find_all('a', class_='external')
        for link in search_result_links[:10000]:  
            url = link['href']  
            search_results.append(url)

    finally:
        driver.quit()
    return search_results


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        query1 = request.form['query']
        query2 = request.form['query2']  # Récupérer la deuxième requête
        lieu = request.form['lieu']
        
        # Effectuer la première recherche
        search_results1 = scrape_Qwant_search_results(query1, lieu)
        all_results1 = scrape_emails(search_results1, lieu)
        
        # Effectuer la deuxième recherche
        search_results2 = scrape_Qwant_search_results(query2, lieu)
        all_results2 = scrape_emails(search_results2, lieu)
        
        # Convertir les listes en ensembles pour supprimer les doublons
        all_results1_set = set(tuple(result.items()) for result in all_results1)
        all_results2_set = set(tuple(result.items()) for result in all_results2)
        print("Résultats de la première recherche:", all_results1_set)
        print("Résultats de la deuxième recherche:", all_results2_set)
        # Comparer les résultats et supprimer les doublons
        unique_results = all_results2_set.symmetric_difference(all_results1_set)
        
        all_results = {
            "unique_results": unique_results
        }
        
        print("Tous les résultats trouvés:", all_results)
        return render_template('index.html', results=all_results)
    else:
        return render_template('index.html', results={})

if __name__ == '__main__':
    app.run(debug=True)