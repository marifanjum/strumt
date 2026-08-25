import os
import re
import json
import urllib.parse
import urllib.request


def clean_input_text(text: str) -> str:
    """Clean markdown labels and prefixes from input text."""
    if not text:
        return ""
    txt = str(text).replace('TITLE:', '').replace('CONTENT:', '').replace('KEYWORDS:', '').replace('ٹائٹل:', '').strip()
    return txt


def translate_urdu_to_english(text: str) -> str:
    """Free Google Translate endpoint for quick English baseline translation."""
    try:
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=ur&tl=en&dt=t&q=" + urllib.parse.quote(text)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            translated = "".join([sentence[0] for sentence in result[0] if sentence[0]])
            return translated.strip()
    except Exception:
        return text.strip()


def generate_social_post(input_text: str, provider: str = "Google Gemini", api_key: str = "") -> str:
    """Legacy compatibility bridge returning combined multiline text."""
    return generate_video_metadata(input_text, provider=provider, api_key=api_key)


def generate_video_metadata(video_topic_or_script: str, provider: str = "Google Gemini", api_key: str = "") -> str:
    """
    Generates unified social copy and YouTube SEO metadata.
    Returns standard multiline text block separated by '|'.
    """
    res = generate_social_metadata_dict(video_topic_or_script, provider=provider, api_key=api_key)
    if "error" in res:
        return res["error"]

    return f"""{res['urdu_headline']}
More details in comments

{res['social_english']}

{res['social_hashtags']}

|

{res['youtube_title']}

{res['youtube_description']}

{res['youtube_hashtags']}"""


def generate_social_metadata_dict(video_topic_or_script: str, provider: str = "Google Gemini", api_key: str = "") -> dict:
    """
    Generates structured SEO and social copy as a dictionary for easy rendering in Streamlit widgets.
    """
    raw_text = clean_input_text(video_topic_or_script)
    if not raw_text:
        return {"error": "Please enter Urdu text first."}

    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    urdu_headline = lines[0] if lines else raw_text

    # --- 1. Social Copy & Basic Hashtags ---
    social_english = translate_urdu_to_english(urdu_headline)
    
    words = re.findall(r'\b[a-zA-Z]{4,}\b', social_english)
    ignore_words = {'were', 'them', 'they', 'from', 'with', 'that', 'this', 'have', 'been', 'does', 'your', 'about', 'after'}
    filtered_words = [w for w in words if w.lower() not in ignore_words]
    social_hashtags = " ".join([f"#{w.capitalize()}" for w in filtered_words[:5]]) if filtered_words else "#News #Updates #Trending #GlobalNews #UrduNews"

    # --- 2. AI Prompt & Generation ---
    prompt_yt = f"""
You are a YouTube SEO Expert. Based strictly on this news context, generate high-converting YouTube Metadata in natural English:
New Text: "{raw_text}"

STRICT OUTPUT REQUIREMENTS:
Line 1: One Catchy High-CTR YouTube Title in English (Under 70 characters, complete sentence).
Line 2: Empty line.
Line 3: A natural 2-sentence YouTube Description in fluent, grammatically perfect English matching the context.
Line 4: Empty line.
Line 5: 5 Powerful YouTube Hashtags starting with # (e.g. #GlobalNews #BreakingNews).

DO NOT ADD ANY LABELS LIKE "Title:", "Description:", "Hashtags:". Output fresh raw text only.
"""

    ai_yt_data = None

    if api_key and api_key.strip():
        try:
            # 1. Google Gemini
            if provider == "Google Gemini":
                from google import genai
                client = genai.Client(api_key=api_key.strip())
                models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash']
                for model_name in models_to_try:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt_yt,
                        )
                        if response and hasattr(response, 'text') and response.text:
                            ai_yt_data = response.text.strip()
                            break
                    except Exception:
                        continue

            # 2. Groq (Llama)
            elif provider == "Groq (Llama)":
                from groq import Groq
                client = Groq(api_key=api_key.strip())
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt_yt}],
                    model="llama-3.3-70b-versatile",
                )
                ai_yt_data = chat_completion.choices[0].message.content.strip()

            # 3. OpenAI (GPT)
            elif provider == "OpenAI (GPT)":
                from openai import OpenAI
                client = OpenAI(api_key=api_key.strip())
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt_yt}]
                )
                ai_yt_data = completion.choices[0].message.content.strip()

        except Exception as e:
            print(f"⚠️ AI Social Generation Error ({provider}): {e}")

    # Fallback if AI call failed or returned empty
    if not ai_yt_data:
        yt_title = social_english
        yt_desc = f"{social_english}. Local communities and experts have reacted to this recent development as details continue to unfold."
        yt_tags = social_hashtags
    else:
        # Clean labels and split response
        cleaned_yt = re.sub(r'^(Title:|Description:|Hashtags:|Line \d+:)', '', ai_yt_data, flags=re.MULTILINE).strip()
        yt_lines = [l.strip() for l in cleaned_yt.split('\n') if l.strip()]
        yt_title = yt_lines[0] if len(yt_lines) > 0 else social_english
        yt_desc = yt_lines[1] if len(yt_lines) > 1 else social_english
        yt_tags = yt_lines[2] if len(yt_lines) > 2 else social_hashtags

    return {
        "urdu_headline": urdu_headline,
        "social_english": social_english,
        "social_hashtags": social_hashtags,
        "youtube_title": yt_title,
        "youtube_description": yt_desc,
        "youtube_hashtags": yt_tags
    }