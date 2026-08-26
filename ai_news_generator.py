import os
import re
import urllib.parse
import requests
from bs4 import BeautifulSoup


def correct_urdu_orthography(text: str) -> str:
    """
    Standardizes and corrects common Urdu typing errors, misspellings,
    hamza errors, and misuse of Do-Chashmi He (ھ) vs Gol He (ہ).
    """
    if not text:
        return ""

    replacements = [
        # Common hamza & Bari-Ye / Chhoti-Ye typos
        (r'\bکوئ\b', 'کوئی'),
        (r'\bکاروائ\b', 'کارروائی'),
        (r'\bکارروائ\b', 'کارروائی'),
        (r'\bماوں\b', 'ماؤں'),
        (r'\bماؤں\b', 'ماؤں'),
        (r'\bبھائ\b', 'بھائی'),
        (r'\bلڑاکائ\b', 'لڑائی'),
        (r'\bرہائشی\b', 'رہائشی'),
        (r'\bرہائش\b', 'رہائش'),
        (r'\bانتہائ\b', 'انتہائی'),
        (r'\bابتدائ\b', 'ابتدائی'),
        (r'\bعدالتِ عظمیٰ\b', 'عدالتِ عظمیٰ'),
        (r'\bوزیراعظم\b', 'وزیر اعظم'),
        (r'\bوزیرصحت\b', 'وزیر صحت'),

        # Do-chashmi He (ھ) vs Gol He (ہ) corrections
        (r'\bآھستہ\b', 'آہستہ'),
        (r'\bچاھئے\b', 'چاہیے'),
        (r'\bچاھیے\b', 'چاہیے'),
        (r'\bچاھتے\b', 'چاہتے'),
        (r'\bچاھتا\b', 'چاہتا'),
        (r'\bچاھتی\b', 'چاہتی'),
        (r'\bچاھا\b', 'چاہا'),
        (r'\bھم\b', 'ہم'),
        (r'\bھمارا\b', 'ہمارا'),
        (r'\bھماری\b', 'ہماری'),
        (r'\bھمارے\b', 'ہمارے'),
        (r'\bھمیشہ\b', 'ہمیشہ'),
        (r'\bھونا\b', 'ہونا'),
        (r'\bھونے\b', 'ہونے'),
        (r'\bھوتی\b', 'ہوتی'),
        (r'\bھوتا\b', 'ہوتا'),
        (r'\bھیں\b', 'ہیں'),
        (r'\bھے\b', 'ہے'),
        (r'\bھو\b', 'ہو'),
        (r'\bھوا\b', 'ہوا'),
        (r'\bھوئی\b', 'ہوئی'),
        (r'\bھوئے\b', 'ہوئے'),
        (r'\bیھ\b', 'یہ'),
        (r'\bوھ\b', 'وہ'),
        (r'\bکھاں\b', 'کہاں'),
        (r'\bیھاں\b', 'یہاں'),
        (r'\bوھاں\b', 'وہاں'),
        (r'\bکھی\b', 'کہی'),
        (r'\bکہہ\b', 'کہہ'),
        (r'\bوجھ\b', 'وجہ'),
        (r'\bجگھ\b', 'جگہ'),
        (r'\bنگاھ\b', 'نگاہ'),
        (r'\bگواھ\b', 'گواہ'),
        (r'\bشھادت\b', 'شہادت'),
        (r'\bشھید\b', 'شہید'),
        (r'\bشھر\b', 'شہر'),
        (r'\bظاھر\b', 'ظاہر'),
        (r'\bکاھش\b', 'کاہش'),

        # Multiple spaces / duplicate full stops
        (r'[۔]{2,}', '۔'),
        (r'[.]{2,}', '.'),
    ]

    cleaned = text
    for pattern, replacement in replacements:
        cleaned = re.sub(pattern, replacement, cleaned)

    return cleaned


def fetch_tweet_details(tweet_url: str) -> dict:
    """
    Fetches full untruncated tweet text, author name, and screen name via direct JSON proxy APIs.
    """
    clean_url = tweet_url.strip().split('?')[0]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # 1. FxTwitter API
    try:
        api_url = re.sub(r'https?://(www\.)?(twitter|x)\.com', 'https://api.fxtwitter.com', clean_url)
        resp = requests.get(api_url, headers=headers, timeout=12)
        if resp.status_code == 200:
            data = resp.json().get("tweet", {})
            full_text = data.get("text", "").strip()
            
            quote_text = ""
            if "quote" in data and data["quote"]:
                q_author = data["quote"].get("author", {}).get("name", "")
                q_handle = data["quote"].get("author", {}).get("screen_name", "")
                q_body = data["quote"].get("text", "")
                quote_text = f"\n[منسلک کوٹ ٹویٹ از {q_author} (@{q_handle}): {q_body}]"

            if full_text:
                return {
                    "author_name": data.get("author", {}).get("name", ""),
                    "handle": f"@{data.get('author', {}).get('screen_name', '')}",
                    "text": (full_text + quote_text).strip(),
                    "url": clean_url
                }
    except Exception as e:
        print(f"FxTwitter note: {e}")

    # 2. VxTwitter API Fallback
    try:
        vx_url = re.sub(r'https?://(www\.)?(twitter|x)\.com', 'https://api.vxtwitter.com', clean_url)
        resp = requests.get(vx_url, headers=headers, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            full_text = data.get("text", "").strip()
            if full_text:
                return {
                    "author_name": data.get("user_name", ""),
                    "handle": f"@{data.get('user_screen_name', '')}",
                    "text": full_text,
                    "url": clean_url
                }
    except Exception as e:
        print(f"VxTwitter note: {e}")

    # 3. oEmbed Fallback
    try:
        oembed_endpoint = f"https://publish.twitter.com/oembed?url={urllib.parse.quote(clean_url)}&omit_script=true"
        resp = requests.get(oembed_endpoint, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            author_name = data.get("author_name", "")
            author_url = data.get("author_url", "")
            handle = author_url.strip('/').split('/')[-1] if author_url else ""

            soup = BeautifulSoup(data.get("html", ""), "html.parser")
            p_tag = soup.find("p")
            tweet_text = p_tag.get_text() if p_tag else soup.get_text()

            return {
                "author_name": author_name,
                "handle": f"@{handle}" if handle and not handle.startswith("@") else handle,
                "text": tweet_text.strip(),
                "url": clean_url
            }
    except Exception as e:
        print(f"oEmbed note: {e}")

    return None


def extract_text_from_url(url: str) -> str:
    """Natively scrapes article body text using requests and Playwright fallback."""
    clean_url = url.strip()
    desktop_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,ur;q=0.8'
    }

    try:
        res = requests.get(clean_url, headers=desktop_headers, timeout=10, verify=False)
        if res.status_code == 200 and len(res.text) > 800:
            soup = BeautifulSoup(res.text, 'html.parser')
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'noscript']):
                tag.decompose()

            article_elem = soup.find('article') or soup.find('div', class_=re.compile(r'content|post|story|entry|detail', re.I))
            p_tags = article_elem.find_all('p') if article_elem else soup.find_all('p')
            paragraphs = [p.get_text().strip() for p in p_tags if len(p.get_text().strip()) > 35]

            if len(paragraphs) >= 2:
                return f"ماخوذ شدہ اصل خبر:\n" + "\n\n".join(paragraphs[:20])
    except Exception:
        pass

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(user_agent=desktop_headers['User-Agent'])
            page.goto(clean_url, timeout=15000, wait_until="domcontentloaded")
            paragraphs = page.eval_on_selector_all(
                "article p, .post-content p, .story-body p, main p, p",
                "elements => elements.map(el => el.innerText.trim()).filter(txt => txt.length > 35)"
            )
            browser.close()
            if paragraphs:
                return f"ماخوذ شدہ اصل خبر:\n" + "\n\n".join(paragraphs[:20])
    except Exception as e:
        print(f"Playwright error: {e}")

    return ""


def preprocess_input_text(raw_input: str) -> str:
    """Extracts content for both webpage URLs and X/Twitter URLs."""
    url_pattern = r'(https?://[^\s]+)'
    urls = re.findall(url_pattern, raw_input)

    extracted_notes = []
    for u in urls:
        if "twitter.com" in u.lower() or "x.com" in u.lower():
            t_data = fetch_tweet_details(u)
            if t_data and t_data.get("text"):
                extracted_notes.append(
                    f"--- ٹویٹ کی مکمل تفصیلات ({u}) ---\n"
                    f"صارف کا نام (Display Name): {t_data['author_name']}\n"
                    f"صارف کا ہینڈل (Handle): {t_data['handle']}\n"
                    f"ٹویٹ کا اصل مکمل متن (Full Untruncated Text):\n{t_data['text']}\n"
                    f"ٹویٹ لنک: {t_data['url']}"
                )
            else:
                extracted_notes.append(f"⚠️ نوٹ: ٹویٹ کا لنک ({u}) دیا گیا تھا مگر مکمل متن حاصل نہ ہو سکا۔")
        else:
            scraped_content = extract_text_from_url(u)
            if scraped_content.strip():
                extracted_notes.append(f"--- ویب صفحہ کا ماخوذ مواد ({u}) ---\n{scraped_content}")

    combined_input = raw_input
    if extracted_notes:
        combined_input += "\n\n" + "\n\n".join(extracted_notes)

    return combined_input


def generate_ai_news(input_text: str, provider: str = "Groq (Llama)", api_key: str = "", model_name: str = "") -> str:
    """
    Generates verified, factual Urdu news articles adhering strictly to
    the 3-line format compatible with Direct Publisher.
    """
    if not api_key or not api_key.strip():
        return f"❌ Error: API key for {provider} is missing. Please configure it in the Settings tab."

    if not model_name or not model_name.strip():
        if provider == "Groq (Llama)":
            model_name = "llama-3.3-70b-versatile"
        elif provider == "Google Gemini":
            model_name = "gemini-2.5-flash"
        else:
            model_name = "gpt-4o"

    augmented_input = preprocess_input_text(input_text)

    prompt = f"""
آپ روزنامہ امت کے ایک انتہائی تجربہ کار، ذمہ دار اور سینئر نیوز ایڈیٹر ہیں۔
نیچے دیے گئے ماخوذ شدہ مواد، ٹویٹس، اور حقائق کو بنیاد بنا کر ایک پیشہ ورانہ، مستند، املا کی غلطیوں سے پاک اور شستہ اردو خبر تحریر کریں۔

سخت ادارتی ہدایات (Editorial Rules):

۱. اردو املا و صحتِ الفاظ کی تصحیح (Orthography Rules):
- اصل مواد میں موجود املا کی غلطیوں کو درست کریں:
  * "کوئ" کو "کوئی" لکھیں۔
  * "کاروائ" کو "کارروائی" لکھیں۔
  * "ماوں" کو "ماؤں" لکھیں۔
  * "انتہائ" کو "انتہائی" اور "ابتدائ" کو "ابتدائی" لکھیں۔
  * دو چشمی ھ اور گول ہ کا درست استعمال کریں: مثلاً "آھستہ" کو "آہستہ"، "چاھئے" کو "چاہیے"، "ھم" کو "ہم"، "ھمارا" کو "ہمارا"، "ھوگا" کو "ہوگا"، "شھید" کو "شہید"، "شھر" کو "شہر" اور "وجھ" کو "وجہ" لکھیں۔

۲. سرخی اور جواب کا ڈھانچہ (Exact Output Structure):
- اگر فراہم کردہ مواد کے آغاز میں کوئی سرخی دی گئی ہو، تو اسے ہی بعینہٖ سرخی کے طور پر استعمال کریں اور خبر کا پورا متن اسی سرخی کے تناظر میں تحریر کریں۔
- جواب کا فارمیٹ بلاناغہ صرف اور صرف یہ ۳ لائنیں ہوں (کوئی اضافی لیبل، ستارے یا مارک ڈاؤن نہ لگائیں):
TITLE: [اردو سرخی]
EXCERPT: [تقریباً 10 سے 14 الفاظ کا مکمل خلاصہ یا ذیلی سرخی]
CONTENT: [خبر کا مکمل متن۔ خبر میں کوئی بلٹ پوائنٹس، ستارے (*)، یا ڈیش ہرگز استعمال نہ کریں۔]

۳. اعداد و شمار (Numbers Rule):
- تمام اعداد کو ہمیشہ ہندسوں (Digits) میں لکھیں (مثلاً 2، 3، 10، 50، 100، 2026 وغیرہ)۔
- صرف اور صرف عدد 1 کے لیے لفظ "ایک" استعمال کریں۔ باقی تمام اعداد لازماً ہندسوں میں ہوں۔

۴. ایکس (Twitter/X) کے بیانات اور ٹویٹس کا اصول:
- صارف کا نام لازماً اردو رسم الخط میں لکھیں (مثلاً: Ch Fawad Hussain کو "چوہدری فواد حسین")، اور اس کے بعد اس کا اصل یوزر ہینڈل انگریزی میں بریکٹ میں درج کریں (مثلاً: سوشل میڈیا پلیٹ فارم ایکس پر اپنے بیان میں معروف رہنما چوہدری فواد حسین (@fawadchaudhry) نے کہا کہ...)۔
- اگر ٹویٹ انگریزی یا کسی دوسری زبان میں ہو، تو اس کا مکمل اور شستہ اردو میں لفظ بہ لفظ (Verbatim) ترجمہ کریں، خلاصہ ہرگز نہ کریں۔
- ٹویٹ کے متن کے گرد کوٹیشن مارکس ("..." یا ”...“) نہ لگائیں۔
- اگر ٹویٹ میں کوئی گالی گلوچ ہو تو صرف اس لفظ کو حذف کریں۔
- ٹویٹ کا پیراگراف مکمل ہونے کے فوری بعد، اگلی لائن پر ایک بالکل الگ اور آزاد پیراگراف (Separate Paragraph) کے طور پر اس ٹویٹ کا اصل URL تنہا درج کریں۔

۵. حقائق اور معروضیت:
- صرف فراہم کردہ مواد اور ٹویٹ کے اصل متن پر انحصار کریں۔ کوئی من گھڑت واقعہ یا بیان شامل نہ کریں۔

مواد برائے تحریر:
{augmented_input}
"""

    try:
        raw_result = ""
        if provider == "Groq (Llama)":
            from groq import Groq
            client = Groq(api_key=api_key.strip())
            res = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
            )
            raw_result = res.choices[0].message.content

        elif provider == "Google Gemini":
            from google import genai
            client = genai.Client(api_key=api_key.strip())
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            raw_result = response.text

        elif provider == "OpenAI (GPT)":
            from openai import OpenAI
            client = OpenAI(api_key=api_key.strip())
            res = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            raw_result = res.choices[0].message.content

        cleaned = re.sub(r'[*_`]', '', raw_result).strip()
        corrected = correct_urdu_orthography(cleaned)

        # Standardize prefix tags so app.py replace logic works cleanly
        if not re.search(r'TITLE:', corrected, re.IGNORECASE):
            lines = [l.strip() for l in corrected.splitlines() if l.strip()]
            if len(lines) >= 2:
                title = lines[0]
                excerpt = lines[1]
                content = "\n\n".join(lines[2:]) if len(lines) > 2 else excerpt
                return f"TITLE: {title}\nEXCERPT: {excerpt}\nCONTENT: {content}"

        return corrected

    except Exception as e:
        print(f"❌ AI Execution Error ({provider}): {e}")
        return f"❌ AI Error ({provider}): {e}"


def parse_ai_news_response(raw_text: str) -> dict:
    """Parses TITLE, EXCERPT, and CONTENT from AI output string."""
    title_match = re.search(r'TITLE:\s*(.*?)(?=\nEXCERPT:|\nCONTENT:|$)', raw_text, re.DOTALL | re.IGNORECASE)
    excerpt_match = re.search(r'EXCERPT:\s*(.*?)(?=\nCONTENT:|$)', raw_text, re.DOTALL | re.IGNORECASE)
    content_match = re.search(r'CONTENT:\s*(.*)', raw_text, re.DOTALL | re.IGNORECASE)

    title = title_match.group(1).strip() if title_match else ""
    excerpt = excerpt_match.group(1).strip() if excerpt_match else ""
    content = content_match.group(1).strip() if content_match else ""

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
