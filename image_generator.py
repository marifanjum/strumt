from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

def create_news_card(headline_text, output_path="featured_image.png"):
    # 1200x630 HD Canvas (Standard Featured Image Size)
    width, height = 1200, 630
    img = Image.new('RGB', (width, height), color='#1e293b')
    draw = ImageDraw.Draw(img)

    # Top Banner (Ummat.net Branding Header)
    draw.rectangle([(0, 0), (width, 80)], fill='#0f172a')
    
    # Header Branding Text
    try:
        font_header = ImageFont.truetype("arial.ttf", 32)
    except:
        font_header = ImageFont.load_default()
    draw.text((40, 20), "UMMAT.NET | LATEST NEWS", fill="#38bdf8", font=font_header)

    # Center Image / Background Box Placeholder
    draw.rectangle([(40, 100), (width - 40, 420)], fill='#334155', outline='#475569', width=2)

    # Footer Banner
    draw.rectangle([(0, height - 70), (width, height)], fill='#0f172a')

    # Reshape Urdu Headline Text for Correct Rendering
    try:
        reshaped_text = arabic_reshaper.reshape(headline_text)
        bidi_text = get_display(reshaped_text)
        # Font file path in your project folder
        font_headline = ImageFont.truetype("JameelNoori.ttf", 45)
    except Exception:
        bidi_text = headline_text
        font_headline = ImageFont.load_default()

    # Draw Headline Text on Image
    draw.text((width // 2, 500), bidi_text, fill="#ffffff", font=font_headline, anchor="mm")

    # Save Output
    img.save(output_path)
    return output_path

if __name__ == "__main__":
    create_news_card("پاک بھارت کشیدگی میں کمی کے امکانات")
    print("✅ News Card Image Created!")