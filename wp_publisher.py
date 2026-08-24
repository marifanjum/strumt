import requests
import json
import base64
import os
from bs4 import BeautifulSoup
import urllib.parse
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

def upload_media_to_wordpress(image_source, wp_url, wp_user, wp_pass, title_text="", caption_text=""):
    """
    Downloads/reads the image and uploads it to the WordPress Media Library
    with complete WordPress-native metadata (Title, Caption, Alt Text, Description).
    """
    if not image_source or not wp_url or not wp_user or not wp_pass:
        return None
        
    clean_base_url, _, media_url = format_wp_urls(wp_url)
    headers = get_headers(wp_user, wp_pass)
    clean_source = str(image_source).strip().strip("'").strip('"')

    # 1. Check if the image already exists in WP Media Library
    if clean_source.startswith("http") and clean_base_url in clean_source:
        try:
            parsed_url = urllib.parse.urlparse(clean_source)
            full_filename = os.path.basename(parsed_url.path)
            base_name, _ = os.path.splitext(full_filename)
            core_name = re.sub(r'-\d+x\d+$', '', base_name).lower()

            search_url = f"{media_url}?search={urllib.parse.quote(core_name)}&per_page=20"
            res = requests.get(search_url, headers=headers, timeout=15, verify=False)
            
            if res.status_code == 200:
                for item in res.json():
                    stored_url = item.get('source_url', '')
                    if full_filename.lower() in stored_url.lower() or core_name in stored_url.lower():
                        existing_id = item.get('id')
                        print(f"✅ Found existing media in library: ID {existing_id}")
                        return existing_id
        except Exception as e:
            print(f"⚠️ Media search error: {e}")

    # 2. Extract and download the raw image bytes
    try:
        file_bytes = None
        filename = "story_image.jpg"
        browser_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
        }

        if os.path.exists(clean_source):
            filename = os.path.basename(clean_source)
            with open(clean_source, "rb") as f:
                file_bytes = f.read()
        elif clean_source.startswith("http"):
            target_img_url = clean_source
            if not target_img_url.lower().split('?')[0].endswith(('png', 'jpg', 'jpeg', 'webp', 'gif')):
                page_res = requests.get(target_img_url, headers=browser_headers, timeout=15, verify=False)
                soup = BeautifulSoup(page_res.text, 'html.parser')
                meta_img = soup.find('meta', property='og:image:secure_url') or soup.find('meta', property='og:image')
                if meta_img and meta_img.get('content'):
                    target_img_url = meta_img['content']
                else:
                    img_tag = soup.select_one('.wp-post-image, .featured-image img, article img, .entry-content img, img')
                    if img_tag:
                        target_img_url = img_tag.get('data-orig-file') or img_tag.get('src')

                if not target_img_url.startswith('http'):
                    target_img_url = urllib.parse.urljoin(clean_source, target_img_url)

            img_resp = requests.get(target_img_url, headers=browser_headers, timeout=20, verify=False)
            if img_resp.status_code == 200 and len(img_resp.content) > 1000:
                file_bytes = img_resp.content
                raw_name = target_img_url.split('/')[-1].split('?')[0]
                filename = raw_name if '.' in raw_name else f"news_{os.urandom(3).hex()}.jpg"

        # 3. Upload Binary to WordPress Media REST Endpoint
        if file_bytes and len(file_bytes) > 1000:
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
                print(f"✅ Successfully Uploaded Media ID: {new_id} ({filename})")

                # 4. Set Standard WordPress Media Metadata
                meta_label = caption_text.strip() if (caption_text and caption_text.strip()) else title_text.strip()
                if not meta_label:
                    meta_label = filename.rsplit('.', 1)[0]

                update_payload = {
                    "title": meta_label,
                    "caption": meta_label,
                    "alt_text": meta_label,
                    "description": meta_label
                }
                
                update_headers = headers.copy()
                update_headers['Content-Type'] = 'application/json; charset=utf-8'
                requests.post(
                    f"{media_url}/{new_id}",
                    data=json.dumps(update_payload, ensure_ascii=False).encode('utf-8'),
                    headers=update_headers,
                    timeout=15,
                    verify=False
                )

                return new_id
            else:
                print(f"❌ WP Media Upload Error [{upload_res.status_code}]: {upload_res.text}")

    except Exception as e:
        print(f"❌ Error handling media upload: {e}")
        
    return None

# Backward compatibility alias
get_media_id_from_url = upload_media_to_wordpress

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

    clean_base_url, posts_url, media_url = format_wp_urls(wp_url)
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
            # Force standard post_meta thumbnail key for SEO plugins
            payload["meta"] = {"_thumbnail_id": int(media_id)}
        except Exception as e:
            print(f"⚠️ Error setting featured_media in payload: {e}")
        
    if category_ids:
        payload["categories"] = [int(cat_id) for cat_id in category_ids]

    try:
        json_data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        response = requests.post(posts_url, data=json_data, headers=headers, verify=False)
        
        if response.status_code in [200, 201]:
            post_data = response.json()
            post_id = post_data.get("id")
            post_link = post_data.get("link")

            # Link the media attachment to the post as parent and trigger standard update hook
            if media_id and post_id:
                try:
                    # 1. Attach media to post parent
                    requests.post(
                        f"{media_url}/{int(media_id)}",
                        data=json.dumps({"post": int(post_id)}),
                        headers=headers,
                        timeout=10,
                        verify=False
                    )
                    # 2. Trigger instant post-update hook so WP flushes SEO and og:image cache
                    requests.post(
                        f"{posts_url}/{int(post_id)}",
                        data=json.dumps({"featured_media": int(media_id)}),
                        headers=headers,
                        timeout=10,
                        verify=False
                    )
                except Exception as attach_err:
                    print(f"⚠️ Notice on attaching media: {attach_err}")

            print(f"✅ WordPress Post Published: {post_link} (Featured Media ID: {post_data.get('featured_media')})")
            return post_link
        else:
            print(f"❌ WP Post Error [{response.status_code}]: {response.text}")
    except Exception as e:
        print(f"❌ WP Exception Error: {e}")
        
    return None
