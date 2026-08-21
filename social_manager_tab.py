import os
import time
import tempfile
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup
import requests
from image_designer import generate_custom_card
import streamlit as st

def generate_seo_metadata(text, provider, api_key, model_name="", include_youtube=True):
    yt_instruction = "Provide a catchy YouTube Title and YouTube Keywords comma-separated on a single line." if include_youtube else ""
    
    if not model_name or not model_name.strip():
        if provider == "Groq (Llama)": model_name = "groq/compound"
        elif provider == "Google Gemini": model_name = "gemini-3.7-flash"
        else: model_name = "gpt-5.6-sol"

    prompt = f"""
Strictly follow these rules without any introductory text, reasoning lines, bullet points, or asterisks (*):
1. HASHTAGS: Exactly 5 trending hashtags, space-separated on a single unnumbered line.
2. ENGLISH DESCRIPTION: A concise, catchy English description for social media on a single paragraph.
3. {yt_instruction}

Urdu Text:
{text}

Output format (use these exact labels without any extra markdown or asterisks):
HASHTAGS:
ENGLISH DESCRIPTION:
YOUTUBE TITLE:
YOUTUBE KEYWORDS:
"""
    try:
        if provider == "Groq (Llama)":
            from groq import Groq
            client = Groq(api_key=api_key.strip())
            res = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
            )
            return res.choices[0].message.content.replace("*", "").strip()

        elif provider == "Google Gemini":
            from google import genai
            client = genai.Client(api_key=api_key.strip())
            interaction = client.interactions.create(model=model_name, input=prompt)
            return interaction.output_text.replace("*", "").strip()

        elif provider == "OpenAI (GPT)":
            from openai import OpenAI
            client = OpenAI(api_key=api_key.strip())
            res = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            return res.choices[0].message.content.replace("*", "").strip()
    except Exception as e:
        return f"❌ SEO Error: {e}"
    return "❌ SEO Failed."


def render_social_manager_tab(app_config):
    """Renders the Social Media Manager & SEO Studio tab inside Streamlit."""
    
    st.header("🌐 Social Media Manager & SEO Studio")
    
    # 1. Urdu Text / Headline Input
    headline_text = st.text_area("Urdu Text / Headline:", placeholder="یہاں خبر کی سرخی درج کریں...", height=110)
    
    # 2. Image Source Options
    st.markdown("🖼️ Image Source (Select File or Provide URL):")
    col_img1, col_img2 = st.columns([2, 1])
    
    with col_img1:
        img_url_input = st.text_input("Paste Direct Image URL or Story URL:", placeholder="https://...")
    with col_img2:
        uploaded_img_file = st.file_uploader("Upload Image File", type=["png", "jpg", "jpeg", "webp"])

    # 3. AI Platform Selector & YouTube Checkbox Row
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        ai_provider = st.selectbox("AI Platform:", ["Groq (Llama)", "Google Gemini", "OpenAI (GPT)"], index=0)
    with col_opt2:
        include_yt = st.checkbox("Generate YouTube Title & Keywords", value=True)

    # 4. Custom Card Name Prefix Input
    custom_card_prefix = st.text_input("🏷️ Custom Card Name Prefix (Optional):", placeholder="e.g., reel-part1, podcast-quote")

    # Helper function to get credentials based on active selection
    def get_credentials():
        if ai_provider == "Groq (Llama)":
            return app_config.get("groq_key", "").strip(), app_config.get("groq_model", "").strip()
        elif ai_provider == "Google Gemini":
            return app_config.get("gemini_key", "").strip(), app_config.get("gemini_model", "").strip()
        else:
            return app_config.get("openai_key", "").strip(), app_config.get("openai_model", "").strip()

    # Helper function to resolve image path
    def resolve_image():
        if uploaded_img_file is not None:
            temp_p = os.path.join(tempfile.gettempdir(), f"social_upload_{os.urandom(4).hex()}.png")
            with open(temp_p, "wb") as f:
                f.write(uploaded_img_file.getbuffer())
            return temp_p
            
        if img_url_input.strip():
            try:
                target_url = img_url_input.strip()
                if not target_url.lower().endswith(('png', 'jpg', 'jpeg', 'webp', 'gif')):
                    res = requests.get(target_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10, verify=False)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    meta_img = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'twitter:image'})
                    if meta_img and meta_img.get('content'):
                        target_url = meta_img['content']
                    else:
                        img_tag = soup.find('img')
                        if img_tag and img_tag.get('src'):
                            target_url = img_tag['src']
                    if not target_url.startswith('http'):
                        target_url = urllib.parse.urljoin(img_url_input, target_url)

                img_resp = requests.get(target_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=12, verify=False)
                if img_resp.status_code == 200:
                    temp_p = os.path.join(tempfile.gettempdir(), "social_manager_thumb.jpg")
                    with open(temp_p, 'wb') as f:
                        f.write(img_resp.content)
                    return temp_p
            except Exception as e:
                st.error(f"Image fetch error: {e}")
        return None

    # 5. Action Buttons Row
    st.markdown("---")
    btn_col1, btn_col2, btn_col3 = st.columns(3)
    
    # We maintain states for outputs using Streamlit session state
    if "social_output_card" not in st.session_state:
        st.session_state["social_output_card"] = None
    if "social_output_seo" not in st.session_state:
        st.session_state["social_output_seo"] = ""

    with btn_col1:
        if st.button("✨ Generate Only Card", use_container_width=True):
            if not headline_text.strip():
                st.warning("Please enter Urdu text for the card!")
            else:
                with st.spinner("Generating social card..."):
                    output_dir = app_config.get("output_dir", tempfile.gettempdir())
                    os.makedirs(output_dir, exist_ok=True)
                    
                    default_base = f"news_card_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    safe_prefix = "".join([c if c.isalnum() or c in "-_" else "_" for c in custom_card_prefix])
                    final_filename = f"{safe_prefix}_{default_base}" if safe_prefix else default_base
                    card_file = os.path.join(output_dir, final_filename)

                    try:
                        img_p = resolve_image()
                        generate_custom_card(
                            headline_text=headline_text,
                            news_img_path=img_p,
                            template_path=app_config.get("template_path", "ummat_frame.png"),
                            output_path=card_file
                        )
                        st.session_state["social_output_card"] = card_file
                        st.success("Social card generated successfully!")
                    except Exception as e:
                        st.error(f"Card generation failed: {e}")

    with btn_col2:
        if st.button("🚀 Generate Card & SEO", use_container_width=True):
            if not headline_text.strip():
                st.warning("Please enter text!")
            else:
                # Run card generation
                with st.spinner("Generating card and AI SEO..."):
                    output_dir = app_config.get("output_dir", tempfile.gettempdir())
                    os.makedirs(output_dir, exist_ok=True)
                    default_base = f"news_card_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    safe_prefix = "".join([c if c.isalnum() or c in "-_" else "_" for c in custom_card_prefix])
                    final_filename = f"{safe_prefix}_{default_base}" if safe_prefix else default_base
                    card_file = os.path.join(output_dir, final_filename)

                    try:
                        img_p = resolve_image()
                        generate_custom_card(
                            headline_text=headline_text,
                            news_img_path=img_p,
                            template_path=app_config.get("template_path", "ummat_frame.png"),
                            output_path=card_file
                        )
                        st.session_state["social_output_card"] = card_file
                    except Exception as e:
                        st.error(f"Card failed: {e}")

                    # Run SEO generation
                    key, model = get_credentials()
                    if not key:
                        st.error(f"API Key for {ai_provider} is missing!")
                    else:
                        seo_res = generate_seo_metadata(headline_text, ai_provider, key, model, include_yt)
                        st.session_state["social_output_seo"] = seo_res
                        st.success("Card & SEO metadata generated!")

    with btn_col3:
        if st.button("🔍 Generate Only SEO", use_container_width=True):
            if not headline_text.strip():
                st.warning("Please enter Urdu text to generate SEO!")
            else:
                key, model = get_credentials()
                if not key:
                    st.error(f"API Key for {ai_provider} is missing!")
                else:
                    with st.spinner(f"Generating SEO metadata via {ai_provider}..."):
                        seo_res = generate_seo_metadata(headline_text, ai_provider, key, model, include_yt)
                        st.session_state["social_output_seo"] = seo_res
                        st.success("SEO metadata generated successfully!")

    # Display Generated Card Preview & Download if available
    if st.session_state["social_output_card"] and os.path.exists(st.session_state["social_output_card"]):
        st.image(st.session_state["social_output_card"], caption="Generated Social Card Preview")
        with open(st.session_state["social_output_card"], "rb") as cf:
            st.download_button("📥 Download Generated Card", cf, file_name=os.path.basename(st.session_state["social_output_card"]), mime="image/png")


# 6. SEO Output Box Display (Updated to reflect real-time session state output)
    st.markdown("📊 **AI SEO & Social Media Output:**")
    
    # This ensures the text box automatically displays the result when generated
    st.text_area(
        "SEO Metadata Result", 
        value=st.session_state.get("social_output_seo", ""), 
        height=130, 
        key="seo_display_box"
    )