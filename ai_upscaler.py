import os
import urllib.request
import numpy as np
import onnxruntime as ort
from PIL import Image, ImageEnhance, ImageFilter
import streamlit as st

MODEL_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.onnx"
MODEL_PATH = "realesr-general-x4v3.onnx"


@st.cache_resource
def load_upscaler_session():
    """Downloads Real-ESRGAN Compact ONNX model (~6.5MB) once and caches session."""
    if not os.path.exists(MODEL_PATH):
        try:
            with st.spinner("📦 Downloading Real-ESRGAN ONNX model (~6.5MB)..."):
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


def upscale_image_cpu(pil_img: Image.Image, scale: int = 2) -> Image.Image:
    """Runs Real-ESRGAN super-resolution and enhances high-frequency details."""
    session = load_upscaler_session()
    if session is None:
        return pil_img

    img_rgb = pil_img.convert("RGB")
    orig_w, orig_h = img_rgb.size
    img_np = np.array(img_rgb)

    # 1. RGB -> BGR & normalize [0, 1]
    img_bgr = img_np[:, :, ::-1].astype(np.float32) / 255.0
    img_tensor = np.transpose(img_bgr, (2, 0, 1))
    img_tensor = np.expand_dims(img_tensor, axis=0)

    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    # 2. Run ONNX Inference
    output = session.run([output_name], {input_name: img_tensor})[0]

    # 3. Post-process tensor to RGB image
    output = np.squeeze(output, axis=0)
    output = np.clip(output, 0.0, 1.0)
    output = np.transpose(output, (1, 2, 0))
    output_rgb = (output[:, :, ::-1] * 255.0).round().astype(np.uint8)
    upscaled = Image.fromarray(output_rgb)

    # 4. Smooth scale adjustment
    if scale == 2:
        upscaled = upscaled.resize((orig_w * 2, orig_h * 2), Image.Resampling.LANCZOS)

    # 5. Apply subtle Unsharp Mask to emphasize reconstructed edges
    enhanced = upscaled.filter(ImageFilter.UnsharpMask(radius=1.5, percent=140, threshold=3))
    enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.25)

    return enhanced
