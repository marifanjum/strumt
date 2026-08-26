import os
import urllib.request
import numpy as np
import onnxruntime as ort
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import streamlit as st

MODEL_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.onnx"
MODEL_PATH = "realesr-general-x4v3.onnx"


@st.cache_resource
def load_upscaler_session():
    """Downloads Real-ESRGAN Compact ONNX model (~6.5MB) once and caches session."""
    if not os.path.exists(MODEL_PATH):
        try:
            with st.spinner("📦 Initializing AI Super-Resolution Engine..."):
                urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        except Exception as e:
            st.error(f"Failed to download ONNX model: {e}")
            return None

    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 2
    opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(MODEL_PATH, sess_options=opts, providers=["CPUExecutionProvider"])
    return session


def upscale_image_cpu(pil_img: Image.Image, target_min_w: int = 1200, target_min_h: int = 720) -> Image.Image:
    """
    Super-resolves web images directly to HD canvas scale (1200x720+) using Real-ESRGAN 4x.
    """
    orig_img = pil_img.convert("RGB")
    orig_w, orig_h = orig_img.size

    session = load_upscaler_session()
    upscaled = None

    if session is not None:
        try:
            # If the image is small, run full 4x ESRGAN
            img_np = np.array(orig_img)
            img_bgr = img_np[:, :, ::-1].astype(np.float32) / 255.0
            img_tensor = np.transpose(img_bgr, (2, 0, 1))
            img_tensor = np.expand_dims(img_tensor, axis=0)

            input_name = session.get_inputs()[0].name
            output_name = session.get_outputs()[0].name

            output = session.run([output_name], {input_name: img_tensor})[0]

            output = np.squeeze(output, axis=0)
            output = np.clip(output, 0.0, 1.0)
            output = np.transpose(output, (1, 2, 0))
            output_rgb = (output[:, :, ::-1] * 255.0).round().astype(np.uint8)
            upscaled = Image.fromarray(output_rgb)
        except Exception as e:
            print(f"ONNX inference note: {e}")

    # Fallback / Scale Target Computation
    if upscaled is None:
        scale_w = target_min_w / max(1, orig_w)
        scale_h = target_min_h / max(1, orig_h)
        best_scale = max(scale_w, scale_h, 2.0)
        target_w = int(orig_w * best_scale)
        target_h = int(orig_h * best_scale)
        upscaled = orig_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    else:
        # If the 4x ESRGAN output is larger than canvas, downsample slightly with Lanczos for anti-aliasing
        current_w, current_h = upscaled.size
        if current_w < target_min_w or current_h < target_min_h:
            scale_factor = max(target_min_w / current_w, target_min_h / current_h)
            upscaled = upscaled.resize((int(current_w * scale_factor), int(current_h * scale_factor)), Image.Resampling.LANCZOS)

    # Multi-Stage Post-Processing for Web Images:
    # 1. Subtle median de-noise to suppress JPEG compression blocks
    denoised = upscaled.filter(ImageFilter.MedianFilter(size=3))
    blend = Image.blend(upscaled, denoised, alpha=0.35)

    # 2. Auto-contrast stretch (fixes washed out web photos)
    contrasted = ImageOps.autocontrast(blend, cutoff=0.5)

    # 3. High-pass Unsharp Mask to restore facial & text contours
    crisp = contrasted.filter(ImageFilter.UnsharpMask(radius=2.5, percent=180, threshold=1))
    
    # 4. Micro-contrast & vividness boost
    final_output = ImageEnhance.Sharpness(crisp).enhance(1.3)
    final_output = ImageEnhance.Color(final_output).enhance(1.08)

    return final_output
