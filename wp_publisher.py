import requests
import json
import base64
import os
from bs4 import BeautifulSoup
import urllib.parse
import mimetypes
import re

def get_headers(wp_user, wp_pass):
    credentials = f"{wp_user}:{wp_pass}"
    encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    return {'Authorization': f'Basic {encoded}'}

def format_wp_urls(base_url):
    clean_url = base_url.replace("/xmlrpc.php", "").strip("/")
    if not clean_url.startswith("http"):
        clean_url = "https://" + clean_url
    posts_url = f"{clean_url}/wp-json/wp/v2/posts"
    media_url = f"{clean_url}/wp-json/wp/v2/media"
    return clean_url, posts_url, media_url

def get_media_id_from_url(image_source, wp_url, wp_user, wp_pass, caption_text=""):
    """
    سائٹ کے اپنے URL کو پہچانتا ہے، سائز کے لاحقے (dimensions) ہٹا کر میچ کرتا ہے، اور دوبارہ اپ لوڈ ہونے سے روکتا ہے۔
    """
    if not image_source or not wp_url or not wp_user or not wp_pass:
        return None
        
    clean_base_url, _, media_url = format_wp_urls(wp_url)
    headers = get_headers(wp_user, wp_pass)
    clean_source = str(image_source).strip().strip("'").strip('"')

    # 1. Check if the image belongs to the own site
    if clean_source.startswith("http") and clean_base_url in clean_source:
        try:
            parsed_url = urllib.parse.urlparse(clean_source)
            full_filename = os.path.basename(parsed_url.path) # e.g., 'hafiz-naeem.jpg'
            base_name, _ = os.path.splitext(full_filename)
            
            core_name = re.sub(r'-\d+x\d+$', '', base_name).lower()
            print(f"🔍 Direct WP Search for file: '{full_filename}' (Core: '{core_name}')")

            search_url = f"{media_url}?search={urllib.parse.quote(core_name)}&per_page=20"
            res = requests.get(search_url, headers=headers, timeout=15, verify=False)
            
            if res.status_code == 200:
                media_items = res.json()
                for item in media_items:
                    stored_url = item.get('source_url', '')
                    if full_filename.lower() in stored_url.lower() or core_name in stored_url.lower():
                        existing_id = item.get('id')
                        print(f"✅ Exact match found via WP Search! Media ID: {existing_id} (URL: {stored_url})")
                        return existing_id
        except Exception as e:
            print(f"⚠️ API library lookup error: {e}")

    # 2. Proceed to upload ONLY if it is truly a new external/local file not found in library
    print(f"ℹ️ Image not found in library or is external, uploading: {clean_source}")
    
    try:
        file_bytes = None
        filename = "uploaded_image.jpg"

        if os.path.exists(clean_source):
            filename = os.path.basename(clean_source)
            with open(clean_source, "rb") as f:
                file_bytes = f.read()
        else:
            target_img_url = clean_source
            if not target_img_url.lower().endswith(('png', 'jpg', 'jpeg', 'webp', 'gif')):
                res = requests.get(target_img_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10, verify=False)
                soup = BeautifulSoup(res.text, 'html.parser')
                meta_img = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'twitter:image'})
                if meta_img and meta_img.get('content'):
                    target_img_url = meta_img['content']
                else:
                    img_tag = soup.find('img')
                    if img_tag and img_tag.get('src'):
                        target_img_url = img_tag['src']
                if not target_img_url.startswith('http'):
                    target_img_url = urllib.parse.urljoin(clean_source, target_img_url)

            filename = target_img_url.split('/')[-1].split('?')[0]
            if not filename:
                filename = "web_image.jpg"

            img_resp = requests.get(target_img_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15, verify=False)
            if img_resp.status_code == 200:
                file_bytes = img_resp.content

        if file_bytes:
            ext = filename.split('.')[-1].lower()
            if ext not in ['png', 'jpg', 'jpeg', 'webp']:
                filename = filename.rsplit('.', 1)[0] + ".jpg"
                ext = "jpg"

            mime_type = "image/jpeg" if ext in ["jpg", "jpeg"] else f"image/{ext}"
            
            upload_headers = headers.copy()
            upload_headers['Content-Type'] = mime_type
            upload_headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            upload_res = requests.post(media_url, data=file_bytes, headers=upload_headers, timeout=30, verify=False)
            if upload_res.status_code in [200, 201]:
                media_data = upload_res.json()
                new_id = media_data.get('id')
                print(f"✅ Successfully Uploaded New Media ID: {new_id}")

                if caption_text and caption_text.strip():
                    update_url = f"{media_url}/{new_id}"
                    update_payload = {
                        "caption": {"raw": caption_text.strip()},
                        "alt_text": caption_text.strip()
                    }
                    update_headers = headers.copy()
                    update_headers['Content-Type'] = 'application/json; charset=utf-8'
                    requests.post(update_url, data=json.dumps(update_payload, ensure_ascii=False).encode('utf-8'), headers=update_headers, timeout=15, verify=False)

                return new_id
            else:
                print(f"❌ WP Media Upload Error [{upload_res.status_code}]: {upload_res.text}")

    except Exception as e:
        print(f"❌ Error handling media upload: {e}")
        
    return None  # 💡 Fixed trailing typo 'Nonep'

def fetch_wordpress_categories(wp_url, wp_user, wp_pass):
    if not wp_url or not wp_user or not wp_pass:
        return {}
        
    clean_base_url, _, _ = format_wp_urls(wp_url)
    cat_url = f"{clean_base_url}/wp-json/wp/v2/categories?per_page=100"
    
    try:
        headers = get_headers(wp_user, wp_pass)
        res = requests.get(cat_url, headers=headers, timeout=10, verify=False)
        if res.status_code == 200:
            categories = res.json()
            return {cat['name']: cat['id'] for cat in categories}
    except Exception as e:
        print(f"⚠️ Error fetching categories: {e}")
        
    return {}

def post_to_wordpress(title, content, wp_url, wp_user, wp_pass, excerpt="", media_id=None, status="draft", category_ids=None):
    if not wp_url or not wp_user or not wp_pass:
        raise ValueError("Missing WordPress credentials.")

    _, posts_url, _ = format_wp_urls(wp_url)
    headers = get_headers(wp_user, wp_pass)
    headers['Content-Type'] = 'application/json; charset=utf-8'

    payload = {
        "title": title,
        "content": content,
        "excerpt": excerpt,
        "status": status,
    }
    
    if media_id:
        try:
            payload["featured_media"] = int(media_id)
            print(f"🖼️ Setting Featured Thumbnail ID for post: {int(media_id)}")
        except Exception as e:
            print(f"⚠️ Error setting featured_media: {e}")
        
    if category_ids:
        payload["categories"] = [int(cat_id) for cat_id in category_ids]

    try:
        json_data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        response = requests.post(posts_url, data=json_data, headers=headers, verify=False)
        if response.status_code in [200, 201]:
            post_data = response.json()
            post_link = post_data.get("link")
            print(f"✅ WordPress Post Published: {post_link} (Featured Media ID: {post_data.get('featured_media')})")
            return post_link
        else:
            print(f"❌ WP Post Error [{response.status_code}]: {response.text}")
    except Exception as e:
        print(f"❌ WP Exception Error: {e}")
        
    return None