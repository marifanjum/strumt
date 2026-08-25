import sys
import os
import glob
import base64
import asyncio
import concurrent.futures
import requests
import urllib.parse
from datetime import datetime
from playwright.async_api import async_playwright

def resource_path(relative_path: str) -> str:
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

    system_chrome_paths = [
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


async def launch_browser_safely(p):
    chrome_exe = get_chromium_executable_path()
    if chrome_exe:
        return await p.chromium.launch(executable_path=chrome_exe, headless=True)
    else:
        return await p.chromium.launch(headless=True)


try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None


def img_to_base64(img_source) -> str:
    """Converts local file paths, in-memory bytes, or BytesIO to base64 Data URLs."""
    if not img_source:
        return ""

    # Streamlit UploadedFile or io.BytesIO
    if hasattr(img_source, "getvalue"):
        raw_bytes = img_source.getvalue()
        encoded_string = base64.b64encode(raw_bytes).decode('utf-8')
        return f"data:image/png;base64,{encoded_string}"

    # Raw Bytes
    if isinstance(img_source, (bytes, bytearray)):
        encoded_string = base64.b64encode(img_source).decode('utf-8')
        return f"data:image/png;base64,{encoded_string}"

    str_path = str(img_source).strip()
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
                
                ext = str(real_path).split('.')[-1].lower()
                if ext in ["jpg", "jpeg"]:
                    mime = "image/jpeg"
                elif ext == "webp":
                    mime = "image/webp"
                else:
                    mime = "image/png"
                return f"data:{mime};base64,{encoded_string}"
        except Exception as e:
            print(f"Base64 Error ({real_path}):", e)
    return ""


def font_to_base64(font_path=None) -> str:
    candidates = [
        font_path,
        "jameel custom.ttf",
        "Jameel Custom.ttf",
        "jameel_custom.ttf",
        "JameelCustom.ttf",
        "Jameel Noori Nastaleeq.ttf",
        "Jameel Noori Nastaleeq Regular.ttf",
        "Jameel Noori Kasheeda.ttf",
        "urdu_font.ttf"
    ]
    resolved = None
    for c in candidates:
        if c:
            p = resource_path(str(c))
            if os.path.exists(p):
                resolved = p
                break

    if resolved and os.path.exists(resolved):
        try:
            with open(resolved, "rb") as font_file:
                encoded_string = base64.b64encode(font_file.read()).decode('utf-8')
                return f"data:font/ttf;charset=utf-8;base64,{encoded_string}"
        except Exception as e:
            print("Font Base64 Error:", e)
    return ""


def fetch_ai_generated_image(news_text: str, output_path="temp_ai_bg.jpg", width=1200, height=1200):
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
        print("AI Image Auto-Gen Error:", e)
    return None


def _run_async_safe(async_func):
    """Safely executes Playwright async routines inside Streamlit's existing event loop."""
    def run_in_thread():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(async_func())
        finally:
            new_loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_thread)
        return future.result()


# ---------------------------------------------------------
# 1. SMART SOCIAL CARD WITH DYNAMIC SIZES & ORPHAN PREVENTION
# ---------------------------------------------------------
def create_ummat_social_card(
    headline_text: str, 
    news_img_path=None, 
    template_path=None, 
    font_path=None, 
    output_path: str = "social_card.png",
    card_width: int = 1080,
    card_height: int = 1350
) -> str:
    try:
        card_width = int(card_width)
        card_height = int(card_height)
    except (TypeError, ValueError):
        card_width = 1080
        card_height = 1350

    clean_headline = str(headline_text).replace('TITLE:', '').replace('CONTENT:', '').replace('ٹائٹل:', '').strip()
    if not clean_headline:
        clean_headline = "یہاں خبر کی اردو سرخی آئے گی۔"

    valid_news_img = None
    if news_img_path:
        if hasattr(news_img_path, "getvalue") or isinstance(news_img_path, (bytes, bytearray)):
            valid_news_img = news_img_path
        else:
            clean_p = str(news_img_path).strip().strip("'").strip('"')
            if os.path.exists(clean_p) and os.path.getsize(clean_p) > 200:
                valid_news_img = os.path.abspath(clean_p)
            elif os.path.exists(resource_path(clean_p)) and os.path.getsize(resource_path(clean_p)) > 200:
                valid_news_img = resource_path(clean_p)

    if not valid_news_img:
        print("⚠️ No valid local image provided, generating AI background fallback...")
        news_img_path = fetch_ai_generated_image(clean_headline, output_path="temp_ai_bg.jpg", width=card_width, height=card_height)
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
            "jameel custom.ttf",
            "Jameel Custom.ttf",
            "jameel_custom.ttf",
            "JameelCustom.ttf",
            "Jameel Noori Nastaleeq.ttf", 
            "Jameel Noori Nastaleeq Regular.ttf", 
            "Jameel Noori Kasheeda.ttf",
            "urdu_font.ttf"
        ]
        for f in possible_fonts:
            resolved_font = resource_path(f)
            if os.path.exists(resolved_font):
                font_path = resolved_font
                break

    font_b64 = font_to_base64(font_path)

    char_len = len(clean_headline)
    scale_factor = card_width / 1080.0

    if char_len <= 30:
        base_size = 135
    elif char_len <= 55:
        base_size = 115
    elif char_len <= 80:
        base_size = 102
    else:
        base_size = 90

    initial_font_size = int(base_size * scale_factor)

    # Dynamic layout positioning based on aspect ratio & dimensions
    photo_top = int(card_height * 0.05)
    photo_height = int(card_height * 0.54)
    headline_top = int(card_height * 0.60)
    headline_height = int(card_height * 0.28)
    headline_left = int(card_width * 0.04)
    headline_width = int(card_width * 0.92)

    font_face_css = f"@font-face {{ font-family: 'Jameel Custom'; src: url('{font_b64}') format('truetype'); font-weight: normal; font-style: normal; }}" if font_b64 else ""

    html_content = f"""
    <!DOCTYPE html>
    <html lang="ur">
    <head>
        <meta charset="UTF-8">
        <style>
            {font_face_css}

            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                width: {card_width}px;
                height: {card_height}px;
                position: relative;
                background-color: #0f172a;
                overflow: hidden;
                font-family: 'Jameel Custom', 'Jameel Noori Nastaleeq', Arial, sans-serif !important;
            }}
            .news-photo {{
                position: absolute; 
                top: {photo_top}px; 
                left: 0; 
                width: {card_width}px; 
                height: {photo_height}px; 
                object-fit: cover; 
                z-index: 1;
            }}
            .frame-overlay {{
                position: absolute; 
                top: 0; 
                left: 0; 
                width: {card_width}px; 
                height: {card_height}px; 
                z-index: 2; 
                pointer-events: none;
            }}
            .headline-container {{
                position: absolute; 
                top: {headline_top}px; 
                left: {headline_left}px; 
                width: {headline_width}px; 
                height: {headline_height}px; 
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
                font-size: {initial_font_size}px; 
                line-height: 1.22;
                text-wrap: balance;
                word-break: keep-all;
                white-space: normal;
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
            <feMorphology operator="dilate" radius="0.35" in="SourceAlpha" result="thicken" />
            <feMerge>
              <feMergeNode in="thicken" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </svg>

        {"<img class='news-photo' src='" + news_img_b64 + "'>" if news_img_b64 else ""}
        {"<img class='frame-overlay' src='" + template_b64 + "'>" if template_b64 else ""}
        <div class="headline-container">
            <div id="headline" class="headline-text">{clean_headline}</div>
        </div>
    </body>
    </html>
    """

    async def _generate():
        try:
            async with async_playwright() as p:
                browser = await launch_browser_safely(p)
                page = await browser.new_page(viewport={"width": card_width, "height": card_height})
                await page.set_content(html_content, wait_until="networkidle")
                await page.wait_for_timeout(300)

                # Responsive Nastaliq balance & multi-line adjustment
                await page.evaluate(f"""() => {{
                    const el = document.getElementById('headline');
                    if (!el) return;

                    let size = parseFloat(window.getComputedStyle(el).fontSize);
                    const maxHeight = {headline_height};

                    for (let i = 0; i < 30; i++) {{
                        const h = el.offsetHeight;
                        if (h > (maxHeight * 0.75) && size > 40) {{
                            size -= 1.5;
                            el.style.fontSize = size + 'px';
                            el.style.lineHeight = '1.20';
                        }} else {{
                            break;
                        }}
                    }}

                    if (el.offsetHeight > (maxHeight * 0.80)) {{
                        el.style.lineHeight = '1.14';
                    }}
                }}""")
                
                await page.wait_for_timeout(200)
                abs_out = os.path.abspath(output_path)
                os.makedirs(os.path.dirname(abs_out) if os.path.dirname(abs_out) else '.', exist_ok=True)
                await page.screenshot(path=abs_out, full_page=True)
                await browser.close()
                print(f"✅ Social Card Generated ({card_width}x{card_height}) -> {abs_out}")
        except Exception as e:
            print(f"❌ Social Card Error: {e}")

    _run_async_safe(_generate)
    return output_path

# Export alias mapping
generate_custom_card = create_ummat_social_card


# ---------------------------------------------------------
# 2. PRO YOUTUBE 16:9 THUMBNAIL
# ---------------------------------------------------------
def make_youtube_169_thumbnail(
    headline_text: str = None, 
    script_text: str = None, 
    news_img_path=None, 
    logo_path=None, 
    output_path: str = "yt_thumb_169.png", 
    **kwargs
) -> str:
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

    if not news_img_path or not (isinstance(news_img_path, (bytes, bytearray)) or hasattr(news_img_path, "getvalue") or os.path.exists(str(news_img_path))):
        news_img_path = fetch_ai_generated_image(top_title, output_path="temp_ai_bg.jpg", width=1280, height=720)

    news_img_b64 = img_to_base64(news_img_path)
    logo_b64 = img_to_base64(final_logo_path)

    bg_style = f"background-image: url('{news_img_b64}'); background-size: cover; background-position: center;" if news_img_b64 else "background: #0f172a;"

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
                {"<img class='logo' src='" + logo_b64 + "'>" if logo_b64 else ""}
            </div>
        </div>
    </body>
    </html>
    """

    async def _generate():
        try:
            async with async_playwright() as p:
                browser = await launch_browser_safely(p)
                page = await browser.new_page(viewport={"width": 1280, "height": 720})
                await page.set_content(html_content, wait_until="networkidle")
                await page.wait_for_timeout(400)
                
                abs_out = os.path.abspath(output_path)
                os.makedirs(os.path.dirname(abs_out) if os.path.dirname(abs_out) else '.', exist_ok=True)
                await page.screenshot(path=abs_out)
                await browser.close()
                print(f"✅ YT Thumbnail Generated -> {abs_out}")
        except Exception as e:
            print(f"❌ YT Thumbnail Error: {e}")

    _run_async_safe(_generate)
    return output_path


# ---------------------------------------------------------
# 3. SHORTS 9:16 COVER
# ---------------------------------------------------------
def make_shorts_916_cover(
    urdu_text: str, 
    english_title: str = "www.ummat.net", 
    news_img_path=None, 
    logo_path=None, 
    output_path: str = "shorts_cover_916.png"
) -> str:
    final_logo_path = None
    possible_logos = [logo_path, "ummat bug final.png"]
    for l in possible_logos:
        if l:
            resolved_logo = resource_path(str(l))
            if os.path.exists(resolved_logo):
                final_logo_path = resolved_logo
                break

    clean_text = str(urdu_text).replace("ٹائٹل:", "").replace("TITLE:", "").replace("Headline:", "").strip()
    
    if not news_img_path or not (isinstance(news_img_path, (bytes, bytearray)) or hasattr(news_img_path, "getvalue") or os.path.exists(str(news_img_path))):
        news_img_path = fetch_ai_generated_image(urdu_text, output_path="temp_ai_shorts_bg.jpg", width=1080, height=1920)

    news_img_b64 = img_to_base64(news_img_path)
    logo_b64 = img_to_base64(final_logo_path)

    bg_style = f"background-image: url('{news_img_b64}'); background-size: cover; background-position: center;" if news_img_b64 else "background-color: #0f172a;"

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
        {"<img class='logo' src='" + logo_b64 + "'>" if logo_b64 else ""}
        <div class="text-card">{clean_text}</div>
    </body>
    </html>
    """

    async def _generate():
        try:
            async with async_playwright() as p:
                browser = await launch_browser_safely(p)
                page = await browser.new_page(viewport={"width": 1080, "height": 1920})
                await page.set_content(html_content, wait_until="networkidle")
                await page.wait_for_timeout(400)
                
                abs_out = os.path.abspath(output_path)
                os.makedirs(os.path.dirname(abs_out) if os.path.dirname(abs_out) else '.', exist_ok=True)
                
                await page.screenshot(path=abs_out, full_page=True)
                await browser.close()
                print(f"✅ Shorts Cover Generated -> {abs_out}")
        except Exception as e:
            print(f"❌ Shorts Cover Error: {e}")

    _run_async_safe(_generate)
    return output_path