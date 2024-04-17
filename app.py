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



def scrape_emails(urls, lieu):
    unique_results = {}
    for url in urls:
        try:
            # Construire l'URL des mentions légales
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            legal_url = f"{base_url}/mentions-legales"
            response = requests.get(legal_url, verify=False, timeout=2)
            # Recherche des adresses e-mail avec Beautiful Soup
            soup = BeautifulSoup(response.content, 'html.parser')
            emails = extract_emails_from_soup(soup)
            unique_emails = list(set(emails))
            # Filtrer les extensions d'images
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
    # Utiliser une expression régulière pour rechercher les adresses e-mail
    email_pattern = re.compile(r'[\w\.-]+@[a-zA-Z0-9\.-]+\.[a-zA-Z]+')
    email_list = []
    # Rechercher les balises contenant du texte
    for tag in soup.find_all(text=True):
        # Rechercher les adresses e-mail dans le texte
        matches = email_pattern.findall(tag)
        # Ajouter les adresses trouvées à la liste
        email_list.extend(matches)
        # Rechercher également "[ at]" et "(at)" dans le texte et les remplacer par "@"
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
        time.sleep(5)
        button.click()
        time.sleep(5)
        button.click()
        time.sleep(5)
        button.click()
        time.sleep(35)  

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
        query = request.form['query']
        lieu = request.form['lieu']
        search_results = scrape_Qwant_search_results(query, lieu)
        all_results = scrape_emails(search_results, lieu)
        print("Tous les résultats trouvés:", all_results)
        return render_template('index.html', results=all_results)
    else:
        return render_template('index.html', results=[])


@app.route('/download_csv', methods=['POST'])
def download_csv():
    if request.method == 'POST':
        csv_data = request.form['csv_data']
        results = parse_csv_data(csv_data)
        csv_content = generate_csv(results)
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-disposition":
                     "attachment; filename=results.csv"})

def parse_csv_data(csv_data):
    results = []
    reader = csv.DictReader(csv_data.splitlines())
    for row in reader:
        results.append(row)
    return results


def generate_csv(results):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Nom du site", "Adresse web", "Adresse Email"])
    for result in results:
        writer.writerow([result.get("site_name", ""), result.get("site_url", ""), result.get("email", "")])
    csv_data = output.getvalue()
    output.close()
    return csv_data


if __name__ == '__main__':
    app.run(debug=True)