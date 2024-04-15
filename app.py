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


app = Flask(__name__)

def get_site_name(url):
    match = re.search(r'www\.(.*?)\.(com|fr)', url)
    if match:
        return match.group(1)
    else:
        return "Nom du site non trouvé"

def contains_location(url, lieu):
    response = requests.get(url, verify=False, timeout=2)
    if response.status_code == 200:
        return lieu.lower() in response.text.lower()
    return False

def scrape_emails(urls, lieu):
    unique_results = {}
    for url in urls:
        try:
            if not contains_location(url, lieu):
                continue

            response = requests.get(url, verify=False, timeout=2)
            soup = BeautifulSoup(response.text, 'html.parser')
            # Recherche des adresses e-mail
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+(?:\[at\]|@)[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', response.text)
            unique_emails = list(set(emails))
            # Filtrer les extensions d'images
            filtered_emails = [email for email in unique_emails if not (email.endswith('.png') or email.endswith('.webp'))]
            site_name = get_site_name(url)
            if site_name not in unique_results:
                unique_results[site_name] = {
                    "site_name": site_name,
                    "site_url": url,
                    "email": ", ".join(filtered_emails) if filtered_emails else "Aucune adresse e-mail trouvée"
                }
        except requests.exceptions.RequestException as e:
            print("Une erreur s'est produite lors de la connexion à", url, ":", e)

    return list(unique_results.values())



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