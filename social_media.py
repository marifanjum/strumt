import os
import re
import urllib.parse
import urllib.request
import json

def clean_input_text(text):
    """Clean the input text"""
    txt = str(text).replace('TITLE:', '').replace('CONTENT:', '').replace('KEYWORDS:', '').strip()
    return txt

def translate_urdu_to_english(text):
    """Free Google Translate for the first part"""
    try:
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=ur&tl=en&dt=t&q=" + urllib.parse.quote(text)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            translated = "".join([sentence[0] for sentence in result[0] if sentence[0]])
            return translated
    except Exception:
        return text

def generate_social_post(input_text, is_manual=False):
    return generate_video_metadata(input_text)

def generate_video_metadata(video_topic_or_script, provider="Google Gemini", api_key=""):
    """
    Generate live YouTube SEO and social post metadata dynamically based on the selected AI provider and API key.
    """
    raw_text = clean_input_text(video_topic_or_script)
    if not raw_text:
        return "Please enter the Urdu news text first."

    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    urdu_headline = lines[0] if lines else raw_text

    # --- 1st Part: All Social ---
    social_english = translate_urdu_to_english(urdu_headline)
    
    words = re.findall(r'\b[a-zA-Z]{4,}\b', social_english)
    ignore_words = {'were', 'them', 'they', 'from', 'with', 'that', 'this', 'have', 'been', 'does', 'your'}
    filtered_words = [w for w in words if w.lower() not in ignore_words]
    social_hashtags = " ".join([f"#{w.capitalize()}" for w in filtered_words[:5]]) if filtered_words else "#News #Updates #Trending #GlobalNews #UrduNews"

    # --- 2nd Part: AI Metadata Generation ---
    ai_yt_data = None
    
    prompt_yt = f"""
    You are a YouTube SEO Expert. Based strictly on this NEW input text, generate high-converting YouTube Metadata in natural English:
    New Text: "{raw_text}"

    STRICT OUTPUT REQUIREMENTS:
    1. Line 1: One Catchy High-CTR YouTube Title in English (Under 70 characters, complete sentence).
    2. Line 2: Empty line.
    3. Line 3: A natural 2-sentence YouTube Description in fluent, grammatically perfect English matching the context.
    4. Line 4: Empty line.
    5. Line 5: 5 Powerful YouTube Hashtags (e.g. #Willpower #SuccessSecrets).

    DO NOT ADD ANY LABELS LIKE "Title:", "Description:", "Hashtags:". Output fresh raw text only.
    """

    if not api_key:
        print(f"AI Error ({provider}): No API key provided.")
    else:
        try:
            # 1. Google Gemini
            if provider == "Google Gemini":
                from google import genai
                client = genai.Client(api_key=api_key)
                models_to_try = [
                    'gemini-2.5-flash',
                    'gemini-2.0-flash',
                    'gemini-1.5-flash'
                ]
                for model_name in models_to_try:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt_yt,
                        )
                        if response and hasattr(response, 'text') and response.text:
                            ai_yt_data = response.text.strip()
                            print(f"✅ Successfully generated using model: {model_name}")
                            break
                    except Exception as inner_e:
                        print(f"⚠️ Model {model_name} failed. Reason: {inner_e}")
                        continue

            # 2. Groq (Llama)
            elif provider == "Groq (Llama)":
                from groq import Groq
                client = Groq(api_key=api_key)
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt_yt}],
                    model="llama-3.3-70b-versatile",
                )
                ai_yt_data = chat_completion.choices[0].message.content.strip()

            # 3. OpenAI (GPT)
            elif provider == "OpenAI (GPT)":
                from openai import OpenAI
                client = OpenAI(api_key=api_key)
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt_yt}]
                )
                ai_yt_data = completion.choices[0].message.content.strip()

        except Exception as e:
            print(f"AI Execution Error ({provider}):", e)

    # Fallback if AI data is empty
    if not ai_yt_data:
        print("💡 AI Generation failed or key missing! Using Local Translation Fallback.")
        ai_yt_data = f"{social_english}\n\n{social_english}. Local communities and experts have reacted to this recent development as details continue to unfold.\n\n{social_hashtags}"

    # Clean unnecessary label prefixes if any remain
    ai_yt_data = re.sub(r'^(Title:|Description:|Hashtags:|Line \d+:)', '', ai_yt_data, flags=re.MULTILINE).strip()

    new_output = f"""{urdu_headline}
More details in comments

{social_english}

{social_hashtags}

|

{ai_yt_data}"""

    return new_output