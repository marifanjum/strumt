import sys

def generate_ai_news(input_text, provider="Groq (Llama)", api_key="", model_name=""):
    """
    Takes raw notes/points and converts them into professional Urdu news 
    using the selected provider and custom model ID.
    """
    if not api_key or not api_key.strip():
        return f"❌ Error: API key for {provider} is missing. Please save it in the Settings tab."

    # Smart defaults if model name is empty
    if not model_name or not model_name.strip():
        if provider == "Groq (Llama)": model_name = "groq/compound"
        elif provider == "Google Gemini": model_name = "gemini-3.7-flash"
        else: model_name = "gpt-5.6-sol"

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