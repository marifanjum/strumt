import os
import io
from PIL import Image, ImageDraw, ImageFont, ImageOps
import arabic_reshaper
from bidi.algorithm import get_display


def resolve_font(font_names: list, size: int) -> ImageFont.FreeTypeFont:
    """Finds the first available font on the system or local directory."""
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
    output_path: str = None,
    width: int = 1200,
    height: int = 630,
    header_text: str = "UMMAT.NET | LATEST NEWS"
) -> Image.Image:
    """
    Generates a 1200x630 featured card using Pillow with RTL Urdu Nastaliq text.
    Returns a PIL.Image object and optionally saves to output_path.
    """
    # 1. Base Canvas
    img = Image.new('RGB', (width, height), color='#1e293b')
    draw = ImageDraw.Draw(img)

    # 2. Header Branding
    draw.rectangle([(0, 0), (width, 70)], fill='#0f172a')
    font_header = resolve_font(["arial.ttf", "Arial.ttf"], 28)
    draw.text((40, 20), header_text, fill="#38bdf8", font=font_header)

    # 3. Center Photo Box
    box_x1, box_y1 = 40, 85
    box_x2, box_y2 = width - 40, 430
    box_w, box_h = box_x2 - box_x1, box_y2 - box_y1

    if news_img_source:
        try:
            if isinstance(news_img_source, Image.Image):
                photo = news_img_source.convert('RGB')
            elif hasattr(news_img_source, "getvalue"):  # Streamlit UploadedFile / BytesIO
                photo = Image.open(news_img_source).convert('RGB')
            elif isinstance(news_img_source, str) and os.path.exists(news_img_source):
                photo = Image.open(news_img_source).convert('RGB')
            else:
                photo = None

            if photo:
                fitted_photo = ImageOps.fit(photo, (box_w, box_h), Image.Resampling.LANCZOS)
                img.paste(fitted_photo, (box_x1, box_y1))
        except Exception as e:
            print(f"⚠️ Photo paste notice: {e}")
            draw.rectangle([(box_x1, box_y1), (box_x2, box_y2)], fill='#334155')
    else:
        draw.rectangle([(box_x1, box_y1), (box_x2, box_y2)], fill='#334155', outline='#475569', width=2)

    # 4. Footer Banner
    draw.rectangle([(0, height - 30), (width, height)], fill='#0f172a')

    # 5. Urdu Nastaliq Headline Text
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

    # Draw centered text with subtle outline/drop-shadow
    text_y = (box_y2 + height - 30) // 2
    draw.text((width // 2, text_y), bidi_text, fill="#ffffff", font=font_headline, anchor="mm")

    # 6. Save or Return Buffer
    if output_path:
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        img.save(output_path, quality=95)

    return img