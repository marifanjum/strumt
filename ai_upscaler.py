import os
import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image
import urllib.request
import streamlit as st

MODEL_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.onnx"
MODEL_PATH = "realesr-general-x4v3.onnx"


@st.cache_resource
def load_upscaler_session():
    """Downloads lightweight ONNX model (~6.5MB) once and caches the CPU session."""
    if not os.path.exists(MODEL_PATH):
        try:
            with st.spinner("📦 Downloading lightweight Real-ESRGAN ONNX model (~6.5MB)..."):
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
    """Fast, deterministic CPU super-resolution and de-noising."""
    session = load_upscaler_session()
    if session is None:
        return pil_img

    img_rgb = pil_img.convert("RGB")
    img_np = np.array(img_rgb)
    
    # RGB to BGR and normalize to float32 [0, 1]
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    img_tensor = img_bgr.astype(np.float32) / 255.0
    img_tensor = np.transpose(img_tensor, (2, 0, 1))
    img_tensor = np.expand_dims(img_tensor, axis=0)

    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    # Inference on CPU
    output = session.run([output_name], {input_name: img_tensor})[0]

    # Post-process output tensor
    output = np.squeeze(output, axis=0)
    output = np.clip(output, 0, 1)
    output = np.transpose(output, (1, 2, 0))
    output = (output * 255.0).round().astype(np.uint8)
    output_rgb = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)

    upscaled_pil = Image.fromarray(output_rgb)

    # Downscale smoothly with Lanczos to desired resolution scale
    if scale == 2:
        upscaled_pil = upscaled_pil.resize(
            (pil_img.width * 2, pil_img.height * 2), 
            Image.Resampling.LANCZOS
        )

    return upscaled_pil