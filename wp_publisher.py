import os
import io
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup
from requests.auth import HTTPBasicAuth


def get_existing_post_featured_media(post_url: str, wp_url: str, auth: HTTPBasicAuth) -> int:
    """Extracts post slug from URL and queries WordPress for its existing featured media ID."""
    try:
        clean_path = urllib.parse.urlparse(post_url).path.strip('/')
        slug = clean_path.split('/')[-1]
        if not slug:
            return None

        endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
        resp = requests.get(endpoint, params={"slug": slug, "_fields": "id,featured_media"}, auth=auth, timeout=10, verify=False)
        if resp.status_code == 200:
            posts = resp.json()
            if posts and isinstance(posts, list) and posts[0].get("featured_media"):
                feat_id = int(posts[0]["featured_media"])
                if feat_id > 0:
                    return feat_id
    except Exception as e:
        print(f"Post featured media lookup note: {e}")
    return None


def query_existing_media_by_url_or_slug(image_url: str, wp_url: str, auth: HTTPBasicAuth) -> int:
    """Finds an existing attachment ID in WordPress by filename, slug, or search term."""
    try:
        clean_wp_url = wp_url.rstrip('/')
        path_part = urllib.parse.urlparse(image_url).path
        filename = os.path.basename(path_part)
        base_name = os.path.splitext(filename)[0]
        # Remove WordPress resize dimensions (e.g., photo-1024x768 -> photo, photo-scaled -> photo)
        base_clean = re.sub(r'(-\d+x\d+|-scaled)$', '', base_name, flags=re.IGNORECASE).strip()

        if not base_clean:
            return None

        media_endpoint = f"{clean_wp_url}/wp-json/wp/v2/media"
        
        # 1. Search by cleaned base slug
        resp = requests.get(media_endpoint, params={"search": base_clean, "per_page": 20}, auth=auth, timeout=15, verify=False)
        if resp.status_code == 200:
            items = resp.json()
            for item in items:
                source_url = item.get("source_url", "")
                guid = item.get("guid", {}).get("rendered", "")
                slug = item.get("slug", "")

                # Exact URL or slug match
                if image_url in [source_url, guid] or base_clean == slug or base_clean in source_url:
                    return int(item["id"])

            if items:
                return int(items[0]["id"])
    except Exception as e:
        print(f"Media search note: {e}")
    return None


def get_media_id_from_url(
    image_source,
    wp_url: str,
    wp_user: str,
    wp_pass: str,
    title_text: str = "",
    caption_text: str = ""
) -> int:
    """Resolves existing media ID for internal site images without re-uploading, or uploads new images."""
    if not image_source or not wp_url:
        return None

    clean_wp_url = wp_url.rstrip('/')
    auth = HTTPBasicAuth(wp_user, wp_pass)
    headers = {'User-Agent': 'Mozilla/5.0'}

    # ---------------------------------------------------------
    # Case 1: Web URL provided (Article URL or Direct Media Link)
    # ---------------------------------------------------------
    if isinstance(image_source, str) and image_source.startswith("http"):
        wp_domain = urllib.parse.urlparse(clean_wp_url).netloc.lower()
        src_domain = urllib.parse.urlparse(image_source).netloc.lower()

        # If URL is from the same WordPress site
        if wp_domain in src_domain or "/wp-content/uploads/" in image_source:
            # 1. Check if the URL is an article page with an existing featured media ID
            existing_feat_id = get_existing_post_featured_media(image_source, clean_wp_url, auth)
            if existing_feat_id:
                return existing_feat_id

            # 2. Check if the media file already exists in WordPress media library
            existing_media_id = query_existing_media_by_url_or_slug(image_source, clean_wp_url, auth)
            if existing_media_id:
                return existing_media_id

            # 3. If it's a page URL, scrape og:image and check media library again
            if not image_source.lower().split('?')[0].endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
                try:
                    res = requests.get(image_source, headers=headers, timeout=12, verify=False)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    meta_img = soup.find('meta', property='og:image:secure_url') or soup.find('meta', property='og:image')
                    if meta_img and meta_img.get('content'):
                        scraped_img = meta_img['content']
                        existing_media_id = query_existing_media_by_url_or_slug(scraped_img, clean_wp_url, auth)
                        if existing_media_id:
                            return existing_media_id
                        image_source = scraped_img
                except Exception:
                    pass

    # ---------------------------------------------------------
    # Case 2: New/External Image Upload
    # ---------------------------------------------------------
    file_bytes = None
    filename = "featured_image.jpg"
    mime_type = "image/jpeg"

    if isinstance(image_source, str):
        if os.path.exists(image_source):
            with open(image_source, "rb") as f:
                file_bytes = f.read()
            filename = os.path.basename(image_source)
        elif image_source.startswith("http"):
            resp = requests.get(image_source, headers=headers, timeout=15, verify=False)
            if resp.status_code == 200:
                file_bytes = resp.content
                filename = os.path.basename(urllib.parse.urlparse(image_source).path) or filename
    elif hasattr(image_source, "getvalue"):
        file_bytes = image_source.getvalue()
        filename = getattr(image_source, "name", filename)
    elif isinstance(image_source, bytes):
        file_bytes = image_source

    if not file_bytes:
        return None

    if filename.lower().endswith(".png"):
        mime_type = "image/png"
    elif filename.lower().endswith(".webp"):
        mime_type = "image/webp"

    upload_headers = {
        "Content-Type": mime_type,
        "Content-Disposition": f'attachment; filename="{filename}"'
    }

    try:
        upload_resp = requests.post(
            f"{clean_wp_url}/wp-json/wp/v2/media",
            headers=upload_headers,
            data=file_bytes,
            auth=auth,
            params={
                "title": title_text[:100] if title_text else filename,
                "caption": caption_text if caption_text else ""
            },
            timeout=30,
            verify=False
        )

        if upload_resp.status_code in [200, 201]:
            return int(upload_resp.json().get("id"))
    except Exception as e:
        print(f"Media upload error: {e}")

    return None


def fetch_wordpress_categories(wp_url: str, wp_user: str, wp_pass: str) -> dict:
    """Fetches category names and IDs from WordPress REST API."""
    if not wp_url:
        return {}

    clean_wp_url = wp_url.rstrip('/')
    endpoint = f"{clean_wp_url}/wp-json/wp/v2/categories"
    auth = HTTPBasicAuth(wp_user, wp_pass) if wp_user and wp_pass else None

    try:
        resp = requests.get(endpoint, params={"per_page": 100, "hide_empty": False}, auth=auth, timeout=10, verify=False)
        if resp.status_code == 200:
            cats = resp.json()
            return {c["name"]: int(c["id"]) for c in cats if "name" in c and "id" in c}
    except Exception as e:
        print(f"Categories fetch note: {e}")

    return {}


def post_to_wordpress(
    title: str,
    content: str,
    wp_url: str,
    wp_user: str,
    wp_pass: str,
    excerpt: str = "",
    media_id: int = None,
    status: str = "publish",
    category_ids: list = None
) -> str:
    """Creates a post via the WordPress REST API and returns its permalink URL."""
    if not wp_url or not wp_user or not wp_pass:
        return None

    clean_wp_url = wp_url.rstrip('/')
    endpoint = f"{clean_wp_url}/wp-json/wp/v2/posts"
    auth = HTTPBasicAuth(wp_user, wp_pass)

    payload = {
        "title": title,
        "content": content,
        "status": status
    }

    if excerpt:
        payload["excerpt"] = excerpt
    if media_id:
        payload["featured_media"] = media_id
    if category_ids:
        payload["categories"] = category_ids

    try:
        resp = requests.post(endpoint, json=payload, auth=auth, timeout=30, verify=False)
        if resp.status_code in [200, 201]:
            return resp.json().get("link", "")
        else:
            print(f"WordPress Post Error ({resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"WordPress Post Exception: {e}")

    return None
