import os
import io
import re
import urllib.parse
import requests
from requests.auth import HTTPBasicAuth


def query_existing_media_id(image_url: str, wp_url: str, auth: HTTPBasicAuth) -> int:
    """Queries WordPress REST API to check if an image filename already exists in the media library."""
    try:
        raw_filename = os.path.basename(urllib.parse.urlparse(image_url).path)
        base_name = os.path.splitext(raw_filename)[0]
        base_clean = re.sub(r'-\d+x\d+$', '', base_name)

        api_endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/media"
        
        resp = requests.get(
            api_endpoint,
            params={"search": base_clean, "per_page": 10},
            auth=auth,
            timeout=15,
            verify=False
        )
        if resp.status_code == 200:
            items = resp.json()
            for item in items:
                source_url = item.get("source_url", "")
                guid = item.get("guid", {}).get("rendered", "")
                if image_url in [source_url, guid] or base_clean in item.get("slug", ""):
                    return int(item["id"])
                    
            if items:
                return int(items[0]["id"])
    except Exception as e:
        print(f"Media lookup note: {e}")
        
    return None


def get_media_id_from_url(
    image_source,
    wp_url: str,
    wp_user: str,
    wp_pass: str,
    title_text: str = "",
    caption_text: str = ""
) -> int:
    """Resolves existing media ID for internal site images, or uploads external images/files."""
    if not image_source or not wp_url:
        return None

    clean_wp_url = wp_url.rstrip('/')
    auth = HTTPBasicAuth(wp_user, wp_pass)
    headers = {'User-Agent': 'Mozilla/5.0'}

    # 1. Existing Media Check on Same WordPress Domain
    if isinstance(image_source, str) and image_source.startswith("http"):
        wp_domain = urllib.parse.urlparse(clean_wp_url).netloc.lower()
        img_domain = urllib.parse.urlparse(image_source).netloc.lower()

        if wp_domain in img_domain or "/wp-content/uploads/" in image_source:
            existing_id = query_existing_media_id(image_source, clean_wp_url, auth)
            if existing_id:
                return existing_id

    # 2. Upload New Image / Binary
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
        resp = requests.get(
            endpoint,
            params={"per_page": 100, "hide_empty": False},
            auth=auth,
            timeout=10,
            verify=False
        )
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
        resp = requests.post(
            endpoint,
            json=payload,
            auth=auth,
            timeout=30,
            verify=False
        )
        if resp.status_code in [200, 201]:
            post_data = resp.json()
            return post_data.get("link", "")
        else:
            print(f"WordPress Post Error ({resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"WordPress Post Exception: {e}")

    return None
