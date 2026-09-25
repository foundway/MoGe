"""
Host the MoGe Gradio demo on Modal (https://modal.com).

    modal deploy modal_app.py            # deploy -> prints the public URL
    modal serve modal_app.py             # dev mode with hot reload

Environment overrides (set before deploying):
    MOGE_VERSION      v1 | v2 | v3   (default v3)
    MOGE_PRETRAINED   HF repo id or checkpoint path (default: per-version HF model)
    MOGE_GPU          Modal GPU type (default L40S)
"""
import os
from pathlib import Path

import modal

MODEL_VERSION = os.environ.get("MOGE_VERSION", "v3")
DEFAULT_PRETRAINED = {
    "v1": "Ruicheng/moge-vitl",
    "v2": "Ruicheng/moge-2-vitl-normal",
    "v3": "Ruicheng/moge-3-vitl",
}
PRETRAINED = os.environ.get("MOGE_PRETRAINED", DEFAULT_PRETRAINED[MODEL_VERSION])
GPU = os.environ.get("MOGE_GPU", "L40S")

REPO_ROOT = Path(__file__).parent
REMOTE_REPO = "/root/MoGe"
HF_CACHE = "/root/.cache/huggingface"

app = modal.App(f"moge-{MODEL_VERSION}")
hf_cache_vol = modal.Volume.from_name("moge-hf-cache", create_if_missing=True)

image = (
    modal.Image.from_registry("nvidia/cuda:12.8.1-devel-ubuntu22.04", add_python="3.12")
    .apt_install("git", "libgl1", "libglib2.0-0")
    .pip_install("torch>=2.4", "torchvision>=0.19", index_url="https://download.pytorch.org/whl/cu128")
    .pip_install("opencv-python-headless==4.10.0.84")
    .add_local_dir(REPO_ROOT / "moge", f"{REMOTE_REPO}/moge", copy=True)
    .add_local_file(REPO_ROOT / "pyproject.toml", f"{REMOTE_REPO}/pyproject.toml", copy=True)
    .add_local_file(REPO_ROOT / "README.md", f"{REMOTE_REPO}/README.md", copy=True)
    .add_local_file(REPO_ROOT / "LICENSE", f"{REMOTE_REPO}/LICENSE", copy=True)
    # torch/opencv are already satisfied above, so pip keeps those pinned builds.
    .run_commands(f"cd {REMOTE_REPO} && pip install -e .")
    .env({"HF_HOME": HF_CACHE, "OPENCV_IO_ENABLE_OPENEXR": "1", "GRADIO_ANALYTICS_ENABLED": "False"})
    .add_local_dir(REPO_ROOT / "example_images", f"{REMOTE_REPO}/example_images")
)


@app.function(
    image=image,
    gpu=GPU,
    volumes={HF_CACHE: hf_cache_vol},
    scaledown_window=300,
    timeout=1800,
    max_containers=1,
)
@modal.concurrent(max_inputs=20)
@modal.asgi_app()
def web():
    os.chdir(REMOTE_REPO)  # so `example_images/` resolves inside the demo
    import gradio as gr
    from fastapi import FastAPI
    from starlette.middleware.gzip import GZipMiddleware

    from moge.scripts.app import TEMP_DIR, create_demo

    demo = create_demo(PRETRAINED, MODEL_VERSION, use_fp16=True)
    hf_cache_vol.commit()

    api = FastAPI()
    api.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=6)
    return gr.mount_gradio_app(api, demo, path="/", allowed_paths=[str(TEMP_DIR)])
