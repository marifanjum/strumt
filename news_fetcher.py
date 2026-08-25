import re
import html
import requests
import urllib3
from bs4 import BeautifulSoup
import streamlit as st

# Suppress unverified SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_news(wp_base_url: str, limit: int = 5) -> list:
    """
    Fetches recent news articles and featured media from the WordPress REST API.
    Cached for 5 minutes to prevent redundant network latency on UI reruns.
    """
    if not wp_base_url or not wp_base_url.strip():
        return []

    base_url = wp_base_url.replace("/xmlrpc.php", "").strip().rstrip('/')
    if not base_url.startswith("http"):
        base_url = "https://" + base_url

    api_url = f"{base_url}/wp-json/wp/v2/posts?_embed&per_page={limit}"
    articles = []

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        response = requests.get(api_url, headers=headers, timeout=15, verify=False)

        if response.status_code == 200:
            posts = response.json()
            for post in posts:
                # 1. Clean Title
                raw_title = post.get('title', {}).get('rendered', '')
                title = html.unescape(re.sub(r'<.*?>', '', raw_title)).strip()

                # 2. Extract Featured Media with Fallbacks
                image_url = None
                embedded = post.get('_embedded', {})
                if 'wp:featuredmedia' in embedded and len(embedded['wp:featuredmedia']) > 0:
                    media_info = embedded['wp:featuredmedia'][0]
                    media_details = media_info.get('media_details', {}).get('sizes', {})
                    if 'full' in media_details:
                        image_url = media_details['full']['source_url']
                    elif 'large' in media_details:
                        image_url = media_details['large']['source_url']
                    else:
                        image_url = media_info.get('source_url', None)

                # 3. Clean Excerpt or Extract First Paragraph from Content
                raw_excerpt = post.get('excerpt', {}).get('rendered', '')
                clean_summary = html.unescape(re.sub(r'<.*?>', '', raw_excerpt)).strip()

                # Content Fallback if excerpt is empty
                content_html = post.get('content', {}).get('rendered', '')
                if not clean_summary and content_html:
                    soup = BeautifulSoup(content_html, 'html.parser')
                    first_p = soup.find('p')
                    if first_p:
                        clean_summary = first_p.get_text().strip()

                # Inline Image Fallback
                if not image_url and content_html:
                    soup = BeautifulSoup(content_html, 'html.parser')
                    c_img = soup.find('img')
                    if c_img and c_img.get('src'):
                        image_url = c_img['src']

                articles.append({
                    'id': post.get('id'),
                    'title': title,
                    'summary': clean_summary,
                    'image': image_url,
                    'link': post.get('link', ''),
                    'date': post.get('date', '')
                })
        else:
            print(f"❌ WordPress API Error [{response.status_code}]: {response.text}")
    except Exception as e:
        print("❌ News Fetch Exception:", e)

    return articles