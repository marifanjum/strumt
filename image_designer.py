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
    """Locates local Chromium on Windows, or returns None to let Playwright use its installed Linux binary on Streamlit Cloud."""
    if sys.platform != "win32":
        return None

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
    """Launches Playwright with mandatory container flags for Streamlit Cloud."""
    chrome_exe = get_chromium_executable_path()
    linux_args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--no-first-run",
        "--no-zygote",
        "--single-process"
    ]
    if chrome_exe:
        return await p.chromium.launch(executable_path=chrome_exe, headless=True, args=linux_args)
    else:
        return await p.chromium.launch(headless=True, args=linux_args)


try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None


def img_to_base64(img_source) -> str:
    if not img_source:
        return ""

    if hasattr(img_source, "getvalue"):
        raw_bytes = img_source.getvalue()
        return f"data:image/png;base64,{base64.b64encode(raw_bytes).decode('utf-8')}"

    if isinstance(img_source, (bytes, bytearray)):
        return f"data:image/png;base64,{base64.b64encode(img_source).decode('utf-8')}"

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
                mime = "image/jpeg" if ext in ["jpg", "jpeg"] else ("image/webp" if ext == "webp" else "image/png")
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
        temp_bg = os.path.join(tempfile.gettempdir(), "temp_ai_bg.jpg")
        news_img_path = fetch_ai_generated_image(clean_headline, output_path=temp_bg, width=card_width, height=card_height)
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
        async with async_playwright() as p:
            browser = await launch_browser_safely(p)
            page = await browser.new_page(viewport={"width": card_width, "height": card_height})
            await page.set_content(html_content, wait_until="networkidle")
            await page.wait_for_timeout(300)

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

    _run_async_safe(_generate)

    if not (os.path.exists(output_path) and os.path.getsize(output_path) > 0):
        raise RuntimeError(f"Playwright finished without writing image to {output_path}")

    return output_path

generate_custom_card = create_ummat_social_card
