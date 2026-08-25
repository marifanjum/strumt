import re

def generate_ai_news(input_text: str, provider: str = "Groq (Llama)", api_key: str = "", model_name: str = "") -> str:
    """
    Takes raw notes/points and converts them into professional Urdu news 
    using the selected provider and custom model ID.
    """
    if not api_key or not api_key.strip():
        return f"❌ Error: API key for {provider} is missing. Please configure it in the Settings panel."

    # Default model fallbacks if not provided
    if not model_name or not model_name.strip():
        if provider == "Groq (Llama)":
            model_name = "llama-3.3-70b-versatile"
        elif provider == "Google Gemini":
            model_name = "gemini-2.5-flash"
        else:
            model_name = "gpt-4o"

    prompt = f"""
آپ ایک سینئر اردو اخبار کے نیوز ایڈیٹر ہیں۔ نیچے دیے گئے مواد یا پوائنٹس کو ایک کامل، پیشہ ورانہ اردو خبر میں تبدیل کریں۔

ہدایات (سختی سے عمل کریں):
۱. جواب کے فارمیٹ میں بالکل یہ ۳ حصے رکھیں:
TITLE: [ایک جاندار اور مکمل اردو سرخی جو تقریباً 12 الفاظ پر مشتمل ہو]
EXCERPT: [تقریباً 12 الفاظ کا ایک زبردست مختصر خلاصہ یا ذیلی سرخی]
CONTENT: [مکمل خبر۔ خبر میں کوئی بھی بلٹ پوائنٹس (•)، ستارے (*)، ڈیش (---)، یا نمبرنگ استعمال نہ کریں۔ ذیلی عنوانات (subheadings) صرف اس صورت میں استعمال کریں جب خبر 400 الفاظ سے طویل ہو۔ اگر ذیلی عنوانات استعمال کیے جائیں تو ہر ذیلی عنوان کے نیچے کم از کم دو پیراگراف ضرور ہونے چاہئیں۔ کسی بھی صورت میں چار ستارے (****) استعمال نہ کریں۔]

مواد برائے تحریر:
{input_text}
"""

    try:
        if provider == "Groq (Llama)":
            from groq import Groq
            client = Groq(api_key=api_key.strip())
            res = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
            )
            content = res.choices[0].message.content
            return content.replace("****", "").strip()

        elif provider == "Google Gemini":
            from google import genai
            client = genai.Client(api_key=api_key.strip())
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            content = response.text
            return content.replace("****", "").strip()

        elif provider == "OpenAI (GPT)":
            from openai import OpenAI
            client = OpenAI(api_key=api_key.strip())
            res = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            content = res.choices[0].message.content
            return content.replace("****", "").strip()

    except Exception as e:
        print(f"❌ AI Execution Critical Error ({provider}): {e}")
        return f"❌ AI Error ({provider}): {e}"

    return f"❌ AI generation failed for {provider}. Please verify your API key and model ID."


def parse_ai_news_response(raw_text: str) -> dict:
    """
    Parses the TITLE, EXCERPT, and CONTENT from the AI output string.
    Returns a clean dictionary for Streamlit session state and text input fields.
    """
    title_match = re.search(r'TITLE:\s*(.*?)(?=\nEXCERPT:|\nCONTENT:|$)', raw_text, re.DOTALL | re.IGNORECASE)
    excerpt_match = re.search(r'EXCERPT:\s*(.*?)(?=\nCONTENT:|$)', raw_text, re.DOTALL | re.IGNORECASE)
    content_match = re.search(r'CONTENT:\s*(.*)', raw_text, re.DOTALL | re.IGNORECASE)

    title = title_match.group(1).strip() if title_match else ""
    excerpt = excerpt_match.group(1).strip() if excerpt_match else ""
    content = content_match.group(1).strip() if content_match else ""

    # Fallback if tags were stripped or altered
    if not title and not excerpt and not content and raw_text:
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        title = lines[0] if len(lines) > 0 else ""
        excerpt = lines[1] if len(lines) > 1 else ""
        content = "\n\n".join(lines[2:]) if len(lines) > 2 else excerpt

    return {
        "title": title,
        "excerpt": excerpt,
        "content": content
    }


def generate_seo_metadata(headline: str, context: str = "", provider: str = "Groq (Llama)", api_key: str = "", model_name: str = "", include_youtube: bool = True) -> str:
    """Generates SEO description, trending hashtags, and optional YouTube metadata for social posting."""
    if not api_key or not api_key.strip():
        return f"❌ API Key for {provider} is missing."

    if not model_name or not model_name.strip():
        if provider == "Groq (Llama)":
            model_name = "llama-3.3-70b-versatile"
        elif provider == "Google Gemini":
            model_name = "gemini-2.5-flash"
        else:
            model_name = "gpt-4o"

    yt_instruction = "3. YOUTUBE METADATA: Provide a catchy YouTube Title and comma-separated keywords on a single line." if include_youtube else ""

    prompt = f"""
Strictly follow these instructions without any markdown bolding (*), introductory conversational filler, or explanations:
1. HASHTAGS: Exactly 5 trending hashtags starting with #, space-separated on one single line.
2. ENGLISH DESCRIPTION: One single concise English SEO description for social media (1 sentence).
{yt_instruction}

Urdu Headline:
{headline}

Context / Details:
{context}

Format your output exactly as follows:
HASHTAGS: #tag1 #tag2 #tag3 #tag4 #tag5
ENGLISH DESCRIPTION: [Description here]
{"YOUTUBE TITLE: [Title here]\nYOUTUBE KEYWORDS: [keyword1, keyword2, keyword3]" if include_youtube else ""}
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
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            return response.text.replace("*", "").strip()

        elif provider == "OpenAI (GPT)":
            from openai import OpenAI
            client = OpenAI(api_key=api_key.strip())
            res = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            return res.choices[0].message.content.replace("*", "").strip()

    except Exception as e:
        return f"❌ SEO Error ({provider}): {e}"

    return "❌ SEO Failed."