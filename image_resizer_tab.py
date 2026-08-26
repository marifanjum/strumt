import os
import io
import math
import re
import json
import base64
import tempfile
from datetime import datetime
from PIL import Image, ImageOps
import streamlit as st
import streamlit.components.v1 as components


def compute_collage_slots(W: int, H: int, count: int, layout: str) -> list:
    slots = []

    if layout == "Row":
        w = math.floor(W / count)
        for i in range(count):
            slots.append({"x": i * w, "y": 0, "w": w, "h": H})

    elif layout == "Column":
        h = math.floor(H / count)
        for i in range(count):
            slots.append({"x": 0, "y": i * h, "w": W, "h": h})

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
                    slots.append({"x": c * cell_w, "y": r * cell_h, "w": cell_w, "h": cell_h})
                    idx += 1

    elif layout == "1 Big (Left) + Small Column":
        big_w = math.floor(W / 3)
        small_w = W - big_w
        slots.append({"x": 0, "y": 0, "w": big_w, "h": H})
        small_count = count - 1
        if small_count > 0:
            small_h = math.floor(H / small_count)
            for i in range(small_count):
                slots.append({"x": big_w, "y": i * small_h, "w": small_w, "h": small_h})

    elif layout == "1 Big (Left) + Others Grid (Right)":
        big_w = math.floor(W / 3)
        grid_w = W - big_w
        slots.append({"x": 0, "y": 0, "w": big_w, "h": H})
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
                        slots.append({"x": big_w + c * cell_w, "y": r * cell_h, "w": cell_w, "h": cell_h})
                        idx += 1

    elif layout == "1 Big (Right) + Others Rows (Left)":
        big_w = math.floor(W / 3)
        grid_w = W - big_w
        slots.append({"x": grid_w, "y": 0, "w": big_w, "h": H})
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
                        slots.append({"x": c * cell_w, "y": r * cell_h, "w": cell_w, "h": cell_h})
                        idx += 1

    elif layout == "1 Big (Top) + Others Rows (Bottom)":
        big_h = math.floor(H / 3)
        grid_h = H - big_h
        slots.append({"x": 0, "y": 0, "w": W, "h": big_h})
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
                        slots.append({"x": c * cell_w, "y": big_h + r * cell_h, "w": cell_w, "h": cell_h})
                        idx += 1

    elif layout == "1 Big (Bottom) + Others Grid (Top)":
        big_h = math.floor(H / 3)
        grid_h = H - big_h
        slots.append({"x": 0, "y": grid_h, "w": W, "h": big_h})
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
                        slots.append({"x": c * cell_w, "y": r * cell_h, "w": cell_w, "h": cell_h})
                        idx += 1

    elif layout == "2 Big Left + Others Grid (Right)":
        big_w = math.floor(W / 3)
        grid_w = W - big_w
        big_h = math.floor(H / 2)
        if count >= 1:
            slots.append({"x": 0, "y": 0, "w": big_w, "h": big_h})
        if count >= 2:
            slots.append({"x": 0, "y": big_h, "w": big_w, "h": big_h})
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
                        slots.append({"x": big_w + c * cell_w, "y": r * cell_h, "w": cell_w, "h": cell_h})
                        idx += 1

    elif layout == "2 Big Right + Others Grid (Left)":
        big_w = math.floor(W / 3)
        grid_w = W - big_w
        big_h = math.floor(H / 2)
        if count >= 1:
            slots.append({"x": grid_w, "y": 0, "w": big_w, "h": big_h})
        if count >= 2:
            slots.append({"x": grid_w, "y": big_h, "w": big_w, "h": big_h})
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
                        slots.append({"x": c * cell_w, "y": r * cell_h, "w": cell_w, "h": cell_h})
                        idx += 1

    elif layout == "2 Big (Top Row) + Small Bottom":
        big_w = math.floor(W / 2)
        big_h = math.floor(H / 3)
        small_h = H - big_h
        if count >= 1:
            slots.append({"x": 0, "y": 0, "w": big_w, "h": big_h})
        if count >= 2:
            slots.append({"x": big_w, "y": 0, "w": big_w, "h": big_h})
        small_count = max(0, count - 2)
        if small_count > 0:
            small_w = math.floor(W / small_count)
            for i in range(small_count):
                slots.append({"x": i * small_w, "y": big_h, "w": small_w, "h": small_h})

    else:
        cols = math.ceil(math.sqrt(count))
        rows = math.ceil(count / cols)
        cell_w = math.floor(W / cols)
        cell_h = math.floor(H / rows)
        idx = 0
        for r in range(rows):
            for c in range(cols):
                if idx < count:
                    slots.append({"x": c * cell_w, "y": r * cell_h, "w": cell_w, "h": cell_h})
                    idx += 1

    return slots


def on_single_upload_change():
    uploaded = st.session_state.get("single_resizer_uploader")
    if uploaded:
        base_name = os.path.splitext(uploaded.name)[0]
        st.session_state["resizer_user_filename"] = base_name


def on_collage_upload_change():
    uploaded_list = st.session_state.get("collage_uploader")
    if uploaded_list and len(uploaded_list) > 0:
        base_name = os.path.splitext(uploaded_list[0].name)[0]
        st.session_state["resizer_user_filename"] = f"{base_name}_collage"


def render_interactive_touch_canvas(
    canvas_w: int,
    canvas_h: int,
    images_b64: list,
    slots_json: str,
    mode: str,
    use_gradient: bool,
    grad_c1: str,
    grad_c2: str,
    grad_dir: str,
    use_border: bool,
    use_credit: bool,
    credit_text: str,
    credit_pos: str
):
    """
    Renders an HTML5 Canvas with continuous touch-panning, pinch-to-zoom,
    mouse drag, wheel zoom, and instant Base64 synchronization.
    """
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
        <style>
            * {{ box-sizing: border-box; user-select: none; -webkit-user-select: none; }}
            body {{ margin: 0; padding: 0; background: transparent; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; }}
            #canvas-container {{
                position: relative;
                width: 100%;
                max-width: 1000px;
                aspect-ratio: {canvas_w} / {canvas_h};
                background: #0f172a;
                border: 2px solid #334155;
                border-radius: 8px;
                overflow: hidden;
                touch-action: none;
                cursor: grab;
            }}
            #canvas-container:active {{ cursor: grabbing; }}
            canvas {{ width: 100%; height: 100%; display: block; }}
            .controls-bar {{
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
                justify-content: center;
                margin-top: 10px;
                width: 100%;
                max-width: 1000px;
            }}
            .tool-btn {{
                background: #1e293b;
                color: #f8fafc;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
                font-weight: 600;
                cursor: pointer;
                transition: background 0.15s;
            }}
            .tool-btn:hover {{ background: #334155; }}
            .slot-badge {{
                position: absolute;
                top: 8px;
                left: 8px;
                background: rgba(15, 23, 42, 0.85);
                color: #38bdf8;
                border: 1px solid #38bdf8;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: bold;
                pointer-events: none;
            }}
        </style>
    </head>
    <body>
        <div id="canvas-container">
            <canvas id="viewport" width="{canvas_w}" height="{canvas_h}"></canvas>
            <div id="slot-badge" class="slot-badge">Slot: 1</div>
        </div>

        <div class="controls-bar">
            <button class="tool-btn" onclick="fitShort()">↔️ Fit Longest Side (Letterbox)</button>
            <button class="tool-btn" onclick="fitLong()">↕️ Auto Zoom to Fill (Crop)</button>
            <button class="tool-btn" onclick="centerActive()">🎯 Center Active</button>
            <button class="tool-btn" onclick="zoomActive(1.15)">🔍 Zoom In (+)</button>
            <button class="tool-btn" onclick="zoomActive(0.85)">🔎 Zoom Out (-)</button>
        </div>

        <script>
            const CW = {canvas_w};
            const CH = {canvas_h};
            const mode = "{mode}";
            const useGradient = {str(use_gradient).lower()};
            const gradC1 = "{grad_c1}";
            const gradC2 = "{grad_c2}";
            const gradDir = "{grad_dir}";
            const useBorder = {str(use_border).lower()};
            const useCredit = {str(use_credit).lower()};
            const creditTxt = {json.dumps(credit_text)};
            const creditPos = "{credit_pos}";
            
            const rawSlots = {slots_json};
            const rawImages = {json.dumps(images_b64)};

            const canvas = document.getElementById('viewport');
            const ctx = canvas.getContext('2d');
            const container = document.getElementById('canvas-container');
            const badge = document.getElementById('slot-badge');

            let activeSlot = 0;
            let slots = rawSlots.map((s, idx) => ({{
                ...s,
                img: null,
                scale: 1.0,
                offsetX: s.x,
                offsetY: s.y,
                forceStretch: false
            }}));

            // Load Image Objects
            let loadedCount = 0;
            slots.forEach((s, idx) => {{
                if (idx < rawImages.length && rawImages[idx]) {{
                    const img = new Image();
                    img.src = "data:image/png;base64," + rawImages[idx];
                    img.onload = () => {{
                        s.img = img;
                        fitSlot(idx, "fill");
                        render();
                    }};
                }}
            }});

            function fitSlot(idx, strategy) {{
                const s = slots[idx];
                if (!s || !s.img) return;
                const imgW = s.img.width;
                const imgH = s.img.height;

                if (strategy === "fill") {{
                    s.scale = Math.max(s.w / imgW, s.h / imgH);
                }} else {{
                    s.scale = Math.min(s.w / imgW, s.h / imgH);
                }}
                s.offsetX = s.x + (s.w - imgW * s.scale) / 2;
                s.offsetY = s.y + (s.h - imgH * s.scale) / 2;
            }}

            function render() {{
                ctx.clearRect(0, 0, CW, CH);

                // Background
                if (useGradient) {{
                    let grad;
                    if (gradDir === "Top → Bottom") grad = ctx.createLinearGradient(0, 0, 0, CH);
                    else if (gradDir === "Bottom → Top") grad = ctx.createLinearGradient(0, CH, 0, 0);
                    else if (gradDir === "Right → Left") grad = ctx.createLinearGradient(CW, 0, 0, 0);
                    else grad = ctx.createLinearGradient(0, 0, CW, 0);

                    grad.addColorStop(0, gradC1);
                    grad.addColorStop(1, gradC2);
                    ctx.fillStyle = grad;
                }} else {{
                    ctx.fillStyle = "#0f172a";
                }}
                ctx.fillRect(0, 0, CW, CH);

                // Draw Slots
                slots.forEach((s, idx) => {{
                    ctx.save();
                    ctx.beginPath();
                    ctx.rect(s.x, s.y, s.w, s.h);
                    ctx.clip();

                    if (s.img) {{
                        ctx.drawImage(s.img, s.offsetX, s.offsetY, s.img.width * s.scale, s.img.height * s.scale);
                    }} else {{
                        ctx.fillStyle = "#1e293b";
                        ctx.fillRect(s.x + 2, s.y + 2, s.w - 4, s.h - 4);
                        ctx.fillStyle = "#64748b";
                        ctx.font = "bold 20px sans-serif";
                        ctx.textAlign = "center";
                        ctx.textBaseline = "middle";
                        ctx.fillText("Slot " + (idx + 1) + " (Empty)", s.x + s.w / 2, s.y + s.h / 2);
                    }}
                    ctx.restore();

                    // Borders for collage
                    if (mode === "Collage Mode") {{
                        ctx.strokeStyle = (idx === activeSlot) ? "#38bdf8" : "#334155";
                        ctx.lineWidth = (idx === activeSlot) ? 4 : 2;
                        ctx.strokeRect(s.x, s.y, s.w, s.h);
                    }}
                }});

                // Double framing border
                if (useBorder) {{
                    ctx.strokeStyle = "#94a3b8";
                    ctx.lineWidth = 2;
                    ctx.strokeRect(8, 8, CW - 16, CH - 16);
                    ctx.strokeRect(12, 12, CW - 24, CH - 24);
                }}

                // Credit Overlay
                if (useCredit && creditTxt.trim()) {{
                    ctx.font = "bold 18px Arial, sans-serif";
                    const tw = ctx.measureText(creditTxt).width + 24;
                    const th = 32;
                    let x = creditPos.includes("Right") ? (CW - tw - 16) : 16;
                    let y = creditPos.includes("Bottom") ? (CH - th - 16) : 16;

                    ctx.fillStyle = "rgba(0,0,0,0.85)";
                    ctx.fillRect(x, y, tw, th);
                    ctx.fillStyle = "#ffffff";
                    ctx.textAlign = "left";
                    ctx.textBaseline = "middle";
                    ctx.fillText(creditTxt, x + 12, y + th / 2);
                }}

                badge.innerText = (mode === "Single Image Mode") ? "Single Mode" : ("Active Slot: " + (activeSlot + 1));
            }}

            function fitLong() {{ fitSlot(activeSlot, "fill"); render(); syncToStreamlit(); }}
            function fitShort() {{ fitSlot(activeSlot, "fit"); render(); syncToStreamlit(); }}
            function centerActive() {{
                const s = slots[activeSlot];
                if (!s || !s.img) return;
                s.offsetX = s.x + (s.w - s.img.width * s.scale) / 2;
                s.offsetY = s.y + (s.h - s.img.height * s.scale) / 2;
                render();
                syncToStreamlit();
            }}
            function zoomActive(factor) {{
                const s = slots[activeSlot];
                if (!s || !s.img) return;
                const oldScale = s.scale;
                s.scale = Math.max(0.05, Math.min(25.0, s.scale * factor));
                s.offsetX -= (s.img.width * s.scale - s.img.width * oldScale) / 2;
                s.offsetY -= (s.img.height * s.scale - s.img.height * oldScale) / 2;
                render();
                syncToStreamlit();
            }}

            // Touch & Mouse Interaction State
            let isDragging = false;
            let startX = 0, startY = 0;
            let initialDist = 0;
            let initialScale = 1.0;

            function getCanvasCoords(clientX, clientY) {{
                const rect = canvas.getBoundingClientRect();
                return {{
                    x: (clientX - rect.left) * (CW / rect.width),
                    y: (clientY - rect.top) * (CH / rect.height)
                }};
            }}

            function findSlotAt(cx, cy) {{
                for (let i = 0; i < slots.length; i++) {{
                    const s = slots[i];
                    if (cx >= s.x && cx <= s.x + s.w && cy >= s.y && cy <= s.y + s.h) {{
                        return i;
                    }}
                }}
                return 0;
            }}

            // Mouse Events
            container.addEventListener('mousedown', (e) => {{
                const pt = getCanvasCoords(e.clientX, e.clientY);
                activeSlot = findSlotAt(pt.x, pt.y);
                isDragging = true;
                startX = pt.x;
                startY = pt.y;
                render();
            }});

            window.addEventListener('mousemove', (e) => {{
                if (!isDragging) return;
                const pt = getCanvasCoords(e.clientX, e.clientY);
                const dx = pt.x - startX;
                const dy = pt.y - startY;
                startX = pt.x;
                startY = pt.y;

                const s = slots[activeSlot];
                if (s) {{
                    s.offsetX += dx;
                    s.offsetY += dy;
                    render();
                }}
            }});

            window.addEventListener('mouseup', () => {{
                if (isDragging) {{
                    isDragging = false;
                    syncToStreamlit();
                }}
            }});

            // Wheel Zoom
            container.addEventListener('wheel', (e) => {{
                e.preventDefault();
                const factor = e.deltaY < 0 ? 1.08 : 0.92;
                zoomActive(factor);
            }}, {{ passive: false }});

            // Touch Events (Pinch-Zoom & Pan)
            container.addEventListener('touchstart', (e) => {{
                if (e.touches.length === 1) {{
                    const pt = getCanvasCoords(e.touches[0].clientX, e.touches[0].clientY);
                    activeSlot = findSlotAt(pt.x, pt.y);
                    isDragging = true;
                    startX = pt.x;
                    startY = pt.y;
                    render();
                }} else if (e.touches.length === 2) {{
                    isDragging = false;
                    const dx = e.touches[0].clientX - e.touches[1].clientX;
                    const dy = e.touches[0].clientY - e.touches[1].clientY;
                    initialDist = Math.hypot(dx, dy);
                    const s = slots[activeSlot];
                    if (s) initialScale = s.scale;
                }}
            }}, {{ passive: false }});

            container.addEventListener('touchmove', (e) => {{
                e.preventDefault();
                if (e.touches.length === 1 && isDragging) {{
                    const pt = getCanvasCoords(e.touches[0].clientX, e.touches[0].clientY);
                    const dx = pt.x - startX;
                    const dy = pt.y - startY;
                    startX = pt.x;
                    startY = pt.y;

                    const s = slots[activeSlot];
                    if (s) {{
                        s.offsetX += dx;
                        s.offsetY += dy;
                        render();
                    }}
                }} else if (e.touches.length === 2) {{
                    const dx = e.touches[0].clientX - e.touches[1].clientX;
                    const dy = e.touches[0].clientY - e.touches[1].clientY;
                    const dist = Math.hypot(dx, dy);
                    if (initialDist > 0) {{
                        const factor = dist / initialDist;
                        const s = slots[activeSlot];
                        if (s && s.img) {{
                            s.scale = Math.max(0.05, Math.min(25.0, initialScale * factor));
                            render();
                        }}
                    }}
                }}
            }}, {{ passive: false }});

            container.addEventListener('touchend', (e) => {{
                if (e.touches.length === 0) {{
                    isDragging = false;
                    syncToStreamlit();
                }}
            }});

            function syncToStreamlit() {{
                try {{
                    const dataUrl = canvas.toDataURL('image/png');
                    window.parent.postMessage({{
                        type: 'streamlit:setComponentValue',
                        value: dataUrl
                    }}, '*');
                }} catch(err) {{}}
            }}

            setTimeout(() => {{ render(); syncToStreamlit(); }}, 250);
        </script>
    </body>
    </html>
    """
    return components.html(html_code, height=int(canvas_h * (1000 / canvas_w) + 120))


def render_image_resizer_tab(config: dict):
    st.markdown("### 🖼️ Interactive Touch & Gesture Studio")
    st.caption("👆 **Touch Drag / Mouse Pan:** Move image | 🤏 **Pinch / Mouse Wheel:** Zoom | 🎯 **Tap / Click:** Switch Collage Slot")

    canvas_w = int(config.get("resizer_width", 1200))
    canvas_h = int(config.get("resizer_height", 720))

    top_col1, top_col2, top_col3 = st.columns([1.5, 1.5, 2])
    with top_col1:
        mode = st.selectbox("Mode:", ["Single Image Mode", "Collage Mode"], key="resizer_mode")

    layout_choice = "Grid — Equal"
    collage_count = 3
    if mode == "Collage Mode":
        with top_col2:
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
        with top_col3:
            collage_count = st.slider("Number of Images:", min_value=2, max_value=16, value=3)

    st.markdown("#### 📂 Image Inputs")
    loaded_b64_list = []

    if mode == "Single Image Mode":
        single_file = st.file_uploader(
            "Upload Image:", 
            type=["png", "jpg", "jpeg", "webp"], 
            key="single_resizer_uploader",
            on_change=on_single_upload_change
        )
        if single_file:
            b64_str = base64.b64encode(single_file.getvalue()).decode('utf-8')
            loaded_b64_list.append(b64_str)
        else:
            loaded_b64_list.append(None)
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
                b64_str = base64.b64encode(uploaded_files[i].getvalue()).decode('utf-8')
                loaded_b64_list.append(b64_str)
            else:
                loaded_b64_list.append(None)

    with st.expander("🎨 Background, Border & Credit Overlays", expanded=False):
        style_c1, style_c2 = st.columns(2)
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

    # Compute layout slots
    if mode == "Single Image Mode":
        slots = [{"x": 0, "y": 0, "w": canvas_w, "h": canvas_h}]
    else:
        slots = compute_collage_slots(canvas_w, canvas_h, max(1, len(loaded_b64_list)), layout_choice)

    # Render Interactive Client Canvas
    render_interactive_touch_canvas(
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        images_b64=loaded_b64_list,
        slots_json=json.dumps(slots),
        mode=mode,
        use_gradient=use_gradient,
        grad_c1=grad_c1,
        grad_c2=grad_c2,
        grad_dir=grad_dir,
        use_border=use_border,
        use_credit=use_credit,
        credit_text=credit_text,
        credit_pos=credit_pos
    )

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

    # Fallback/Default PIL render if user downloads directly
    img_byte_arr = io.BytesIO()
    if loaded_b64_list and loaded_b64_list[0]:
        first_img = Image.open(io.BytesIO(base64.b64decode(loaded_b64_list[0]))).convert("RGB")
        fitted = ImageOps.fit(first_img, (canvas_w, canvas_h), Image.Resampling.LANCZOS)
        fitted.save(img_byte_arr, format=fmt, quality=95)
    else:
        blank = Image.new("RGB", (canvas_w, canvas_h), (15, 23, 42))
        blank.save(img_byte_arr, format=fmt, quality=95)

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