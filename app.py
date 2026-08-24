import sys
import os
import glob
import json
import base64
import tempfile
from datetime import datetime
from PIL import Image, ImageOps, ImageDraw
from playwright.sync_api import sync_playwright
import streamlit as st

# ---------------------------------------------------------
# 1. PAGE SETUP & CONFIG RESOLUTION
# ---------------------------------------------------------
st.set_page_config(
    page_title="AI StoryShare Social Card Producer",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Styling to match your desktop app palette (#0E7BFE / #F3A038 / #0f172a)
st.markdown("""
<style>
    .stButton>button[kind="primary"] {
        background-color: #0E7BFE !important;
        color: white !important;
        font-weight: bold;
        border-radius: 4px;
        padding: 10px 16px;
    }
    .stDownloadButton>button {
        background-color: #F3A038 !important;
        color: #000000 !important;
        font-weight: bold;
        border-radius: 4px;
        padding: 10px 16px;
    }
    .preview-box {
        border: 2px dashed #94a3b8;
        background-color: #0f172a;
        color: #94a3b8;
        border-radius: 8px;
        min-height: 480px;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

PASSWORD_PIN = "999999"
CONFIG_FILE = "settings.json"

DEFAULT_CONFIG = {
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "openai_api_key": "",
    "openai_model": "gpt-4o",
    "groq_api_key": "",
    "groq_model": "llama-3.2-11b-vision-preview"
}

def resource_path(relative_path):
    if not relative_path:
        return ""
    if hasattr(sys, '_MEIPASS'):
        path_in_temp = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(path_in_temp):
            return path_in_temp
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.abspath(".")
    for sub in ["_internal", ""]:
        p = os.path.join(exe_dir, sub, relative_path) if sub else os.path.join(exe_dir, relative_path)
        if os.path.exists(p):
            return p
    return os.path.join(os.path.abspath("."), relative_path)

def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG

def save_settings(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def img_to_base64(img_path):
    if not img_path:
        return ""
    real_path = resource_path(str(img_path))
    if not os.path.exists(real_path):
        real_path = str(img_path)
    if os.path.exists(real_path):
        try:
            with open(real_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
                ext = str(real_path).split('.')[-1].lower()
                mime = "image/png" if ext == "png" else "image/jpeg"
                return f"data:{mime};base64,{b64}"
        except Exception as e:
            print(f"Base64 Error ({real_path}):", e)
    return ""

def font_to_base64(font_path=None):
    candidates = [
        font_path,
        "Jameel Noori Nastaleeq.ttf",
        "Jameel Noori Nastaleeq Regular.ttf",
        "JameelNooriNastaleeq.ttf",
        "JameelNoori.ttf",
        "jameel.ttf",
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
            with open(resolved, "rb") as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
                return f"data:font/ttf;charset=utf-8;base64,{b64}"
        except Exception as e:
            print("Font Base64 Error:", e)
    return ""

def get_chromium_executable_path():
    system_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        "/usr/lib/chromium-browser/chromium-browser",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Users\{}\AppData\Local\Google\Chrome\Application\chrome.exe".format(os.environ.get('USERNAME', '')),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Microsoft Edge\Application\msedge.exe"
    ]
    for path in system_paths:
        if os.path.exists(path):
            return path
    return None

def get_output_dir():
    home_downloads = os.path.expanduser("~/Downloads/NewsAppOutputs")
    try:
        os.makedirs(home_downloads, exist_ok=True)
        return home_downloads
    except Exception:
        fallback = os.path.join(tempfile.gettempdir(), "NewsAppOutputs")
        os.makedirs(fallback, exist_ok=True)
        return fallback

# ---------------------------------------------------------
# 2. IMAGE PREPROCESSING
# ---------------------------------------------------------
def prepare_image(img_path, target_w, target_h, remove_bg=False):
    real_path = resource_path(str(img_path))
    if not os.path.exists(real_path):
        real_path = str(img_path)
    if not os.path.exists(real_path):
        return ""

    img = Image.open(real_path).convert("RGBA")
    if remove_bg:
        try:
            from rembg import remove
            img = remove(img)
            img = ImageOps.fit(img, (int(target_w), int(target_h)), Image.Resampling.LANCZOS)
        except Exception as e:
            print("rembg error:", e)
    else:
        img = ImageOps.fit(img, (int(target_w), int(target_h)), Image.Resampling.LANCZOS)

    temp_dir = get_output_dir()
    temp_out = os.path.join(temp_dir, f"temp_var_{os.path.basename(real_path)}.png")
    img.save(temp_out, "PNG")
    return temp_out

# ---------------------------------------------------------
# 3. AI STRUCTURE & CARD RENDERING
# ---------------------------------------------------------
def analyze_editorial(raw_text, image_paths, provider, config):
    img_count = len(image_paths)
    prompt = f"""
    You are a Pakistani news art director (Daily Pakistan style).
    Analyze the raw Urdu text and {img_count} images.

    STRICT VERBATIM RULE:
    - NEVER drop, change, rewrite, or paraphrase ANY Urdu words.
    - Split verbatim text into:
      "headline": The title/punchline (e.g. before : or - or the first line).
      "body": The main quote or paragraph.
      "citation": Attribution/source line (if identified, else null).
    - "remove_bg_1": true if portrait cutout, false otherwise.
    - "suggested_layout":
        - If {img_count} >= 2: "dual_split"
        - If text is short (<100 chars) and {img_count} == 1: "hero_banner"
        - If {img_count} == 1: "single_split"
        - If {img_count} == 0: "big_quote"

    RAW TEXT:
    \"\"\"{raw_text}\"\"\"

    Return ONLY a raw JSON object:
    {{
      "headline": "...",
      "body": "...",
      "citation": "...",
      "remove_bg_1": false,
      "suggested_layout": "single_split",
      "accent_color": "#dc2626"
    }}
    """

    try:
        if provider == "Gemini" and config.get("gemini_api_key"):
            from google import genai
            client = genai.Client(api_key=config["gemini_api_key"])
            contents = [prompt]
            for p in image_paths[:2]:
                if os.path.exists(p):
                    contents.append(Image.open(p))

            response = client.models.generate_content(
                model=config.get("gemini_model", "gemini-2.5-flash"),
                contents=contents,
                config={"response_mime_type": "application/json"}
            )
            return json.loads(response.text)

        elif provider in ["OpenAI", "Groq"]:
            from openai import OpenAI
            if provider == "OpenAI" and config.get("openai_api_key"):
                client = OpenAI(api_key=config["openai_api_key"])
                model_name = config.get("openai_model", "gpt-4o")
            elif provider == "Groq" and config.get("groq_api_key"):
                client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=config["groq_api_key"])
                model_name = config.get("groq_model", "llama-3.2-11b-vision-preview")
            else:
                raise ValueError("API Key missing")

            messages_content = [{"type": "text", "text": prompt}]
            for p in image_paths[:2]:
                if os.path.exists(p):
                    messages_content.append({"type": "image_url", "image_url": {"url": img_to_base64(p)}})

            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": messages_content}],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.warning(f"AI Parsing Warning: {e}")

    # Fallback segmentation
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    return {
        "headline": lines[0] if len(lines) > 1 else "",
        "body": "\n".join(lines[1:]) if len(lines) > 1 else raw_text,
        "citation": "",
        "remove_bg_1": False,
        "suggested_layout": "dual_split" if img_count >= 2 else "single_split",
        "accent_color": "#dc2626"
    }

def render_html_sync(template_path, image_paths, raw_text, layout_override, design):
    template_b64 = img_to_base64(template_path)
    font_b64 = font_to_base64()

    headline = design.get("headline", "").strip() if design.get("headline") else ""
    body = design.get("body", "").strip() if design.get("body") else raw_text
    citation = design.get("citation", "").strip() if design.get("citation") else ""
    accent_color = design.get("accent_color", "#dc2626")
    img_count = len(image_paths)

    layout_type = layout_override if layout_override != "Auto (AI Decides)" else design.get("suggested_layout", "single_split")
    if img_count >= 2:
        layout_type = "dual_split"

    body_len = len(body)
    body_size = 28 if body_len > 400 else (32 if body_len > 250 else 38)
    line_h = 1.42 if body_len > 400 else 1.48

    # --- DYNAMIC LAYOUT BUILDER ---
    if layout_type == "dual_split" and img_count >= 2:
        p1 = prepare_image(image_paths[0], 215, 270, False)
        p2 = prepare_image(image_paths[1], 215, 270, False)
        b1, b2 = img_to_base64(p1), img_to_base64(p2)
        content_html = f"""
        <div class="top-hero">
            <div class="headline-box" style="font-size: 50px;">{headline}</div>
            <div class="dual-images">
                <img class="img-frame-dual" src="{b1}">
                <img class="img-frame-dual" src="{b2}">
            </div>
        </div>
        <div class="body-section">
            <div class="accent-bar" style="background-color: {accent_color};"></div>
            <div class="body-text" style="font-size: {body_size}px; line-height: {line_h};">{body}</div>
        </div>
        """
    elif layout_type == "hero_banner" and img_count >= 1:
        p1 = prepare_image(image_paths[0], 950, 420, False)
        b1 = img_to_base64(p1)
        content_html = f"""
        <div class="banner-box">
            <img class="img-banner" src="{b1}">
        </div>
        <div class="banner-text-box">
            <div class="headline-box" style="font-size: 58px; text-align: center;">{headline}</div>
            <div class="body-text" style="font-size: 34px; text-align: center; margin-top: 15px;">{body}</div>
        </div>
        """
    elif layout_type == "big_quote" or img_count == 0:
        content_html = f"""
        <div class="quote-spotlight-box">
            {f'<div class="headline-box" style="font-size: 64px; text-align: center; color: #dc2626; margin-bottom: 20px;">{headline}</div>' if headline else ''}
            <div class="body-text" style="font-size: 42px; line-height: 1.55; text-align: center;">{body}</div>
        </div>
        """
    else: # Standard Single Split
        is_cutout = design.get("remove_bg_1", False)
        p1 = prepare_image(image_paths[0], 390, 270, is_cutout)
        b1 = img_to_base64(p1)
        cls = "img-cutout" if is_cutout else "img-frame"
        content_html = f"""
        <div class="top-hero">
            <div class="headline-box">{headline}</div>
            <div class="single-image"><img class="{cls}" src="{b1}"></div>
        </div>
        <div class="body-section">
            <div class="accent-bar" style="background-color: {accent_color};"></div>
            <div class="body-text" style="font-size: {body_size}px; line-height: {line_h};">{body}</div>
        </div>
        """

    font_face_css = f"""
    @font-face {{
        font-family: 'Jameel Custom';
        src: url('{font_b64}') format('truetype');
        font-weight: normal;
        font-style: normal;
    }}
    """ if font_b64 else ""

    html = f"""
    <!DOCTYPE html>
    <html lang="ur">
    <head>
        <meta charset="UTF-8">
        <style>
            {font_face_css}
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                width: 1080px; height: 1350px; position: relative; overflow: hidden;
                background-color: #f59e0b;
                font-family: 'Jameel Custom', 'Jameel Noori Nastaleeq', Arial, sans-serif !important;
            }}
            .template-bg {{
                position: absolute; top: 0; left: 0; width: 1080px; height: 1350px;
                z-index: 1; pointer-events: none;
            }}

            /* Top Hero: Starts safely below NEWS STORY badge at y=215px */
            .top-hero {{
                position: absolute; top: 215px; left: 65px; width: 950px; height: 280px;
                z-index: 5; display: flex; flex-direction: row-reverse; align-items: center; justify-content: space-between;
            }}
            .headline-box {{
                flex: 1; direction: rtl; text-align: right; padding-left: 20px;
                font-size: 60px; font-weight: bold; color: #0f172a; line-height: 1.35;
                font-family: 'Jameel Custom', 'Jameel Noori Nastaleeq', Arial, sans-serif !important;
                filter: url(#bold-filter);
            }}

            .single-image {{ width: 390px; height: 270px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }}
            .img-frame {{ width: 390px; height: 270px; object-fit: cover; border: 3px solid #0f172a; border-radius: 8px; box-shadow: 0 10px 22px rgba(0,0,0,0.3); }}
            .img-cutout {{ max-width: 390px; max-height: 280px; filter: drop-shadow(0 12px 20px rgba(0,0,0,0.45)); }}

            .dual-images {{ display: flex; gap: 10px; flex-shrink: 0; }}
            .img-frame-dual {{ width: 215px; height: 270px; object-fit: cover; border: 3px solid #0f172a; border-radius: 6px; box-shadow: 0 8px 18px rgba(0,0,0,0.3); }}

            /* Banner Variant */
            .banner-box {{ position: absolute; top: 215px; left: 65px; width: 950px; height: 420px; z-index: 5; }}
            .img-banner {{ width: 950px; height: 420px; object-fit: cover; border: 3px solid #0f172a; border-radius: 8px; box-shadow: 0 10px 22px rgba(0,0,0,0.3); }}
            .banner-text-box {{ position: absolute; top: 660px; left: 65px; width: 950px; height: 300px; z-index: 5; direction: rtl; }}

            /* Big Quote Variant */
            .quote-spotlight-box {{ position: absolute; top: 260px; left: 85px; width: 910px; height: 680px; z-index: 5; direction: rtl; display: flex; flex-direction: column; justify-content: center; }}

            /* Body Quote */
            .body-section {{
                position: absolute; top: 515px; left: 65px; width: 950px; height: 445px;
                z-index: 5; display: flex; flex-direction: row-reverse; align-items: stretch;
            }}
            .accent-bar {{ width: 8px; border-radius: 4px; margin-left: 18px; flex-shrink: 0; }}
            .body-text {{
                flex: 1; direction: rtl; text-align: justify; text-justify: inter-word;
                color: #0f172a; padding-left: 10px; font-family: 'Jameel Custom', 'Jameel Noori Nastaleeq', Arial, sans-serif !important;
                filter: url(#bold-filter);
            }}

            /* Citation Footer */
            .citation-section {{
                position: absolute; top: 975px; left: 65px; width: 950px; height: 60px;
                z-index: 5; direction: rtl; display: flex; align-items: center; justify-content: flex-start; gap: 15px;
            }}
            .citation-pill {{ width: 14px; height: 34px; background-color: #ffffff; border-radius: 3px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }}
            .citation-text {{
                font-size: 34px; color: #ffffff; font-weight: bold; font-family: 'Jameel Custom', 'Jameel Noori Nastaleeq', Arial, sans-serif !important;
                text-shadow: 0 2px 5px rgba(0,0,0,0.7); filter: url(#bold-filter);
            }}
        </style>
    </head>
    <body>
        <svg style="position: absolute; width: 0; height: 0; overflow: hidden;">
          <filter id="bold-filter">
            <feMorphology operator="dilate" radius="0.35" in="SourceAlpha" result="thicken" />
            <feMerge><feMergeNode in="thicken" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </svg>

        <img class="template-bg" src="{template_b64}">

        {content_html}

        {f'''
        <div class="citation-section">
            <div class="citation-pill"></div>
            <div class="citation-text">{citation}</div>
        </div>
        ''' if citation else ''}
    </body>
    </html>
    """

    out_dir = get_output_dir()
    output_path = os.path.join(out_dir, f"url_card_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")

    with sync_playwright() as p:
        chrome_exe = get_chromium_executable_path()
        launch_kwargs = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        if chrome_exe:
            launch_kwargs["executable_path"] = chrome_exe

        browser = p.chromium.launch(**launch_kwargs)
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        page.set_content(html, wait_until="networkidle")
        page.wait_for_timeout(450)
        page.screenshot(path=output_path, full_page=True)
        browser.close()

    return output_path

# ---------------------------------------------------------
# 4. SETTINGS MODAL DIALOG (PIN: 999999)
# ---------------------------------------------------------
config = load_settings()

if "@settings_modal" in dir(st):
    # Streamlit 1.34+ Dialog API
    @st.dialog("API Configuration")
    def show_settings_modal():
        st.write("<b>Gemini Vision Engine</b>", unsafe_allow_html=True)
        g_key = st.text_input("Gemini API Key", value=config.get("gemini_api_key", ""), type="password")
        g_model = st.text_input("Gemini Model", value=config.get("gemini_model", "gemini-2.5-flash"))

        st.write("<b>OpenAI Vision Engine</b>", unsafe_allow_html=True)
        o_key = st.text_input("OpenAI API Key", value=config.get("openai_api_key", ""), type="password")
        o_model = st.text_input("OpenAI Model", value=config.get("openai_model", "gpt-4o"))

        st.write("<b>Groq Vision Engine</b>", unsafe_allow_html=True)
        gr_key = st.text_input("Groq API Key", value=config.get("groq_api_key", ""), type="password")
        gr_model = st.text_input("Groq Model", value=config.get("groq_model", "llama-3.2-11b-vision-preview"))

        if st.button("Save Settings", type="primary", use_container_width=True):
            save_settings({
                "gemini_api_key": g_key.strip(),
                "gemini_model": g_model.strip(),
                "openai_api_key": o_key.strip(),
                "openai_model": o_model.strip(),
                "groq_api_key": gr_key.strip(),
                "groq_model": gr_model.strip(),
            })
            st.success("Settings saved successfully!")
            st.rerun()

# ---------------------------------------------------------
# 5. MAIN APPLICATION GUI
# ---------------------------------------------------------
if "last_card" not in st.session_state:
    st.session_state.last_card = None

st.subheader("AI StoryShare Social Card Producer")

# Splitter: Left Controls vs Right Preview
left_panel, right_panel = st.columns([1, 1], gap="large")

with left_panel:
    # Top Bar: Vision AI Selector + Settings Button
    top_c1, top_c2, top_c3 = st.columns([1.2, 2.2, 1.2])
    with top_c1:
        st.markdown("<p style='padding-top:8px; font-weight:bold;'>Vision AI:</p>", unsafe_allow_html=True)
    with top_c2:
        provider = st.selectbox("Vision AI", ["Gemini", "OpenAI", "Groq"], label_visibility="collapsed")
    with top_c3:
        with st.popover("⚙ Settings"):
            pin_input = st.text_input("Enter 6-digit PIN", type="password")
            if pin_input == PASSWORD_PIN:
                st.markdown("---")
                g_key = st.text_input("Gemini Key", value=config.get("gemini_api_key", ""), type="password")
                g_model = st.text_input("Gemini Model", value=config.get("gemini_model", "gemini-2.5-flash"))
                o_key = st.text_input("OpenAI Key", value=config.get("openai_api_key", ""), type="password")
                o_model = st.text_input("OpenAI Model", value=config.get("openai_model", "gpt-4o"))
                gr_key = st.text_input("Groq Key", value=config.get("groq_api_key", ""), type="password")
                gr_model = st.text_input("Groq Model", value=config.get("groq_model", "llama-3.2-11b-vision-preview"))
                if st.button("Save Settings", key="pop_save"):
                    save_settings({
                        "gemini_api_key": g_key.strip(),
                        "gemini_model": g_model.strip(),
                        "openai_api_key": o_key.strip(),
                        "openai_model": o_model.strip(),
                        "groq_api_key": gr_key.strip(),
                        "groq_model": gr_model.strip()
                    })
                    st.success("Saved!")
                    st.rerun()
            elif pin_input:
                st.error("Incorrect PIN.")

    # Layout Selector
    l_c1, l_c2 = st.columns([1.5, 3.5])
    with l_c1:
        st.markdown("<p style='padding-top:8px;'><b>Card Layout Style:</b></p>", unsafe_allow_html=True)
    with l_c2:
        layout_choice = st.selectbox(
            "Card Layout Style",
            [
                "Auto (AI Decides)",
                "Single Split (Story Share)",
                "Hero Banner (Wide Photo + Breaking News)",
                "Big Quote (Editorial Spotlight)"
            ],
            label_visibility="collapsed"
        )

    # Subject Images
    st.markdown("<b>Subject Images (Supports 1 or 2):</b>", unsafe_allow_html=True)
    uploaded_files = st.file_uploader(
        "Subject Images",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )

    # Raw Urdu Text Input
    st.markdown("<b>Raw Urdu Story / News Content (Single Box):</b>", unsafe_allow_html=True)
    raw_text = st.text_area(
        "Urdu Story",
        height=180,
        placeholder="یہاں خبر، سرخی، اقتباس یا مکمل متن درج کریں...",
        label_visibility="collapsed"
    )

    generate_clicked = st.button("Generate Variable Social Card", type="primary", use_container_width=True)

with right_panel:
    if generate_clicked:
        real_template = resource_path("StoryShareTemplate.png")
        if not os.path.exists(real_template) and not os.path.exists("StoryShareTemplate.png"):
            st.error("Template Missing: Please make sure 'StoryShareTemplate.png' is placed in the application root directory.")
        elif not raw_text.strip():
            st.warning("Missing Content: Please paste Urdu content into the text area.")
        else:
            with st.spinner("Rendering social card..."):
                saved_images = []
                if uploaded_files:
                    temp_dir = get_output_dir()
                    for f in uploaded_files[:2]:
                        img_path = os.path.join(temp_dir, f.name)
                        with open(img_path, "wb") as bf:
                            bf.write(f.read())
                        saved_images.append(img_path)

                layout_map = {
                    "Auto (AI Decides)": "Auto (AI Decides)",
                    "Single Split (Story Share)": "single_split",
                    "Hero Banner (Wide Photo + Breaking News)": "hero_banner",
                    "Big Quote (Editorial Spotlight)": "big_quote"
                }
                chosen_layout = layout_map.get(layout_choice, "single_split")

                try:
                    design = analyze_editorial(raw_text.strip(), saved_images, provider, config)
                    out_path = render_html_sync("StoryShareTemplate.png", saved_images, raw_text.strip(), chosen_layout, design)
                    st.session_state.last_card = out_path
                except Exception as e:
                    st.error(f"Generation Failed: Error: {str(e)}")

    if st.session_state.last_card and os.path.exists(st.session_state.last_card):
        st.image(st.session_state.last_card, use_container_width=True)
        with open(st.session_state.last_card, "rb") as file_data:
            st.download_button(
                label="Save Card to Disk",
                data=file_data.read(),
                file_name=os.path.basename(st.session_state.last_card),
                mime="image/png",
                use_container_width=True
            )
    else:
        st.markdown(
            '<div class="preview-box">Card Preview will appear here</div>',
            unsafe_allow_html=True
        )
        st.button("Save Card to Disk", disabled=True, use_container_width=True)
