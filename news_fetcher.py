import requests
import re
import html

def fetch_news(wp_base_url, limit=1):
    """
    ورڈپریس ویب سائٹ کے REST API سے تازہ ترین خبر اور اس کی اصل Featured Image لانا
    """
    if not wp_base_url or not wp_base_url.strip():
        print("❌ Error: WordPress Base URL is missing.")
        return []

    # 💡 Normalize URL: Remove /xmlrpc.php and trailing slashes to prevent 404 errors
    base_url = wp_base_url.replace("/xmlrpc.php", "").strip().rstrip('/')
    if not base_url.startswith("http"):
        base_url = "https://" + base_url
        
    api_url = f"{base_url}/wp-json/wp/v2/posts?_embed&per_page={limit}"
    
    articles = []
    
    try:
        response = requests.get(api_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        print(f"🌐 Fetching news from: {api_url} (Status: {response.status_code})")
        
        if response.status_code == 200:
            posts = response.json()
            for post in posts:
                # 1. Decode HTML entities in Title (fixes broken Urdu/special characters)
                raw_title = post.get('title', {}).get('rendered', '')
                title = html.unescape(re.sub('<.*?>', '', raw_title)).strip()
                
                # 2. Extract Featured Image URL safely
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

                # 3. Clean excerpt/summary HTML tags and entities
                raw_excerpt = post.get('excerpt', {}).get('rendered', '')
                clean_summary = html.unescape(re.sub('<.*?>', '', raw_excerpt)).strip()

                articles.append({
                    'title': title,
                    'summary': clean_summary,
                    'image': image_url,
                    'link': post.get('link', '')
                })
        else:
            print(f"❌ WordPress API Error [{response.status_code}]: {response.text}")
    except Exception as e:
        print("❌ News Fetch Critical Exception:", e)

    return articles