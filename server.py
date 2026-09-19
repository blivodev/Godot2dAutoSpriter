#!/usr/bin/env python3
"""
server.py - Model Context Protocol (MCP) Server for Godot2dAutoSpriter

Exposes end-to-end 2D sprite generation, alpha-blob limb slicing, and Godot 4
auto-rigging tools to AI coding agents (Cline, Claude Desktop, Cursor, OpenCode).

MCP Tools:
  1.  generate_character_sprites     - ComfyUI diffusion or procedural sprite generation
  2.  slice_character_limbs          - Alpha-blob detection limb segmentation
  3.  assemble_godot_rig             - Headless Godot 4 Skeleton2D rig builder
  4.  setup_comfyui_environment      - ComfyUI node/model installer & status checker
  5.  download_comfyui_model         - AI model checkpoint downloader (resumable)
  6.  list_generated_characters      - Lists all characters in the sprites/ directory
  7.  delete_character               - Removes a character's sprites and scene file
  8.  get_character_info             - Returns detailed metadata for a character
  9.  queue_character_generation     - Add one or more characters to the generation queue
  10. get_queue_status               - Get current state of all queued generation jobs
  11. cancel_queue_job               - Cancel a pending or running queue job
"""

import os
import sys
import json
import time
import uuid
import shutil
import threading
import urllib.request
import urllib.error
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

# ==============================================================================
# Generation Queue State (shared across MCP tools and Web UI)
# ==============================================================================
_QUEUE_LOCK = threading.Lock()
_QUEUE_JOBS: List[Dict] = []           # list of job dicts
_QUEUE_WORKER_RUNNING = False

def _queue_worker():
    """Background thread that processes queued generation jobs sequentially."""
    global _QUEUE_WORKER_RUNNING
    while True:
        job = None
        with _QUEUE_LOCK:
            pending = [j for j in _QUEUE_JOBS if j["status"] == "pending"]
            if not pending:
                _QUEUE_WORKER_RUNNING = False
                return
            job = pending[0]
            job["status"] = "running"
            job["started_at"] = time.time()

        try:
            result_str = generate_character_sprites(
                character_name=job["character_name"],
                archetype_prompt=job["concept"],
                seed=job.get("seed", -1),
                rig_type=job.get("rig_type", "biped"),
                checkpoint=job.get("checkpoint", ""),
                art_style=job.get("art_style", "anime"),
                detail_level=job.get("detail_level", 3),
            )
            result = json.loads(result_str)
            with _QUEUE_LOCK:
                job["status"] = "done"
                job["result"] = result
                job["finished_at"] = time.time()

            if job.get("auto_rig", True):
                assemble_godot_rig(
                    character_name=job["character_name"],
                    assets_dir=f"res://sprites/{job['character_name']}",
                    target_scene_path=f"res://scenes/{job['character_name']}_character.tscn",
                    rig_type=job.get("rig_type", "biped"),
                )
        except Exception as e:
            with _QUEUE_LOCK:
                job["status"] = "error"
                job["error"] = str(e)
                job["finished_at"] = time.time()


def _ensure_queue_worker():
    """Starts the background queue worker thread if not already running."""
    global _QUEUE_WORKER_RUNNING
    with _QUEUE_LOCK:
        if not _QUEUE_WORKER_RUNNING:
            _QUEUE_WORKER_RUNNING = True
            t = threading.Thread(target=_queue_worker, daemon=True)
            t.start()


def add_to_queue(job_dicts: List[Dict]) -> List[Dict]:
    """Adds a batch of character generation job dicts to the shared queue."""
    created_jobs = []
    with _QUEUE_LOCK:
        for item in job_dicts:
            job_id = f"job_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
            job = {
                "id": job_id,
                "character_name": item.get("character_name", "custom_character").strip().lower().replace(" ", "_"),
                "concept": item.get("concept") or item.get("archetype_prompt") or "heroic adventurer",
                "seed": item.get("seed", -1),
                "rig_type": item.get("rig_type", "biped"),
                "checkpoint": item.get("checkpoint", ""),
                "art_style": item.get("art_style", "anime"),
                "detail_level": item.get("detail_level", 3),
                "auto_rig": item.get("auto_rig", True),
                "status": "pending",
                "created_at": time.time(),
                "started_at": None,
                "finished_at": None,
                "error": None,
                "result": None
            }
            _QUEUE_JOBS.append(job)
            created_jobs.append(job)
    _ensure_queue_worker()
    return created_jobs


def get_all_queue_jobs() -> List[Dict]:
    """Returns a snapshot copy of all jobs currently in the queue."""
    with _QUEUE_LOCK:
        return [dict(j) for j in _QUEUE_JOBS]


def cancel_job(job_id: str) -> bool:
    """Cancels a pending or running job by ID."""
    with _QUEUE_LOCK:
        for j in _QUEUE_JOBS:
            if j["id"] == job_id:
                if j["status"] in ("pending", "running"):
                    j["status"] = "cancelled"
                    j["finished_at"] = time.time()
                    return True
    return False


def clear_completed_queue_jobs() -> int:
    """Removes finished (done, error, cancelled) jobs from the queue."""
    global _QUEUE_JOBS
    with _QUEUE_LOCK:
        before = len(_QUEUE_JOBS)
        _QUEUE_JOBS = [j for j in _QUEUE_JOBS if j["status"] in ("pending", "running")]
        return before - len(_QUEUE_JOBS)

from PIL import Image
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("Godot2dAutoSpriter")

def get_project_root() -> Path:
    """Finds the actual repository root where project.godot resides."""
    if os.environ.get("GODOT_PROJECT_ROOT"):
        p = Path(os.environ["GODOT_PROJECT_ROOT"]).resolve()
        if (p / "project.godot").is_file():
            return p
    cwd = Path.cwd().resolve()
    if (cwd / "project.godot").is_file():
        return cwd
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()
        if (exe_path.parent / "project.godot").is_file():
            return exe_path.parent
        if (exe_path.parent.parent / "project.godot").is_file():
            return exe_path.parent.parent
    if len(sys.argv) > 0 and sys.argv[0]:
        try:
            argv0 = Path(sys.argv[0]).resolve()
            if (argv0.parent / "project.godot").is_file():
                return argv0.parent
            if (argv0.parent.parent / "project.godot").is_file():
                return argv0.parent.parent
        except Exception:
            pass
    file_path = Path(__file__).resolve()
    if (file_path.parent / "project.godot").is_file():
        return file_path.parent
    if (file_path.parent.parent / "project.godot").is_file():
        return file_path.parent.parent
    known_repo = Path(r"D:\Projects\Godot2dAutoSpriter")
    if (known_repo / "project.godot").is_file():
        return known_repo
    return file_path.parent

PROJECT_ROOT = get_project_root()
COMFYUI_HOST = os.environ.get("COMFYUI_HOST", "127.0.0.1:8188")
GODOT_BIN = os.environ.get("GODOT_BIN", "")

BONE_PARTS_BIPED = [
    "pelvis",
    "torso",
    "head",
    "arm_upper_L",
    "arm_lower_L",
    "hand_L",
    "arm_upper_R",
    "arm_lower_R",
    "hand_R",
    "leg_upper_L",
    "leg_lower_L",
    "foot_L",
    "leg_upper_R",
    "leg_lower_R",
    "foot_R"
]

BONE_PARTS_QUADRUPED = [
    "pelvis",
    "tail_01",
    "tail_02",
    "tail_03",
    "leg_back_upper_L",
    "leg_back_lower_L",
    "paw_back_L",
    "leg_back_upper_R",
    "leg_back_lower_R",
    "paw_back_R",
    "spine",
    "torso",
    "leg_front_upper_L",
    "leg_front_lower_L",
    "paw_front_L",
    "leg_front_upper_R",
    "leg_front_lower_R",
    "paw_front_R",
    "neck",
    "head"
]

BONE_PARTS = BONE_PARTS_BIPED


def _find_godot_executable() -> str:
    """Finds the Godot 4 executable in environment variables or PATH."""
    if GODOT_BIN and os.path.isfile(GODOT_BIN):
        return GODOT_BIN

    candidates = [
        "Godot_v4.7.2-stable_win64_console.exe",
        "Godot_v4.7.2-stable_win64.exe",
        "godot4",
        "godot",
        "godot.exe"
    ]
    for name in candidates:
        found = shutil.which(name)
        if found:
            return found

    local_winget = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"
    if local_winget.is_dir():
        for exe in local_winget.glob("Godot*.exe"):
            if "console" in exe.name.lower():
                return str(exe)
        for exe in local_winget.glob("Godot*.exe"):
            return str(exe)

    local_pkg = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if local_pkg.is_dir():
        for exe in local_pkg.glob("**/Godot*console.exe"):
            return str(exe)
        for exe in local_pkg.glob("**/Godot*.exe"):
            return str(exe)
    return ""


def _find_godot_editor_executable() -> str:
    """Finds the native Godot 4 GUI (non-console) executable for interactive editor windows."""
    if GODOT_BIN and os.path.isfile(GODOT_BIN):
        if "console" in GODOT_BIN.lower():
            gui_sibling = GODOT_BIN.replace("_console.exe", ".exe").replace("-console.exe", ".exe")
            if os.path.isfile(gui_sibling):
                return gui_sibling
        return GODOT_BIN

    local_pkg = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if local_pkg.is_dir():
        for exe in local_pkg.glob("**/Godot*win64.exe"):
            if "console" not in exe.name.lower():
                return str(exe)

    candidates = [
        "Godot_v4.7.2-stable_win64.exe",
        "godot4",
        "godot.exe",
        "godot",
        "Godot_v4.7.2-stable_win64_console.exe"
    ]
    for name in candidates:
        found = shutil.which(name)
        if found:
            return found

    return _find_godot_executable()


def _detect_archetype(text: str) -> str:
    p = text.lower()
    if any(k in p for k in ["mage", "sorcer", "wizard", "magic", "arcane", "witch"]):
        return "mage"
    if any(k in p for k in ["ninja", "assassin", "rogue", "shadow", "stealth", "thief"]):
        return "assassin"
    if any(k in p for k in ["ranger", "archer", "hunt", "bow", "forest", "sniper"]):
        return "ranger"
    if any(k in p for k in ["mech", "robot", "cyborg", "tank", "golem", "juggernaut", "titan"]):
        return "mech"
    return "warrior"


# ==============================================================================
# Alpha-Blob Connected Component Limb Slicer
# ==============================================================================

def _find_alpha_blobs(img: Image.Image, alpha_threshold: int = 30) -> List[Dict]:
    """
    Finds connected alpha blobs in an RGBA image using a scanline flood-fill
    approach. Returns a list of blob dicts with keys: bbox, cx, cy, area, pixels.

    This is much more reliable than fixed % grid crops because it finds where the
    actual character pixels are, regardless of composition position or scale.
    """
    rgba = img.convert("RGBA")
    w, h = rgba.size
    alpha = rgba.split()[3]

    # Auto-keying: If image has a solid background (e.g. from standard VAE decode without LayerDiffuse),
    # sample corner pixels and key out the background color to transparent alpha.
    try:
        extrema = alpha.getextrema()
        if extrema[0] > 240:
            corners = [rgba.getpixel((0, 0)), rgba.getpixel((w - 1, 0)), rgba.getpixel((0, h - 1)), rgba.getpixel((w - 1, h - 1))]
            bg_r = sum(c[0] for c in corners) // 4
            bg_g = sum(c[1] for c in corners) // 4
            bg_b = sum(c[2] for c in corners) // 4
            new_img = Image.new("RGBA", (w, h))
            src_data = rgba.getdata()
            out_data = []
            for p in src_data:
                dist = abs(p[0] - bg_r) + abs(p[1] - bg_g) + abs(p[2] - bg_b)
                if dist < 50:
                    out_data.append((p[0], p[1], p[2], 0))
                else:
                    out_data.append((p[0], p[1], p[2], 255))
            new_img.putdata(out_data)
            rgba = new_img
            alpha = rgba.split()[3]
    except Exception:
        pass

    # Build binary mask: 1 = opaque enough, 0 = transparent
    mask = bytearray(w * h)
    alpha_bytes = alpha.tobytes()
    for i, a in enumerate(alpha_bytes):
        if a >= alpha_threshold:
            mask[i] = 1

    visited = bytearray(w * h)
    blobs = []

    def flood_fill(sx, sy):
        """Iterative BFS flood fill."""
        queue = [(sx, sy)]
        pixels = []
        min_x, min_y = sx, sy
        max_x, max_y = sx, sy
        while queue:
            x, y = queue.pop()
            idx = y * w + x
            if visited[idx] or not mask[idx]:
                continue
            visited[idx] = 1
            pixels.append((x, y))
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
            for nx, ny in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                if 0 <= nx < w and 0 <= ny < h:
                    nidx = ny * w + nx
                    if not visited[nidx] and mask[nidx]:
                        queue.append((nx, ny))
        return pixels, (min_x, min_y, max_x, max_y)

    for y in range(0, h, 2):  # stride 2 for speed; fine enough for 1024px
        for x in range(0, w, 2):
            idx = y * w + x
            if mask[idx] and not visited[idx]:
                pixels, bbox = flood_fill(x, y)
                area = len(pixels)
                if area < 80:  # skip tiny specks / noise
                    continue
                bw = bbox[2] - bbox[0] + 1
                bh = bbox[3] - bbox[1] + 1
                cx = (bbox[0] + bbox[2]) / 2.0
                cy = (bbox[1] + bbox[3]) / 2.0
                blobs.append({
                    "bbox": bbox,
                    "cx": cx, "cy": cy,
                    "area": area,
                    "bw": bw, "bh": bh
                })

    return blobs


def _assign_blobs_to_bones_biped(blobs: List[Dict], img_w: int, img_h: int) -> Dict[str, Dict]:
    """
    Heuristically maps alpha blobs to biped bone slots by position and size.

    Assignment strategy:
    - Sort blobs by vertical center (top → bottom).
    - Top-most blob → head.
    - Second-from-top center blob → torso.
    - Center blob at ~50-65% height → pelvis.
    - Upper-right blobs (from character's perspective, our left) → arm_upper_L etc.
    - Upper-left blobs → arm_upper_R etc.
    - Lower blobs left/right → legs.
    - Bottom-most blobs → feet.
    """
    if not blobs:
        return {}

    # Sort by vertical center (top = smallest cy)
    blobs_sorted = sorted(blobs, key=lambda b: b["cy"])
    mid_x = img_w / 2.0

    assignment = {}

    # Group blobs into rough vertical bands:
    # head zone:   cy < 30% of height
    # torso zone:  30-55%
    # pelvis zone: 50-68%
    # arm zone:    20-65% (lateral)
    # leg zone:    60-88%
    # foot zone:   85-100%

    head_z   = [b for b in blobs_sorted if b["cy"] < img_h * 0.32]
    torso_z  = [b for b in blobs_sorted if img_h * 0.28 <= b["cy"] < img_h * 0.56]
    pelvis_z = [b for b in blobs_sorted if img_h * 0.48 <= b["cy"] < img_h * 0.70]
    arm_z    = [b for b in blobs_sorted if img_h * 0.18 <= b["cy"] < img_h * 0.68 and (b["cx"] < img_w * 0.35 or b["cx"] > img_w * 0.65)]
    leg_z    = [b for b in blobs_sorted if img_h * 0.58 <= b["cy"] < img_h * 0.90]
    foot_z   = [b for b in blobs_sorted if b["cy"] >= img_h * 0.82]

    used_ids = set()

    def pick_best(zone, prefer_left=None, prefer_right=None, exclude=None):
        """Pick largest blob in zone matching lateral preference."""
        candidates = [b for b in zone if id(b) not in used_ids]
        if prefer_left:
            candidates = [b for b in candidates if b["cx"] < mid_x]
        if prefer_right:
            candidates = [b for b in candidates if b["cx"] >= mid_x]
        if not candidates:
            return None
        return max(candidates, key=lambda b: b["area"])

    def assign(name, blob):
        if blob:
            used_ids.add(id(blob))
            assignment[name] = blob

    # --- Core body ---
    head_blob = pick_best(head_z)
    assign("head", head_blob)

    torso_blob = pick_best(torso_z)
    assign("torso", torso_blob)

    pelvis_blob = pick_best(pelvis_z)
    assign("pelvis", pelvis_blob)

    # --- Arms: character's left = our right (cx > mid) ---
    arm_right_blobs = sorted([b for b in arm_z if b["cx"] > mid_x and id(b) not in used_ids], key=lambda b: b["cy"])
    arm_left_blobs  = sorted([b for b in arm_z if b["cx"] < mid_x and id(b) not in used_ids], key=lambda b: b["cy"])

    if len(arm_right_blobs) >= 1: assign("arm_upper_L", arm_right_blobs[0])
    if len(arm_right_blobs) >= 2: assign("arm_lower_L", arm_right_blobs[1])
    if len(arm_right_blobs) >= 3: assign("hand_L",      arm_right_blobs[2])
    if len(arm_left_blobs)  >= 1: assign("arm_upper_R", arm_left_blobs[0])
    if len(arm_left_blobs)  >= 2: assign("arm_lower_R", arm_left_blobs[1])
    if len(arm_left_blobs)  >= 3: assign("hand_R",      arm_left_blobs[2])

    # --- Legs ---
    leg_right_blobs = sorted([b for b in leg_z if b["cx"] > mid_x and id(b) not in used_ids], key=lambda b: b["cy"])
    leg_left_blobs  = sorted([b for b in leg_z if b["cx"] < mid_x and id(b) not in used_ids], key=lambda b: b["cy"])

    if len(leg_right_blobs) >= 1: assign("leg_upper_L", leg_right_blobs[0])
    if len(leg_right_blobs) >= 2: assign("leg_lower_L", leg_right_blobs[1])
    if len(leg_left_blobs)  >= 1: assign("leg_upper_R", leg_left_blobs[0])
    if len(leg_left_blobs)  >= 2: assign("leg_lower_R", leg_left_blobs[1])

    # --- Feet ---
    foot_right = [b for b in foot_z if b["cx"] > mid_x and id(b) not in used_ids]
    foot_left  = [b for b in foot_z if b["cx"] < mid_x and id(b) not in used_ids]
    if foot_right: assign("foot_L", max(foot_right, key=lambda b: b["area"]))
    if foot_left:  assign("foot_R", max(foot_left,  key=lambda b: b["area"]))

    return assignment


def _crop_blob(src: Image.Image, blob: Dict, padding: int = 10) -> Image.Image:
    """Crops a blob region from src RGBA image with padding."""
    x0, y0, x1, y1 = blob["bbox"]
    x0 = max(0, x0 - padding)
    y0 = max(0, y0 - padding)
    x1 = min(src.width - 1, x1 + padding)
    y1 = min(src.height - 1, y1 + padding)
    return src.crop((x0, y0, x1 + 1, y1 + 1))


# ==============================================================================
# MCP TOOL 1: generate_character_sprites
# ==============================================================================
@mcp.tool()
def generate_character_sprites(
    character_name: str,
    archetype_prompt: str,
    seed: int = -1,
    rig_type: str = "biped",
    checkpoint: str = "",
    art_style: str = "anime",
    detail_level: int = 3
) -> str:
    """
    Connects to the local ComfyUI API to trigger character generation via the
    exploded OpenPose + LayerDiffuse pipeline. Automatically adapts the workflow
    based on checkpoint base (SDXL vs SD1.5), art style, and detail level.
    The LoRA node is skipped if the LoRA file is not present.

    Args:
        character_name: Alphanumeric identifier for the character (e.g. 'ronin', 'fenrir').
        archetype_prompt: Visual prompt (e.g. 'cyberpunk cyber-blade assassin, neon visor').
        seed: Random seed for generation (-1 for randomized).
        rig_type: Rig hierarchy type ('biped' or 'quadruped').
        checkpoint: ComfyUI checkpoint filename (e.g. 'animagineXL_v31.safetensors').
        art_style: Render style: 'anime', 'dark_fantasy', 'pixel_8bit', 'pixel_16bit',
                   'cyberpunk', 'moba_chibi', 'comic_ink', 'painterly', 'watercolor'.
        detail_level: 1=minimal, 2=standard, 3=detailed (default), 4=hyper, 5=ultra.

    Returns:
        JSON string containing status, output image path, and parameters.
    """
    import random as _random
    clean_name = character_name.strip().lower().replace(" ", "_")
    if seed == -1:
        seed = _random.randint(1, 2147483647)

    out_dir = PROJECT_ROOT / "sprites" / clean_name
    out_dir.mkdir(parents=True, exist_ok=True)
    exploded_image_path = out_dir / f"{clean_name}_exploded.png"

    client_id = uuid.uuid4().hex
    ckpt_name = checkpoint.strip() if checkpoint else os.environ.get("COMFYUI_CHECKPOINT", "animagineXL_v31.safetensors")

    # Detect model base from filename
    ckpt_lower = ckpt_name.lower()
    is_sdxl = any(k in ckpt_lower for k in ["xl", "sdxl", "pony", "animagine"])
    is_pixel = any(k in ckpt_lower for k in ["pixel", "sprite"])

    # Style-specific prompt prefix and sampler tuning
    style_cfg = {
        "anime":      {"prefix": "masterpiece, best quality, anime 2d game sprite, clean flat cel shading, crisp bold outlines, vibrant saturated colors",          "steps": 22, "cfg": 7.0, "neg": "blurry, 3d, photorealistic, deformed, watermark"},
        "dark_fantasy":{"prefix": "dark fantasy, gothic grimdark game character, weathered steel armor, runic glowing markings, painted shadows, eerie soul glow",    "steps": 26, "cfg": 7.5, "neg": "bright, cheerful, 3d render, blurry, photorealistic"},
        "pixel_8bit": {"prefix": "pixel art, 8-bit retro video game sprite, 8 color palette, crisp pixels, dithering, NES style game character, flat pixel blocks",   "steps": 18, "cfg": 6.5, "neg": "blurry, smooth, 3d, anti-aliased, realistic, gradient"},
        "pixel_16bit":{"prefix": "pixel art, 16-bit SNES-era video game character sprite, 32 color palette, clean pixel clusters, RPG sprite, SNES style character",   "steps": 20, "cfg": 7.0, "neg": "blurry, anti-aliased, 3d render, photorealistic, gradient"},
        "cyberpunk":  {"prefix": "neon cyberpunk synth game sprite, high-tech carbon fiber plates, glowing bioluminescent circuit traces, holo-visor, plasma accents",  "steps": 24, "cfg": 7.5, "neg": "natural, fantasy, medieval, blurry, 3d render"},
        "moba_chibi": {"prefix": "chibi stylized MOBA hero game character, exaggerated cute head proportions, clean flat contours, luminous highlight, League of Legends style", "steps": 20, "cfg": 7.0, "neg": "realistic, 3d, dark, gory, blurry"},
        "comic_ink":  {"prefix": "comic graphic novel game sprite, heavy bold black ink outlines, solid halftone shading, dramatic ink wash, ink splash effects",        "steps": 22, "cfg": 7.5, "neg": "blurry, 3d render, photorealistic, gradient"},
        "painterly":  {"prefix": "painterly oil painting style game character, impressionist brushwork, rich color layering, textured surface, artstation quality",       "steps": 28, "cfg": 8.0, "neg": "flat, cartoon, 3d render, blurry, amateur"},
        "watercolor": {"prefix": "soft watercolor illustration game character, transparent wash layers, bleeding ink edges, whimsical palette, studio ghibli aesthetic",   "steps": 24, "cfg": 7.5, "neg": "3d render, photorealistic, sharp lines, pixel, blurry"},
    }
    sc = style_cfg.get(art_style, style_cfg["anime"])

    # Detail level adjustments
    detail_prefixes = {
        1: "simple flat silhouette, minimal details, clean shape",
        2: "clean standard anime details, basic shading",
        3: "detailed anatomy, layered shading, intricate costume",
        4: "hyper detailed, ultra intricate costume, rich texture, fine line art",
        5: "ultra detailed masterpiece, extremely intricate detail, every thread visible, museum quality",
    }
    detail_steps_bonus = {1: -6, 2: -3, 3: 0, 4: +5, 5: +10}
    detail_cfg_bonus   = {1: -1.0, 2: -0.5, 3: 0.0, 4: +0.5, 5: +1.0}
    dl = max(1, min(5, int(detail_level)))
    detail_prefix = detail_prefixes[dl]
    total_steps = max(10, sc["steps"] + detail_steps_bonus[dl])
    total_cfg = round(sc["cfg"] + detail_cfg_bonus[dl], 1)

    full_prompt = f"{sc['prefix']}, {detail_prefix}, {archetype_prompt}, orthographic front view, modular exploded character cut-out sheet, transparent background"
    neg_prompt = sc["neg"] + ", low quality, extra limbs, missing limbs, mutation, deformed, ugly"

    # Determine if LoRA is available
    from scripts.download_models import find_comfyui_models_directory
    mdir = find_comfyui_models_directory()
    lora_path = mdir / "loras" / "flat2DAnimerge_v10.safetensors"
    has_lora = lora_path.is_file() and is_sdxl  # Only use SDXL flat LoRA with SDXL checkpoints

    # Pixel Art LoRA (SDXL vs SD 1.5)
    pixel_lora_file = "pixel-art-xl.safetensors" if is_sdxl else "PixelArtRedmond15V-PixelArt-PIXARFK.safetensors"
    has_pixel_lora = (mdir / "loras" / pixel_lora_file).is_file() and art_style in ("pixel_8bit", "pixel_16bit")

    # ControlNet availability
    cn_file = "thibaud_xl_openpose.safetensors" if is_sdxl else "control_v11p_sd15_openpose_fp16.safetensors"
    has_cn = (mdir / "controlnet" / cn_file).is_file()

    # LayerDiffuse availability
    if is_sdxl:
        has_ld = (mdir / "layer_model" / "layer_xl_transparent_conv.safetensors").is_file() and (mdir / "layer_model" / "vae_transparent_decoder.safetensors").is_file()
        ld_config = "SDXL, Conv Injection"
    else:
        has_ld = (mdir / "layer_model" / "layer_sd15_transparent_attn.safetensors").is_file() and (mdir / "layer_model" / "vae_transparent_decoder.safetensors").is_file()
        ld_config = "SD1.5, Attn Injection"

    latent_size = 512 if (not is_sdxl or art_style in ("pixel_8bit", "pixel_16bit")) else 1024

    # Build workflow dynamically — LoRA, LayerDiffuse, and ControlNet are optional/adaptive
    checkpoint_node_id = "1"
    model_ref = ["1", 0]
    clip_ref  = ["1", 1]
    next_node = 2

    workflow: Dict = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": ckpt_name}
        }
    }

    # Optional style LoRA
    if has_lora:
        workflow[str(next_node)] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": "flat2DAnimerge_v10.safetensors",
                "strength_model": 0.75,
                "strength_clip": 0.75,
                "model": model_ref,
                "clip": clip_ref
            }
        }
        model_ref = [str(next_node), 0]
        clip_ref  = [str(next_node), 1]
        next_node += 1
    elif has_pixel_lora:
        workflow[str(next_node)] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": pixel_lora_file,
                "strength_model": 0.9,
                "strength_clip": 0.9,
                "model": model_ref,
                "clip": clip_ref
            }
        }
        model_ref = [str(next_node), 0]
        clip_ref  = [str(next_node), 1]
        next_node += 1

    pos_node = str(next_node)
    workflow[pos_node] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": full_prompt, "clip": clip_ref}
    }
    next_node += 1

    neg_node = str(next_node)
    workflow[neg_node] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": neg_prompt, "clip": clip_ref}
    }
    next_node += 1

    if has_ld:
        ld_node = str(next_node)
        workflow[ld_node] = {
            "class_type": "LayeredDiffusionApply",
            "inputs": {"config": ld_config, "weight": 1.0, "model": model_ref}
        }
        next_node += 1
        active_model_ref = [ld_node, 0]
    else:
        active_model_ref = model_ref

    if has_cn:
        cn_load_node = str(next_node)
        workflow[cn_load_node] = {
            "class_type": "ControlNetLoader",
            "inputs": {"control_net_name": cn_file}
        }
        next_node += 1

        pose_img_node = str(next_node)
        template_file = "exploded_openpose_template.png"
        workflow[pose_img_node] = {
            "class_type": "LoadImage",
            "inputs": {"image": template_file}
        }
        next_node += 1

        cn_apply_node = str(next_node)
        workflow[cn_apply_node] = {
            "class_type": "ControlNetApply",
            "inputs": {
                "strength": 0.85,
                "conditioning": [pos_node, 0],
                "control_net": [cn_load_node, 0],
                "image": [pose_img_node, 0]
            }
        }
        next_node += 1
        active_pos_ref = [cn_apply_node, 0]
    else:
        active_pos_ref = [pos_node, 0]

    latent_node = str(next_node)
    workflow[latent_node] = {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": latent_size, "height": latent_size, "batch_size": 1}
    }
    next_node += 1

    sampler_node = str(next_node)
    workflow[sampler_node] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": seed,
            "steps": total_steps,
            "cfg": total_cfg,
            "sampler_name": "dpmpp_2m",
            "scheduler": "karras",
            "denoise": 1.0,
            "model": active_model_ref,
            "positive": active_pos_ref,
            "negative": [neg_node, 0],
            "latent_image": [latent_node, 0]
        }
    }
    next_node += 1

    vae_node = str(next_node)
    workflow[vae_node] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": [sampler_node, 0], "vae": [checkpoint_node_id, 2]}
    }
    next_node += 1

    if has_ld:
        decode_node = str(next_node)
        workflow[decode_node] = {
            "class_type": "LayeredDiffusionDecodeRGBA",
            "inputs": {
                "samples": [sampler_node, 0],
                "images": [vae_node, 0],
                "sd_version": "SDXL" if is_sdxl else "SD1.5",
                "sub_batch_size": 16
            }
        }
        next_node += 1
        final_img_ref = [decode_node, 0]
    else:
        final_img_ref = [vae_node, 0]

    save_node = str(next_node)
    workflow[save_node] = {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": f"exploded_{clean_name}",
            "images": final_img_ref
        }
    }

    # Attempt to query live ComfyUI API
    comfy_url = f"http://{COMFYUI_HOST}/prompt"
    prompt_id = None
    prompt_error = ""
    try:
        req = urllib.request.Request(
            comfy_url,
            data=json.dumps({"prompt": workflow, "client_id": client_id}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            prompt_id = data.get("prompt_id")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
        prompt_error = f"HTTP {e.code}: {err_body[:300]}"
    except Exception as e:
        prompt_error = str(e)

    if prompt_id:
        output_filename = None
        for _ in range(90):  # poll up to 90 seconds
            time.sleep(1.0)
            try:
                hist_req = urllib.request.Request(f"http://{COMFYUI_HOST}/history/{prompt_id}")
                with urllib.request.urlopen(hist_req, timeout=3) as hresp:
                    hist_data = json.loads(hresp.read().decode("utf-8"))
                    if prompt_id in hist_data:
                        task_info = hist_data[prompt_id]
                        status = task_info.get("status", {})
                        if status.get("completed", False):
                            outputs = task_info.get("outputs", {})
                            for nid, nout in outputs.items():
                                if "images" in nout and len(nout["images"]) > 0:
                                    output_filename = nout["images"][0].get("filename")
                                    break
                            break
                        elif status.get("status_str") == "error":
                            break
            except Exception:
                pass

        if output_filename:
            candidate_paths = [
                Path(os.environ.get("LOCALAPPDATA", "")) / "Comfy-Desktop" / "ComfyUI-Shared" / "output" / output_filename,
                Path(os.environ.get("LOCALAPPDATA", "")) / "Comfy-Desktop" / "ComfyUI-Installs" / "ComfyUI" / "ComfyUI" / "output" / output_filename
            ]
            saved_file = None
            for cp in candidate_paths:
                if cp.is_file():
                    saved_file = cp
                    break

            if saved_file:
                shutil.copyfile(saved_file, exploded_image_path)
                # Use blob-detection slicer
                sliced = slice_character_limbs(
                    character_name=clean_name,
                    input_image_path=str(exploded_image_path),
                    output_dir=str(out_dir),
                    rig_type=rig_type,
                    force=True
                )
                return json.dumps({
                    "status": "completed",
                    "source": "comfyui_api",
                    "character_name": clean_name,
                    "seed": seed,
                    "checkpoint": ckpt_name,
                    "output_image": str(exploded_image_path),
                    "limbs_sliced": len(sliced),
                    "message": f"Successfully generated and sliced diffusion character sprites for {clean_name}"
                }, indent=2)

    # Offline / Standalone Fallback: Use internal organic spriter
    try:
        from scripts.generate_sample_sprites import generate_all, generate_quadruped
        arch = _detect_archetype(archetype_prompt)
        if rig_type.lower() == "quadruped":
            generate_quadruped(str(out_dir), prefix=clean_name, archetype="assassin" if arch == "beast" else arch, prompt=archetype_prompt, seed=seed)
        else:
            generate_all(str(out_dir), prefix=clean_name, archetype=arch, prompt=archetype_prompt, seed=seed)
    except Exception as e:
        pass

    return json.dumps({
        "status": "ready",
        "source": "local_pipeline",
        "character_name": clean_name,
        "seed": seed,
        "output_image": str(exploded_image_path),
        "note": f"ComfyUI host ({COMFYUI_HOST}) error: {prompt_error}" if prompt_error else f"ComfyUI host ({COMFYUI_HOST}) was unreachable or timed out; generated local master sprite set.",
        "assets_directory": str(out_dir)
    }, indent=2)


# ==============================================================================
# MCP TOOL 2: slice_character_limbs
# ==============================================================================
@mcp.tool()
def slice_character_limbs(
    character_name: str,
    input_image_path: str,
    output_dir: str = "",
    rig_type: str = "biped",
    force: bool = False
) -> List[str]:
    """
    Segments individual transparent limb PNGs from an exploded character sheet
    using alpha-channel connected component blob detection.

    Replaces the previous hardcoded %-grid crop approach with a spatial blob finder
    that locates actual alpha regions in the image regardless of composition position.
    Falls back to the organic procedural generator if fewer than 8 blobs are found.

    Args:
        character_name: Name of character to prefix files with.
        input_image_path: Path to the exploded RGBA image sheet.
        output_dir: Destination folder. If omitted, defaults to 'sprites/<character_name>'.
        rig_type: Rig hierarchy type ('biped' or 'quadruped').
        force: Force re-slicing even if files exist.

    Returns:
        List of generated absolute file paths for each body part.
    """
    clean_name = character_name.strip().lower().replace(" ", "_")
    target_dir = Path(output_dir) if output_dir else PROJECT_ROOT / "sprites" / clean_name
    target_dir.mkdir(parents=True, exist_ok=True)

    bone_list = BONE_PARTS_QUADRUPED if rig_type.lower() == "quadruped" else BONE_PARTS_BIPED
    generated_files: List[str] = []

    # Check if pre-separated files already exist (skip if not forcing)
    if not force:
        existing_parts = list(target_dir.glob(f"{clean_name}_*.png"))
        if len(existing_parts) >= len(bone_list):
            return [str(p.resolve()) for p in existing_parts]

    img_path = Path(input_image_path)
    if img_path.is_file():
        try:
            src = Image.open(img_path).convert("RGBA")
            w, h = src.size

            # Find alpha blobs
            blobs = _find_alpha_blobs(src, alpha_threshold=30)

            if len(blobs) >= 5:
                # We have enough blobs — use positional assignment
                if rig_type.lower() == "biped":
                    blob_map = _assign_blobs_to_bones_biped(blobs, w, h)
                else:
                    # For quadruped, use biped logic as approximation (extend later)
                    blob_map = _assign_blobs_to_bones_biped(blobs, w, h)

                for bone_name, blob in blob_map.items():
                    cropped = _crop_blob(src, blob, padding=10)
                    dest = target_dir / f"{clean_name}_{bone_name}.png"
                    cropped.save(dest, "PNG")
                    generated_files.append(str(dest.resolve()))

                # For any bones not assigned by blob matching, evaluate whether fallback is needed
                missing_bones = [b for b in bone_list if b not in blob_map]
                if len(missing_bones) > 2 or "torso" in missing_bones or "head" in missing_bones:
                    # Too many essential parts missing or missing critical core; fall back to procedural generator
                    _procedural_fallback(clean_name, target_dir, rig_type, character_name)
                    generated_files = []
                    for bone in bone_list:
                        fpath = target_dir / f"{clean_name}_{bone}.png"
                        if fpath.is_file():
                            generated_files.append(str(fpath.resolve()))
                    try:
                        from scripts.generate_sample_sprites import create_character_assembled_preview
                        create_character_assembled_preview(target_dir, clean_name, rig_type)
                    except Exception:
                        pass
                    return generated_files
                elif missing_bones:
                    _generate_placeholder_limbs(clean_name, target_dir, missing_bones, src, blob_map)
                    for bone in missing_bones:
                        dest = target_dir / f"{clean_name}_{bone}.png"
                        if dest.is_file():
                            generated_files.append(str(dest.resolve()))

                if generated_files:
                    try:
                        from scripts.generate_sample_sprites import create_character_assembled_preview
                        create_character_assembled_preview(target_dir, clean_name, rig_type)
                    except Exception:
                        pass
                    return generated_files
            else:
                # Too few blobs — image is mostly solid, fall through to procedural
                pass

        except Exception as e:
            pass

    # Procedural fallback: generate clean limb set
    _procedural_fallback(clean_name, target_dir, rig_type, character_name)

    for bone in bone_list:
        fpath = target_dir / f"{clean_name}_{bone}.png"
        if fpath.is_file():
            generated_files.append(str(fpath.resolve()))

    try:
        from scripts.generate_sample_sprites import create_character_assembled_preview
        create_character_assembled_preview(target_dir, clean_name, rig_type)
    except Exception:
        pass

    return generated_files


def _generate_placeholder_limbs(char_name: str, target_dir: Path, missing_bones: List[str],
                                  src_img: Image.Image, blob_map: Dict) -> None:
    """Generates small placeholder limb sprites for bones not found in the blob map,
    by sampling the dominant color from existing assigned blobs."""
    # Sample a representative color from the source image center
    w, h = src_img.size
    sample = src_img.getpixel((w // 2, h // 2))
    r, g, b = sample[:3]

    for bone in missing_bones:
        # Infer size from similar bones
        size = (48, 64)
        if "hand" in bone or "foot" in bone:
            size = (40, 40)
        elif "head" in bone:
            size = (64, 72)
        elif "torso" in bone or "pelvis" in bone:
            size = (72, 80)

        placeholder = Image.new("RGBA", size, (0, 0, 0, 0))
        from PIL import ImageDraw
        draw = ImageDraw.Draw(placeholder)
        draw.ellipse([4, 4, size[0]-4, size[1]-4], fill=(r, g, b, 200))
        dest = target_dir / f"{char_name}_{bone}.png"
        placeholder.save(dest, "PNG")


def _procedural_fallback(char_name: str, target_dir: Path, rig_type: str, prompt: str = "") -> None:
    """Calls the organic procedural spriter as a fallback when blob detection fails."""
    try:
        from scripts.generate_sample_sprites import generate_all, generate_quadruped
        arch = _detect_archetype(prompt or char_name)
        if rig_type.lower() == "quadruped":
            generate_quadruped(str(target_dir), prefix=char_name, archetype=arch)
        else:
            generate_all(str(target_dir), prefix=char_name, archetype=arch)
    except Exception:
        pass


# ==============================================================================
# MCP TOOL 3: assemble_godot_rig
# ==============================================================================
@mcp.tool()
def assemble_godot_rig(
    character_name: str,
    assets_dir: str,
    target_scene_path: str = "",
    rig_type: str = "biped",
    template_path: str = ""
) -> str:
    """
    Invokes Godot CLI in headless mode to bind exported cut-out PNGs to the master
    Skeleton2D template and save a production-ready character .tscn scene.

    Args:
        character_name: Name of the character.
        assets_dir: Directory containing the sliced PNGs (e.g. 'res://sprites/warrior').
        target_scene_path: Destination .tscn file (e.g. 'res://scenes/warrior.tscn').
        rig_type: Rig hierarchy type ('biped' or 'quadruped').
        template_path: Optional custom .tscn template path (e.g. 'res://scenes/custom_rig.tscn').

    Returns:
        JSON string reporting execution status, exit code, and target scene path.
    """
    clean_name = character_name.strip().lower().replace(" ", "_")
    godot_exe = _find_godot_executable()
    if not godot_exe:
        return json.dumps({
            "status": "error",
            "character_name": clean_name,
            "message": "Godot 4 executable not found. Please set GODOT_BIN environment variable or install Godot 4."
        }, indent=2)

    if not target_scene_path:
        target_scene_path = f"res://scenes/{clean_name}_character.tscn"

    if not assets_dir.startswith("res://"):
        assets_dir = f"res://sprites/{clean_name}"

    # Verify sprites exist before attempting rig
    sprites_abs = PROJECT_ROOT / "sprites" / clean_name
    if not sprites_abs.is_dir() or not any(sprites_abs.glob("*.png")):
        return json.dumps({
            "status": "error",
            "character_name": clean_name,
            "message": f"No sprite PNGs found in sprites/{clean_name}/. Generate sprites first."
        }, indent=2)

    script_path = "res://scripts/headless_rig_builder.gd"

    cmd = [
        godot_exe,
        "--headless",
        "--path",
        str(PROJECT_ROOT),
        "--script",
        script_path,
        "--",
        "--character-name",
        clean_name,
        "--assets-dir",
        assets_dir,
        "--target-scene",
        target_scene_path,
        "--rig-type",
        rig_type
    ]
    if template_path:
        cmd.extend(["--template", template_path])

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30
        )

        success = (proc.returncode == 0)
        return json.dumps({
            "status": "success" if success else "error",
            "character_name": clean_name,
            "target_scene": target_scene_path,
            "exit_code": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip()
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "character_name": clean_name,
            "message": str(e),
            "godot_command": " ".join(cmd)
        }, indent=2)


# ==============================================================================
# MCP TOOL 4: setup_comfyui_environment
# ==============================================================================
@mcp.tool()
def setup_comfyui_environment(
    action: str = "check"
) -> str:
    """
    Checks, verifies, or automatically installs required ComfyUI components:
    custom node packs (LayerDiffuse, IP-Adapter, ControlNet-aux), input control templates,
    and neural network model weights.

    Args:
        action: One of 'check', 'install_nodes', 'install_inputs', 'install_models', 'install_all'.

    Returns:
        JSON string reporting current status and operation results.
    """
    from scripts.setup_comfyui import (
        find_comfyui_paths,
        install_custom_nodes,
        install_inputs,
        install_models,
        NODE_REPOSITORIES,
        MODEL_MANIFEST
    )

    comfy_root, custom_nodes, models_dir, py_bin = find_comfyui_paths()

    if action == "install_nodes" and custom_nodes:
        install_custom_nodes(custom_nodes, py_bin)
    elif action == "install_inputs":
        install_inputs(comfy_root)
    elif action == "install_models" and models_dir:
        install_models(models_dir, include_checkpoint=False)
    elif action == "install_checkpoint" or action == "download_checkpoint":
        from scripts.download_models import download_model
        download_model("animagine_xl", models_dir=models_dir)
    elif action == "install_all":
        if custom_nodes:
            install_custom_nodes(custom_nodes, py_bin)
        install_inputs(comfy_root)
        if models_dir:
            install_models(models_dir, include_checkpoint=False)

    nodes_status = {}
    if custom_nodes and custom_nodes.is_dir():
        for k in NODE_REPOSITORIES.keys():
            nodes_status[k] = (custom_nodes / k).is_dir()

    models_status = {}
    if models_dir and models_dir.is_dir():
        for rel, info in MODEL_MANIFEST.items():
            p = models_dir / rel
            models_status[p.name] = {
                "installed": p.is_file(),
                "size_mb": round(p.stat().st_size / (1024*1024), 1) if p.is_file() else 0.0,
                "expected_mb": info["size_mb"],
                "desc": info["desc"]
            }

    inputs_status = {
        "biped_template": (PROJECT_ROOT / "workflows" / "inputs" / "exploded_openpose_template.png").is_file(),
        "quadruped_template": (PROJECT_ROOT / "workflows" / "inputs" / "exploded_quadruped_openpose_template.png").is_file()
    }

    return json.dumps({
        "status": "ready",
        "action": action,
        "comfyui_detected": comfy_root is not None,
        "comfyui_path": str(comfy_root) if comfy_root else None,
        "models_directory": str(models_dir) if models_dir else None,
        "custom_nodes": nodes_status,
        "inputs": inputs_status,
        "models": models_status
    }, indent=2)


# ==============================================================================
# MCP TOOL 5: download_comfyui_model
# ==============================================================================
@mcp.tool()
def download_comfyui_model(
    model_name: str = "animagine_xl"
) -> str:
    """
    Downloads an AI diffusion model checkpoint or neural weight file
    (e.g., Animagine XL 3.1, Counterfeit V3.0, DreamShaper 8) for local ComfyUI generation.
    Supports HTTP Range resumption so interrupted downloads automatically continue.

    Args:
        model_name: One of 'animagine_xl', 'counterfeit_v3', 'dreamshaper_8', 'layer_conv',
                    'vae_decoder', 'controlnet_openpose', 'flat_anime_lora', or 'status'.

    Returns:
        JSON string reporting download result or status table.
    """
    from scripts.download_models import download_model, get_model_status, find_comfyui_models_directory, MODELS_CATALOG

    mdir = find_comfyui_models_directory()
    if model_name == "status":
        return json.dumps({
            "status": "success",
            "models_dir": str(mdir),
            "catalog": get_model_status(mdir)
        }, indent=2)

    if model_name not in MODELS_CATALOG:
        return json.dumps({
            "status": "error",
            "message": f"Unknown model '{model_name}'. Available models: {list(MODELS_CATALOG.keys())} or 'status'"
        }, indent=2)

    ok, msg = download_model(model_name, models_dir=mdir)
    return json.dumps({
        "status": "success" if ok else "error",
        "model": model_name,
        "models_dir": str(mdir),
        "message": msg
    }, indent=2)


# ==============================================================================
# MCP TOOL 6: list_generated_characters
# ==============================================================================
@mcp.tool()
def list_generated_characters() -> str:
    """
    Lists all characters that have been generated and stored in the sprites/ directory,
    along with their metadata (limb count, Godot scene availability, last modified time).

    Returns:
        JSON string with a list of character metadata dicts.
    """
    sprites_root = PROJECT_ROOT / "sprites"
    scenes_root  = PROJECT_ROOT / "scenes"
    characters = []

    if sprites_root.is_dir():
        for char_dir in sorted(sprites_root.iterdir()):
            if not char_dir.is_dir():
                continue
            limb_files = sorted(char_dir.glob("*.png"))
            limb_files = [f for f in limb_files if "_exploded" not in f.name]
            has_exploded = (char_dir / f"{char_dir.name}_exploded.png").is_file()
            full_preview = (char_dir / f"{char_dir.name}_full.png")
            if not full_preview.is_file():
                try:
                    from scripts.generate_sample_sprites import create_character_assembled_preview
                    create_character_assembled_preview(char_dir, prefix=char_dir.name)
                except Exception:
                    pass
            has_full = full_preview.is_file()
            scene_file = scenes_root / f"{char_dir.name}_character.tscn"
            last_mod = 0.0
            for f in limb_files:
                try:
                    last_mod = max(last_mod, f.stat().st_mtime)
                except Exception:
                    pass
            characters.append({
                "name": char_dir.name,
                "limb_count": len(limb_files),
                "has_exploded_sheet": has_exploded,
                "has_full_preview": has_full,
                "full_preview_url": f"/sprites/{char_dir.name}/{char_dir.name}_full.png" if has_full else None,
                "has_godot_scene": scene_file.is_file(),
                "scene_path": f"res://scenes/{char_dir.name}_character.tscn" if scene_file.is_file() else None,
                "sprites_dir": f"res://sprites/{char_dir.name}",
                "last_modified_ts": last_mod,
                "limbs": [f.name for f in limb_files]
            })

    return json.dumps({
        "status": "success",
        "count": len(characters),
        "characters": characters
    }, indent=2)


# ==============================================================================
# MCP TOOL 7: delete_character
# ==============================================================================
@mcp.tool()
def delete_character(
    character_name: str,
    delete_scene: bool = True
) -> str:
    """
    Removes a character's sprite directory and optionally their Godot scene file.
    This is an irreversible operation.

    Args:
        character_name: Name of the character to delete (e.g. 'cyber_alien').
        delete_scene: If True, also deletes the scenes/<character>_character.tscn file.

    Returns:
        JSON string confirming deletion results.
    """
    clean_name = character_name.strip().lower().replace(" ", "_")
    result = {"character_name": clean_name, "deleted": []}

    sprites_dir = PROJECT_ROOT / "sprites" / clean_name
    if sprites_dir.is_dir():
        shutil.rmtree(sprites_dir, ignore_errors=True)
        result["deleted"].append(f"sprites/{clean_name}/")
        result["sprites_deleted"] = True
    else:
        result["sprites_deleted"] = False

    if delete_scene:
        scene_file = PROJECT_ROOT / "scenes" / f"{clean_name}_character.tscn"
        if scene_file.is_file():
            scene_file.unlink()
            result["deleted"].append(f"scenes/{clean_name}_character.tscn")
            result["scene_deleted"] = True
        else:
            result["scene_deleted"] = False

    result["status"] = "success" if result["deleted"] else "not_found"
    return json.dumps(result, indent=2)


# ==============================================================================
# MCP TOOL 8: get_character_info
# ==============================================================================
@mcp.tool()
def get_character_info(
    character_name: str
) -> str:
    """
    Returns detailed metadata for a specific generated character, including
    limb file listing, bone name mapping, Godot scene path, and file sizes.

    Args:
        character_name: Name of the character to inspect (e.g. 'cyber_alien').

    Returns:
        JSON string with full character metadata.
    """
    clean_name = character_name.strip().lower().replace(" ", "_")
    sprites_dir = PROJECT_ROOT / "sprites" / clean_name
    scene_file  = PROJECT_ROOT / "scenes" / f"{clean_name}_character.tscn"

    if not sprites_dir.is_dir():
        return json.dumps({
            "status": "not_found",
            "character_name": clean_name,
            "message": f"No sprites directory found for '{clean_name}'. Generate sprites first."
        }, indent=2)

    limb_files = sorted(sprites_dir.glob("*.png"))
    limbs = []
    for f in limb_files:
        bone_name = f.stem
        if bone_name.startswith(clean_name + "_"):
            bone_name = bone_name[len(clean_name) + 1:]
        try:
            img = Image.open(f)
            width, height = img.size
            size_bytes = f.stat().st_size
        except Exception:
            width = height = 0
            size_bytes = f.stat().st_size if f.is_file() else 0
        limbs.append({
            "filename": f.name,
            "bone_name": bone_name,
            "width": width,
            "height": height,
            "size_bytes": size_bytes,
            "url": f"/sprites/{clean_name}/{f.name}"
        })

    is_exploded = any(l["bone_name"] == "exploded" for l in limbs)
    actual_limbs = [l for l in limbs if l["bone_name"] != "exploded"]

    full_preview = (sprites_dir / f"{clean_name}_full.png")
    if not full_preview.is_file():
        try:
            from scripts.generate_sample_sprites import create_character_assembled_preview
            create_character_assembled_preview(sprites_dir, prefix=clean_name)
        except Exception:
            pass

    return json.dumps({
        "status": "found",
        "character_name": clean_name,
        "sprites_dir": f"res://sprites/{clean_name}",
        "limb_count": len(actual_limbs),
        "has_exploded_sheet": is_exploded,
        "has_full_preview": full_preview.is_file(),
        "full_preview_url": f"/sprites/{clean_name}/{clean_name}_full.png" if full_preview.is_file() else None,
        "has_godot_scene": scene_file.is_file(),
        "scene_path": f"res://scenes/{clean_name}_character.tscn" if scene_file.is_file() else None,
        "limbs": actual_limbs
    }, indent=2)


# ==============================================================================
# MCP TOOL 9: queue_character_generation
# ==============================================================================
@mcp.tool()
def queue_character_generation(characters: List[Dict[str, Any]]) -> str:
    """Queues one or more characters for background generation and auto-rigging.

    Args:
        characters: List of character config dicts. Each dict can have:
                    - 'character_name' (str, required): e.g. 'shadow_ninja'
                    - 'concept' or 'archetype_prompt' (str): concept description
                    - 'seed' (int, optional): random seed (-1 for random)
                    - 'rig_type' (str, optional): 'biped' or 'quadruped'
                    - 'checkpoint' (str, optional): model checkpoint name
                    - 'art_style' (str, optional): 'anime', 'pixel_8bit', 'pixel_16bit', etc.
                    - 'detail_level' (int, optional): 1-5 (default 3)
                    - 'auto_rig' (bool, optional): whether to auto-rig into Godot (default True)

    Returns:
        JSON string with queue submission status and queued jobs.
    """
    if not isinstance(characters, list) or not characters:
        return json.dumps({"status": "error", "message": "Expected a non-empty list of character configs."}, indent=2)

    created = add_to_queue(characters)
    return json.dumps({
        "status": "queued",
        "queued_count": len(created),
        "jobs": created
    }, indent=2)


# ==============================================================================
# MCP TOOL 10: get_queue_status
# ==============================================================================
@mcp.tool()
def get_queue_status(job_id: str = "") -> str:
    """Returns the current status of all jobs or a specific job in the generation queue.

    Args:
        job_id: Optional specific job ID to query. If omitted, returns all jobs.

    Returns:
        JSON string with queue status, counts (pending, running, done, error, cancelled), and jobs list.
    """
    all_jobs = get_all_queue_jobs()
    if job_id:
        match = [j for j in all_jobs if j["id"] == job_id]
        if not match:
            return json.dumps({"status": "not_found", "job_id": job_id}, indent=2)
        return json.dumps({"status": "found", "job": match[0]}, indent=2)

    counts = {
        "pending": sum(1 for j in all_jobs if j["status"] == "pending"),
        "running": sum(1 for j in all_jobs if j["status"] == "running"),
        "done": sum(1 for j in all_jobs if j["status"] == "done"),
        "error": sum(1 for j in all_jobs if j["status"] == "error"),
        "cancelled": sum(1 for j in all_jobs if j["status"] == "cancelled"),
    }
    return json.dumps({
        "status": "ok",
        "total_jobs": len(all_jobs),
        "counts": counts,
        "jobs": all_jobs
    }, indent=2)


# ==============================================================================
# MCP TOOL 11: cancel_queue_job
# ==============================================================================
@mcp.tool()
def cancel_queue_job(job_id: str) -> str:
    """Cancels a pending or running job in the generation queue.

    Args:
        job_id: The ID of the job to cancel.

    Returns:
        JSON string indicating whether cancellation succeeded.
    """
    success = cancel_job(job_id)
    return json.dumps({
        "status": "cancelled" if success else "not_found_or_finished",
        "job_id": job_id,
        "success": success
    }, indent=2)


if __name__ == "__main__":
    # Start FastMCP server via standard I/O for MCP clients
    mcp.run()
