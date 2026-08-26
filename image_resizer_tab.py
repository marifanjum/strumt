import os
import io
import math
import re
import tempfile
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import streamlit as st
from ai_upscaler import upscale_image_cpu


def apply_image_enhancements(
    img: Image.Image,
    brightness: float = 1.0,
    contrast: float = 1.0,
    sharpness: float = 1.0,
    color: float = 1.0
) -> Image.Image:
    """Applies lighting, contrast, clarity, and saturation adjustments."""
    enhanced = img
    if brightness != 1.0:
        enhanced = ImageEnhance.Brightness(enhanced).enhance(brightness)
    if contrast != 1.0:
        enhanced = ImageEnhance.Contrast(enhanced).enhance(contrast)
    if color != 1.0:
        enhanced = ImageEnhance.Color(enhanced).enhance(color)
    if sharpness != 1.0:
        enhanced = ImageEnhance.Sharpness(enhanced).enhance(sharpness)
    return enhanced


def create_gradient(width: int, height: int, c1_hex: str, c2_hex: str, direction: str) -> Image.Image:
    def hex_to_rgb(hex_str):
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 3:
            hex_str = ''.join(c * 2 for c in hex_str)
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

    c1 = hex_to_rgb(c1_hex)
    c2 = hex_to_rgb(c2_hex)

    base = Image.new("RGB", (width, height), c1)
    draw = ImageDraw.Draw(base)

    if direction in ["Top → Bottom", "Bottom → Top"]:
        for y in range(height):
            ratio = y / max(1, height - 1)
            if direction == "Bottom → Top":
                ratio = 1.0 - ratio
            r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
            g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
            b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
    else:
        for x in range(width):
            ratio = x / max(1, width - 1)
            if direction == "Right → Left":
                ratio = 1.0 - ratio
            r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
            g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
            b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
            draw.line([(x, 0), (x, height)], fill=(r, g, b))

    return base


def compute_collage_slots(W: int, H: int, count: int, layout: str) -> list:
    slots = []

    if layout == "Row":
        w = math.floor(W / count)
        for i in range(count):
            slots.append((i * w, 0, w, H))

    elif layout == "Column":
        h = math.floor(H / count)
        for i in range(count):
            slots.append((0, i * h, W, h))

    elif layout == "Grid — Equal (4:3 ratio)":
        if count <= 3:
            rows, cols = 1, count
        elif count <= 4:
            rows, cols = 1, 4
        elif count <= 6:
            rows, cols = 2, 3
        elif count <= 8:
            rows, cols = 2, 4
        elif count <= 10:
            rows, cols = 2, 5
        elif count <= 12:
            rows, cols = 2, 6
        elif count <= 14:
            rows, cols = 2, 7
        elif count <= 16:
            rows, cols = 2, 8
        else:
            cols = math.ceil(math.sqrt(count * (4 / 3)))
            rows = math.ceil(count / cols)

        cell_w = math.floor(W / cols)
        cell_h = math.floor(H / rows)
        idx = 0
        for r in range(rows):
            for c in range(cols):
                if idx < count:
                    slots.append((c * cell_w, r * cell_h, cell_w, cell_h))
                    idx += 1

    elif layout == "1 Big (Left) + Small Column":
        big_w = math.floor(W / 3)
        small_w = W - big_w
        slots.append((0, 0, big_w, H))
        small_count = count - 1
        if small_count > 0:
            small_h = math.floor(H / small_count)
            for i in range(small_count):
                slots.append((big_w, i * small_h, small_w, small_h))

    elif layout == "1 Big (Left) + Others Grid (Right)":
        big_w = math.floor(W / 3)
        grid_w = W - big_w
        slots.append((0, 0, big_w, H))
        others = count - 1
        if others > 0:
            rows = 2 if others > 4 else 1
            cols = math.ceil(others / rows)
            cell_w = math.floor(grid_w / cols)
            cell_h = math.floor(H / rows)
            idx = 1
            for r in range(rows):
                for c in range(cols):
                    if idx < count:
                        slots.append((big_w + c * cell_w, r * cell_h, cell_w, cell_h))
                        idx += 1

    elif layout == "1 Big (Right) + Others Rows (Left)":
        big_w = math.floor(W / 3)
        grid_w = W - big_w
        slots.append((grid_w, 0, big_w, H))
        others = count - 1
        if others > 0:
            rows = 2 if others > 4 else 1
            cols = math.ceil(others / rows)
            cell_w = math.floor(grid_w / cols)
            cell_h = math.floor(H / rows)
            idx = 1
            for r in range(rows):
                for c in range(cols):
                    if idx < count:
                        slots.append((c * cell_w, r * cell_h, cell_w, cell_h))
                        idx += 1

    elif layout == "1 Big (Top) + Others Rows (Bottom)":
        big_h = math.floor(H / 3)
        grid_h = H - big_h
        slots.append((0, 0, W, big_h))
        others = count - 1
        if others > 0:
            rows = 2 if others > 4 else 1
            cols = math.ceil(others / rows)
            cell_w = math.floor(W / cols)
            cell_h = math.floor(grid_h / rows)
            idx = 1
            for r in range(rows):
                for c in range(cols):
                    if idx < count:
                        slots.append((c * cell_w, big_h + r * cell_h, cell_w, cell_h))
                        idx += 1

    elif layout == "1 Big (Bottom) + Others Grid (Top)":
        big_h = math.floor(H / 3)
        grid_h = H - big_h
        slots.append((0, grid_h, W, big_h))
        others = count - 1
        if others > 0:
            rows = 2 if others > 4 else 1
            cols = math.ceil(others / rows)
            cell_w = math.floor(W / cols)
            cell_h = math.floor(grid_h / rows)
            idx = 1
            for r in range(rows):
                for c in range(cols):
                    if idx < count:
                        slots.append((c * cell_w, r * cell_h, cell_w, cell_h))
                        idx += 1

    elif layout == "2 Big Left + Others Grid (Right)":
        big_w = math.floor(W / 3)
        grid_w = W - big_w
        big_h = math.floor(H / 2)
        if count >= 1:
            slots.append((0, 0, big_w, big_h))
        if count >= 2:
            slots.append((0, big_h, big_w, big_h))
        others = max(0, count - 2)
        if others > 0:
            rows = 2 if others > 4 else math.ceil(others / 2)
            cols = math.ceil(others / rows)
            cell_w = math.floor(grid_w / cols)
            cell_h = math.floor(H / rows)
            idx = 2
            for r in range(rows):
                for c in range(cols):
                    if idx < count:
                        slots.append((big_w + c * cell_w, r * cell_h, cell_w, cell_h))
                        idx += 1

    elif layout == "2 Big Right + Others Grid (Left)":
        big_w = math.floor(W / 3)
        grid_w = W - big_w
        big_h = math.floor(H / 2)
        if count >= 1:
            slots.append((grid_w, 0, big_w, big_h))
        if count >= 2:
            slots.append((grid_w, big_h, big_w, big_h))
        others = max(0, count - 2)
        if others > 0:
            rows = 2 if others > 4 else math.ceil(others / 2)
            cols = math.ceil(others / rows)
            cell_w = math.floor(grid_w / cols)
            cell_h = math.floor(H / rows)
            idx = 2
            for r in range(rows):
                for c in range(cols):
                    if idx < count:
                        slots.append((c * cell_w, r * cell_h, cell_w, cell_h))
                        idx += 1

    elif layout == "2 Big (Top Row) + Small Bottom":
        big_w = math.floor(W / 2)
        big_h = math.floor(H / 3)
        small_h = H - big_h
        if count >= 1:
            slots.append((0, 0, big_w, big_h))
        if count >= 2:
            slots.append((big_w, 0, big_w, big_h))
        small_count = max(0, count - 2)
        if small_count > 0:
            small_w = math.floor(W / small_count)
            for i in range(small_count):
                slots.append((i * small_w, big_h, small_w, small_h))

    else:
        cols = math.ceil(math.sqrt(count))
        rows = math.ceil(count / cols)
        cell_w = math.floor(W / cols)
        cell_h = math.floor(H / rows)
        idx = 0
        for r in range(rows):
            for c in range(cols):
                if idx < count:
                    slots.append((c * cell_w, r * cell_h, cell_w, cell_h))
                    idx += 1

    return slots


def render_resizer_canvas(
    canvas_w: int,
    canvas_h: int,
    images: list,
    mode: str,
    layout: str,
    fit_mode: str,
    zoom_val: float,
    pan_x: int,
    pan_y: int,
    brightness_val: float,
    contrast_val: float,
    sharpness_val: float,
    color_val: float,
    use_gradient: bool,
    grad_c1: str,
    grad_c2: str,
    grad_dir: str,
    use_border: bool,
    use_credit: bool,
    credit_text: str,
    credit_pos: str
) -> Image.Image:
    if use_gradient:
        canvas = create_gradient(canvas_w, canvas_h, grad_c1, grad_c2, grad_dir)
    else:
        canvas = Image.new("RGB", (canvas_w, canvas_h), (15, 23, 42))

    draw = ImageDraw.Draw(canvas)

    if mode == "Single Image Mode":
        slots = [(0, 0, canvas_w, canvas_h)]
    else:
        slots = compute_collage_slots(canvas_w, canvas_h, max(1, len(images)), layout)

    for i, (sx, sy, sw, sh) in enumerate(slots):
        if i < len(images) and images[i] is not None:
            raw_img = images[i].convert("RGB")
            
            # Apply Live Quality & Lighting Enhancements
            raw_img = apply_image_enhancements(
                raw_img,
                brightness=brightness_val,
                contrast=contrast_val,
                sharpness=sharpness_val,
                color=color_val
            )

            # 1. Base Fit Strategy
            if fit_mode == "Auto Zoom to Fill (Crop)":
                base_scale = max(sw / raw_img.width, sh / raw_img.height)
            elif fit_mode == "Fit Longest Side (Letterbox)":
                base_scale = min(sw / raw_img.width, sh / raw_img.height)
            else:
                base_scale = 1.0

            # 2. Apply Custom User Zoom
            final_scale = base_scale * zoom_val
            target_w = max(1, int(raw_img.width * final_scale))
            target_h = max(1, int(raw_img.height * final_scale))

            scaled_img = raw_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

            # 3. Calculate Center + Pan Offsets
            base_offset_x = (sw - target_w) // 2
            base_offset_y = (sh - target_h) // 2

            final_img_x = base_offset_x + pan_x
            final_img_y = base_offset_y + pan_y

            # 4. Crop to Slot Bounding Box
            slot_canvas = Image.new("RGB", (sw, sh), (15, 23, 42) if not use_gradient else (0, 0, 0))
            slot_canvas.paste(scaled_img, (final_img_x, final_img_y))
            canvas.paste(slot_canvas, (sx, sy))
        else:
            draw.rectangle([sx + 2, sy + 2, sx + sw - 2, sy + sh - 2], fill=(30, 41, 59), outline=(71, 85, 105), width=1)

        if mode == "Collage Mode":
            draw.rectangle([sx, sy, sx + sw, sy + sh], outline=(51, 65, 85), width=2)

    if use_border:
        draw.rectangle([8, 8, canvas_w - 8, canvas_h - 8], outline=(148, 163, 184), width=2)
        draw.rectangle([12, 12, canvas_w - 12, canvas_h - 12], outline=(148, 163, 184), width=2)

    if use_credit and credit_text.strip():
        txt = credit_text.strip()
        try:
            font = ImageFont.truetype("Arial", 16)
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), txt, font=font)
        tw = bbox[2] - bbox[0] + 24
        th = bbox[3] - bbox[1] + 12

        x = (canvas_w - tw - 16) if "Right" in credit_pos else 16
        y = (canvas_h - th - 16) if "Bottom" in credit_pos else 16

        draw.rectangle([x, y, x + tw, y + th], fill=(0, 0, 0))
        draw.text((x + 12, y + 6), txt, fill=(255, 255, 255), font=font)

    return canvas


def on_single_upload_change():
    uploaded = st.session_state.get("single_resizer_uploader")
    if uploaded:
        base_name = os.path.splitext(uploaded.name)[0]
        st.session_state["resizer_user_filename"] = base_name
        st.session_state["ai_enhanced_image"] = None


def on_collage_upload_change():
    uploaded_list = st.session_state.get("collage_uploader")
    if uploaded_list and len(uploaded_list) > 0:
        base_name = os.path.splitext(uploaded_list[0].name)[0]
        st.session_state["resizer_user_filename"] = f"{base_name}_collage"


def render_image_resizer_tab(config: dict):
    st.markdown("### 🖼️ Image Resizer & Collage Studio")

    canvas_w = int(config.get("resizer_width", 1200))
    canvas_h = int(config.get("resizer_height", 720))

    if "ai_enhanced_image" not in st.session_state:
        st.session_state["ai_enhanced_image"] = None

    top_col1, top_col2, top_col3 = st.columns([1.5, 1.5, 2])
    with top_col1:
        mode = st.selectbox("Mode:", ["Single Image Mode", "Collage Mode"], key="resizer_mode")

    with top_col2:
        fit_mode = st.selectbox(
            "Fitting Strategy:", 
            ["Auto Zoom to Fill (Crop)", "Fit Longest Side (Letterbox)", "Force Stretch"],
            key="resizer_fit"
        )

    layout_choice = "Grid — Equal"
    collage_count = 3
    if mode == "Collage Mode":
        with top_col3:
            layout_choice = st.selectbox(
                "Collage Layout:", 
                [
                    "Grid — Equal",
                    "Grid — Equal (4:3 ratio)",
                    "Row",
                    "Column",
                    "1 Big (Left) + Small Column",
                    "1 Big (Left) + Others Grid (Right)",
                    "1 Big (Right) + Others Rows (Left)",
                    "1 Big (Top) + Others Rows (Bottom)",
                    "1 Big (Bottom) + Others Grid (Top)",
                    "2 Big Left + Others Grid (Right)",
                    "2 Big Right + Others Grid (Left)",
                    "2 Big (Top Row) + Small Bottom"
                ]
            )
            collage_count = st.slider("Number of Images:", min_value=2, max_value=16, value=3)

    st.markdown("#### 📂 Image Inputs")
    loaded_images = []

    if mode == "Single Image Mode":
        in_col1, in_col2 = st.columns([2.8, 1.2])
        with in_col1:
            single_file = st.file_uploader(
                "Upload Image:", 
                type=["png", "jpg", "jpeg", "webp"], 
                key="single_resizer_uploader",
                on_change=on_single_upload_change
            )

        base_img = None
        if single_file:
            if st.session_state.get("ai_enhanced_image") is not None:
                base_img = st.session_state["ai_enhanced_image"]
            else:
                base_img = Image.open(single_file)

            with in_col2:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                if st.button("⚡ Improve Quality (AI Denoise & 2x)", type="secondary", width="stretch"):
                    with st.spinner("🧠 Enhancing details with Real-ESRGAN..."):
                        raw_pil = Image.open(single_file)
                        st.session_state["ai_enhanced_image"] = upscale_image_cpu(raw_pil, scale=2)
                        st.rerun()

                if st.session_state.get("ai_enhanced_image") is not None:
                    st.caption(f"✨ AI Enhanced: {base_img.width}x{base_img.height}px")
                    if st.button("↺ Reset to Original", width="stretch"):
                        st.session_state["ai_enhanced_image"] = None
                        st.rerun()

        loaded_images.append(base_img)
    else:
        uploaded_files = st.file_uploader(
            f"Upload up to {collage_count} Images for Collage:", 
            type=["png", "jpg", "jpeg", "webp"], 
            accept_multiple_files=True,
            key="collage_uploader",
            on_change=on_collage_upload_change
        )
        for i in range(collage_count):
            if uploaded_files and i < len(uploaded_files):
                loaded_images.append(Image.open(uploaded_files[i]))
            else:
                loaded_images.append(None)

    # 1. Transform Controls (Zoom & Pan Positioning)
    with st.expander("🔍 Zoom & Positioning Controls", expanded=True):
        pos_c1, pos_c2, pos_c3 = st.columns(3)
        with pos_c1:
            zoom_val = st.slider("Zoom Level:", min_value=0.2, max_value=4.0, value=1.0, step=0.05, key="resizer_zoom_slider")
        with pos_c2:
            pan_x = st.slider("Move Horizontal (X Offset):", min_value=-int(canvas_w // 2), max_value=int(canvas_w // 2), value=0, step=5, key="resizer_pan_x_slider")
        with pos_c3:
            pan_y = st.slider("Move Vertical (Y Offset):", min_value=-int(canvas_h // 2), max_value=int(canvas_h // 2), value=0, step=5, key="resizer_pan_y_slider")

    # 2. Lighting, Clarity & Color Adjustments (Brightness, Contrast, Sharpness, Saturation)
    with st.expander("✨ Lighting, Clarity & Color Adjustments", expanded=True):
        eq_c1, eq_c2, eq_c3, eq_c4 = st.columns(4)
        with eq_c1:
            brightness_val = st.slider("Brightness:", 0.5, 2.0, 1.0, step=0.05, key="resizer_bright_slider")
        with eq_c2:
            contrast_val = st.slider("Contrast:", 0.5, 2.0, 1.0, step=0.05, key="resizer_contrast_slider")
        with eq_c3:
            sharpness_val = st.slider("Sharpness (Clarity):", 0.5, 3.0, 1.0, step=0.1, key="resizer_sharp_slider")
        with eq_c4:
            color_val = st.slider("Saturation (Color):", 0.0, 2.0, 1.0, step=0.05, key="resizer_color_slider")

    # 3. Background, Border & Credit Overlays
    with st.expander("🎨 Background, Border & Credit Overlays", expanded=False):
        style_c1, style_c2, style_c3 = st.columns(3)
        with style_c1:
            use_border = st.checkbox("Double Framing Border", value=False)
            use_gradient = st.checkbox("Gradient Background", value=False)
            grad_c1 = st.color_picker("Gradient Start:", value="#000000")
            grad_c2 = st.color_picker("Gradient End:", value="#1E293B")
            grad_dir = st.selectbox("Direction:", ["Left → Right", "Right → Left", "Top → Bottom", "Bottom → Top"])

        with style_c2:
            use_credit = st.checkbox("Credit Label Overlay", value=False)
            credit_text = st.text_input("Credit Text:", placeholder="e.g. Photo: AFP / Daily Ummat")
            credit_pos = st.selectbox("Position:", ["Top Right", "Top Left", "Bottom Right", "Bottom Left"])

    # Render Output Canvas with Transformations
    rendered_image = render_resizer_canvas(
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        images=loaded_images,
        mode=mode,
        layout=layout_choice,
        fit_mode=fit_mode,
        zoom_val=zoom_val,
        pan_x=pan_x,
        pan_y=pan_y,
        brightness_val=brightness_val,
        contrast_val=contrast_val,
        sharpness_val=sharpness_val,
        color_val=color_val,
        use_gradient=use_gradient,
        grad_c1=grad_c1,
        grad_c2=grad_c2,
        grad_dir=grad_dir,
        use_border=use_border,
        use_credit=use_credit,
        credit_text=credit_text,
        credit_pos=credit_pos
    )

    st.markdown("#### 👁️ Canvas Preview")
    st.image(rendered_image, caption=f"Canvas Output ({canvas_w}x{canvas_h})", width="stretch")

    st.markdown("---")
    bot_c1, bot_c2, bot_c3, bot_c4, bot_c5 = st.columns([2, 1, 1.5, 1.5, 1.5])

    if "resizer_user_filename" not in st.session_state:
        st.session_state["resizer_user_filename"] = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    with bot_c1:
        st.text_input("Filename (without extension):", key="resizer_user_filename")

    with bot_c2:
        format_choice = st.selectbox("Format:", ["WebP (.webp)", "JPG (.jpg)", "PNG (.png)"], key="resizer_format_choice")

    ext = ".webp" if "WebP" in format_choice else (".jpg" if "JPG" in format_choice else ".png")
    fmt = "WEBP" if "WebP" in format_choice else ("JPEG" if "JPG" in format_choice else "PNG")

    raw_typed_name = st.session_state.get("resizer_user_filename", "").strip()
    raw_clean_name = os.path.splitext(raw_typed_name)[0]
    clean_name = re.sub(r'[^a-zA-Z0-9-_\s]', '', raw_clean_name).strip().replace(' ', '_')
    if not clean_name:
        clean_name = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    final_filename = clean_name + ext

    # Save the rendered transformation directly to bytes
    img_byte_arr = io.BytesIO()
    rendered_image.save(img_byte_arr, format=fmt, quality=95)
    img_bytes = img_byte_arr.getvalue()

    with bot_c3:
        st.download_button(
            label="💾 Download Image",
            data=img_bytes,
            file_name=final_filename,
            mime=f"image/{fmt.lower()}",
            width="stretch"
        )

    with bot_c4:
        if st.button("🚀 Send to Publisher", type="primary", width="stretch"):
            st.session_state["story_img_bytes"] = img_bytes
            st.session_state["story_img_name"] = final_filename
            st.session_state["pub_card_custom_prefix"] = clean_name

            temp_p = os.path.join(tempfile.gettempdir(), final_filename)
            try:
                with open(temp_p, "wb") as f:
                    f.write(img_bytes)
                st.session_state["story_img_path"] = temp_p
            except Exception:
                pass

            st.success(f"✅ Transferred to Direct Publisher as `{final_filename}`! Click on 'Direct Story Publisher' tab.")

    with bot_c5:
        if st.button("🌐 Send to Social Manager", width="stretch"):
            st.session_state["social_media_image_bytes"] = img_bytes
            st.session_state["social_media_image_name"] = final_filename
            st.session_state["social_custom_prefix"] = clean_name

            temp_p = os.path.join(tempfile.gettempdir(), final_filename)
            try:
                with open(temp_p, "wb") as f:
                    f.write(img_bytes)
                st.session_state["social_media_image_path"] = temp_p
            except Exception:
                pass

            st.success(f"✅ Transferred to Social Media Manager as `{final_filename}`!")
