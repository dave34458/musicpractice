import re
import json
import html
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

def _extract_store_data(page_text):
    soup = BeautifulSoup(page_text, 'html.parser')
    store_div = soup.select_one('.js-store')
    if not store_div:
        return None
    content = store_div.get('data-content', '')
    if not content:
        return None
    decoded = html.unescape(content)
    try:
        return json.loads(decoded)
    except json.JSONDecodeError:
        return None


def search_songs(query):
    results = []
    try:
        resp = requests.get(
            'https://www.ultimate-guitar.com/search.php',
            params={'search_type': 'title', 'value': query},
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException:
        return results

    store = _extract_store_data(resp.text)
    if not store:
        return results

    page_data = store.get('store', {}).get('page', {}).get('data', {})
    for item in page_data.get('results', []):
        tab_url = item.get('tab_url', '')
        access = item.get('tab_access_type', '')
        if not tab_url:
            continue
        if '/pro/' in tab_url or access not in ('public', ''):
            continue
        results.append({
            'title': item.get('song_name', ''),
            'artist': item.get('artist_name', ''),
            'rating': float(item.get('rating', 0)),
            'votes': int(item.get('votes', 0)),
            'type': item.get('type', ''),
            'key': item.get('tonality_name', '') or '',
            'url': tab_url,
        })
    return results[:20]


def fetch_chart(tab_url):
    try:
        resp = requests.get(tab_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException:
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')
    title = soup.select_one('h1')
    title = title.get_text(strip=True) if title else ''
    artist = soup.select_one('a[href*="/artist/"]')
    artist = artist.get_text(strip=True) if artist else ''

    raw_chart = ''
    store = _extract_store_data(resp.text)
    if store:
        page_data = store.get('store', {}).get('page', {}).get('data', {})
        tab = page_data.get('tab', {})
        title = tab.get('song_name', '')
        artist = tab.get('artist_name', '')
        tab_view = page_data.get('tab_view', {})
        wiki_tab = tab_view.get('wiki_tab', {})
        if isinstance(wiki_tab, dict):
            raw_chart = wiki_tab.get('content', '')
        elif isinstance(wiki_tab, str):
            raw_chart = wiki_tab

    if not raw_chart:
        pre = soup.select_one('pre')
        if pre:
            raw_chart = pre.get_text()

    if not raw_chart:
        for script in soup.select('script'):
            if 'tab_view' in script.text:
                m = re.search(r'"wiki_tab"\s*:\s*"(.+?)"\s*[,}]', script.text, re.DOTALL)
                if m:
                    raw_chart = m.group(1)
                    raw_chart = raw_chart.replace('\\n', '\n').replace('\\r', '').replace('\\t', ' ')
                    raw_chart = re.sub(r'\\u[0-9a-fA-F]{4}', '', raw_chart)
                break

    return {
        'title': title,
        'artist': artist,
        'raw_chart': raw_chart.strip(),
        'source_url': tab_url,
    }
