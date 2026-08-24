import sys
import os
import glob
import json
import base64
from datetime import datetime
from PIL import Image, ImageOps, ImageDraw
from playwright.sync_api import sync_playwright

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QFileDialog,
    QComboBox, QDialog, QMessageBox, QListWidget, QProgressBar,
    QSplitter, QCheckBox
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QThread, pyqtSignal

# ---------------------------------------------------------
# 1. CONFIG & ASSET RESOLUTION
# ---------------------------------------------------------
PASSWORD_PIN = "999999"
CONFIG_FILE = "settings.json"

DEFAULT_CONFIG = {
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "openai_api_key": "",
    "openai_model": "gpt-4o",
    "groq_api_key": "",
    "groq_model": "llama-3.2-11b-vision-preview"
}

def resource_path(relative_path):
    if not relative_path:
        return ""
    if hasattr(sys, '_MEIPASS'):
        path_in_temp = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(path_in_temp):
            return path_in_temp
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.abspath(".")
    for sub in ["_internal", ""]:
        p = os.path.join(exe_dir, sub, relative_path) if sub else os.path.join(exe_dir, relative_path)
        if os.path.exists(p):
            return p
    return os.path.join(os.path.abspath("."), relative_path)

def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG

def save_settings(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def img_to_base64(img_path):
    if not img_path:
        return ""
    real_path = resource_path(str(img_path))
    if not os.path.exists(real_path):
        real_path = str(img_path)
    if os.path.exists(real_path):
        try:
            with open(real_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
                ext = str(real_path).split('.')[-1].lower()
                mime = "image/png" if ext == "png" else "image/jpeg"
                return f"data:{mime};base64,{b64}"
        except Exception as e:
            print(f"Base64 Error ({real_path}):", e)
    return ""

def font_to_base64(font_path=None):
    candidates = [
        font_path,
        "Jameel Noori Nastaleeq.ttf",
        "Jameel Noori Nastaleeq Regular.ttf",
        "JameelNooriNastaleeq.ttf",
        "JameelNoori.ttf",
        "jameel.ttf",
        "urdu_font.ttf"
    ]
    resolved = None
    for c in candidates:
        if c:
            p = resource_path(str(c))
            if os.path.exists(p):
                resolved = p
                break
    if resolved and os.path.exists(resolved):
        try:
            with open(resolved, "rb") as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
                return f"data:font/ttf;charset=utf-8;base64,{b64}"
        except Exception as e:
            print("Font Base64 Error:", e)
    return ""

def get_chromium_executable_path():
    system_chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Users\{}\AppData\Local\Google\Chrome\Application\chrome.exe".format(os.environ.get('USERNAME', '')),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Microsoft Edge\Application\msedge.exe"
    ]
    for path in system_chrome_paths:
        if os.path.exists(path):
            return path
    return None

# ---------------------------------------------------------
# 2. IMAGE PREPROCESSING
# ---------------------------------------------------------
def prepare_image(img_path, target_w, target_h, remove_bg=False):
    real_path = resource_path(str(img_path))
    if not os.path.exists(real_path):
        real_path = str(img_path)
    if not os.path.exists(real_path):
        return ""

    img = Image.open(real_path).convert("RGBA")
    if remove_bg:
        try:
            from rembg import remove
            img = remove(img)
            img = ImageOps.fit(img, (int(target_w), int(target_h)), Image.Resampling.LANCZOS)
        except Exception as e:
            print("rembg error:", e)
    else:
        img = ImageOps.fit(img, (int(target_w), int(target_h)), Image.Resampling.LANCZOS)

    temp_out = os.path.abspath(f"temp_var_{os.path.basename(real_path)}.png")
    img.save(temp_out, "PNG")
    return temp_out

# ---------------------------------------------------------
# 3. AI STRUCTURE & VARIANT WORKER
# ---------------------------------------------------------
class GenerateCardWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, template_path, image_paths, raw_text, layout_override, provider, config):
        super().__init__()
        self.template_path = template_path
        self.image_paths = image_paths
        self.raw_text = raw_text.strip()
        self.layout_override = layout_override
        self.provider = provider
        self.config = config

    def run(self):
        try:
            design_data = self.analyze_editorial()
            output_file = self.render_html_sync(design_data)
            self.finished.emit(output_file)
        except Exception as e:
            self.error.emit(str(e))

    def analyze_editorial(self):
        img_count = len(self.image_paths)
        prompt = f"""
        You are a Pakistani news art director (Daily Pakistan style).
        Analyze the raw Urdu text and {img_count} images.

        STRICT VERBATIM RULE:
        - NEVER drop, change, rewrite, or paraphrase ANY Urdu words.
        - Split verbatim text into:
          "headline": The title/punchline (e.g. before : or - or the first line).
          "body": The main quote or paragraph.
          "citation": Attribution/source line (if identified, else null).
        - "remove_bg_1": true if portrait cutout, false otherwise.
        - "suggested_layout":
            - If {img_count} >= 2: "dual_split"
            - If text is short (<100 chars) and {img_count} == 1: "hero_banner"
            - If {img_count} == 1: "single_split"
            - If {img_count} == 0: "big_quote"

        RAW TEXT:
        \"\"\"{self.raw_text}\"\"\"

        Return ONLY a raw JSON object:
        {{
          "headline": "...",
          "body": "...",
          "citation": "...",
          "remove_bg_1": false,
          "suggested_layout": "single_split",
          "accent_color": "#dc2626"
        }}
        """

        try:
            if self.provider == "Gemini" and self.config.get("gemini_api_key"):
                from google import genai
                client = genai.Client(api_key=self.config["gemini_api_key"])
                contents = [prompt]
                for p in self.image_paths[:2]:
                    if os.path.exists(p):
                        contents.append(Image.open(p))

                response = client.models.generate_content(
                    model=self.config.get("gemini_model", "gemini-2.5-flash"),
                    contents=contents,
                    config={"response_mime_type": "application/json"}
                )
                return json.loads(response.text)

            elif self.provider in ["OpenAI", "Groq"]:
                from openai import OpenAI
                if self.provider == "OpenAI" and self.config.get("openai_api_key"):
                    client = OpenAI(api_key=self.config["openai_api_key"])
                    model_name = self.config.get("openai_model", "gpt-4o")
                elif self.provider == "Groq" and self.config.get("groq_api_key"):
                    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=self.config["groq_api_key"])
                    model_name = self.config.get("groq_model", "llama-3.2-11b-vision-preview")
                else:
                    raise ValueError("API Key missing")

                messages_content = [{"type": "text", "text": prompt}]
                for p in self.image_paths[:2]:
                    if os.path.exists(p):
                        messages_content.append({"type": "image_url", "image_url": {"url": img_to_base64(p)}})

                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": messages_content}],
                    response_format={"type": "json_object"}
                )
                return json.loads(response.choices[0].message.content)
        except Exception as e:
            print("AI Parsing Warning:", e)

        # Fallback segmentation
        lines = [l.strip() for l in self.raw_text.split('\n') if l.strip()]
        return {
            "headline": lines[0] if len(lines) > 1 else "",
            "body": "\n".join(lines[1:]) if len(lines) > 1 else self.raw_text,
            "citation": "",
            "remove_bg_1": False,
            "suggested_layout": "dual_split" if img_count >= 2 else "single_split",
            "accent_color": "#dc2626"
        }

    def render_html_sync(self, design):
        template_b64 = img_to_base64(self.template_path)
        font_b64 = font_to_base64()

        headline = design.get("headline", "").strip() if design.get("headline") else ""
        body = design.get("body", "").strip() if design.get("body") else self.raw_text
        citation = design.get("citation", "").strip() if design.get("citation") else ""
        accent_color = design.get("accent_color", "#dc2626")
        img_count = len(self.image_paths)

        layout_type = self.layout_override if self.layout_override != "Auto (AI Decides)" else design.get("suggested_layout", "single_split")
        if img_count >= 2:
            layout_type = "dual_split"

        body_len = len(body)
        body_size = 28 if body_len > 400 else (32 if body_len > 250 else 38)
        line_h = 1.42 if body_len > 400 else 1.48

        # --- DYNAMIC LAYOUT BUILDER ---
        if layout_type == "dual_split" and img_count >= 2:
            p1 = prepare_image(self.image_paths[0], 215, 270, False)
            p2 = prepare_image(self.image_paths[1], 215, 270, False)
            b1, b2 = img_to_base64(p1), img_to_base64(p2)
            content_html = f"""
            <div class="top-hero">
                <div class="headline-box" style="font-size: 50px;">{headline}</div>
                <div class="dual-images">
                    <img class="img-frame-dual" src="{b1}">
                    <img class="img-frame-dual" src="{b2}">
                </div>
            </div>
            <div class="body-section">
                <div class="accent-bar" style="background-color: {accent_color};"></div>
                <div class="body-text" style="font-size: {body_size}px; line-height: {line_h};">{body}</div>
            </div>
            """
        elif layout_type == "hero_banner" and img_count >= 1:
            p1 = prepare_image(self.image_paths[0], 950, 420, False)
            b1 = img_to_base64(p1)
            content_html = f"""
            <div class="banner-box">
                <img class="img-banner" src="{b1}">
            </div>
            <div class="banner-text-box">
                <div class="headline-box" style="font-size: 58px; text-align: center;">{headline}</div>
                <div class="body-text" style="font-size: 34px; text-align: center; margin-top: 15px;">{body}</div>
            </div>
            """
        elif layout_type == "big_quote" or img_count == 0:
            content_html = f"""
            <div class="quote-spotlight-box">
                {f'<div class="headline-box" style="font-size: 64px; text-align: center; color: #dc2626; margin-bottom: 20px;">{headline}</div>' if headline else ''}
                <div class="body-text" style="font-size: 42px; line-height: 1.55; text-align: center;">{body}</div>
            </div>
            """
        else: # Standard Single Split
            is_cutout = design.get("remove_bg_1", False)
            p1 = prepare_image(self.image_paths[0], 390, 270, is_cutout)
            b1 = img_to_base64(p1)
            cls = "img-cutout" if is_cutout else "img-frame"
            content_html = f"""
            <div class="top-hero">
                <div class="headline-box">{headline}</div>
                <div class="single-image"><img class="{cls}" src="{b1}"></div>
            </div>
            <div class="body-section">
                <div class="accent-bar" style="background-color: {accent_color};"></div>
                <div class="body-text" style="font-size: {body_size}px; line-height: {line_h};">{body}</div>
            </div>
            """

        font_face_css = f"""
        @font-face {{
            font-family: 'Jameel Custom';
            src: url('{font_b64}') format('truetype');
            font-weight: normal;
            font-style: normal;
        }}
        """ if font_b64 else ""

        html = f"""
        <!DOCTYPE html>
        <html lang="ur">
        <head>
            <meta charset="UTF-8">
            <style>
                {font_face_css}
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    width: 1080px; height: 1350px; position: relative; overflow: hidden;
                    background-color: #f59e0b;
                    font-family: 'Jameel Custom', 'Jameel Noori Nastaleeq', Arial, sans-serif !important;
                }}
                .template-bg {{
                    position: absolute; top: 0; left: 0; width: 1080px; height: 1350px;
                    z-index: 1; pointer-events: none;
                }}

                /* Top Hero: Starts safely below NEWS STORY badge at y=215px */
                .top-hero {{
                    position: absolute; top: 215px; left: 65px; width: 950px; height: 280px;
                    z-index: 5; display: flex; flex-direction: row-reverse; align-items: center; justify-content: space-between;
                }}
                .headline-box {{
                    flex: 1; direction: rtl; text-align: right; padding-left: 20px;
                    font-size: 60px; font-weight: bold; color: #0f172a; line-height: 1.35;
                    font-family: 'Jameel Custom', 'Jameel Noori Nastaleeq', Arial, sans-serif !important;
                    filter: url(#bold-filter);
                }}

                .single-image {{ width: 390px; height: 270px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; }}
                .img-frame {{ width: 390px; height: 270px; object-fit: cover; border: 3px solid #0f172a; border-radius: 8px; box-shadow: 0 10px 22px rgba(0,0,0,0.3); }}
                .img-cutout {{ max-width: 390px; max-height: 280px; filter: drop-shadow(0 12px 20px rgba(0,0,0,0.45)); }}

                .dual-images {{ display: flex; gap: 10px; flex-shrink: 0; }}
                .img-frame-dual {{ width: 215px; height: 270px; object-fit: cover; border: 3px solid #0f172a; border-radius: 6px; box-shadow: 0 8px 18px rgba(0,0,0,0.3); }}

                /* Banner Variant */
                .banner-box {{ position: absolute; top: 215px; left: 65px; width: 950px; height: 420px; z-index: 5; }}
                .img-banner {{ width: 950px; height: 420px; object-fit: cover; border: 3px solid #0f172a; border-radius: 8px; box-shadow: 0 10px 22px rgba(0,0,0,0.3); }}
                .banner-text-box {{ position: absolute; top: 660px; left: 65px; width: 950px; height: 300px; z-index: 5; direction: rtl; }}

                /* Big Quote Variant */
                .quote-spotlight-box {{ position: absolute; top: 260px; left: 85px; width: 910px; height: 680px; z-index: 5; direction: rtl; display: flex; flex-direction: column; justify-content: center; }}

                /* Body Quote */
                .body-section {{
                    position: absolute; top: 515px; left: 65px; width: 950px; height: 445px;
                    z-index: 5; display: flex; flex-direction: row-reverse; align-items: stretch;
                }}
                .accent-bar {{ width: 8px; border-radius: 4px; margin-left: 18px; flex-shrink: 0; }}
                .body-text {{
                    flex: 1; direction: rtl; text-align: justify; text-justify: inter-word;
                    color: #0f172a; padding-left: 10px; font-family: 'Jameel Custom', 'Jameel Noori Nastaleeq', Arial, sans-serif !important;
                    filter: url(#bold-filter);
                }}

                /* Citation Footer */
                .citation-section {{
                    position: absolute; top: 975px; left: 65px; width: 950px; height: 60px;
                    z-index: 5; direction: rtl; display: flex; align-items: center; justify-content: flex-start; gap: 15px;
                }}
                .citation-pill {{ width: 14px; height: 34px; background-color: #ffffff; border-radius: 3px; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }}
                .citation-text {{
                    font-size: 34px; color: #ffffff; font-weight: bold; font-family: 'Jameel Custom', 'Jameel Noori Nastaleeq', Arial, sans-serif !important;
                    text-shadow: 0 2px 5px rgba(0,0,0,0.7); filter: url(#bold-filter);
                }}
            </style>
        </head>
        <body>
            <svg style="position: absolute; width: 0; height: 0; overflow: hidden;">
              <filter id="bold-filter">
                <feMorphology operator="dilate" radius="0.35" in="SourceAlpha" result="thicken" />
                <feMerge><feMergeNode in="thicken" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            </svg>

            <img class="template-bg" src="{template_b64}">

            {content_html}

            {f'''
            <div class="citation-section">
                <div class="citation-pill"></div>
                <div class="citation-text">{citation}</div>
            </div>
            ''' if citation else ''}
        </body>
        </html>
        """

        output_path = os.path.abspath(f"card_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")

        with sync_playwright() as p:
            chrome_exe = get_chromium_executable_path()
            browser = p.chromium.launch(executable_path=chrome_exe, headless=True)
            page = browser.new_page(viewport={"width": 1080, "height": 1350})
            page.set_content(html, wait_until="networkidle")
            page.wait_for_timeout(450)
            page.screenshot(path=output_path, full_page=True)
            browser.close()

        return output_path

# ---------------------------------------------------------
# 4. SETTINGS DIALOG (PIN: 999999)
# ---------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API Configuration")
        self.setFixedSize(480, 440)
        self.config = load_settings()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("<b>Gemini Vision Engine</b>"))
        self.gemini_key = QLineEdit(self.config.get("gemini_api_key", ""))
        self.gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.gemini_key.setPlaceholderText("Enter Gemini API Key")
        self.gemini_model = QLineEdit(self.config.get("gemini_model", "gemini-2.5-flash"))
        layout.addWidget(self.gemini_key)
        layout.addWidget(self.gemini_model)

        layout.addWidget(QLabel("<b>OpenAI Vision Engine</b>"))
        self.openai_key = QLineEdit(self.config.get("openai_api_key", ""))
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key.setPlaceholderText("Enter OpenAI API Key")
        self.openai_model = QLineEdit(self.config.get("openai_model", "gpt-4o"))
        layout.addWidget(self.openai_key)
        layout.addWidget(self.openai_model)

        layout.addWidget(QLabel("<b>Groq Vision Engine</b>"))
        self.groq_key = QLineEdit(self.config.get("groq_api_key", ""))
        self.groq_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.groq_key.setPlaceholderText("Enter Groq API Key")
        self.groq_model = QLineEdit(self.config.get("groq_model", "llama-3.2-11b-vision-preview"))
        layout.addWidget(self.groq_key)
        layout.addWidget(self.groq_model)

        save_btn = QPushButton("Save Settings")
        save_btn.setStyleSheet("background-color: #0E7BFE; color: white; padding: 8px; font-weight: bold;")
        save_btn.clicked.connect(self.save)
        layout.addWidget(save_btn)

        self.setLayout(layout)

    def save(self):
        new_data = {
            "gemini_api_key": self.gemini_key.text().strip(),
            "gemini_model": self.gemini_model.text().strip(),
            "openai_api_key": self.openai_key.text().strip(),
            "openai_model": self.openai_model.text().strip(),
            "groq_api_key": self.groq_key.text().strip(),
            "groq_model": self.groq_model.text().strip(),
        }
        save_settings(new_data)
        self.accept()

# ---------------------------------------------------------
# 5. MAIN APPLICATION GUI
# ---------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI StoryShare Social Card Producer")
        self.resize(1220, 840)
        self.image_paths = []
        self.last_generated_card = None
        self.template_path = "StoryShareTemplate.png"
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        top_bar = QHBoxLayout()
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Gemini", "OpenAI", "Groq"])

        settings_btn = QPushButton("⚙ Settings")
        settings_btn.clicked.connect(self.unlock_settings)

        top_bar.addWidget(QLabel("Vision AI:"))
        top_bar.addWidget(self.provider_combo)
        top_bar.addWidget(settings_btn)
        left_layout.addLayout(top_bar)

        # Layout Variant Selector
        layout_sel_box = QHBoxLayout()
        layout_sel_box.addWidget(QLabel("Card Layout Style:"))
        self.layout_combo = QComboBox()
        self.layout_combo.addItems([
            "Auto (AI Decides)",
            "Single Split (Story Share)",
            "Hero Banner (Wide Photo + Breaking News)",
            "Big Quote (Editorial Spotlight)"
        ])
        layout_sel_box.addWidget(self.layout_combo)
        left_layout.addLayout(layout_sel_box)

        # Input Images
        left_layout.addWidget(QLabel("<b>Subject Images (Supports 1 or 2):</b>"))
        self.img_list = QListWidget()
        left_layout.addWidget(self.img_list)

        img_btn_layout = QHBoxLayout()
        add_img_btn = QPushButton("+ Add Images")
        add_img_btn.clicked.connect(self.add_images)
        clear_img_btn = QPushButton("Clear")
        clear_img_btn.clicked.connect(self.clear_images)
        img_btn_layout.addWidget(add_img_btn)
        img_btn_layout.addWidget(clear_img_btn)
        left_layout.addLayout(img_btn_layout)

        # Urdu Content Input
        left_layout.addWidget(QLabel("<b>Raw Urdu Story / News Content (Single Box):</b>"))
        self.raw_text_input = QTextEdit()
        self.raw_text_input.setPlaceholderText("یہاں خبر، سرخی، اقتباس یا مکمل متن درج کریں...")
        self.raw_text_input.setAlignment(Qt.AlignmentFlag.AlignRight)
        left_layout.addWidget(self.raw_text_input)

        self.generate_btn = QPushButton("Generate Variable Social Card")
        self.generate_btn.setStyleSheet("background-color: #0E7BFE; color: white; padding: 10px; font-weight: bold;")
        self.generate_btn.clicked.connect(self.generate_card)
        left_layout.addWidget(self.generate_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        left_layout.addWidget(self.progress)

        # Right Preview Panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.preview_label = QLabel("Card Preview will appear here")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("border: 2px dashed #94a3b8; background: #0f172a; color: #94a3b8;")

        self.save_btn = QPushButton("Save Card to Disk")
        self.save_btn.setEnabled(False)
        self.save_btn.setStyleSheet("background-color: #F3A038; color: #000; padding: 8px; font-weight: bold;")
        self.save_btn.clicked.connect(self.save_card)

        right_layout.addWidget(self.preview_label, 1)
        right_layout.addWidget(self.save_btn)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        layout = QHBoxLayout(main_widget)
        layout.addWidget(splitter)
        self.setCentralWidget(main_widget)

    def unlock_settings(self):
        auth_dialog = QDialog(self)
        auth_dialog.setWindowTitle("Password Verification")
        vbox = QVBoxLayout()
        pin_field = QLineEdit()
        pin_field.setEchoMode(QLineEdit.EchoMode.Password)
        pin_field.setPlaceholderText("Enter 6-digit PIN")
        ok_btn = QPushButton("Verify")

        def check_pin():
            if pin_field.text().strip() == PASSWORD_PIN:
                auth_dialog.accept()
                SettingsDialog(self).exec()
            else:
                QMessageBox.warning(self, "Access Denied", "Incorrect PIN.")
                auth_dialog.reject()

        ok_btn.clicked.connect(check_pin)
        vbox.addWidget(QLabel("Enter Administrator PIN:"))
        vbox.addWidget(pin_field)
        vbox.addWidget(ok_btn)
        auth_dialog.setLayout(vbox)
        auth_dialog.exec()

    def add_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Subject Images", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if files:
            self.image_paths.extend(files)
            for f in files:
                self.img_list.addItem(os.path.basename(f))

    def clear_images(self):
        self.image_paths.clear()
        self.img_list.clear()

    def generate_card(self):
        real_template = resource_path(self.template_path)
        if not os.path.exists(real_template) and not os.path.exists(self.template_path):
            QMessageBox.critical(self, "Template Missing", f"Please make sure '{self.template_path}' is placed in the application directory.")
            return

        raw_text = self.raw_text_input.toPlainText().strip()
        if not raw_text:
            QMessageBox.warning(self, "Missing Content", "Please paste Urdu content into the text area.")
            return

        self.generate_btn.setEnabled(False)
        self.progress.show()

        config = load_settings()
        provider = self.provider_combo.currentText()
        
        # Map Layout Combo to Key
        layout_map = {
            "Auto (AI Decides)": "Auto (AI Decides)",
            "Single Split (Story Share)": "single_split",
            "Hero Banner (Wide Photo + Breaking News)": "hero_banner",
            "Big Quote (Editorial Spotlight)": "big_quote"
        }
        chosen_layout = layout_map.get(self.layout_combo.currentText(), "single_split")

        self.worker = GenerateCardWorker(
            self.template_path, self.image_paths, raw_text, chosen_layout, provider, config
        )
        self.worker.finished.connect(self.on_success)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_success(self, output_path):
        self.last_generated_card = output_path
        self.progress.hide()
        self.generate_btn.setEnabled(True)
        self.save_btn.setEnabled(True)

        pixmap = QPixmap(output_path)
        self.preview_label.setPixmap(
            pixmap.scaled(self.preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        )

    def on_error(self, err_msg):
        self.progress.hide()
        self.generate_btn.setEnabled(True)
        QMessageBox.critical(self, "Generation Failed", f"Error:\n{err_msg}")

    def save_card(self):
        if not self.last_generated_card or not os.path.exists(self.last_generated_card):
            return
        dest, _ = QFileDialog.getSaveFileName(self, "Save Final Image", "social_card.png", "PNG (*.png)")
        if dest:
            import shutil
            shutil.copy(self.last_generated_card, dest)
            QMessageBox.information(self, "Saved", f"Card saved successfully to:\n{dest}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
