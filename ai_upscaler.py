import os
import urllib.request
import numpy as np
import onnxruntime as ort
from PIL import Image
import streamlit as st

MODEL_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.onnx"
MODEL_PATH = "realesr-general-x4v3.onnx"


@st.cache_resource
def load_upscaler_session():
    """Downloads lightweight ONNX model (~6.5MB) once and caches the CPU session."""
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
    """Fast, deterministic CPU super-resolution using pure NumPy & ONNX Runtime (no OpenCV needed)."""
    session = load_upscaler_session()
    if session is None:
        return pil_img

    img_rgb = pil_img.convert("RGB")
    img_np = np.array(img_rgb)  # Shape: (H, W, 3) in RGB

    # 1. Convert RGB to BGR in pure NumPy ([..., ::-1]) and normalize to [0, 1]
    img_bgr = img_np[:, :, ::-1].astype(np.float32) / 255.0
    
    # 2. Transpose (H, W, C) -> (C, H, W) and add batch dimension -> (1, C, H, W)
    img_tensor = np.transpose(img_bgr, (2, 0, 1))
    img_tensor = np.expand_dims(img_tensor, axis=0)

    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    # 3. Run Inference on CPU
    output = session.run([output_name], {input_name: img_tensor})[0]

    # 4. Post-process tensor output: remove batch dim, clip [0, 1], transpose to (H, W, C)
    output = np.squeeze(output, axis=0)
    output = np.clip(output, 0.0, 1.0)
    output = np.transpose(output, (1, 2, 0))
    
    # 5. Convert BGR back to RGB in NumPy ([..., ::-1]) and scale to uint8 [0, 255]
    output_rgb = (output[:, :, ::-1] * 255.0).round().astype(np.uint8)
    upscaled_pil = Image.fromarray(output_rgb)

    # 6. If 2x is selected, downscale the 4x output smoothly with Lanczos
    if scale == 2:
        upscaled_pil = upscaled_pil.resize(
            (pil_img.width * 2, pil_img.height * 2), 
            Image.Resampling.LANCZOS
        )

    return upscaled_pil
