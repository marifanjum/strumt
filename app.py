import os
import io
import tempfile
import urllib.parse
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import streamlit as st

from image_designer import generate_custom_card
from ai_news_generator import generate_seo_metadata


def render_social_manager_tab(config: dict):
    """Renders the dedicated Social Media Manager & SEO Studio in Streamlit."""
    st.markdown("### 🌐 Social Media Manager & SEO Studio")

    st.markdown("""
        <style>
            textarea[aria-label="Urdu Text / Headline:"] {
                font-family: 'Jameel Noori Nastaleeq', 'Jameel Custom', 'Noto Nastaliq Urdu', Arial, sans-serif !important;
                direction: rtl !important;
                text-align: right !important;
                font-size: 19px !important;
                line-height: 1.8 !important;
            }
        </style>
    """, unsafe_allow_html=True)

    headline = st.text_area(
        "Urdu Text / Headline:",
        value=st.session_state.get("social_headline", ""),
        height=100,
        placeholder="یہاں خبر کی اردو سرخی یا سوشل میڈیا پوسٹ کا متن درج کریں..."
    )

    st.markdown("#### 🖼️ Image Source")
    img_col1, img_col2 = st.columns([1, 1])

    transferred_image = st.session_state.get("social_media_image_path", None)
    transferred_name = st.session_state.get("social_media_image_name", None)

    if transferred_image and os.path.exists(transferred_image):
        display_name = transferred_name if transferred_name else os.path.basename(transferred_image)
        st.info(f"✅ Image received: `{display_name}`")
        if st.button("❌ Remove Transferred Image"):
            del st.session_state["social_media_image_path"]
            if "social_media_image_name" in st.session_state:
                del st.session_state["social_media_image_name"]
            st.rerun()

    with img_col1:
        uploaded_file = st.file_uploader(
            "Upload Local Image:", 
            type=["png", "jpg", "jpeg", "webp"], 
            key="social_img_uploader"
        )

    with img_col2:
        img_url = st.text_input(
            "Or Paste Direct / Story URL:", 
            placeholder="https://example.com/image.jpg"
        )

    st.markdown("#### ⚙️ Card & AI Configurations")
    opt_col1, opt_col2, opt_col3 = st.columns([1.5, 1.5, 2])

    with opt_col1:
        current_ai = config.get("ai_provider", "Groq (Llama)")
        provider_options = ["Groq (Llama)", "Google Gemini", "OpenAI (GPT)"]
        default_index = provider_options.index(current_ai) if current_ai in provider_options else 0
        selected_provider = st.selectbox("AI Platform:", provider_options, index=default_index)

    with opt_col2:
        chk_youtube = st.checkbox("Generate YouTube SEO", value=True)

    with opt_col3:
        default_pfx = os.path.splitext(transferred_name)[0] if transferred_name else ""
        custom_prefix = st.text_input("Custom Card Prefix (Optional):", value=default_pfx, placeholder="e.g. breaking_news")

    def resolve_image_input():
        if transferred_image and os.path.exists(transferred_image):
            return transferred_image

        if uploaded_file is not None:
            return uploaded_file

        if img_url and img_url.strip():
            clean_url = img_url.strip()
            target_url = clean_url
            try:
                if not clean_url.lower().split('?')[0].endswith(('png', 'jpg', 'jpeg', 'webp', 'gif')):
                    res = requests.get(clean_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10, verify=False)
                    soup = BeautifulSoup(res.text, 'html.parser')
                    meta_img = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'twitter:image'})
                    if meta_img and meta_img.get('content'):
                        target_url = meta_img['content']
                    else:
                        img_tag = soup.find('img')
                        if img_tag and img_tag.get('src'):
                            target_url = img_tag['src']
                    if not target_url.startswith('http'):
                        target_url = urllib.parse.urljoin(clean_url, target_url)

                img_resp = requests.get(target_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15, verify=False)
                if img_resp.status_code == 200 and len(img_resp.content) > 500:
                    return io.BytesIO(img_resp.content)
            except Exception as e:
                st.warning(f"⚠️ Could not scrape image URL: {e}")

        return None

    def get_credentials(provider):
        if provider == "Groq (Llama)":
            return config.get("groq_key", ""), config.get("groq_model", "llama-3.3-70b-versatile")
        elif provider == "Google Gemini":
            return config.get("gemini_key", ""), config.get("gemini_model", "gemini-2.5-flash")
        else:
            return config.get("openai_key", ""), config.get("openai_model", "gpt-4o")

    st.markdown("---")
    btn_col1, btn_col2, btn_col3 = st.columns(3)

    do_card = False
    do_seo = False

    with btn_col1:
        if st.button("✨ Generate Only Card", width="stretch"):
            do_card = True

    with btn_col2:
        if st.button("🚀 Generate Card & SEO", type="primary", width="stretch"):
            do_card = True
            do_seo = True

    with btn_col3:
        if st.button("🔍 Generate Only SEO", width="stretch"):
            do_seo = True

    card_width = int(config.get("card_width", 1080))
    card_height = int(config.get("card_height", 1350))

    if do_card:
        if not headline.strip():
            st.error("❌ Please provide an Urdu headline first.")
        else:
            with st.spinner("🎨 Rendering social media card via Playwright..."):
                resolved_img = resolve_image_input()
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                prefix = f"{custom_prefix.strip()}_" if custom_prefix.strip() else ""
                card_filename = f"{prefix}news_card_{timestamp}.png"
                
                output_dir = config.get("output_dir", os.path.join(os.path.expanduser("~"), "Downloads"))
                os.makedirs(output_dir, exist_ok=True)
                target_card_path = os.path.join(output_dir, card_filename)

                try:
                    generated_card = generate_custom_card(
                        headline_text=headline.strip(),
                        news_img_path=resolved_img,
                        template_path="ummat_frame.png",
                        output_path=target_card_path,
                        card_width=card_width,
                        card_height=card_height
                    )
                    st.session_state["latest_card_path"] = generated_card
                    st.success(f"✅ Card generated successfully: `{card_filename}`")
                except Exception as e:
                    st.error(f"❌ Failed to generate card: {e}")

    if do_seo:
        if not headline.strip():
            st.error("❌ Please provide an Urdu headline first.")
        else:
            api_key, model_name = get_credentials(selected_provider)
            if not api_key:
                st.error(f"❌ Missing API Key for {selected_provider}. Please configure it in Settings.")
            else:
                with st.spinner(f"🤖 Generating SEO & Hashtags via {selected_provider}..."):
                    seo_text = generate_seo_metadata(
                        headline=headline.strip(),
                        provider=selected_provider,
                        api_key=api_key,
                        model_name=model_name,
                        include_youtube=chk_youtube
                    )
                    st.session_state["latest_seo_output"] = seo_text

    res_col1, res_col2 = st.columns([1, 1])

    with res_col1:
        st.markdown("#### 🖼️ Social Card Output")
        latest_card = st.session_state.get("latest_card_path", None)
        if latest_card and os.path.exists(latest_card):
            st.image(latest_card, caption="Generated Social Media Card", width="stretch")
            with open(latest_card, "rb") as f:
                st.download_button(
                    label="💾 Download Card Image",
                    data=f.read(),
                    file_name=os.path.basename(latest_card),
                    mime="image/png",
                    width="stretch"
                )
        else:
            st.info("No card generated yet. Click 'Generate Only Card' or 'Generate Card & SEO' above.")

    with res_col2:
        st.markdown("#### 📊 SEO & Social Metadata")
        latest_seo = st.session_state.get("latest_seo_output", "")
        if latest_seo:
            st.text_area("Generated Metadata:", value=latest_seo, height=320)
        else:
            st.info("SEO metadata will appear here after generation.")
