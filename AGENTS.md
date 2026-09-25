# Notes for maintainers and agents (foundway fork)

This is a fork of [microsoft/MoGe](https://github.com/microsoft/MoGe). `main` tracks upstream
unchanged; our additions live on the `deploy` branch:

- `modal_app.py` — hosts the Gradio demo on Modal (GPU).
- `moge/scripts/app.py` — split into `create_demo()` (returns unlaunched `gr.Blocks`, used by
  Modal) and `main()` (CLI). Falls back to CPU / fp32 and skips the `flex_gemm` import when
  CUDA is unavailable, so MoGe-1/2 can run on a GPU-less box.
- `AGENTS.md` — this file.

## Syncing with upstream

```bash
git remote add upstream https://github.com/microsoft/MoGe.git   # once
git fetch upstream
git checkout main && git merge --ff-only upstream/main && git push
git checkout deploy && git merge main                            # resolve app.py conflicts if any
```

## Hosted demo (Modal)

- Workspace `foundway`, app `moge-v3`: https://modal.com/apps/foundway/main/deployed/moge-v3
- URL: https://foundway--moge-v3-web.modal.run
- Deploy/redeploy: `modal deploy modal_app.py` (needs a Modal token: `modal token new`, or
  `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` env vars).
- Defaults: MoGe-3 (`Ruicheng/moge-3-vitl`), L40S GPU, scales to zero after 5 min idle
  (cold start ~30 s). Override with `MOGE_VERSION`, `MOGE_PRETRAINED`, `MOGE_GPU` env vars at
  deploy time. HF weights are cached in the `moge-hf-cache` Volume.
- GPU functions require a payment method on the Modal workspace.
- Image build order matters: every `add_local_*` without `copy=True` must come after all
  `run_commands` / `env` steps, or Modal refuses to build.

## Local (CPU) run

MoGe-3 needs FlexGEMM/Triton on CUDA and will not run on CPU; use v2:

```bash
uv venv --python 3.12
uv pip install --torch-backend=cpu torch torchvision
uv pip install -e . "opencv-python-headless==4.10.0.84"
GRADIO_SERVER_PORT=7860 .venv/bin/python -m moge.scripts.app --version v2
```

## Gotchas

- `opencv-python-headless` 5.x wheels have no EXR writer, so the demo fails after inference
  with `could not find a writer for the specified extension` when saving `depth.exr`. Pin 4.10.0.84
  (already done in `modal_app.py`).
- Gradio shows only a generic "Error" in the UI; the traceback is in the server log
  (`modal app logs moge-v3` for the hosted app, stdout for local).
- Inference on CPU: ~6 s for a 512 px image at Medium, minutes at High/Ultra.
