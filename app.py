import streamlit as st
import os
import tempfile
import urllib.parse
import pathlib
import json
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import markdown
import streamlit as st

# Core Modules (Keeping your existing files intact)
from wp_publisher import post_to_wordpress, get_media_id_from_url, fetch_wordpress_categories
from social_media import generate_social_post
from image_designer import generate_custom_card
from ai_news_generator import generate_ai_news

# 1. Page Configuration & Layout
st.set_page_config(page_title="Ummat News Studio & Direct Publisher", layout="wide")

# --- PASSWORD PROTECTION GATE ---
def check_password():
    """Returns `True` if the user entered the correct password."""
    
    def password_entered():
        if st.session_state["password"] == st.secrets.get("auth", {}).get("password", "999999"):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password
        st.text_input(
            "🔒 Enter Master Password to Access Studio", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input + error
        st.text_input(
            "🔒 Enter Master Password to Access Studio", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct
        return True

if not check_password():
    st.stop()  # Do not render the rest of the app until authenticated

st.title("⚡ Direct Story Publisher & Studio Pro")

# Initialize Playwright browser binaries for cloud environment
@st.cache_resource
def init_playwright():
    import subprocess
    subprocess.run(["playwright", "install", "chromium"])

init_playwright()

# 2. Secure Configuration Loader (Using Streamlit Secrets for Cloud / Fallback for Local)
def get_config_value(section, key, default=""):
    try:
        if section in st.secrets:
            return st.secrets[section].get(key, default)
    except Exception:
        pass
    return default

# Load configuration values
WP_URL = get_config_value("wordpress", "wp_url", "")
WP_USER = get_config_value("wordpress", "wp_user", "")
WP_PASS = get_config_value("wordpress", "wp_pass", "")

AI_PROVIDER = get_config_value("ai", "provider", "Groq (Llama)")
GROQ_KEY = get_config_value("ai", "groq_key", "")
GROQ_MODEL = get_config_value("ai", "groq_model", "groq/compound")
GEMINI_KEY = get_config_value("ai", "gemini_key", "")
GEMINI_MODEL = get_config_value("ai", "gemini_model", "gemini-3.7-flash")
OPENAI_KEY = get_config_value("ai", "openai_key", "")
OPENAI_MODEL = get_config_value("ai", "openai_model", "gpt-5.6-sol")

OUTPUT_DIR = str(pathlib.Path.home() / "Downloads" / "NewsAppOutputs")
LOGO_PATH = "ummat bug final.png"
TEMPLATE_PATH = "ummat_frame.png"

# Helper for filename prefixing
def get_card_filename(default_name: str, custom_prefix: str) -> str:
    if custom_prefix:
        safe_prefix = re.sub(r'[^a-zA-Z0-9-_]', '_', custom_prefix.strip())
        return f"{safe_prefix}_{default_name}"
    return default_name

# 3. Sidebar Navigation Tabs
tab_choice = st.sidebar.selectbox("Select Studio Module", [
    "📝 Direct Story Publisher",
    "🤖 AI News Studio",
    "🌐 Social Media Manager",
    "🔗 Card from URL",
    "⚙️ Branding & Settings"
])

# --- TAB 1: DIRECT STORY PUBLISHER ---
if tab_choice == "📝 Direct Story Publisher":
    st.header("📝 Direct Story Publisher")
    st.markdown("Paste complete story text (**Line 1: Title**, **Line 2: Excerpt**, **Rest: Content/Markdown**)")
    
    story_input = st.text_area("Story Text (Urdu RTL supported)", height=150, placeholder="یہاں خبر کی سرخی درج کریں...\nدوسری سطر (خلاصہ)...\nباقی تفصیلی مواد...")
    
    col1, col2 = st.columns(2)
    with col1:
        custom_card_name = st.text_input("🏷️ Custom Card Name Prefix (Optional):", placeholder="e.g., breaking-news")
    with col2:
        image_caption = st.text_input("✍️ Image Caption (تصویر کا کیپشن):")
        
    st.markdown("---")
    st.subheader("🖼️ Thumbnail Source")
    thumb_source_type = st.radio("Choose Source Type", ["Direct Image URL / Story URL", "Upload Local Image File"])
    
    resolved_img_path = None
    if thumb_source_type == "Direct Image URL / Story URL":
        thumb_url_input = st.text_input("Paste Story URL or Direct Image URL:")
        if thumb_url_input:
            resolved_img_path = thumb_url_input
    else:
        uploaded_file = st.file_uploader("Upload Image File", type=["png", "jpg", "jpeg", "webp"])
        if uploaded_file:
            temp_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            temp_img.write(uploaded_file.read())
            temp_img.close()
            resolved_img_path = temp_img.name

    col_cat1, col_cat2 = st.columns(2)
    with col_cat1:
        pub_status = st.selectbox("Status", ["draft", "publish"])
    with col_cat2:
        # Fetch categories dynamically if credentials exist
        category_map = {}
        if WP_URL and WP_USER and WP_PASS:
            try:
                category_map = fetch_wordpress_categories(WP_URL, WP_USER, WP_PASS)
            except Exception:
                pass
        cat_names = list(category_map.keys()) if category_map else ["Default / Uncategorized"]
        selected_cat = st.selectbox("📂 WordPress Category", cat_names)

    st.markdown("---")
    action_cols = st.columns(3)
    
    def process_publishing(mode):
        if not story_input.strip():
            st.warning("Please paste story text first!")
            return
            
        lines = [line.strip() for line in story_input.splitlines() if line.strip()]
        if len(lines) < 2:
            st.warning("Story text must have at least 2 lines (Line 1: Title, Line 2: Excerpt)!")
            return
            
        title = lines[0]
        excerpt = lines[1]
        raw_content = "\n\n".join(lines[2:]) if len(lines) > 2 else excerpt
        html_content = markdown.markdown(raw_content)
        
        category_ids = [category_map[selected_cat]] if selected_cat in category_map else []
        
        with st.spinner("Processing story and communicating with WordPress..."):
            try:
                # Handle image downloading if remote URL provided
                card_img_source = resolved_img_path
                if resolved_img_path and resolved_img_path.startswith("http"):
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    img_resp = requests.get(resolved_img_path, headers=headers, timeout=15, verify=False)
                    if img_resp.status_code == 200:
                        temp_p = os.path.join(tempfile.gettempdir(), f"wp_card_{os.urandom(4).hex()}.jpg")
                        with open(temp_p, 'wb') as f:
                            f.write(img_resp.content)
                        card_img_source = temp_p

                media_id = None
                if resolved_img_path:
                    media_id = get_media_id_from_url(resolved_img_path, WP_URL, WP_USER, WP_PASS, caption_text=image_caption)

                posted_link = post_to_wordpress(
                    title=title, content=html_content, wp_url=WP_URL,
                    wp_user=WP_USER, wp_pass=WP_PASS,
                    excerpt=excerpt, media_id=media_id, status=pub_status, category_ids=category_ids
                )

                if posted_link:
                    st.success(f"Story successfully published! [View Live Post]({posted_link})")
                    
                    if mode in ["card", "seo"] and card_img_source and os.path.exists(card_img_source):
                        os.makedirs(OUTPUT_DIR, exist_ok=True)
                        default_base = f"card_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        final_filename = get_card_filename(default_base, custom_card_name)
                        card_file = os.path.join(OUTPUT_DIR, final_filename)
                        
                        generate_custom_card(
                            headline_text=title, news_img_path=card_img_source,
                            template_path=TEMPLATE_PATH, output_path=card_file
                        )
                        st.image(card_file, caption="Generated Social Media Card")
                        with open(card_file, "rb") as cf:
                            st.download_button("📥 Download Social Card", cf, file_name=final_filename, mime="image/png")

                    if mode == "seo":
                        ai_active_key = GROQ_KEY if AI_PROVIDER == "Groq (Llama)" else (GEMINI_KEY if AI_PROVIDER == "Google Gemini" else OPENAI_KEY)
                        ai_active_model = GROQ_MODEL if AI_PROVIDER == "Groq (Llama)" else (GEMINI_MODEL if AI_PROVIDER == "Google Gemini" else OPENAI_MODEL)
                        
                        ai_prompt = f"Based on headline: '{title}' and excerpt: '{excerpt}', write one single-line English SEO description and 3-5 hashtags."
                        seo_output = generate_ai_news(ai_prompt, provider=AI_PROVIDER, api_key=ai_active_key, model_name=ai_active_model)
                        st.info(f"📋 SEO & Hashtags:\n\n{seo_output}")
                else:
                    st.error("Could not publish to WordPress.")
            except Exception as e:
                st.error(f"Publishing failed: {e}")

    with action_cols[0]:
        if st.button("🚀 Post Only"): process_publishing("post")
    with action_cols[1]:
        if st.button("⚡ Post + Card"): process_publishing("card")
    with action_cols[2]:
        if st.button("🌐 Post + Card + SEO"): process_publishing("seo")

# --- TAB 2: AI NEWS STUDIO ---
elif tab_choice == "🤖 AI News Studio":
    st.header("🤖 Generate Professional Urdu News via AI")
    ai_input_text = st.text_area("Enter raw notes or points:", height=120)
    
    col_ai1, col_ai2 = st.columns(2)
    with col_ai1:
        ai_platform = st.selectbox("Select AI Platform", ["Groq (Llama)", "Google Gemini", "OpenAI (GPT)"], index=0)
    with col_ai2:
        ai_status_choice = st.selectbox("Status Selection", ["draft", "publish"])
        
    review_chk = st.checkbox("Review output before action", value=True)
    
    if st.button("✨ Generate News via AI & Process"):
        if not ai_input_text.strip():
            st.warning("Please enter raw text or points!")
        else:
            active_key = GROQ_KEY if ai_platform == "Groq (Llama)" else (GEMINI_KEY if ai_platform == "Google Gemini" else OPENAI_KEY)
            active_model = GROQ_MODEL if ai_platform == "Groq (Llama)" else (GEMINI_MODEL if ai_platform == "Google Gemini" else OPENAI_MODEL)
            
            with st.spinner(f"Generating Urdu news article via {ai_platform}..."):
                result = generate_ai_news(ai_input_text, provider=ai_platform, api_key=active_key, model_name=active_model)
                st.text_area("AI Generated Urdu News Preview:", value=result, height=200)

# --- TAB 4: SOCIAL MEDIA MANAGER (PASTE IT HERE) ---
elif tab_choice == "🌐 Social Media Manager":
    from social_manager_tab import render_social_manager_tab
    
    # Pass configuration dictionary from Streamlit secrets or state
    app_config = {
        "output_dir": OUTPUT_DIR,
        "template_path": TEMPLATE_PATH,
        "groq_key": GROQ_KEY,
        "groq_model": GROQ_MODEL,
        "gemini_key": GEMINI_KEY,
        "gemini_model": GEMINI_MODEL,
        "openai_key": OPENAI_KEY,
        "openai_model": OPENAI_MODEL
    }
    render_social_manager_tab(app_config)

# --- TAB 3: CARD FROM URL ---
elif tab_choice == "🔗 Card from URL":
    st.header("🔗 Generate Social Media Card by Inputting Story URL")
    url_input = st.text_input("Story URL:", placeholder="https://ummat.net/...")
    url_custom_name = st.text_input("Custom Card Name Prefix (Optional):")
    
    if st.button("🚀 Fetch Story & Generate Card"):
        if not url_input.strip():
            st.warning("Please enter story URL!")
        else:
            with st.spinner("Fetching story and generating card..."):
                try:
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    res = requests.get(url_input, headers=headers, timeout=12, verify=False)
                    res.encoding = 'utf-8'
                    soup = BeautifulSoup(res.text, 'html.parser')

                    title_tag = soup.find('h1') or soup.find('h2') or soup.find('title')
                    headline = title_tag.get_text().strip() if title_tag else "Important News"

                    meta_img = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'twitter:image'})
                    img_url = meta_img['content'] if meta_img and meta_img.get('content') else None
                    if not img_url:
                        img_tag = soup.find('img')
                        if img_tag and img_tag.get('src'):
                            img_url = img_tag['src']

                    img_path = None
                    if img_url:
                        if not img_url.startswith('http'):
                            img_url = urllib.parse.urljoin(url_input, img_url)
                        img_resp = requests.get(img_url, headers=headers, timeout=12, verify=False)
                        if img_resp.status_code == 200:
                            img_path = os.path.join(tempfile.gettempdir(), "fetched_url_img.jpg")
                            with open(img_path, 'wb') as f:
                                f.write(img_resp.content)

                    os.makedirs(OUTPUT_DIR, exist_ok=True)
                    default_base = f"url_card_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    final_filename = get_card_filename(default_base, url_custom_name)
                    card_file = os.path.join(OUTPUT_DIR, final_filename)

                    generate_custom_card(
                        headline_text=headline, news_img_path=img_path,
                        template_path=TEMPLATE_PATH, output_path=card_file
                    )
                    st.success("Social card generated successfully!")
                    st.image(card_file, caption="Generated Card Preview")
                    with open(card_file, "rb") as cf:
                        st.download_button("📥 Download Card", cf, file_name=final_filename, mime="image/png")
                except Exception as e:
                    st.error(f"Card generation failed: {e}")

# --- TAB 4: BRANDING & SETTINGS ---
elif tab_choice == "⚙️ Branding & Settings":
    st.header("⚙️ WordPress & Studio Configuration")
    st.info("On Streamlit Cloud, configuration keys are safely managed via the Cloud Dashboard Settings under Secrets (TOML format).")
    
    st.text_input("WordPress URL", value=WP_URL, disabled=True)
    st.text_input("WordPress Username", value=WP_USER, disabled=True)
    st.text_input("Groq Model", value=GROQ_MODEL, disabled=True)
    st.text_input("Gemini Model", value=GEMINI_MODEL, disabled=True)

st.markdown("---")
st.markdown("© 2026 Developed & Maintained by AREs | Cloud Web Studio Version")