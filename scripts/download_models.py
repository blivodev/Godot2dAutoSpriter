#!/usr/bin/env python3
"""
download_models.py - Intelligent AI Model Downloader for Godot2dAutoSpriter

Automates downloading state-of-the-art anime & game-art AI model checkpoints,
ControlNets, LoRAs, and LayerDiffuse models for local generative diffusion in ComfyUI.

Features:
- Streamed chunk downloading with live percentage, speed (MB/s), and ETA
- HTTP Range resume support via .part files (avoids restarting interrupted downloads)
- Automatic path detection for ComfyUI Desktop, Portable, and standalone installs
- Python library API and CLI interface
- MCP server and Web UI integration

Supported Checkpoints:
  SDXL Models (require more VRAM, highest quality):
  - animagine_xl    : Animagine XL 3.1 (SDXL ~6.6 GB) - Premier anime character
  - pony_xl         : Pony Diffusion XL v6 (SDXL ~6.6 GB) - Expressive game character art
  - pixel_xl        : Pixel Art XL (SDXL fine-tuned, pixel sprite sheets)

  SD 1.5 Models (fast, ~2 GB, good for lower VRAM):
  - anything_v5     : AnythingV5 (SD 1.5 ~2 GB) - Ultra clean anime
  - counterfeit_v3  : Counterfeit V3.0 (SD 1.5 ~2 GB) - Classic anime
  - dreamshaper_8   : DreamShaper 8 (SD 1.5 ~2 GB) - Fantasy game art
  - toonyou         : ToonYou Beta 6 (SD 1.5 ~2 GB) - Cartoon / cel-shaded game
  - rpg_v5          : RPG v5 (SD 1.5 ~2 GB) - RPG concept character art
  - mix_pro_v4      : MIX-Pro v4 (SD 1.5 ~2 GB) - Hyper detailed anime/realism mix
  - waifu_diffusion : Waifu Diffusion 1.4 (SD 1.5 ~2 GB) - Foundational 2D anime

  Essential Add-ons:
  - layer_conv          : LayerDiffuse SDXL Conv Model (transparent RGBA)
  - vae_decoder         : LayerDiffuse VAE Decoder
  - controlnet_openpose : SDXL OpenPose ControlNet
  - flat_anime_lora     : Flat Cel-Shading SDXL LoRA
  - pixel_lora          : Pixel Art Style LoRA (SD 1.5)
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Optional, Callable, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODELS_CATALOG: Dict[str, dict] = {
    # =========================================================
    # SDXL Checkpoints (1024×1024, high quality, needs 8+ GB VRAM)
    # =========================================================
    "animagine_xl": {
        "filename": "animagineXL_v31.safetensors",
        "subfolder": "checkpoints",
        "url": "https://huggingface.co/cagliostrolab/animagine-xl-3.1/resolve/main/animagine-xl-3.1.safetensors",
        "size_mb": 6616.9,
        "type": "checkpoint",
        "base": "SDXL",
        "desc": "Animagine XL 3.1 — Premier SDXL anime character checkpoint (6.6 GB)",
        "tags": ["anime", "character", "sdxl"],
        "style_hint": "masterpiece, best quality, highres, anime character"
    },
    "pony_xl": {
        "filename": "ponyDiffusionV6XL_v6StartWithThisOne.safetensors",
        "subfolder": "checkpoints",
        "url": "https://huggingface.co/LyliaEngine/Pony_Diffusion_V6_XL/resolve/main/ponyDiffusionV6XL_v6StartWithThisOne.safetensors",
        "size_mb": 6460.0,
        "type": "checkpoint",
        "base": "SDXL",
        "desc": "Pony Diffusion XL v6 — Expressive stylized SDXL game character art (6.5 GB)",
        "tags": ["anime", "game-art", "sdxl", "stylized"],
        "style_hint": "score_9, score_8_up, score_7_up, source_anime, game character"
    },
    "pixel_xl": {
        "filename": "pixel-art-xl.safetensors",
        "subfolder": "checkpoints",
        "url": "https://huggingface.co/nerijs/pixel-art-xl/resolve/main/pixel-art-xl.safetensors",
        "size_mb": 6614.0,
        "type": "checkpoint",
        "base": "SDXL",
        "desc": "Pixel Art XL — SDXL fine-tuned for crisp pixel-art sprite sheets (6.6 GB)",
        "tags": ["pixel-art", "sprite", "sdxl", "retro"],
        "style_hint": "pixel art, 16-bit, sprite sheet, game sprite, crisp pixels, pixel character"
    },

    # =========================================================
    # SD 1.5 Checkpoints (~2 GB, runs on 4+ GB VRAM)
    # =========================================================
    "anything_v5": {
        "filename": "AnythingV5.safetensors",
        "subfolder": "checkpoints",
        "url": "https://huggingface.co/Yntec/AnythingV5/resolve/main/AnythingV5.safetensors",
        "size_mb": 1993.4,
        "type": "checkpoint",
        "base": "SD1.5",
        "desc": "AnythingV5 — Ultra clean, flat-color anime SD 1.5 (~2 GB)",
        "tags": ["anime", "flat-color", "sd15", "clean"],
        "style_hint": "masterpiece, best quality, anime, (2d game sprite), character design"
    },
    "counterfeit_v3": {
        "filename": "Counterfeit-V3.0_fp16.safetensors",
        "subfolder": "checkpoints",
        "url": "https://huggingface.co/gsdf/Counterfeit-V3.0/resolve/main/Counterfeit-V3.0_fp16.safetensors",
        "size_mb": 1993.4,
        "type": "checkpoint",
        "base": "SD1.5",
        "desc": "Counterfeit V3.0 — High quality classic anime SD 1.5 (~2 GB)",
        "tags": ["anime", "sd15", "classic"],
        "style_hint": "masterpiece, best quality, ultra-detailed, anime"
    },
    "dreamshaper_8": {
        "filename": "DreamShaper_8_pruned.safetensors",
        "subfolder": "checkpoints",
        "url": "https://huggingface.co/Lykon/DreamShaper/resolve/main/DreamShaper_8_pruned.safetensors",
        "size_mb": 1993.5,
        "type": "checkpoint",
        "base": "SD1.5",
        "desc": "DreamShaper 8 — Detailed fantasy & game concept character art (~2 GB)",
        "tags": ["fantasy", "game-art", "sd15", "detailed"],
        "style_hint": "masterpiece, highly detailed, fantasy game character design, concept art"
    },
    "toonyou": {
        "filename": "toonyou_alpha3.safetensors",
        "subfolder": "checkpoints",
        "url": "https://huggingface.co/ckpt/toonyou/resolve/main/toonyou_alpha3.safetensors",
        "size_mb": 1993.0,
        "type": "checkpoint",
        "base": "SD1.5",
        "desc": "ToonYou Alpha 3 — Bright cartoon / cel-shaded toon game character art (~2 GB)",
        "tags": ["cartoon", "toon", "cel-shading", "sd15", "bright"],
        "style_hint": "toon, cartoon, cel shading, colorful, clean line art, game character"
    },
    "rpg_v5": {
        "filename": "RPG_Remix.safetensors",
        "subfolder": "checkpoints",
        "url": "https://huggingface.co/Yntec/RPG_Remix/resolve/main/RPG_Remix.safetensors",
        "size_mb": 4067.6,
        "type": "checkpoint",
        "base": "SD1.5",
        "desc": "RPG Remix v5 — Rich RPG character concept sheet art (~4 GB)",
        "tags": ["rpg", "fantasy", "character", "sd15", "concept-art"],
        "style_hint": "RPG character art, concept sheet, detailed armor and costume, game character design"
    },
    "cuteyuki_v2": {
        "filename": "cuteyukimixAdorable_v20.safetensors",
        "subfolder": "checkpoints",
        "url": "https://huggingface.co/Yntec/CuteYuki2/resolve/main/cuteyukimixAdorable_v20.safetensors",
        "size_mb": 1993.0,
        "type": "checkpoint",
        "base": "SD1.5",
        "desc": "CuteYukiMix Adorable v2 — Polished anime character illustration fine-tune (~2 GB)",
        "tags": ["anime", "illustration", "sd15", "clean"],
        "style_hint": "masterpiece, ultra detailed, vibrant anime character art, game sprite"
    },
    "anything_v3": {
        "filename": "Anything-V3.0-non-ema-fp16.safetensors",
        "subfolder": "checkpoints",
        "url": "https://huggingface.co/swl-models/anything-v3.0/resolve/main/Anything-V3.0-non-ema-fp16.safetensors",
        "size_mb": 2080.0,
        "type": "checkpoint",
        "base": "SD1.5",
        "desc": "Anything V3.0 — Benchmark classic 2D anime character generation (~2 GB)",
        "tags": ["anime", "2d", "foundational", "sd15"],
        "style_hint": "anime, 2d illustration, high quality character design, anime sprite"
    },

    # =========================================================
    # Essential Add-on Models
    # =========================================================
    "layer_conv": {
        "filename": "layer_xl_transparent_conv.safetensors",
        "subfolder": "layer_model",
        "url": "https://huggingface.co/LayerDiffusion/layerdiffusion-v1/resolve/main/layer_xl_transparent_conv.safetensors",
        "size_mb": 3452.1,
        "type": "layer_model",
        "base": "SDXL",
        "desc": "LayerDiffuse SDXL Transparent RGBA Conv Model",
        "tags": ["transparent", "rgba", "layerdiffuse"],
        "style_hint": ""
    },
    "vae_decoder": {
        "filename": "vae_transparent_decoder.safetensors",
        "subfolder": "layer_model",
        "url": "https://huggingface.co/LayerDiffusion/layerdiffusion-v1/resolve/main/vae_transparent_decoder.safetensors",
        "size_mb": 198.6,
        "type": "layer_model",
        "base": "SDXL",
        "desc": "LayerDiffuse Transparent VAE Decoder",
        "tags": ["transparent", "vae", "layerdiffuse"],
        "style_hint": ""
    },
    "controlnet_openpose": {
        "filename": "thibaud_xl_openpose.safetensors",
        "subfolder": "controlnet",
        "url": "https://huggingface.co/xinsir/controlnet-openpose-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors",
        "size_mb": 2386.2,
        "type": "controlnet",
        "base": "SDXL",
        "desc": "SDXL OpenPose ControlNet — Pose-guided character generation",
        "tags": ["controlnet", "openpose", "pose-guidance"],
        "style_hint": ""
    },
    "flat_anime_lora": {
        "filename": "flat2DAnimerge_v10.safetensors",
        "subfolder": "loras",
        "url": "https://huggingface.co/Muapi/line-art-flat-colors-sdxl/resolve/main/line-art-flat-colors-sdxl.safetensors",
        "size_mb": 217.8,
        "type": "lora",
        "base": "SDXL",
        "desc": "Anime Flat-Color / Cel-Shading SDXL LoRA",
        "tags": ["lora", "flat-color", "cel-shading", "sdxl"],
        "style_hint": ""
    },
    "pixel_lora": {
        "filename": "PixelArtRedmond15V-PixelArt-PIXARFK.safetensors",
        "subfolder": "loras",
        "url": "https://huggingface.co/artificialguybr/pixelartredmond-1-5v-pixel-art-loras-for-sd-1-5/resolve/main/PixelArtRedmond15V-PixelArt-PIXARFK.safetensors",
        "size_mb": 26.0,
        "type": "lora",
        "base": "SD1.5",
        "desc": "PixelArt Redmond LoRA (SD 1.5) — Converts SD 1.5 models to pixel-art sprites (26 MB)",
        "tags": ["lora", "pixel-art", "sprite", "sd15"],
        "style_hint": "PixelArt, pixel art, 8-bit, 16-bit retro sprite, pixelated character"
    },
    "pixel_lora_xl": {
        "filename": "pixel-art-xl.safetensors",
        "subfolder": "loras",
        "url": "https://huggingface.co/nerijs/pixel-art-xl/resolve/main/pixel-art-xl.safetensors",
        "size_mb": 170.5,
        "type": "lora",
        "base": "SDXL",
        "desc": "Pixel Art XL LoRA (SDXL) — Converts SDXL models to crisp pixel-art sprites (170 MB)",
        "tags": ["lora", "pixel-art", "sprite", "sdxl"],
        "style_hint": "pixel art, 16-bit, sprite sheet, game sprite, crisp pixels, pixel character"
    },
}

# Grouped for UI display
MODEL_GROUPS = {
    "SDXL Checkpoints (High Quality, 8+ GB VRAM)": ["animagine_xl", "pony_xl"],
    "SD 1.5 Checkpoints (Fast, ~2 GB, 4+ GB VRAM)": ["anything_v5", "counterfeit_v3", "dreamshaper_8", "toonyou", "rpg_v5", "cuteyuki_v2", "anything_v3"],
    "Essential Add-ons & LoRAs": ["layer_conv", "vae_decoder", "controlnet_openpose", "flat_anime_lora", "pixel_lora", "pixel_lora_xl"],
}


def find_comfyui_models_directory() -> Path:
    """Finds the active ComfyUI models directory across common install types."""
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))

    # 1. ComfyUI Desktop Shared (preferred standard)
    desktop_shared = local_app_data / "Comfy-Desktop" / "ComfyUI-Shared" / "models"
    if desktop_shared.is_dir():
        return desktop_shared

    # 2. ComfyUI Desktop Installs
    desktop_install = local_app_data / "Comfy-Desktop" / "ComfyUI-Installs" / "ComfyUI" / "ComfyUI" / "models"
    if desktop_install.is_dir():
        return desktop_install

    # 3. Portable or local installs
    candidates = [
        Path("C:/ComfyUI_windows_portable/ComfyUI/models"),
        Path("D:/ComfyUI_windows_portable/ComfyUI/models"),
        Path(os.environ.get("USERPROFILE", "")) / "ComfyUI" / "models",
        Path("C:/ComfyUI/models"),
        Path("D:/ComfyUI/models"),
        PROJECT_ROOT / "models"
    ]
    for c in candidates:
        if c.is_dir():
            return c

    fallback = PROJECT_ROOT / "models"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def get_model_status(models_dir: Optional[Path] = None) -> Dict[str, dict]:
    """Returns a dictionary mapping model keys to their current installation status."""
    mdir = models_dir or find_comfyui_models_directory()
    status = {}
    for key, info in MODELS_CATALOG.items():
        target = mdir / info["subfolder"] / info["filename"]
        installed = target.is_file() and target.stat().st_size > 1024 * 1024
        size_mb = round(target.stat().st_size / (1024 * 1024), 1) if installed else 0.0

        part_file = target.with_suffix(target.suffix + ".part")
        partial = part_file.is_file() and part_file.stat().st_size > 0
        part_mb = round(part_file.stat().st_size / (1024 * 1024), 1) if partial else 0.0

        status[key] = {
            "key": key,
            "filename": info["filename"],
            "subfolder": info["subfolder"],
            "installed": installed,
            "partial": partial,
            "installed_size_mb": size_mb,
            "partial_size_mb": part_mb,
            "expected_size_mb": info["size_mb"],
            "desc": info["desc"],
            "base": info.get("base", ""),
            "tags": info.get("tags", []),
            "target_path": str(target)
        }
    return status


def download_model(
    model_key: str,
    models_dir: Optional[Path] = None,
    progress_callback: Optional[Callable[[float, float, float, float], None]] = None
) -> Tuple[bool, str]:
    """
    Downloads a model with HTTP Range resumption.

    Args:
        model_key: Key in MODELS_CATALOG (e.g. 'animagine_xl', 'anything_v5')
        models_dir: Destination models root folder (auto-detected if None)
        progress_callback: Optional fn(pct, downloaded_mb, total_mb, speed_mbps)

    Returns:
        (success: bool, message: str)
    """
    if model_key not in MODELS_CATALOG:
        return False, f"Unknown model key '{model_key}'. Available: {list(MODELS_CATALOG.keys())}"

    info = MODELS_CATALOG[model_key]
    mdir = models_dir or find_comfyui_models_directory()
    target_dir = mdir / info["subfolder"]
    target_dir.mkdir(parents=True, exist_ok=True)

    dest_path = target_dir / info["filename"]
    temp_path = dest_path.with_suffix(dest_path.suffix + ".part")

    # Already installed check
    if dest_path.is_file() and dest_path.stat().st_size > 1024 * 1024:
        mb = dest_path.stat().st_size / (1024 * 1024)
        return True, f"Model '{info['filename']}' already installed ({mb:.1f} MB) at {dest_path}"

    existing_bytes = temp_path.stat().st_size if temp_path.is_file() else 0
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    if existing_bytes > 0:
        headers["Range"] = f"bytes={existing_bytes}-"

    req = urllib.request.Request(info["url"], headers=headers)
    print(f"\n[ModelDownloader] Connecting: {info['desc']}")
    print(f"  Target: {dest_path}")
    if existing_bytes > 0:
        print(f"  Resuming from byte offset: {existing_bytes / (1024*1024):.1f} MB")

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            content_len = resp.headers.get("Content-Length")
            if content_len:
                total_bytes = int(content_len) + (existing_bytes if resp.status == 206 else 0)
            else:
                total_bytes = int(info["size_mb"] * 1024 * 1024)

            mode = "ab" if existing_bytes > 0 and resp.status == 206 else "wb"
            downloaded = existing_bytes if mode == "ab" else 0

            start_time = time.time()
            last_report_time = start_time
            bytes_since_report = 0

            with open(temp_path, mode) as f:
                block_size = 1024 * 1024  # 1 MB chunk
                while True:
                    chunk = resp.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    bytes_since_report += len(chunk)

                    now = time.time()
                    elapsed_report = now - last_report_time
                    if elapsed_report >= 0.5:
                        speed_mbps = (bytes_since_report / (1024 * 1024)) / elapsed_report
                        pct = (downloaded / total_bytes) * 100.0 if total_bytes > 0 else 0.0
                        mb_done = downloaded / (1024 * 1024)
                        mb_tot = total_bytes / (1024 * 1024)

                        sys.stdout.write(f"\r  Progress: {pct:5.1f}% ({mb_done:.1f}/{mb_tot:.1f} MB) @ {speed_mbps:.1f} MB/s  ")
                        sys.stdout.flush()

                        if progress_callback:
                            progress_callback(pct, mb_done, mb_tot, speed_mbps)

                        last_report_time = now
                        bytes_since_report = 0

            print()

        if temp_path.is_file():
            if dest_path.is_file():
                dest_path.unlink()
            temp_path.rename(dest_path)
            return True, f"Successfully downloaded and verified '{info['filename']}' ({info['size_mb']:.1f} MB)"

    except urllib.error.HTTPError as e:
        if e.code == 416 and temp_path.is_file():
            temp_path.unlink(missing_ok=True)
            return download_model(model_key, models_dir=models_dir, progress_callback=progress_callback)
        return False, f"Download failed for '{info['filename']}': {str(e)}"
    except Exception as e:
        return False, f"Download failed for '{info['filename']}': {str(e)}"

    return False, "Unknown download failure."


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Godot2dAutoSpriter Model Downloader")
    parser.add_argument("--model", choices=list(MODELS_CATALOG.keys()) + ["all_checkpoints", "all_sd15"], help="Model key to download")
    parser.add_argument("--status", action="store_true", help="Print model installation status table")
    parser.add_argument("--models-dir", default="", help="Custom models directory path")
    args = parser.parse_args()

    mdir = Path(args.models_dir).resolve() if args.models_dir else find_comfyui_models_directory()

    if args.status or not args.model:
        st = get_model_status(mdir)
        print("\n" + "=" * 72)
        print(f"AI Diffusion Models Status (Path: {mdir})")
        print("=" * 72)
        for group, keys in MODEL_GROUPS.items():
            print(f"\n  {group}:")
            for k in keys:
                if k in st:
                    v = st[k]
                    flag = "[INSTALLED]" if v["installed"] else ("[PARTIAL]" if v["partial"] else "[MISSING ]")
                    size = f"{v['installed_size_mb']} MB" if v["installed"] else f"~{v['expected_size_mb']:.0f} MB"
                    print(f"    {flag:12} {k:20} ({size:10}) {v['desc'][:55]}")
        print("=" * 72)
        if not args.model:
            print("\nUsage: python scripts/download_models.py --model <key>")
            print("Available keys:", list(MODELS_CATALOG.keys()))
            return

    if args.model:
        if args.model == "all_checkpoints":
            targets = ["animagine_xl", "pony_xl", "anything_v5"]
        elif args.model == "all_sd15":
            targets = ["anything_v5", "counterfeit_v3", "dreamshaper_8", "toonyou", "rpg_v5", "mix_pro_v4"]
        else:
            targets = [args.model]
        for t in targets:
            ok, msg = download_model(t, models_dir=mdir)
            print(f"\nResult: {'SUCCESS' if ok else 'FAILED'} - {msg}")


if __name__ == "__main__":
    main()
