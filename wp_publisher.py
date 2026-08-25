import os
import re
import json
import base64
import urllib.parse
import urllib3
import requests
from bs4 import BeautifulSoup
import streamlit as st

# Suppress unverified HTTPS warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_headers(wp_user: str, wp_pass: str) -> dict:
    credentials = f"{wp_user}:{wp_pass}"
    encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    return {'Authorization': f'Basic {encoded}'}


def format_wp_urls(base_url: str):
    clean_url = base_url.replace("/xmlrpc.php", "").strip("/")
    if not clean_url.startswith("http"):
        clean_url = "https://" + clean_url
    posts_url = f"{clean_url}/wp-json/wp/v2/posts"
    media_url = f"{clean_url}/wp-json/wp/v2/media"
    return clean_url, posts_url, media_url


def get_media_id_from_url(
    image_source, 
    wp_url: str, 
    wp_user: str, 
    wp_pass: str, 
    title_text: str = "", 
    caption_text: str = "", 
    custom_filename: str = None
):
    """
    Handles WordPress Media Library uploads for Streamlit:
    1. In-memory file bytes / Streamlit UploadedFile buffers.
    2. Local file paths.
    3. Self-site deduplication by stripping thumbnail sizes.
    4. External image URLs and deep DOM scraping.
    5. Automatic metadata setting (Title, Caption, Alt text, Description).
    """
    if not image_source or not wp_url or not wp_user or not wp_pass:
        return None

    clean_base_url, _, media_url = format_wp_urls(wp_url)
    headers = get_headers(wp_user, wp_pass)

    file_bytes = None
    filename = custom_filename or "story_image.jpg"

    # =========================================================================
    # BRANCH 1: STREAMLIT UPLOADED FILE OR IN-MEMORY BYTES/BYTESIO
    # =========================================================================
    if hasattr(image_source, "getvalue"):  # Streamlit UploadedFile or io.BytesIO
        file_bytes = image_source.getvalue()
        if hasattr(image_source, "name") and image_source.name:
            filename = image_source.name
    elif isinstance(image_source, (bytes, bytearray)):
        file_bytes = image_source

    # =========================================================================
    # BRANCH 2: STRING PATHS OR WEB URLS
    # =========================================================================
    elif isinstance(image_source, str):
        clean_source = str(image_source).strip().strip("'").strip('"')

        # 2a. Self-site deduplication
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
                            return item.get('id')
            except Exception as e:
                print(f"⚠️ Media search notice: {e}")

        # 2b. Local File on Disk
        if os.path.exists(clean_source) and os.path.isfile(clean_source):
            filename = os.path.basename(clean_source)
            with open(clean_source, "rb") as f:
                file_bytes = f.read()

        # 2c. External Web Scraping
        elif clean_source.startswith("http"):
            browser_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
            }
            target_img_url = clean_source
            if not target_img_url.lower().split('?')[0].endswith(('png', 'jpg', 'jpeg', 'webp', 'gif')):
                try:
                    page_res = requests.get(target_img_url, headers={'User-Agent': browser_headers['User-Agent']}, timeout=15, verify=False)
                    soup = BeautifulSoup(page_res.text, 'html.parser')
                    meta_img = (
                        soup.find('meta', property='og:image:secure_url') or 
                        soup.find('meta', property='og:image') or 
                        soup.find('meta', attrs={'name': 'twitter:image'})
                    )
                    if meta_img and meta_img.get('content'):
                        target_img_url = meta_img['content']
                    else:
                        img_tag = soup.select_one('.wp-post-image, .featured-image img, article img, .post-thumbnail img, .entry-content img, img')
                        if img_tag:
                            target_img_url = img_tag.get('data-orig-file') or img_tag.get('data-src') or img_tag.get('src')

                    if target_img_url and not target_img_url.startswith('http'):
                        target_img_url = urllib.parse.urljoin(clean_source, target_img_url)
                except Exception as scrape_err:
                    print(f"⚠️ Scraping notice: {scrape_err}")

            if target_img_url:
                try:
                    img_resp = requests.get(target_img_url, headers=browser_headers, timeout=20, verify=False)
                    if img_resp.status_code == 200 and len(img_resp.content) > 300:
                        file_bytes = img_resp.content
                        raw_name = target_img_url.split('/')[-1].split('?')[0]
                        filename = raw_name if '.' in raw_name else f"news_{os.urandom(3).hex()}.jpg"
                except Exception as dl_err:
                    print(f"⚠️ Download notice: {dl_err}")

    # =========================================================================
    # STEP 3: UPLOAD BINARY PAYLOAD TO WORDPRESS
    # =========================================================================
    if file_bytes and len(file_bytes) > 300:
        ext = filename.split('.')[-1].lower()
        if ext == "png":
            mime_type = "image/png"
        elif ext == "webp":
            mime_type = "image/webp"
        elif ext == "gif":
            mime_type = "image/gif"
        else:
            mime_type = "image/jpeg"
            if ext not in ["jpg", "jpeg"]:
                filename = f"{filename.rsplit('.', 1)[0]}.jpg"

        safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        upload_headers = headers.copy()
        upload_headers['Content-Type'] = mime_type
        upload_headers['Content-Disposition'] = f'attachment; filename="{safe_filename}"'

        try:
            upload_res = requests.post(media_url, data=file_bytes, headers=upload_headers, timeout=35, verify=False)
            if upload_res.status_code in [200, 201]:
                media_data = upload_res.json()
                new_id = media_data.get('id')

                # Set WordPress Metadata
                meta_label = caption_text.strip() if caption_text else (title_text.strip() or safe_filename.rsplit('.', 1)[0])
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
            print(f"❌ Error uploading binary: {e}")

    return None

upload_media_to_wordpress = get_media_id_from_url


@st.cache_data(ttl=600, show_spinner=False)
def fetch_wordpress_categories(wp_url: str, wp_user: str, wp_pass: str) -> dict:
    """Fetches and caches categories for 10 minutes to maintain snappy Streamlit performance."""
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


def post_to_wordpress(
    title: str, 
    content: str, 
    wp_url: str, 
    wp_user: str, 
    wp_pass: str, 
    excerpt: str = "", 
    media_id: int = None, 
    status: str = "draft", 
    category_ids: list = None
):
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
            payload["meta"] = {"_thumbnail_id": int(media_id)}
        except Exception as e:
            print(f"⚠️ Error setting featured_media: {e}")

    if category_ids:
        payload["categories"] = [int(cat_id) for cat_id in category_ids]

    try:
        json_data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        response = requests.post(posts_url, data=json_data, headers=headers, verify=False)
        if response.status_code in [200, 201]:
            post_data = response.json()
            post_id = post_data.get("id")
            post_link = post_data.get("link")

            if media_id and post_id:
                try:
                    requests.post(
                        f"{media_url}/{int(media_id)}",
                        data=json.dumps({"post": int(post_id)}),
                        headers=headers,
                        timeout=10,
                        verify=False
                    )
                except Exception as attach_err:
                    print(f"⚠️ Notice attaching media to post ID: {attach_err}")

            return post_link
        else:
            print(f"❌ WP Post Error [{response.status_code}]: {response.text}")
    except Exception as e:
        print(f"❌ WP Exception Error: {e}")

    return None