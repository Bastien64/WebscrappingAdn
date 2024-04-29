from flask import Flask, render_template, request, send_file
import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

app = Flask(__name__)

def get_site_name(url):
    match = re.search(r'www\.(.*?)\.(com|fr)', url)
    return match.group(1) if match else "Nom du site non trouvé"

# GESTION DES SITES A EXCLURE

def read_excluded_sites(file_path):
    with open(file_path, "r") as file:
        return {line.strip() for line in file}

def add_site_to_exclude_list(site_url):
    excluded_sites = read_excluded_sites("siteaexclure.txt")
    if site_url not in excluded_sites:
        with open("siteaexclure.txt", "a") as file:
            file.write(site_url + "\n")
    else:
        print("Le site est déjà dans la liste d'exclusion.")

@app.route('/download_blacklist', methods=['GET'])
def download_blacklist():
    try:
        # Lire les sites blacklistés depuis le fichier
        excluded_sites = read_excluded_sites("siteaexclure.txt")
        
        # Créer un fichier temporaire pour stocker les sites blacklistés
        temp_file_path = "siteaexclure.txt"
        with open(temp_file_path, "w") as temp_file:
            for site in excluded_sites:
                temp_file.write(site + "\n")
        
        # Envoyer le fichier temporaire en tant que téléchargement
        return send_file(temp_file_path, as_attachment=True)
    
    except Exception as e:
        # En cas d'erreur, retourner un message d'erreur approprié
        return str(e), 500      

@app.route('/add_sites', methods=['POST'])
def add_site():
    if request.method == 'POST':
        site_url = request.json.get('site_url')
        add_site_to_exclude_list(site_url)
        return "Site ajouté avec succès !", 200
    else:
        return "Erreur : Méthode non autorisée", 405

# SCRAPING DES ADRESSES EMAILS

def extract_emails_from_soup(soup):
    email_pattern = re.compile(r'[\w\.-]+@[a-zA-Z0-9\.-]+\.[a-zA-Z]+')
    email_list = []
    
    # Recherche dans les balises <a> (liens hypertextes)
    for tag in soup.find_all('a', href=True):
        matches = email_pattern.findall(tag.get('href'))
        email_list.extend(matches)
    
    # Recherche dans les balises <p> (paragraphes)
    for tag in soup.find_all('p'):
        matches = email_pattern.findall(tag.text)
        email_list.extend(matches)
    
    # Recherche dans le texte brut de la soupe
    for tag in soup.find_all(text=True):
        matches = email_pattern.findall(tag)
        email_list.extend(matches)
        
    # Nettoyage des adresses e-mail dupliquées
    email_list = list(set(email_list))
    
    return email_list

def scrape_emails(urls, lieu):
    unique_results = {}
    excluded_sites = read_excluded_sites("siteaexclure.txt")
    for url in urls:
        try:
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            if base_url in excluded_sites:
                continue
            legal_url = f"{base_url}/mentions-legales"
            main_url = base_url
            response = requests.get(legal_url, verify=False, timeout=2)
            soup = BeautifulSoup(response.content, 'html.parser')
            emails = extract_emails_from_soup(soup)
            unique_emails = list(set(emails) - {'.png', '.webp'})
            site_name = get_site_name(url)
            unique_results[site_name] = {
                "site_name": site_name,
                "site_url": legal_url,
                "email": ", ".join(unique_emails) if unique_emails else "Aucune adresse e-mail trouvée"
            }
            response_main = requests.get(main_url, verify=False, timeout=2)
            soup_main = BeautifulSoup(response_main.content, 'html.parser')
            emails_main = extract_emails_from_soup(soup_main)
            unique_emails_main = list(set(emails_main) - {'.png', '.webp'})
            if unique_emails_main:
                if site_name not in unique_results:
                    unique_results[site_name] = {
                        "site_name": site_name,
                        "site_url": main_url,
                        "email": ", ".join(unique_emails_main)
                    }
                else:
                    unique_results[site_name]["email"] += f", {', '.join(unique_emails_main)}"
        except requests.exceptions.RequestException as e:
            print("Une erreur s'est produite lors de la connexion à", legal_url, ":", e)
    return list(unique_results.values())



def scrape_Qwant_search_results(query, lieu):
    search_results = []
    
    # Configuration du service Chrome pour se connecter au conteneur Docker
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Démarrer le navigateur Chrome avec le service
    driver = webdriver.Remote(
        command_executor="http://162.19.67.246:4444/wd/hub",
        options=chrome_options
    )

    # Naviguer vers la page Qwant avec la requête de recherche et le lieu
    driver.get(f"https://www.qwant.com/?l=fr&q={query} {lieu}") 
    
    try:
        # Cliquer sur le bouton "Plus de résultats" plusieurs fois pour charger plus de résultats
        for _ in range(4):
            button = driver.find_element(By.XPATH, "//button[contains(text(),'Plus de résultats')]")
            button.click()
            time.sleep(1)

        # Obtenir le contenu de la page après le chargement
        page_content = driver.page_source
        soup = BeautifulSoup(page_content, 'html.parser')
        
        # Extraire les liens des résultats de recherche
        search_result_links = soup.find_all('a', class_='external')
        search_results.extend(link['href'] for link in search_result_links[:10000])
    finally:
        # Arrêter le navigateur
        driver.quit()
    
    return search_results


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        query1 = request.form.get('query', '')
        query2 = request.form.get('query2', '')
        lieu = request.form.get('lieu', '')
        
        search_results1 = scrape_Qwant_search_results(query1, lieu)
        all_results1 = scrape_emails(search_results1, lieu)
        
        search_results2 = scrape_Qwant_search_results(query2, lieu)
        all_results2 = scrape_emails(search_results2, lieu)
        
        all_results1_set = {tuple(result.items()) for result in all_results1}
        all_results2_set = {tuple(result.items()) for result in all_results2}
        unique_results = all_results2_set.symmetric_difference(all_results1_set)
        
        all_results = {"unique_results": unique_results}
        
        print("Tous les résultats trouvés:", all_results)
        return render_template('index.html', results=all_results)
    else:
        return render_template('index.html', results={})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)
