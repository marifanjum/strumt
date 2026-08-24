import sys
import os
import glob
import base64
import requests
import urllib.parse
from datetime import datetime
from playwright.sync_api import sync_playwright

def resource_path(relative_path):
    if not relative_path:
        return ""

    if hasattr(sys, '_MEIPASS'):
        path_in_temp = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(path_in_temp):
            return path_in_temp

    exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.abspath(".")
    internal_dir = os.path.join(exe_dir, "_internal")

    path_in_internal = os.path.join(internal_dir, relative_path)
    if os.path.exists(path_in_internal):
        return path_in_internal

    path_in_exe = os.path.join(exe_dir, relative_path)
    if os.path.exists(path_in_exe):
        return path_in_exe

    return os.path.join(os.path.abspath("."), relative_path)


def get_chromium_executable_path():
    # 1. Bundled Chromium search (desktop/pyinstaller)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        base_dirs = [
            getattr(sys, '_MEIPASS', ''),
            exe_dir,
            os.path.join(exe_dir, "_internal")
        ]
    else:
        base_dirs = [os.path.abspath(".")]

    for b_dir in base_dirs:
        if not b_dir:
            continue
        browsers_dir = os.path.join(b_dir, "playwright-browsers")
        direct_chrome = os.path.join(browsers_dir, "chrome-win64", "chrome.exe")
        if os.path.exists(direct_chrome):
            return direct_chrome

        patterns = [
            os.path.join(browsers_dir, "*", "chrome-win64", "chrome.exe"),
            os.path.join(browsers_dir, "*", "chrome-win", "chrome.exe"),
            os.path.join(browsers_dir, "chromium-*", "chrome.exe")
        ]
        for p in patterns:
            found = glob.glob(p)
            if found and os.path.exists(found[0]):
                return found[0]

    # 2. System binary detection
    system_chrome_paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/snap/bin/chromium",
        "/usr/lib/chromium-browser/chromium-browser",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Users\{}\AppData\Local\Google\Chrome\Application\chrome.exe".format(os.environ.get('USERNAME', '')),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Microsoft Edge\Application\msedge.exe"
    ]

    for path in system_chrome_paths:
        if os.path.exists(path):
            return path

    return None


def launch_browser_safely(p):
    chrome_exe = get_chromium_executable_path()
    container_args = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
    if chrome_exe:
        return p.chromium.launch(executable_path=chrome_exe, headless=True, args=container_args)
    else:
        return p.chromium.launch(headless=True, args=container_args)


try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None


def img_to_base64(img_path):
    if not img_path or not isinstance(img_path, (str, bytes, os.PathLike)):
        return ""

    # If it's already a full data URI, return as-is
    str_path = str(img_path).strip()
    if str_path.startswith("data:image"):
        return str_path

    real_path = resource_path(str_path)
    if not os.path.exists(real_path):
        real_path = str_path

    if os.path.exists(real_path):
        try:
            with open(real_path, "rb") as image_file:
                raw_bytes = image_file.read()
                if not raw_bytes:
                    return ""
                encoded_string = base64.b64encode(raw_bytes).decode('utf-8')
                
                # Detect MIME type
                ext = str(real_path).split('.')[-1].lower()
                if ext in ["jpg", "jpeg"]:
                    mime = "image/jpeg"
                elif ext == "webp":
                    mime = "image/webp"
                else:
                    mime = "image/png"
                return f"data:{mime};base64,{encoded_string}"
        except Exception as e:
            print(f"Base64 Error ({real_path}): {e}")
    return ""


def font_to_base64(font_path):
    if not font_path:
        return ""
    real_path = resource_path(str(font_path))
    if not os.path.exists(real_path):
        real_path = str(font_path)

    if os.path.exists(real_path):
        try:
            with open(real_path, "rb") as font_file:
                encoded_string = base64.b64encode(font_file.read()).decode('utf-8')
                return f"data:font/ttf;charset=utf-8;base64,{encoded_string}"
        except Exception as e:
            print(f"Font Base64 Error: {e}")
    return ""


def fetch_ai_generated_image(news_text, output_path="temp_ai_bg.jpg", width=1280, height=720):
    try:
        clean_prompt = str(news_text)[:100].replace("\n", " ").strip()
        if not clean_prompt:
            clean_prompt = "breaking news studio broadcast background"

        if GoogleTranslator:
            try:
                clean_prompt = GoogleTranslator(source='auto', target='en').translate(clean_prompt)
            except Exception:
                pass

        english_prompt = f"professional news broadcast cinematic studio background, high quality 8k, photorealistic, {clean_prompt}"
        encoded_prompt = urllib.parse.quote(english_prompt)
        img_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true"

        response = requests.get(img_url, timeout=30, verify=False)
        if response.status_code == 200 and len(response.content) > 5000:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return output_path
    except Exception as e:
        print(f"AI Image Auto-Gen Error: {e}")
    return None


def calculate_dynamic_font_size(text):
    length = len(text.strip())
    if length <= 25:
        return 140, 1.2
    elif length <= 50:
        return 120, 1.2
    elif length <= 85:
        return 100, 1.2
    else:
        return 93, 1.2


# ---------------------------------------------------------
# 1. SOCIAL CARD FUNCTION 
# ---------------------------------------------------------
def create_ummat_social_card(
    headline_text, 
    news_img_path=None, 
    template_path=None, 
    font_path=None, 
    output_path="social_card.png"
):
    clean_headline = str(headline_text).replace('TITLE:', '').replace('CONTENT:', '').replace('ٹائٹل:', '').strip()
    if not clean_headline:
        clean_headline = "یہاں خبر کی اردو سرخی آئے گی۔"

    valid_news_img = None
    if news_img_path:
        clean_p = str(news_img_path).strip().strip("'").strip('"')
        if os.path.exists(clean_p) and os.path.getsize(clean_p) > 200:
            valid_news_img = os.path.abspath(clean_p)
        elif os.path.exists(resource_path(clean_p)) and os.path.getsize(resource_path(clean_p)) > 200:
            valid_news_img = resource_path(clean_p)

    if not valid_news_img:
        print("⚠️ No valid local image provided, generating AI background fallback...")
        news_img_path = fetch_ai_generated_image(clean_headline, output_path="temp_ai_bg.jpg", width=1080, height=1350)
    else:
        news_img_path = valid_news_img

    final_template_path = None
    possible_templates = [template_path, "ummat_frame.png", "ummat_frame.png.png"]
    for t in possible_templates:
        if t:
            resolved = resource_path(str(t))
            if os.path.exists(resolved):
                final_template_path = resolved
                break

    news_img_b64 = img_to_base64(news_img_path)
    template_b64 = img_to_base64(final_template_path)

    if not font_path:
        possible_fonts = [
            "Jameel Noori Nastaleeq.ttf", 
            "Jameel Noori Nastaleeq Regular.ttf", 
            "Jameel Noori Kasheeda.ttf",
            "jameel.ttf", 
            "urdu_font.ttf"
        ]
        for f in possible_fonts:
            resolved_font = resource_path(f)
            if os.path.exists(resolved_font):
                font_path = resolved_font
                break

    font_b64 = font_to_base64(font_path)
    font_size, line_height = calculate_dynamic_font_size(clean_headline)

    font_face_css = f"@font-face {{ font-family: 'Jameel Custom'; src: url('{font_b64}') format('truetype'); font-weight: normal; font-style: normal; }}" if font_b64 else ""

    news_tag = f"<img class='news-photo' src='{news_img_b64}'>" if news_img_b64 else ""
    frame_tag = f"<img class='frame-overlay' src='{template_b64}'>" if template_b64 else ""

    html_content = f"""
    <!DOCTYPE html>
    <html lang="ur">
    <head>
        <meta charset="UTF-8">
        <style>
            {font_face_css}

            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                width: 1080px;
                height: 1350px;
                position: relative;
                background-color: #0f172a;
                overflow: hidden;
                font-family: 'Jameel Custom', 'Jameel Noori Nastaleeq', Arial, sans-serif !important;
            }}
            .news-photo {{
                position: absolute; 
                top: 65px; 
                left: 0; 
                width: 1080px; 
                height: 720px; 
                object-fit: cover; 
                z-index: 1;
            }}
            .frame-overlay {{
                position: absolute; 
                top: 0; 
                left: 0; 
                width: 1080px; 
                height: 1350px; 
                z-index: 2; 
                pointer-events: none;
            }}
            .headline-container {{
                position: absolute; 
                top: 800px; 
                left: 40px; 
                width: 1000px; 
                height: 350px; 
                z-index: 3;
                display: flex; 
                align-items: center; 
                justify-content: center; 
                text-align: center; 
                direction: rtl;
            }}
            .headline-text {{
                font-family: 'Jameel Custom', 'Jameel Noori Nastaleeq', Arial, sans-serif !important;
                color: #000000 !important; 
                font-size: {font_size}px; 
                line-height: {line_height};
                word-wrap: break-word; 
                width: 100%; 
                padding: 0 10px;
                -webkit-font-smoothing: antialiased;
                filter: url(#bold-filter);
            }}
        </style>
    </head>
    <body>
        <svg style="position: absolute; width: 0; height: 0; overflow: hidden;">
          <filter id="bold-filter">
            <feMorphology operator="dilate" radius="0.4" in="SourceAlpha" result="thicken" />
            <feMerge>
              <feMergeNode in="thicken" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </svg>

        {news_tag}
        {frame_tag}
        <div class="headline-container">
            <div class="headline-text">{clean_headline}</div>
        </div>
    </body>
    </html>
    """

    abs_out = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_out) if os.path.dirname(abs_out) else '.', exist_ok=True)

    with sync_playwright() as p:
        browser = launch_browser_safely(p)
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        page.set_content(html_content, wait_until="networkidle")
        page.wait_for_timeout(400)
        page.screenshot(path=abs_out, full_page=True)
        browser.close()

    return output_path

generate_custom_card = create_ummat_social_card


# ---------------------------------------------------------
# 2. PRO YOUTUBE 16:9 THUMBNAIL
# ---------------------------------------------------------
def make_youtube_169_thumbnail(headline_text=None, script_text=None, news_img_path=None, logo_path=None, output_path="yt_thumb_169.png", **kwargs):
    raw_input = headline_text if headline_text else script_text
    if not raw_input: 
        raw_input = "اہم خبر\nتفصیلات یہاں آئیں گی"

    final_logo_path = None
    possible_logos = [logo_path, "ummat bug final.png"]
    for l in possible_logos:
        if l:
            resolved_logo = resource_path(str(l))
            if os.path.exists(resolved_logo):
                final_logo_path = resolved_logo
                break

    clean_lines = [line.strip() for line in str(raw_input).split('\n') if line.strip()]
    top_title = clean_lines[0] if len(clean_lines) > 0 else "اہم خبر"
    top_title = top_title.replace("ٹائٹل:", "").replace("TITLE:", "").replace("Headline:", "").strip()

    bottom_text = clean_lines[1] if len(clean_lines) > 1 else "تازہ ترین اپڈیٹ"

    if not news_img_path or not os.path.exists(str(news_img_path)):
        news_img_path = fetch_ai_generated_image(top_title, output_path="temp_ai_bg.jpg", width=1280, height=720)

    news_img_b64 = img_to_base64(news_img_path)
    logo_b64 = img_to_base64(final_logo_path)

    bg_style = f"background-image: url('{news_img_b64}'); background-size: cover; background-position: center;" if news_img_b64 else "background: #0f172a;"
    logo_tag = f"<img class='logo' src='{logo_b64}'>" if logo_b64 else ""

    html_content = f"""
    <!DOCTYPE html>
    <html lang="ur">
    <head>
        <meta charset="UTF-8">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                width: 1280px; height: 720px; position: relative; overflow: hidden;
                font-family: 'Jameel Custom', 'Jameel Noori Nastaleeq', sans-serif;
                {bg_style}
            }}
            .bg-overlay {{
                position: absolute; top: 0; left: 0; width: 100%; height: 100%;
                background: linear-gradient(to top, rgba(0,0,0,0.9) 0%, rgba(0,0,0,0.3) 50%, rgba(0,0,0,0.7) 100%);
            }}
            .top-title {{
                position: absolute; top: 40px; width: 100%; text-align: center;
                color: #FA9D1C; font-size: 65px; font-weight: bold; direction: rtl;
                text-shadow: 3px 3px 6px rgba(0,0,0,0.9); z-index: 10;
                padding: 0 50px;
                filter: url(#bold-filter-yt);
            }}
            .bottom-bar {{
                position: absolute; bottom: 35px; left: 50px; right: 50px; height: 110px;
                background-color: rgba(0, 0, 0, 0.85); border-radius: 15px;
                display: flex; align-items: center; justify-content: space-between;
                padding: 0 30px; border: 2px solid #FA9D1C; z-index: 10; direction: rtl;
            }}
            .bottom-text {{
                color: #ffffff; font-size: 42px; font-weight: bold;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
            }}
            .logo-box {{
                display: flex; align-items: center; gap: 15px; direction: ltr;
            }}
            .logo {{
                height: 75px; width: auto;
                filter: drop-shadow(0px 2px 5px rgba(0,0,0,0.5));
            }}
            .yellow-line {{
                width: 6px; height: 50px; background-color: #FA9D1C; border-radius: 3px;
            }}
        </style>
    </head>
    <body>
        <svg style="position: absolute; width: 0; height: 0; overflow: hidden;">
          <filter id="bold-filter-yt">
            <feMorphology operator="dilate" radius="0.4" in="SourceAlpha" result="thicken" />
            <feMerge>
              <feMergeNode in="thicken" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </svg>

        <div class="bg-overlay"></div>
        <div class="top-title">{top_title}</div>
        <div class="bottom-bar">
            <div class="bottom-text">{bottom_text}</div>
            <div class="logo-box">
                <div class="yellow-line"></div>
                {logo_tag}
            </div>
        </div>
    </body>
    </html>
    """

    abs_out = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_out) if os.path.dirname(abs_out) else '.', exist_ok=True)

    with sync_playwright() as p:
        browser = launch_browser_safely(p)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.set_content(html_content, wait_until="networkidle")
        page.wait_for_timeout(400)
        page.screenshot(path=abs_out)
        browser.close()

    return output_path


# ---------------------------------------------------------
# 3. SHORTS 9:16 COVER
# ---------------------------------------------------------
def make_shorts_916_cover(urdu_text, english_title="www.ummat.net", news_img_path=None, logo_path=None, output_path="shorts_cover_916.png"):
    final_logo_path = None
    possible_logos = [logo_path, "ummat bug final.png"]
    for l in possible_logos:
        if l:
            resolved_logo = resource_path(str(l))
            if os.path.exists(resolved_logo):
                final_logo_path = resolved_logo
                break

    clean_text = str(urdu_text).replace("ٹائٹل:", "").replace("TITLE:", "").replace("Headline:", "").strip()

    if not news_img_path or not os.path.exists(str(news_img_path)):
        news_img_path = fetch_ai_generated_image(urdu_text, output_path="temp_ai_shorts_bg.jpg", width=1080, height=1920)

    news_img_b64 = img_to_base64(news_img_path)
    logo_b64 = img_to_base64(final_logo_path)

    bg_style = f"background-image: url('{news_img_b64}'); background-size: cover; background-position: center;" if news_img_b64 else "background-color: #0f172a;"
    logo_tag = f"<img class='logo' src='{logo_b64}'>" if logo_b64 else ""

    html_content = f"""
    <!DOCTYPE html>
    <html lang="ur">
    <head>
        <meta charset="UTF-8">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                width: 1080px; height: 1920px; position: relative;
                overflow: hidden; font-family: 'Jameel Custom', 'Jameel Noori Nastaleeq', sans-serif;
                {bg_style}
            }}
            .bg-overlay {{
                position: absolute; top: 0; left: 0; width: 100%; height: 100%;
                background: linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.2) 50%, rgba(0,0,0,0.6) 100%);
            }}
            .header-bar {{
                position: absolute; top: 60px; width: 100%; height: 90px;
                background-color: #d97706; color: #ffffff; display: flex;
                align-items: center; justify-content: center; font-size: 38px;
                font-family: sans-serif; font-weight: bold; letter-spacing: 2px; z-index: 10;
            }}
            .logo {{
                position: absolute; top: 180px; right: 60px; width: 180px; z-index: 10;
                filter: drop-shadow(2px 4px 10px rgba(0,0,0,0.6));
            }}
            .text-card {{
                position: absolute; bottom: 220px; left: 90px; width: 900px; min-height: 220px;
                background-color: #d97706; color: #ffffff; padding: 35px 40px;
                border-radius: 25px; text-align: center; direction: rtl; font-size: 88px;
                line-height: 1.3; box-shadow: 0 15px 35px rgba(0,0,0,0.7);
                border: 3px solid #ffffff; display: flex; align-items: center; justify-content: center;
                filter: drop-shadow(0.5px 0px 0px #000); z-index: 10;
            }}
        </style>
    </head>
    <body>
        <div class="bg-overlay"></div>
        <div class="header-bar">{english_title}</div>
        {logo_tag}
        <div class="text-card">{clean_text}</div>
    </body>
    </html>
    """

    abs_out = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_out) if os.path.dirname(abs_out) else '.', exist_ok=True)

    with sync_playwright() as p:
        browser = launch_browser_safely(p)
        page = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.set_content(html_content, wait_until="networkidle")
        page.wait_for_timeout(400)
        page.screenshot(path=abs_out, full_page=True)
        browser.close()

    return output_path
