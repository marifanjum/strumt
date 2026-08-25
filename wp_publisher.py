import os
import io
import re
import urllib.parse
import requests
from requests.auth import HTTPBasicAuth


def query_existing_media_id(image_url: str, wp_url: str, auth: HTTPBasicAuth) -> int:
    """Queries WordPress REST API to check if an image filename already exists in the media library."""
    try:
        # Extract the base filename without dimensions/extensions (e.g. image-1200x630.jpg -> image)
        raw_filename = os.path.basename(urllib.parse.urlparse(image_url).path)
        base_name = os.path.splitext(raw_filename)[0]
        base_clean = re.sub(r'-\d+x\d+$', '', base_name)  # Remove WP thumbnail suffix

        api_endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/media"
        
        # 1. Search by exact slug / filename
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
                
                # Exact URL match or base filename match
                if image_url in [source_url, guid] or base_clean in item.get("slug", ""):
                    return int(item["id"])
                    
            # Fallback to first search result if closely matched
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

    # ---------------------------------------------------------
    # Case 1: Image URL from the SAME WordPress site
    # ---------------------------------------------------------
    if isinstance(image_source, str) and image_source.startswith("http"):
        wp_domain = urllib.parse.urlparse(clean_wp_url).netloc.lower()
        img_domain = urllib.parse.urlparse(image_source).netloc.lower()

        # If image belongs to the same domain or contains /wp-content/uploads/
        if wp_domain in img_domain or "/wp-content/uploads/" in image_source:
            existing_id = query_existing_media_id(image_source, clean_wp_url, auth)
            if existing_id:
                return existing_id

    # ---------------------------------------------------------
    # Case 2: Upload new file or binary (Local File, BytesIO, External URL)
    # ---------------------------------------------------------
    file_bytes = None
    filename = "featured_image.jpg"
    mime_type = "image/jpeg"

    if isinstance(image_source, str):
        if os.path.exists(image_source):  # Local file path
            with open(image_source, "rb") as f:
                file_bytes = f.read()
            filename = os.path.basename(image_source)
        elif image_source.startswith("http"):  # External URL
            resp = requests.get(image_source, headers=headers, timeout=15, verify=False)
            if resp.status_code == 200:
                file_bytes = resp.content
                filename = os.path.basename(urllib.parse.urlparse(image_source).path) or filename
    elif hasattr(image_source, "getvalue"):  # BytesIO / UploadedFile
        file_bytes = image_source.getvalue()
        filename = getattr(image_source, "name", filename)
    elif isinstance(image_source, bytes):
        file_bytes = image_source

    if not file_bytes:
        return None

    # Detect MIME type
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
