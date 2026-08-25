import sys
import subprocess
import streamlit as st

@st.cache_resource
def ensure_playwright_installed():
    try:
        # Install chromium and any missing linux OS dependencies
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"],
            check=True
        )
    except Exception as e:
        print(f"Playwright installation note: {e}")

ensure_playwright_installed()

import os
import io
import re
import json
import tempfile
import pathlib
import urllib.parse
from datetime import datetime

import requests
import markdown
from bs4 import BeautifulSoup
import streamlit as st
from cryptography.fernet import Fernet
from PIL import Image, ImageDraw, ImageFont, ImageOps
import arabic_reshaper
from bidi.algorithm import get_display

# Core Modules
from wp_publisher import post_to_wordpress, get_media_id_from_url, fetch_wordpress_categories
from image_designer import generate_custom_card
from ai_news_generator import generate_ai_news
from social_manager_tab import render_social_manager_tab
from image_resizer_tab import render_image_resizer_tab


# ---------------------------------------------------------
# 1. PAGE SETUP & ENCRYPTED CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="Ummat News Studio & Publisher Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# RTL Urdu Nastaliq CSS Injection
st.markdown("""
    <style>
        .urdu-text, textarea[aria-label*="Urdu"], textarea[aria-label*="Story Text"], textarea[aria-label*="Headline"], input[aria-label*="Card Headline"] {
            font-family: 'Jameel Noori Nastaleeq', 'Jameel Custom', 'Noto Nastaliq Urdu', Arial, sans-serif !important;
            direction: rtl !important;
            text-align: right !important;
            font-size: 19px !important;
            line-height: 1.8 !important;
        }
    </style>
""", unsafe_allow_html=True)


def get_or_create_cipher() -> Fernet:
    key_file = "secret.key"
    if os.path.exists(key_file):
        with open(key_file, "rb") as kf:
            key = kf.read()
    else:
        key = Fernet.generate_key()
        with open(key_file, "wb") as kf:
            kf.write(key)
    return Fernet(key)


def load_master_config() -> dict:
    default_config = {
        "wp_url": "",
        "wp_user": "",
        "wp_pass": "",
        "ai_provider": "Groq (Llama)",
        "groq_key": "",
        "groq_model": "llama-3.3-70b-versatile",
        "gemini_key": "",
        "gemini_model": "gemini-2.5-flash",
        "openai_key": "",
        "openai_model": "gpt-4o",
        "output_dir": str(pathlib.Path.home() / "Downloads" / "NewsAppOutputs"),
        "logo_path": "ummat bug final.png",
        "resizer_width": 1200,
        "resizer_height": 720,
        "card_width": 1080,
        "card_height": 1350
    }
    config_file = "config.encrypted"
    if os.path.exists(config_file):
        try:
            cipher = get_or_create_cipher()
            with open(config_file, "rb") as f:
                encrypted_data = f.read()
            decrypted_data = cipher.decrypt(encrypted_data)
            loaded_data = json.loads(decrypted_data.decode('utf-8'))
            default_config.update(loaded_data)
        except Exception as e:
            print(f"⚠️ Notice reading config: {e}")
    return default_config


def save_master_config(config_dict: dict) -> bool:
    try:
        cipher = get_or_create_cipher()
        json_bytes = json.dumps(config_dict, indent=4).encode('utf-8')
        encrypted_bytes = cipher.encrypt(json_bytes)
        with open("config.encrypted", "wb") as f:
            f.write(encrypted_bytes)
        return True
    except Exception as e:
        print(f"❌ Config saving error: {e}")
        return False


config = load_master_config()


def get_api_credentials(provider_name: str):
    if provider_name == "Groq (Llama)":
        return config.get("groq_key", "").strip(), config.get("groq_model", "llama-3.3-70b-versatile").strip()
    elif provider_name == "Google Gemini":
        return config.get("gemini_key", "").strip(), config.get("gemini_model", "gemini-2.5-flash").strip()
    else:
        return config.get("openai_key", "").strip(), config.get("openai_model", "gpt-4o").strip()


def sanitize_seo_text(raw_text: str) -> str:
    cleaned = raw_text.strip()
    cleaned = re.sub(
        r'^(Description|SEO Description|Summary|Short Description|Hashtags|Tags|SEO|Keywords)\s*:\s*', 
        '', 
        cleaned, 
        flags=re.IGNORECASE | re.MULTILINE
    )
    cleaned = re.sub(
        r'(\n\s*)(Description|SEO Description|Summary|Short Description|Hashtags|Tags|SEO|Keywords)\s*:\s*', 
        r'\1', 
        cleaned, 
        flags=re.IGNORECASE
    )
    cleaned = re.sub(r'[*_`]', '', cleaned)
    cleaned = re.sub(r'^\s*#{1,6}\s+', '', cleaned, flags=re.MULTILINE)
    return cleaned.strip()


def resolve_font(font_names: list, size: int) -> ImageFont.FreeTypeFont:
    for f in font_names:
        if f and os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except Exception:
                continue
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def create_news_card(
    headline_text: str,
    news_img_source=None,
    width: int = 1200,
    height: int = 630,
    header_text: str = "UMMAT.NET | LATEST NEWS"
) -> Image.Image:
    img = Image.new('RGB', (width, height), color='#1e293b')
    draw = ImageDraw.Draw(img)

    # Top Header
    draw.rectangle([(0, 0), (width, 70)], fill='#0f172a')
    font_header = resolve_font(["arial.ttf", "Arial.ttf"], 28)
    draw.text((40, 20), header_text, fill="#38bdf8", font=font_header)

    # Center Box
    box_x1, box_y1 = 40, 85
    box_x2, box_y2 = width - 40, 430
    box_w, box_h = box_x2 - box_x1, box_y2 - box_y1

    if news_img_source:
        try:
            if isinstance(news_img_source, Image.Image):
                photo = news_img_source.convert('RGB')
            elif hasattr(news_img_source, "getvalue"):
                photo = Image.open(news_img_source).convert('RGB')
            elif isinstance(news_img_source, str) and os.path.exists(news_img_source):
                photo = Image.open(news_img_source).convert('RGB')
            else:
                photo = None

            if photo:
                fitted_photo = ImageOps.fit(photo, (box_w, box_h), Image.Resampling.LANCZOS)
                img.paste(fitted_photo, (box_x1, box_y1))
        except Exception:
            draw.rectangle([(box_x1, box_y1), (box_x2, box_y2)], fill='#334155')
    else:
        draw.rectangle([(box_x1, box_y1), (box_x2, box_y2)], fill='#334155', outline='#475569', width=2)

    # Footer
    draw.rectangle([(0, height - 30), (width, height)], fill='#0f172a')

    # Headline
    font_candidates = [
        "JameelNoori.ttf",
        "jameel custom.ttf",
        "Jameel Custom.ttf",
        "Jameel Noori Nastaleeq.ttf",
        "urdu_font.ttf"
    ]
    font_headline = resolve_font(font_candidates, 44)

    try:
        reshaped = arabic_reshaper.reshape(headline_text)
        bidi_text = get_display(reshaped)
    except Exception:
        bidi_text = headline_text

    text_y = (box_y2 + height - 30) // 2
    draw.text((width // 2, text_y), bidi_text, fill="#ffffff", font=font_headline, anchor="mm")
    return img


# ---------------------------------------------------------
# 2. MAIN NAVIGATION TABS
# ---------------------------------------------------------
st.title("⚡ Direct Story Publisher & News Studio Pro")

tab_pub, tab_resizer, tab_ai, tab_social, tab_url, tab_settings = st.tabs([
    "📝 Direct Story Publisher",
    "🖼️ Image Resizer & Collage",
    "🤖 AI News Studio",
    "🌐 Social Media Manager",
    "🔗 Card from URL",
    "⚙️ Branding Settings"
])


# =========================================================
# TAB 1: DIRECT STORY PUBLISHER
# =========================================================
with tab_pub:
    st.markdown("### 📝 Direct WordPress Story Publisher")

    story_input_val = st.session_state.get("pub_story_text", "")
    story_text = st.text_area(
        "Paste complete story text (Line 1: Title, Line 2: Excerpt, Rest: Content/Markdown):",
        value=story_input_val,
        height=140,
        placeholder="سرخی (Line 1)\nخلاصہ (Line 2)\nمکمل تفصیلات و متن (Line 3 onwards)..."
    )

    lines_preview = [l.strip() for l in story_text.splitlines() if l.strip()]
    extracted_title = lines_preview[0] if lines_preview else ""

    st.markdown("#### 🖼️ Thumbnail Source")
    thumb_col1, thumb_col2 = st.columns([1, 1])

    transferred_thumb = st.session_state.get("story_img_path", None)
    if transferred_thumb and os.path.exists(transferred_thumb):
        st.info(f"✅ Image loaded from Resizer Studio: `{os.path.basename(transferred_thumb)}`")
        if st.button("❌ Remove Loaded Thumbnail"):
            del st.session_state["story_img_path"]
            st.rerun()

    with thumb_col1:
        pub_local_img = st.file_uploader("Upload Image File:", type=["png", "jpg", "jpeg", "webp"], key="pub_file_up")
    with thumb_col2:
        pub_thumb_url = st.text_input("Or Image / Story Web URL:", placeholder="https://example.com/photo.jpg")

    # Quick Featured Card Generator Expander
    with st.expander("🖼️ Quick Featured Image Generator (1200x630)", expanded=False):
        st.caption("Compose a 1200x630 banner with Nastaliq typography and auto-attach as featured image.")
        quick_hl = st.text_input("Card Headline:", value=extracted_title, placeholder="سرخی درج کریں...")
        quick_photo = st.file_uploader("Upload Center Photo:", type=["jpg", "png", "webp"], key="quick_photo_up")

        if st.button("🎨 Generate & Attach Banner", key="btn_gen_quick_card"):
            if not quick_hl.strip():
                st.warning("Please provide a headline.")
            else:
                card_img = create_news_card(
                    headline_text=quick_hl.strip(),
                    news_img_source=quick_photo if quick_photo else (transferred_thumb if transferred_thumb else pub_local_img)
                )
                buf = io.BytesIO()
                card_img.save(buf, format="PNG")
                img_bytes = buf.getvalue()

                temp_card_path = os.path.join(tempfile.gettempdir(), f"featured_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                with open(temp_card_path, "wb") as f:
                    f.write(img_bytes)

                st.session_state["story_img_path"] = temp_card_path
                st.image(card_img, caption="Generated 1200x630 Featured Image", use_container_width=True)
                st.download_button("💾 Download Banner", data=img_bytes, file_name="featured_image.png", mime="image/png")
                st.success("✅ Set as the active featured thumbnail for Direct Publishing!")
                st.rerun()

    caption_text = st.text_input("Image Caption (تصویر کا کیپشن):", placeholder="تصویر کا عنوان یا کیپشن...")

    st.markdown("#### 📂 Taxonomy & Configuration")
    tax_c1, tax_c2, tax_c3 = st.columns([2, 1, 1.5])

    with tax_c1:
        cats_map = fetch_wordpress_categories(config.get("wp_url", ""), config.get("wp_user", ""), config.get("wp_pass", ""))
        cat_names = list(cats_map.keys()) if cats_map else ["Standard News"]
        selected_category = st.selectbox("WordPress Category:", cat_names)

    with tax_c2:
        pub_status = st.selectbox("Post Status:", ["draft", "publish"])

    with tax_c3:
        pub_ai_provider = st.selectbox(
            "SEO AI Engine:", 
            ["Groq (Llama)", "Google Gemini", "OpenAI (GPT)"], 
            index=["Groq (Llama)", "Google Gemini", "OpenAI (GPT)"].index(config.get("ai_provider", "Groq (Llama)"))
        )

    pub_card_prefix = st.text_input("Custom Card Filename Prefix (Optional):", placeholder="e.g. breaking_news")

    st.markdown("---")
    act_c1, act_c2, act_c3, act_c4 = st.columns(4)

    run_post = False
    run_card = False
    run_seo = False

    with act_c1:
        if st.button("🧹 Clear All Fields", use_container_width=True):
            st.session_state["pub_story_text"] = ""
            if "story_img_path" in st.session_state:
                del st.session_state["story_img_path"]
            st.session_state["pub_seo_preview"] = ""
            st.rerun()

    with act_c2:
        if st.button("🚀 Post Only", use_container_width=True):
            run_post = True

    with act_c3:
        if st.button("⚡ Post + Card", type="primary", use_container_width=True):
            run_post = True
            run_card = True

    with act_c4:
        if st.button("🌐 Post + Card + SEO", use_container_width=True):
            run_post = True
            run_card = True
            run_seo = True

    if run_post:
        if not story_text.strip():
            st.error("❌ Please paste story text first.")
        else:
            lines = [l.strip() for l in story_text.splitlines() if l.strip()]
            if len(lines) < 2:
                st.error("❌ Story text must have at least 2 lines (Line 1: Title, Line 2: Excerpt).")
            else:
                title = lines[0]
                excerpt = lines[1]
                raw_content = "\n\n".join(lines[2:]) if len(lines) > 2 else excerpt
                html_content = markdown.markdown(raw_content)

                image_source = None
                if transferred_thumb and os.path.exists(transferred_thumb):
                    image_source = transferred_thumb
                elif pub_local_img is not None:
                    image_source = pub_local_img
                elif pub_thumb_url.strip():
                    image_source = pub_thumb_url.strip()

                cat_ids = [cats_map[selected_category]] if (cats_map and selected_category in cats_map) else []

                with st.spinner("🚀 Uploading media and publishing to WordPress..."):
                    media_id = None
                    if image_source:
                        media_id = get_media_id_from_url(
                            image_source=image_source,
                            wp_url=config.get("wp_url", ""),
                            wp_user=config.get("wp_user", ""),
                            wp_pass=config.get("wp_pass", ""),
                            title_text=title,
                            caption_text=caption_text
                        )

                    post_link = post_to_wordpress(
                        title=title,
                        content=html_content,
                        wp_url=config.get("wp_url", ""),
                        wp_user=config.get("wp_user", ""),
                        wp_pass=config.get("wp_pass", ""),
                        excerpt=excerpt,
                        media_id=media_id,
                        status=pub_status,
                        category_ids=cat_ids
                    )

                    if post_link:
                        st.success(f"✅ Story Published Successfully: [View Post]({post_link})")

                        if run_card:
                            with st.spinner("🎨 Rendering Social Media Card..."):
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                pfx = f"{pub_card_prefix.strip()}_" if pub_card_prefix.strip() else ""
                                out_name = f"{pfx}card_{timestamp}.png"
                                out_dir = config.get("output_dir", os.path.join(os.path.expanduser("~"), "Downloads"))
                                os.makedirs(out_dir, exist_ok=True)
                                card_file = os.path.join(out_dir, out_name)

                                generate_custom_card(
                                    headline_text=title,
                                    news_img_path=image_source,
                                    template_path="ummat_frame.png",
                                    output_path=card_file,
                                    card_width=config.get("card_width", 1080),
                                    card_height=config.get("card_height", 1350)
                                )
                                st.session_state["latest_card_path"] = card_file
                                st.success(f"✨ Card saved to `{out_name}`")

                        if run_seo:
                            with st.spinner("🤖 Generating SEO description & hashtags..."):
                                a_key, a_model = get_api_credentials(pub_ai_provider)
                                prompt_seo = (
                                    f"Based on headline: '{title}' and context: '{excerpt}', "
                                    f"write one single-line concise English SEO description followed by 3-5 hashtags starting with #. "
                                    f"Provide ONLY the description and hashtags without extra labels."
                                )
                                raw_seo = generate_ai_news(prompt_seo, provider=pub_ai_provider, api_key=a_key, model_name=a_model)
                                clean_seo = sanitize_seo_text(raw_seo)
                                final_seo = f"{title}\n\n{clean_seo}"
                                st.session_state["pub_seo_preview"] = final_seo

                    else:
                        st.error("❌ Failed to publish post to WordPress. Check credentials in Settings.")

    seo_preview_val = st.session_state.get("pub_seo_preview", "")
    if seo_preview_val:
        st.markdown("#### 📋 Generated SEO Metadata")
        st.text_area("SEO Copy Box:", value=seo_preview_val, height=120)


# =========================================================
# TAB 2: IMAGE RESIZER & COLLAGE STUDIO
# =========================================================
with tab_resizer:
    render_image_resizer_tab(config)


# =========================================================
# TAB 3: AI NEWS STUDIO
# =========================================================
with tab_ai:
    st.markdown("### 🤖 Generate Professional Urdu News via AI")

    ai_raw_input = st.text_area(
        "Enter Raw Points, Bullets, or Notes in Urdu/English:",
        height=120,
        placeholder="یہاں کچی خبر، نوٹس یا اہم نکات درج کریں..."
    )

    ai_c1, ai_c2 = st.columns(2)
    with ai_c1:
        ai_tab_provider = st.selectbox(
            "AI Platform:",
            ["Groq (Llama)", "Google Gemini", "OpenAI (GPT)"],
            key="ai_tab_p",
            index=["Groq (Llama)", "Google Gemini", "OpenAI (GPT)"].index(config.get("ai_provider", "Groq (Llama)"))
        )
    with ai_c2:
        auto_load_pub = st.checkbox("Automatically load output into Direct Publisher", value=True)

    if st.button("✨ Generate Urdu News Article", type="primary", use_container_width=True):
        if not ai_raw_input.strip():
            st.warning("⚠️ Please provide input notes or points.")
        else:
            api_k, model_n = get_api_credentials(ai_tab_provider)
            with st.spinner(f"🤖 Generating professional Urdu news article via {ai_tab_provider}..."):
                generated_article = generate_ai_news(
                    ai_raw_input.strip(), 
                    provider=ai_tab_provider, 
                    api_key=api_k, 
                    model_name=model_n
                )
                st.session_state["ai_news_result"] = generated_article

                if auto_load_pub:
                    clean_for_pub = generated_article.replace("TITLE:", "").replace("EXCERPT:", "").replace("CONTENT:", "").strip()
                    st.session_state["pub_story_text"] = clean_for_pub
                    st.success("✅ News article generated and loaded into Direct Story Publisher!")

    ai_result = st.session_state.get("ai_news_result", "")
    if ai_result:
        st.markdown("#### 📋 AI Generated Article Preview")
        st.text_area("Generated Output:", value=ai_result, height=250)


# =========================================================
# TAB 4: SOCIAL MEDIA MANAGER
# =========================================================
with tab_social:
    render_social_manager_tab(config)


# =========================================================
# TAB 5: CARD FROM URL
# =========================================================
with tab_url:
    st.markdown("### 🔗 Generate Social Media Card by Story URL")

    story_url_input = st.text_input("Enter Article URL:", placeholder="https://ummat.net/2026/08/article-name/")
    
    url_c1, url_c2 = st.columns(2)
    with url_c1:
        url_card_prefix = st.text_input("Card Name Prefix (Optional):", placeholder="e.g. url_news", key="url_pfx")
    with url_c2:
        url_ai_platform = st.selectbox("AI Platform for SEO:", ["Groq (Llama)", "Google Gemini", "OpenAI (GPT)"], key="url_ai")

    url_btn1, url_btn2 = st.columns(2)
    gen_url_card = False
    gen_url_seo = False

    with url_btn1:
        if st.button("⚡ Generate Card Only", use_container_width=True):
            gen_url_card = True
    with url_btn2:
        if st.button("🌐 Generate Card + SEO", type="primary", use_container_width=True):
            gen_url_card = True
            gen_url_seo = True

    if gen_url_card:
        if not story_url_input.strip():
            st.error("❌ Please provide a valid URL.")
        else:
            with st.spinner("🔍 Extracting article data and rendering card..."):
                try:
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    res = requests.get(story_url_input.strip(), headers=headers, timeout=15, verify=False)
                    res.encoding = 'utf-8'
                    soup = BeautifulSoup(res.text, 'html.parser')

                    headline = ""
                    title_tag = soup.find('h1') or soup.find('meta', property='og:title') or soup.find('title')
                    if title_tag:
                        headline = title_tag.get('content') if title_tag.name == 'meta' else title_tag.get_text().strip()
                    else:
                        headline = "Breaking News"

                    headline = re.sub(r'\s*[-–|—]\s*(روزنامہ\s*امت|Ummat|Daily Ummat).*$', '', headline, flags=re.I).strip()

                    target_img = None
                    meta_img = soup.find('meta', property='og:image:secure_url') or soup.find('meta', property='og:image')
                    if meta_img and meta_img.get('content'):
                        target_img = meta_img['content']

                    img_bytes = None
                    if target_img:
                        img_res = requests.get(target_img, headers=headers, timeout=15, verify=False)
                        if img_res.status_code == 200:
                            img_bytes = io.BytesIO(img_res.content)

                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    pfx = f"{url_card_prefix.strip()}_" if url_card_prefix.strip() else ""
                    out_name = f"{pfx}url_card_{timestamp}.png"
                    out_dir = config.get("output_dir", os.path.join(os.path.expanduser("~"), "Downloads"))
                    os.makedirs(out_dir, exist_ok=True)
                    card_target = os.path.join(out_dir, out_name)

                    generate_custom_card(
                        headline_text=headline,
                        news_img_path=img_bytes,
                        template_path="ummat_frame.png",
                        output_path=card_target,
                        card_width=config.get("card_width", 1080),
                        card_height=config.get("card_height", 1350)
                    )

                    st.session_state["url_card_path"] = card_target
                    st.success(f"✅ Card generated: `{out_name}`")

                    if gen_url_seo:
                        k, m = get_api_credentials(url_ai_platform)
                        prompt = f"Write one concise English SEO sentence followed by 5 hashtags starting with # for this Urdu headline: '{headline}'."
                        raw_seo = generate_ai_news(prompt, provider=url_ai_platform, api_key=k, model_name=m)
                        st.session_state["url_seo_output"] = f"{headline}\n\n{sanitize_seo_text(raw_seo)}"

                except Exception as e:
                    st.error(f"❌ Extraction error: {e}")

    url_card_file = st.session_state.get("url_card_path", None)
    if url_card_file and os.path.exists(url_card_file):
        st.image(url_card_file, caption="Generated Card", width=450)
        with open(url_card_file, "rb") as f:
            st.download_button("💾 Download Card", data=f.read(), file_name=os.path.basename(url_card_file), mime="image/png")

    url_seo = st.session_state.get("url_seo_output", "")
    if url_seo:
        st.text_area("Generated SEO:", value=url_seo, height=120)


# =========================================================
# TAB 6: BRANDING & SETTINGS
# =========================================================
with tab_settings:
    st.markdown("### ⚙️ Master Branding & System Configuration")

    if not st.session_state.get("master_unlocked", False):
        pwd = st.text_input("Enter Master Password to Unlock Settings:", type="password")
        if st.button("🔓 Unlock Settings"):
            if pwd == "999999":
                st.session_state["master_unlocked"] = True
                st.rerun()
            else:
                st.error("❌ Incorrect Password!")
    else:
        st.success("🔒 Master Control Unlocked")

        with st.form("settings_form"):
            st.markdown("#### 📁 Directories & Dimensions")
            out_dir_val = st.text_input("Output Directory:", value=config.get("output_dir", ""))
            
            d_c1, d_c2 = st.columns(2)
            with d_c1:
                r_w = st.number_input("Resizer Canvas Width:", value=int(config.get("resizer_width", 1200)))
                r_h = st.number_input("Resizer Canvas Height:", value=int(config.get("resizer_height", 720)))
            with d_c2:
                c_w = st.number_input("Social Card Width:", value=int(config.get("card_width", 1080)))
                c_h = st.number_input("Social Card Height:", value=int(config.get("card_height", 1350)))

            st.markdown("#### 🔑 WordPress API Credentials")
            wp_url_val = st.text_input("WordPress URL:", value=config.get("wp_url", ""))
            wp_u1, wp_u2 = st.columns(2)
            with wp_u1:
                wp_user_val = st.text_input("WordPress Username:", value=config.get("wp_user", ""))
            with wp_u2:
                wp_pass_val = st.text_input("Application Password:", value=config.get("wp_pass", ""), type="password")

            st.markdown("#### 🤖 AI Platform API Keys & Models")
            
            groq_c1, groq_c2 = st.columns(2)
            with groq_c1:
                groq_k = st.text_input("Groq API Key:", value=config.get("groq_key", ""), type="password")
            with groq_c2:
                groq_m = st.text_input("Groq Model ID:", value=config.get("groq_model", "llama-3.3-70b-versatile"))

            gem_c1, gem_c2 = st.columns(2)
            with gem_c1:
                gem_k = st.text_input("Gemini API Key:", value=config.get("gemini_key", ""), type="password")
            with gem_c2:
                gem_m = st.text_input("Gemini Model ID:", value=config.get("gemini_model", "gemini-2.5-flash"))

            oa_c1, oa_c2 = st.columns(2)
            with oa_c1:
                oa_k = st.text_input("OpenAI API Key:", value=config.get("openai_key", ""), type="password")
            with oa_c2:
                oa_m = st.text_input("OpenAI Model ID:", value=config.get("openai_model", "gpt-4o"))

            save_btn = st.form_submit_button("💾 Save All Settings Encrypted", type="primary")

            if save_btn:
                new_config = {
                    "wp_url": wp_url_val.strip(),
                    "wp_user": wp_user_val.strip(),
                    "wp_pass": wp_pass_val.strip(),
                    "ai_provider": config.get("ai_provider", "Groq (Llama)"),
                    "groq_key": groq_k.strip(),
                    "groq_model": groq_m.strip(),
                    "gemini_key": gem_k.strip(),
                    "gemini_model": gem_m.strip(),
                    "openai_key": oa_k.strip(),
                    "openai_model": oa_m.strip(),
                    "output_dir": out_dir_val.strip(),
                    "logo_path": config.get("logo_path", "ummat bug final.png"),
                    "resizer_width": int(r_w),
                    "resizer_height": int(r_h),
                    "card_width": int(c_w),
                    "card_height": int(c_h)
                }
                if save_master_config(new_config):
                    st.success("✅ Configuration saved securely!")
                    st.rerun()
                else:
                    st.error("❌ Error saving encrypted configuration.")

        if st.button("🔒 Re-Lock Settings Panel"):
            st.session_state["master_unlocked"] = False
            st.rerun()
