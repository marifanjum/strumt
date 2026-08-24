import os
import sys
import json
import base64
import tempfile
import glob
from datetime import datetime
from PIL import Image, ImageOps
from playwright.sync_api import sync_playwright
import streamlit as st

# ---------------------------------------------------------
# 1. PAGE SETUP & CONFIG
# ---------------------------------------------------------
st.set_page_config(
    page_title="NewsApp2026 - AI Social Card Studio",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

def get_output_dir():
    out_dir = os.path.join(tempfile.gettempdir(), "NewsAppOutputs")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir

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
    if not img_path or not os.path.exists(str(img_path)):
        return ""
    try:
        with open(str(img_path), "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
            ext = str(img_path).split(".")[-1].lower()
            mime = "image/png" if ext == "png" else "image/jpeg"
            return f"data:{mime};base64,{b64}"
    except Exception as e:
        print(f"Base64 Error ({img_path}):", e)
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
    for c in candidates:
        if c and os.path.exists(c):
            try:
                with open(c, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
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
        "/usr/lib/chromium-browser/chromium-browser"
    ]
    for path in system_paths:
        if os.path.exists(path):
            return path
    return None

# ---------------------------------------------------------
# 2. IMAGE PREPROCESSING
# ---------------------------------------------------------
def prepare_image(img_path, target_w, target_h, remove_bg=False):
    if not os.path.exists(str(img_path)):
        return ""

    img = Image.open(str(img_path)).convert("RGBA")
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
    temp_out = os.path.join(temp_dir, f"temp_var_{os.path.basename(str(img_path))}.png")
    img.save(temp_out, "PNG")
    return temp_out

# ---------------------------------------------------------
# 3. AI STRUCTURE & CARD RENDERING ENGINE
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
        st.warning(f"AI auto-parser notice: Defaulting to structured segmentation ({e})")

    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    return {
        "headline": lines[0] if len(lines) > 1 else "",
        "body": "\n".join(lines[1:]) if len(lines) > 1 else raw_text,
        "citation": "",
        "remove_bg_1": False,
        "suggested_layout": "dual_split" if img_count >= 2 else "single_split",
        "accent_color": "#dc2626"
    }

def render_html_to_image(template_path, image_paths, raw_text, layout_override, design, prefix="card"):
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
        <div class="banner-box"><img class="img-banner" src="{b1}"></div>
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
    else:
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
            .top-hero {{
                position: absolute; top: 215px; left: 65px; width: 950px; height: 280px;
                z-index: 5; display: flex; flex-direction: row-reverse; align-items: center; justify-content: space-between;
            }}
            .headline-box {{
                flex: 1; direction: rtl; text-align: right; padding-left: 20px;
                font-size: 60px; font-weight: bold; color: #0f172a; line-height: 1.35;
                font-family: 'Jameel Custom', 'Jameel Noori Nastaleeq', Arial, sans-serif !important;
            }}
            .single-image {{ width: 390px; height: 270px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }}
            .img-frame {{ width: 390px; height: 270px; object-fit: cover; border: 3px solid #0f172a; border-radius: 8px; box-shadow: 0 10px 22px rgba(0,0,0,0.3); }}
            .img-cutout {{ max-width: 390px; max-height: 280px; filter: drop-shadow(0 12px 20px rgba(0,0,0,0.45)); }}
            .dual-images {{ display: flex; gap: 10px; flex-shrink: 0; }}
            .img-frame-dual {{ width: 215px; height: 270px; object-fit: cover; border: 3px solid #0f172a; border-radius: 6px; box-shadow: 0 8px 18px rgba(0,0,0,0.3); }}
            .banner-box {{ position: absolute; top: 215px; left: 65px; width: 950px; height: 420px; z-index: 5; }}
            .img-banner {{ width: 950px; height: 420px; object-fit: cover; border: 3px solid #0f172a; border-radius: 8px; box-shadow: 0 10px 22px rgba(0,0,0,0.3); }}
            .banner-text-box {{ position: absolute; top: 660px; left: 65px; width: 950px; height: 300px; z-index: 5; direction: rtl; }}
            .quote-spotlight-box {{ position: absolute; top: 260px; left: 85px; width: 910px; height: 680px; z-index: 5; direction: rtl; display: flex; flex-direction: column; justify-content: center; }}
            .body-section {{
                position: absolute; top: 515px; left: 65px; width: 950px; height: 445px;
                z-index: 5; display: flex; flex-direction: row-reverse; align-items: stretch;
            }}
            .accent-bar {{ width: 8px; border-radius: 4px; margin-left: 18px; flex-shrink: 0; }}
            .body-text {{
                flex: 1; direction: rtl; text-align: justify; text-justify: inter-word;
                color: #0f172a; padding-left: 10px; font-family: 'Jameel Custom', 'Jameel Noori Nastaleeq', Arial, sans-serif !important;
            }}
            .citation-section {{
                position: absolute; top: 975px; left: 65px; width: 950px; height: 60px;
                z-index: 5; direction: rtl; display: flex; align-items: center; justify-content: flex-start; gap: 15px;
            }}
            .citation-pill {{ width: 14px; height: 34px; background-color: #ffffff; border-radius: 3px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }}
            .citation-text {{
                font-size: 34px; color: #ffffff; font-weight: bold; font-family: 'Jameel Custom', 'Jameel Noori Nastaleeq', Arial, sans-serif !important;
                text-shadow: 0 2px 5px rgba(0,0,0,0.7);
            }}
        </style>
    </head>
    <body>
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
    output_path = os.path.join(out_dir, f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")

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
# 4. SIDEBAR SETTINGS & ENGINE CONFIG
# ---------------------------------------------------------
config = load_settings()

with st.sidebar:
    st.header("⚙️ Global Settings")
    pin = st.text_input("Admin PIN", type="password", placeholder="Enter 6-digit PIN")
    
    if pin == PASSWORD_PIN:
        st.success("Admin Panel Unlocked")
        gemini_key = st.text_input("Gemini API Key", value=config.get("gemini_api_key", ""), type="password")
        gemini_model = st.text_input("Gemini Model", value=config.get("gemini_model", "gemini-2.5-flash"))
        openai_key = st.text_input("OpenAI API Key", value=config.get("openai_api_key", ""), type="password")
        openai_model = st.text_input("OpenAI Model", value=config.get("openai_model", "gpt-4o"))
        groq_key = st.text_input("Groq API Key", value=config.get("groq_api_key", ""), type="password")
        groq_model = st.text_input("Groq Model", value=config.get("groq_model", "llama-3.2-11b-vision-preview"))

        if st.button("Save Settings", use_container_width=True):
            save_settings({
                "gemini_api_key": gemini_key.strip(),
                "gemini_model": gemini_model.strip(),
                "openai_api_key": openai_key.strip(),
                "openai_model": openai_model.strip(),
                "groq_api_key": groq_key.strip(),
                "groq_model": groq_model.strip()
            })
            st.toast("Settings saved successfully!", icon="✅")
    elif pin:
        st.error("Invalid PIN")

# ---------------------------------------------------------
# 5. MULTI-TAB APPLICATION INTERFACE
# ---------------------------------------------------------
st.title("NewsApp2026 Studio")

tab1, tab2, tab3, tab4 = st.tabs([
    "🎨 Story Card Studio", 
    "🔗 URL / Quick Card", 
    "📦 Batch Producer", 
    "📁 Generated Archive"
])

# ==========================================
# TAB 1: STORY CARD STUDIO
# ==========================================
with tab1:
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("Card Configuration")
        c1_prov, c1_layout = st.columns(2)
        with c1_prov:
            provider = st.selectbox("Vision AI Engine", ["Gemini", "OpenAI", "Groq"], key="t1_prov")
        with c1_layout:
            layout_style = st.selectbox(
                "Layout Style",
                [
                    "Auto (AI Decides)",
                    "Single Split (Story Share)",
                    "Hero Banner (Wide Photo + Breaking News)",
                    "Big Quote (Editorial Spotlight)"
                ],
                key="t1_layout"
            )

        uploaded_images = st.file_uploader(
            "Subject Images (1 or 2 files)",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="t1_imgs"
        )

        raw_text = st.text_area(
            "Urdu News / Story Text",
            height=220,
            placeholder="یہاں خبر، سرخی، اقتباس یا مکمل متن درج کریں...",
            key="t1_text"
        )

        gen_btn = st.button("✨ Generate Social Card", type="primary", use_container_width=True, key="t1_gen")

    with col2:
        st.subheader("Card Live Preview")
        preview_box = st.empty()

        if gen_btn:
            if not raw_text.strip():
                st.warning("Please paste or type the Urdu news content.")
            else:
                with st.spinner("Analyzing text layout & generating card..."):
                    saved_paths = []
                    if uploaded_images:
                        t_dir = get_output_dir()
                        for f in uploaded_images[:2]:
                            p = os.path.join(t_dir, f.name)
                            with open(p, "wb") as buffer:
                                buffer.write(f.read())
                            saved_paths.append(p)

                    layout_map = {
                        "Auto (AI Decides)": "Auto (AI Decides)",
                        "Single Split (Story Share)": "single_split",
                        "Hero Banner (Wide Photo + Breaking News)": "hero_banner",
                        "Big Quote (Editorial Spotlight)": "big_quote"
                    }
                    chosen = layout_map.get(layout_style, "single_split")

                    try:
                        design = analyze_editorial(raw_text, saved_paths, provider, config)
                        card_path = render_html_to_image("StoryShareTemplate.png", saved_paths, raw_text, chosen, design, prefix="story_card")
                        
                        preview_box.image(card_path, use_container_width=True)
                        with open(card_path, "rb") as file_data:
                            st.download_button(
                                label="📥 Download Card (High-Res)",
                                data=file_data.read(),
                                file_name=os.path.basename(card_path),
                                mime="image/png",
                                use_container_width=True
                            )
                    except Exception as e:
                        st.error(f"Card generation error: {str(e)}")

# ==========================================
# TAB 2: URL / QUICK CARD
# ==========================================
with tab2:
    st.subheader("Generate Direct Card from Web URL / Article")
    col_u1, col_u2 = st.columns([1, 1], gap="large")

    with col_u1:
        target_url = st.text_input("News Article URL", placeholder="https://example.com/news-story")
        url_text = st.text_area("Or Quick Headline & Summary", height=140, placeholder="سوشل میڈیا سرخی اور متن...")
        url_img = st.file_uploader("Featured Article Image", type=["png", "jpg", "jpeg", "webp"], key="t2_img")
        url_btn = st.button("🚀 Render URL Quick Card", type="primary", use_container_width=True, key="t2_btn")

    with col_u2:
        st.subheader("Generated URL Preview")
        url_preview = st.empty()

        if url_btn:
            content_to_use = url_text.strip() or f"Breaking News Story:\n{target_url}"
            with st.spinner("Processing article content..."):
                saved_paths = []
                if url_img:
                    t_dir = get_output_dir()
                    p = os.path.join(t_dir, url_img.name)
                    with open(p, "wb") as buffer:
                        buffer.write(url_img.read())
                    saved_paths.append(p)

                try:
                    design = analyze_editorial(content_to_use, saved_paths, "Gemini", config)
                    out_path = render_html_to_image("StoryShareTemplate.png", saved_paths, content_to_use, "single_split", design, prefix="url_card")
                    
                    url_preview.image(out_path, use_container_width=True)
                    with open(out_path, "rb") as f_data:
                        st.download_button(
                            label="📥 Download URL Card",
                            data=f_data.read(),
                            file_name=os.path.basename(out_path),
                            mime="image/png",
                            use_container_width=True
                        )
                except Exception as e:
                    st.error(f"URL card generation failed: {str(e)}")

# ==========================================
# TAB 3: BATCH PRODUCER
# ==========================================
with tab3:
    st.subheader("Batch News Card Processing")
    st.caption("Paste multiple stories separated by '---' to render and download cards simultaneously.")

    batch_input = st.text_area(
        "Batch Urdu Stories",
        height=260,
        placeholder="پہلی خبر کی سرخی اور متن\n---\nدوسری خبر کی سرخی اور تفصیل\n---\nتیسری اہم ترین بریکنگ نیوز..."
    )
    batch_btn = st.button("⚡ Process Batch Stories", type="primary")

    if batch_btn:
        stories = [s.strip() for s in batch_input.split("---") if s.strip()]
        if not stories:
            st.warning("Please provide at least one story block separated by '---'.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            batch_cols = st.columns(min(len(stories), 3))

            for idx, story in enumerate(stories):
                status_text.text(f"Processing story {idx+1} of {len(stories)}...")
                try:
                    design = analyze_editorial(story, [], "Gemini", config)
                    card_file = render_html_to_image("StoryShareTemplate.png", [], story, "big_quote", design, prefix=f"batch_card_{idx+1}")
                    
                    col_target = batch_cols[idx % 3]
                    with col_target:
                        st.image(card_file, caption=f"Story #{idx+1}")
                        with open(card_file, "rb") as bf:
                            st.download_button(
                                label=f"Download #{idx+1}",
                                data=bf.read(),
                                file_name=os.path.basename(card_file),
                                mime="image/png",
                                key=f"batch_dl_{idx}"
                            )
                except Exception as e:
                    st.error(f"Failed to process story #{idx+1}: {e}")

                progress_bar.progress((idx + 1) / len(stories))
            status_text.success("Batch generation complete!")

# ==========================================
# TAB 4: GENERATED ARCHIVE
# ==========================================
with tab4:
    st.subheader("Card Output Library")
    out_dir = get_output_dir()
    existing_cards = sorted(glob.glob(os.path.join(out_dir, "*.png")), key=os.path.getmtime, reverse=True)

    if not existing_cards:
        st.info("No rendered cards in this session yet. Generate cards in Tab 1, 2, or 3 to see them here.")
    else:
        st.write(f"Total Generated Assets: **{len(existing_cards)}**")
        arch_cols = st.columns(4)
        for i, card_path in enumerate(existing_cards[:16]):
            with arch_cols[i % 4]:
                st.image(card_path, use_container_width=True)
                with open(card_path, "rb") as cf:
                    st.download_button(
                        label="Download",
                        data=cf.read(),
                        file_name=os.path.basename(card_path),
                        mime="image/png",
                        key=f"arch_dl_{i}"
                    )
