# Fang's notes: MoGe-3 hosting

Personal notes for me and my agents. Repo-level agent instructions live in `../AGENTS.md`.

## What's running

| | |
|---|---|
| Public URL | https://foundway--moge-v3-web.modal.run |
| Modal app | https://modal.com/apps/foundway/main/deployed/moge-v3 |
| Model | MoGe-3 `Ruicheng/moge-3-vitl` (fp16, 3 refine steps default) |
| GPU | L40S, 1 container, scales to zero after 5 min idle (cold start ~30 s) |
| Source | `modal_app.py` on the `deploy` branch of https://github.com/foundway/MoGe |
| Redeploy | `modal deploy modal_app.py` (needs Modal token for workspace `foundway`) |
| Logs | `modal app logs moge-v3` |

No auth on the endpoint — anyone with the URL can use it and burn GPU time. Add
`modal.Proxy`/an auth header before sharing widely.

---

## Instruction block for other apps

Copy-paste the block below into another project's README / AGENTS.md when it needs depth,
normals, point maps, or meshes from a single image.

````markdown
## Monocular 3D geometry via hosted MoGe-3

A hosted MoGe-3 (Microsoft monocular geometry estimation) Gradio app is available at
`https://foundway--moge-v3-web.modal.run`. Given one RGB image it returns metric depth,
normals, a 3D point map, a camera FOV estimate and textured mesh / point-cloud files.
First call after idle takes ~30 s (cold start); warm calls take ~5-25 s depending on size.

### Endpoint `/run`

Inputs (positional, in order):

| # | name | type | default | notes |
|---|------|------|---------|-------|
| 0 | image | file | required | RGB image (jpg/png) |
| 1 | max_size | int | 1024 | longer side is downscaled to this (256-4096) |
| 2 | resolution_level | `"Low"`,`"Medium"`,`"High"`,`"Ultra"` | `"High"` | inference token resolution |
| 3 | apply_mask | bool | true | mask out sky / invalid regions |
| 4 | remove_edge | bool | true | drop depth-discontinuity edges from the mesh |
| 5 | refine_steps | int | 3 | 0-5 MoGe-3 refinement steps (0 = fastest) |

Outputs (list, in order):

| # | content |
|---|---------|
| 0 | colorized depth map (png) |
| 1 | normal map (png) |
| 2 | valid-pixel mask (png) |
| 3 | 3D viewer payload (ignore for API use) |
| 4 | list of files: `mesh.glb`, `mesh.ply`, `pointcloud.glb`, `pointcloud.ply`, `depth.exr` (float32 metric depth, m), `points.exr` (float32 XYZ per pixel, m, stored BGR order), `normal.exr` (half, camera-space) |
| 5 | markdown string with horizontal/vertical FOV in degrees |
| 6-7 | UI notes (ignore) |

Output files are served for ~5 min, then deleted — download them immediately.

### Python (`pip install gradio_client`)

```python
from gradio_client import Client, handle_file

client = Client("https://foundway--moge-v3-web.modal.run")
out = client.predict(
    image=handle_file("photo.jpg"),      # local path or URL
    max_size=1024,
    resolution_level="High",
    apply_mask=True,
    remove_edge=True,
    refine_steps=3,
    api_name="/run",
)
depth_png, normal_png, mask_png, _viewer, files, fov_md, *_ = out
# `files` are local paths already downloaded by the client, e.g. .../mesh.glb, .../depth.exr
```

Read the EXRs with OpenCV (`OPENCV_IO_ENABLE_OPENEXR=1` must be set before `import cv2`):

```python
import os; os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
import cv2, numpy as np
depth  = cv2.imread(f"{d}/depth.exr",  cv2.IMREAD_UNCHANGED)                 # (H,W) float32, metres
points = cv2.imread(f"{d}/points.exr", cv2.IMREAD_UNCHANGED)[..., ::-1]      # (H,W,3) XYZ, metres
```

### Any language (raw HTTP)

```bash
BASE=https://foundway--moge-v3-web.modal.run

# 1. upload image -> server-side path
P=$(curl -s -F "files=@photo.jpg" $BASE/gradio_api/upload | jq -r '.[0]')

# 2. start the job -> event_id
EID=$(curl -s -X POST $BASE/gradio_api/call/run -H "Content-Type: application/json" \
  -d "{\"data\":[{\"path\":\"$P\",\"meta\":{\"_type\":\"gradio.FileData\"}},1024,\"High\",true,true,3]}" \
  | jq -r .event_id)

# 3. stream result (SSE); the final `data:` line is the JSON output list
curl -s -N $BASE/gradio_api/call/run/$EID | grep '^data:' | tail -1 | cut -c7- > result.json

# 4. download files; each FileData has a "url" field
jq -r '.[4][].url' result.json | xargs -n1 curl -sO
```

### Tips
- For speed: `max_size=512`, `resolution_level="Medium"`, `refine_steps=0` (~5 s warm).
- For quality: `max_size=2048`, `resolution_level="Ultra"`, `refine_steps=3`.
- Metric scale is most reliable for ordinary indoor/street photos; degrades on stylised or macro images.
- Errors surface only as a generic Gradio error; check `modal app logs moge-v3` (owner only).
````

---

## Maintenance

- Sync with Microsoft: `git fetch upstream && git checkout main && git merge --ff-only upstream/main && git push && git checkout deploy && git merge main` (also in `AGENTS.md`).
- Change GPU/model: `MOGE_GPU=A100 MOGE_VERSION=v3 modal deploy modal_app.py`.
- Cost: only billed while a container is running (request time + 5 min idle window).
- Local CPU fallback (MoGe-2 only): see `AGENTS.md` -> "Local (CPU) run".
