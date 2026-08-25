import os
import io
import json
import base64
import urllib.parse
import re
import requests
import urllib3
from bs4 import BeautifulSoup

# Suppress unverified HTTPS warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_headers(wp_user: str, wp_pass: str) -> dict:
    """Generates standard HTTP Basic Authentication header."""
    credentials = f"{wp_user}:{wp_pass}"
    encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    return {'Authorization': f'Basic {encoded}'}


def format_wp_urls(base_url: str):
    """Normalizes WordPress root URL and derives standard REST API endpoints."""
    clean_url = base_url.replace("/xmlrpc.php", "").strip().rstrip("/")
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
    caption_text: str = ""
) -> int:
    """
    1. Checks if the image is already in the site's WP Media Library (deduplication).
    2. Supports direct local files from disk or Streamlit UploadedFile/BytesIO.
    3. Supports external URLs via deep DOM scraping (og:image, twitter:image, lazy-load attributes).
    4. Uploads binary data and updates WordPress Title, Caption, Alt Text, and Description.
    """
    if not image_source or not wp_url or not wp_user or not wp_pass:
        return None

    clean_base_url, _, media_url = format_wp_urls(wp_url)
    headers = get_headers(wp_user, wp_pass)
    
    # Handle string sources (URLs / Local paths)
    is_str_source = isinstance(image_source, str)
    clean_source = str(image_source).strip().strip("'").strip('"') if is_str_source else ""

    # Normalize domain checking (ignore protocols and www)
    def normalize_domain(u):
        parsed = urllib.parse.urlparse(u if u.startswith("http") else f"https://{u}")
        return parsed.netloc.lower().replace("www.", "")

    target_domain = normalize_domain(clean_base_url)

    # =========================================================================
    # STEP 1: CHECK IF IMAGE ALREADY EXISTS IN OWN SITE MEDIA LIBRARY
    # =========================================================================
    if is_str_source and clean_source.startswith("http") and (target_domain in normalize_domain(clean_source) or "/wp-content/uploads/" in clean_source):
        try:
            parsed_url = urllib.parse.urlparse(clean_source)
            full_filename = os.path.basename(parsed_url.path)
            base_name, _ = os.path.splitext(full_filename)
            core_name = re.sub(r'-\d+x\d+$', '', base_name).lower()
            print(f"🔍 Searching WP Library for existing file: '{full_filename}' (Core: '{core_name}')")

            search_url = f"{media_url}?search={urllib.parse.quote(core_name)}&per_page=20"
            res = requests.get(search_url, headers=headers, timeout=15, verify=False)

            if res.status_code == 200:
                media_items = res.json()
                for item in media_items:
                    stored_url = item.get('source_url', '')
                    guid_url = item.get('guid', {}).get('rendered', '')
                    item_slug = item.get('slug', '')

                    if (full_filename.lower() in stored_url.lower() or 
                        full_filename.lower() in guid_url.lower() or 
                        core_name == item_slug.lower() or 
                        core_name in stored_url.lower()):
                        existing_id = item.get('id')
                        print(f"✅ Found existing media in library! ID: {existing_id}")
                        return int(existing_id)
        except Exception as e:
            print(f"⚠️ Library search notice: {e}")

    # =========================================================================
    # STEP 2: EXTRACT FILE BYTES (STREAMLIT OBJECT, LOCAL FILE, OR WEB SCRAPE)
    # =========================================================================
    try:
        file_bytes = None
        filename = "story_image.jpg"
        browser_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
        }

        # Branch A: Streamlit UploadedFile or BytesIO buffer
        if hasattr(image_source, "getvalue"):
            file_bytes = image_source.getvalue()
            filename = getattr(image_source, "name", filename)
            print(f"📦 Extracted binary from in-memory upload stream: {filename}")

        # Branch B: Raw bytes
        elif isinstance(image_source, bytes):
            file_bytes = image_source

        # Branch C: Local file on disk (from Image Resizer Tab)
        elif is_str_source and os.path.exists(clean_source) and os.path.isfile(clean_source):
            filename = os.path.basename(clean_source)
            print(f"📁 Reading local image binary: {clean_source}")
            with open(clean_source, "rb") as f:
                file_bytes = f.read()

        # Branch D: Web URL extraction
        elif is_str_source and clean_source.startswith("http"):
            target_img_url = clean_source
            if not target_img_url.lower().split('?')[0].endswith(('png', 'jpg', 'jpeg', 'webp', 'gif')):
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

            if target_img_url:
                img_resp = requests.get(target_img_url, headers=browser_headers, timeout=20, verify=False)
                if img_resp.status_code == 200 and len(img_resp.content) > 300:
                    file_bytes = img_resp.content
                    raw_name = target_img_url.split('/')[-1].split('?')[0]
                    filename = raw_name if '.' in raw_name else f"news_{os.urandom(3).hex()}.jpg"

        # =========================================================================
        # STEP 3: UPLOAD TO WORDPRESS MEDIA ENDPOINT
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

            upload_res = requests.post(media_url, data=file_bytes, headers=upload_headers, timeout=35, verify=False)

            if upload_res.status_code in [200, 201]:
                media_data = upload_res.json()
                new_id = media_data.get('id')
                print(f"✅ Successfully Uploaded Media ID: {new_id} ({safe_filename})")

                # =====================================================================
                # STEP 4: SET COMPLETE WORDPRESS MEDIA METADATA
                # =====================================================================
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

                return int(new_id)
            else:
                print(f"❌ WP Media Upload Error [{upload_res.status_code}]: {upload_res.text}")

    except Exception as e:
        print(f"❌ Error handling media upload: {e}")

    return None

upload_media_to_wordpress = get_media_id_from_url


def fetch_wordpress_categories(wp_url: str, wp_user: str, wp_pass: str) -> dict:
    """Fetches WordPress category map {name: id}."""
    if not wp_url or not wp_user or not wp_pass:
        return {}

    clean_base_url, _, _ = format_wp_urls(wp_url)
    cat_url = f"{clean_base_url}/wp-json/wp/v2/categories?per_page=100"

    try:
        headers = get_headers(wp_user, wp_pass)
        res = requests.get(cat_url, headers=headers, timeout=10, verify=False)
        if res.status_code == 200:
            categories = res.json()
            return {cat['name']: int(cat['id']) for cat in categories if 'name' in cat and 'id' in cat}
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
) -> str:
    """Publishes or saves a WordPress post and attaches featured media."""
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
            print(f"🖼️ Setting Featured Thumbnail ID for post: {int(media_id)}")
        except Exception as e:
            print(f"⚠️ Error setting featured_media in payload: {e}")

    if category_ids:
        payload["categories"] = [int(cat_id) for cat_id in category_ids]

    try:
        json_data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        response = requests.post(posts_url, data=json_data, headers=headers, timeout=30, verify=False)
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

            print(f"✅ WordPress Post Published: {post_link} (Featured Media ID: {post_data.get('featured_media')})")
            return post_link
        else:
            print(f"❌ WP Post Error [{response.status_code}]: {response.text}")
    except Exception as e:
        print(f"❌ WP Exception Error: {e}")

    return None
