from flask import Flask, render_template
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

def get_site_name(url):
    # Utilisation d'une expression régulière pour extraire le nom du site
    match = re.search(r'www\.(.*?)\.(com|fr)', url)
    if match:
        return match.group(1)
    else:
        return "Nom du site non trouvé"

def scrape_emails(urls):
    all_results = []
    for url in urls:
        response = requests.get(url)
        print("HTTP Response for", url, ":", response.status_code)  # Ajout d'un message d'impression
        soup = BeautifulSoup(response.text, 'html.parser')
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', response.text)
        print("Emails trouvées pour", url, ":", emails)  # Ajout d'un message d'impression
        result = {
            "site_name": get_site_name(url),  # Remplacez "Nom du site" par le nom réel du site
            "site_url": url,
            "email": ", ".join(emails) if emails else "Aucune adresse e-mail trouvée"
        }
        all_results.append(result)
    return all_results

def scrape_google_search_results(query):
    search_results = []
    url = f"https://www.google.com/search?q={query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.55 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        search_results_divs = soup.find_all('div', class_='tF2Cxc')
        for div in search_results_divs:
            link = div.find('a')['href']
            search_results.append(link)
    return search_results

@app.route('/')
def index():
    # Liste d'URLs à scraper (remplacée par les résultats de recherche Google)
    query = "agence web bidart"
    search_results = scrape_google_search_results(query)
    all_results = scrape_emails(search_results)
    print("Tous les résultats trouvés:", all_results)
    return render_template('index.html', results=all_results)

if __name__ == '__main__':
    app.run(debug=True)
