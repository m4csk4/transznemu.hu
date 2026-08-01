import requests
import json

url_women = 'https://file.nytud.hu/osszesnoi.txt'
url_men = 'https://file.nytud.hu/osszesffi.txt'

# The three surname collections, in the order they are shown on the site. Only
# the first two carry bearer counts; MACSE is a bare attestation list. The files
# are checked in rather than fetched — 'source' records where each came from.
FAMILY_SOURCES = [
    {
        'id': 'enciklopedia',
        'name': 'Családnevek enciklopédiája',
        'file': './csaladnevek_enciklopediaja.txt',
        'source': 'https://hornyak.hu/csaladfa/Csaladnevek_enciklopediaja.pdf',
        'counted': True,
    },
    {
        'id': 'forebears',
        'name': 'Forebears',
        'file': './forebears.txt',
        'source': 'https://forebears.io/hungary/surnames',
        'counted': True,
    },
    {
        'id': 'macse',
        'name': 'MACSE családnév-adatbázis',
        'file': './macse_csaladnevek.txt',
        # Scraped by scrape_macse.py, which documents the paging it walks.
        'source': 'https://macse.hu/familiae/CsaladNevekLista.php',
        'counted': False,
    },
]


def fetch_names(url):
    response = requests.get(url)
    if response.status_code == 200:
        lines = response.text.splitlines()
        return {'updated': lines[0].split(' -- ')[1], 'names': lines[1:]}
    else:
        print(f"Failed to fetch names from {url}. Status code: {response.status_code}")
        return []


def get_names(source):
    with open(source['file'], 'r', encoding='utf-8') as f:
        if source['counted']:
            # "<name> <bearers>" — the name itself is always a single token here.
            return [{'name': line.strip().split()[0].title(),
                     'number': int(line.strip().split()[1])}
                    for line in f if line.strip()]

        # MACSE names have no count, and plenty of them contain spaces
        # ("Almási Balogh", "Aba nemzetségből"), so the whole line is the name —
        # splitting on whitespace here would truncate ~1400 of them. A comma
        # separates spelling variants of one name, which are listed separately.
        names = []
        for line in f:
            for variant in line.strip().split(','):
                variant = variant.strip()
                if variant:
                    names.append({'name': variant.title(), 'number': None})
        return names


data = {
    'women': fetch_names(url_women),
    'men': fetch_names(url_men),
    'family': [{'id': s['id'], 'name': s['name'], 'names': get_names(s)}
               for s in FAMILY_SOURCES],
}

with open('../data/names.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)
