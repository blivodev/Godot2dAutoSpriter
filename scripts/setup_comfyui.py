#!/usr/bin/env python3
"""
setup_comfyui.py - Automated ComfyUI Environment & Model Installer

Automates the complete installation and configuration of:
1. Required Custom Node Packs:
   - ComfyUI-layerdiffuse (LayeredDiffusion alpha channel injection)
   - ComfyUI_IPAdapter_plus (Image-to-image conditioning bridge)
   - comfyui_controlnet_aux (OpenPose and skeletal preprocessors)
2. Input Template Assets:
   - exploded_openpose_template.png (Biped exploded control sheet)
   - exploded_quadruped_openpose_template.png (Quadruped exploded control sheet)
3. Essential AI Models & Weights:
   - ControlNet SDXL OpenPose (xinsir / thibaud)
   - Anime Flat-Color / Cel-Shading LoRA
   - LayerDiffusion SDXL Alpha Model & Transparent VAE Decoder
   - SDXL Anime Base Checkpoint (Animagine XL 3.1)

Usage:
  python scripts/setup_comfyui.py --all            # Install nodes, inputs, and models
  python scripts/setup_comfyui.py --nodes          # Install custom node packs and dependencies
  python scripts/setup_comfyui.py --inputs         # Install exploded OpenPose template images
  python scripts/setup_comfyui.py --models         # Download missing model weights
  python scripts/setup_comfyui.py --check          # Check installation status
"""

import os
import sys
import json
import shutil
import urllib.request
import urllib.error
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUTS_SOURCE = PROJECT_ROOT / "workflows" / "inputs"

NODE_REPOSITORIES = {
    "comfyui-layerdiffuse": "https://github.com/huchenlei/ComfyUI-layerdiffuse.git",
    "ComfyUI_IPAdapter_plus": "https://github.com/cubiq/ComfyUI_IPAdapter_plus.git",
    "comfyui_controlnet_aux": "https://github.com/Fannovel16/comfyui_controlnet_aux.git",
}

# Reliable, publicly accessible HuggingFace direct download URLs
MODEL_MANIFEST = {
    "layer_model/vae_transparent_decoder.safetensors": {
        "url": "https://huggingface.co/LayerDiffusion/layerdiffusion-v1/resolve/main/vae_transparent_decoder.safetensors",
        "size_mb": 198.6,
        "category": "essential",
        "desc": "LayerDiffuse Transparent VAE Decoder"
    },
    "layer_model/layer_xl_transparent_conv.safetensors": {
        "url": "https://huggingface.co/LayerDiffusion/layerdiffusion-v1/resolve/main/layer_xl_transparent_conv.safetensors",
        "size_mb": 3452.1,
        "category": "essential",
        "desc": "LayerDiffuse SDXL Transparent Conv Model"
    },
    "controlnet/thibaud_xl_openpose.safetensors": {
        "url": "https://huggingface.co/xinsir/controlnet-openpose-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors",
        "size_mb": 2386.2,
        "category": "essential",
        "desc": "SDXL OpenPose ControlNet (Xinsir/Thibaud)"
    },
    "loras/flat2DAnimerge_v10.safetensors": {
        "url": "https://huggingface.co/Muapi/line-art-flat-colors-sdxl/resolve/main/line-art-flat-colors-sdxl.safetensors",
        "size_mb": 217.8,
        "category": "essential",
        "desc": "Anime Cel-Shading & Flat-Color SDXL LoRA"
    },
    "checkpoints/animagineXL_v31.safetensors": {
        "url": "https://huggingface.co/cagliostrolab/animagine-xl-3.1/resolve/main/animagine-xl-3.1.safetensors",
        "size_mb": 6616.9,
        "category": "checkpoint",
        "desc": "Animagine XL 3.1 SDXL Anime Master Checkpoint"
    }
}


def find_comfyui_paths(explicit_dir: str = "") -> Tuple[Optional[Path], Optional[Path], Optional[Path], Optional[Path]]:
    """
    Detects ComfyUI core path, custom_nodes, models directory, and python executable.
    Returns: (comfy_root, custom_nodes_dir, models_dir, python_bin)
    """
    if explicit_dir and os.path.isdir(explicit_dir):
        root = Path(explicit_dir).resolve()
        cn = root / "custom_nodes"
        models = root / "models"
        py = root / ".venv" / "Scripts" / "python.exe"
        if not py.is_file():
            py = root.parent / "python_embeded" / "python.exe"
        return root, cn, models, py if py.is_file() else None

    # Check Comfy Desktop
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    desktop_comfy = local_app_data / "Comfy-Desktop" / "ComfyUI-Installs" / "ComfyUI" / "ComfyUI"
    desktop_models = local_app_data / "Comfy-Desktop" / "ComfyUI-Shared" / "models"
    desktop_inputs = local_app_data / "Comfy-Desktop" / "ComfyUI-Shared" / "input"
    desktop_py = desktop_comfy / ".venv" / "Scripts" / "python.exe"

    if desktop_comfy.is_dir():
        cn = desktop_comfy / "custom_nodes"
        models = desktop_models if desktop_models.is_dir() else desktop_comfy / "models"
        return desktop_comfy, cn, models, desktop_py if desktop_py.is_file() else None

    # Check portable locations
    candidates = [
        Path("C:/ComfyUI_windows_portable/ComfyUI"),
        Path("D:/ComfyUI_windows_portable/ComfyUI"),
        Path(os.environ.get("USERPROFILE", "")) / "ComfyUI",
        Path("C:/ComfyUI"),
        Path("D:/ComfyUI")
    ]
    for c in candidates:
        if c.is_dir():
            cn = c / "custom_nodes"
            models = c / "models"
            py = c.parent / "python_embeded" / "python.exe"
            return c, cn, models, py if py.is_file() else None

    return None, None, None, None


def download_file(url: str, dest_path: Path, expected_mb: float = 0.0) -> bool:
    """Downloads a file with resumption support and progress reporting."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(dest_path.suffix + ".part")

    existing_bytes = temp_path.stat().st_size if temp_path.is_file() else 0
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    if existing_bytes > 0:
        headers["Range"] = f"bytes={existing_bytes}-"

    req = urllib.request.Request(url, headers=headers)
    print(f"\n[Downloading] {dest_path.name} ({expected_mb:.1f} MB)")
    print(f"  Source: {url}")
    print(f"  Target: {dest_path}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            total_bytes = resp.headers.get("Content-Length")
            total_bytes = int(total_bytes) + existing_bytes if total_bytes else 0

            mode = "ab" if existing_bytes > 0 and resp.status == 206 else "wb"
            downloaded = existing_bytes if mode == "ab" else 0

            with open(temp_path, mode) as f:
                block_size = 1024 * 1024  # 1 MB blocks
                while True:
                    chunk = resp.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_bytes > 0:
                        pct = (downloaded / total_bytes) * 100
                        mb_done = downloaded / (1024 * 1024)
                        mb_tot = total_bytes / (1024 * 1024)
                        sys.stdout.write(f"\r  Progress: {pct:5.1f}% ({mb_done:.1f}/{mb_tot:.1f} MB)")
                        sys.stdout.flush()
                    else:
                        mb_done = downloaded / (1024 * 1024)
                        sys.stdout.write(f"\r  Downloaded: {mb_done:.1f} MB")
                        sys.stdout.flush()
            print()

        if temp_path.is_file():
            if dest_path.is_file():
                dest_path.unlink()
            temp_path.rename(dest_path)
            print(f"  [OK] Saved: {dest_path.name}")
            return True
    except Exception as e:
        print(f"\n  [ERROR] Download failed: {e}")
        return False
    return False


def install_custom_nodes(custom_nodes_dir: Path, python_bin: Optional[Path]) -> bool:
    """Clones missing custom node repositories and installs pip requirements."""
    if not custom_nodes_dir or not custom_nodes_dir.is_dir():
        print("[ERROR] Custom nodes directory not found.")
        return False

    print("\n========================================================")
    print("1. Installing Required ComfyUI Custom Node Packs")
    print("========================================================")

    for name, git_url in NODE_REPOSITORIES.items():
        dest = custom_nodes_dir / name
        if dest.is_dir():
            print(f"  [FOUND] {name} is already installed.")
            continue

        print(f"  [CLONING] {name} from {git_url}...")
        try:
            res = subprocess.run(["git", "clone", git_url, str(dest)], capture_output=True, text=True, timeout=120)
            if res.returncode == 0:
                print(f"  [OK] Successfully cloned {name}")
            else:
                print(f"  [WARN] Git clone error for {name}: {res.stderr.strip()}")
        except Exception as e:
            print(f"  [ERROR] Failed to clone {name}: {e}")

        # Install requirements.txt if present
        req_file = dest / "requirements.txt"
        if req_file.is_file() and python_bin and python_bin.is_file():
            print(f"  [PIP] Installing dependencies for {name}...")
            try:
                subprocess.run(
                    [str(python_bin), "-m", "pip", "install", "-r", str(req_file), "--no-deps"],
                    capture_output=True, text=True, timeout=90
                )
                print(f"  [OK] Pip dependencies configured for {name}.")
            except Exception as e:
                print(f"  [WARN] Pip install error: {e}")

    return True


def install_inputs(comfy_root: Optional[Path]) -> bool:
    """Generates and copies input template images into ComfyUI input folder."""
    print("\n========================================================")
    print("2. Installing OpenPose Template Input Images")
    print("========================================================")

    # 1. Ensure source templates exist in repo
    gen_script = PROJECT_ROOT / "scripts" / "generate_openpose_templates.py"
    if gen_script.is_file():
        try:
            subprocess.run([sys.executable, str(gen_script)], check=True, capture_output=True, text=True)
        except Exception as e:
            print(f"  [WARN] Template generator note: {e}")

    # 2. Target ComfyUI input locations
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    target_dirs = []

    desktop_shared_input = local_app_data / "Comfy-Desktop" / "ComfyUI-Shared" / "input"
    if desktop_shared_input.is_dir():
        target_dirs.append(desktop_shared_input)

    if comfy_root and (comfy_root / "input").is_dir():
        target_dirs.append(comfy_root / "input")

    copied_count = 0
    if INPUTS_SOURCE.is_dir():
        for src in INPUTS_SOURCE.glob("*.png"):
            for tdir in target_dirs:
                dest = tdir / src.name
                shutil.copy2(src, dest)
                print(f"  [COPIED] {src.name} -> {tdir}")
                copied_count += 1

    print(f"  [OK] Installed {copied_count} input control templates.")
    return True


def install_models(models_dir: Path, include_checkpoint: bool = True) -> bool:
    """Downloads missing models into the ComfyUI models hierarchy."""
    if not models_dir or not models_dir.is_dir():
        print("[ERROR] Models directory not found.")
        return False

    print("\n========================================================")
    print("3. Checking & Downloading Model Weights")
    print("========================================================")

    for rel_path, info in MODEL_MANIFEST.items():
        if not include_checkpoint and info["category"] == "checkpoint":
            print(f"  [SKIPPED] {info['desc']} (large checkpoint; pass --checkpoint to download)")
            continue

        dest = models_dir / rel_path
        if dest.is_file() and dest.stat().st_size > 1024 * 1024:
            mb = dest.stat().st_size / (1024 * 1024)
            print(f"  [EXISTS] {dest.name} ({mb:.1f} MB) in {dest.parent.name}/")
            continue

        download_file(info["url"], dest, expected_mb=info["size_mb"])

    return True


def check_status():
    """Prints a diagnostic summary of ComfyUI components."""
    comfy_root, custom_nodes, models_dir, py_bin = find_comfyui_paths()

    print("\n========================================================")
    print("ComfyUI System Diagnostics")
    print("========================================================")
    print(f"ComfyUI Directory : {comfy_root if comfy_root else '[NOT DETECTED]'}")
    print(f"Custom Nodes Dir  : {custom_nodes if custom_nodes else '[NOT DETECTED]'}")
    print(f"Models Directory  : {models_dir if models_dir else '[NOT DETECTED]'}")
    print(f"Python Executable : {py_bin if py_bin else '[NOT DETECTED]'}")

    # Node packs
    print("\n--- Custom Node Packs ---")
    if custom_nodes and custom_nodes.is_dir():
        for pack in NODE_REPOSITORIES.keys():
            status = "[INSTALLED]" if (custom_nodes / pack).is_dir() else "[MISSING]"
            print(f"  {status} {pack}")
    else:
        print("  [ERROR] Custom nodes directory unavailable.")

    # Input templates
    print("\n--- Input Templates ---")
    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    input_dir = local_app_data / "Comfy-Desktop" / "ComfyUI-Shared" / "input"
    if not input_dir.is_dir() and comfy_root:
        input_dir = comfy_root / "input"

    templates = ["exploded_openpose_template.png", "exploded_quadruped_openpose_template.png"]
    for t in templates:
        f = input_dir / t if input_dir.is_dir() else None
        status = "[FOUND]" if f and f.is_file() else "[MISSING]"
        print(f"  {status} {t} in {input_dir}")

    # Model files
    print("\n--- Models & Weights ---")
    if models_dir and models_dir.is_dir():
        for rel_path, info in MODEL_MANIFEST.items():
            dest = models_dir / rel_path
            if dest.is_file():
                mb = dest.stat().st_size / (1024 * 1024)
                print(f"  [FOUND] {dest.name} ({mb:.1f} MB) - {info['desc']}")
            else:
                print(f"  [MISSING] {dest.name} (~{info['size_mb']:.1f} MB) - {info['desc']}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="ComfyUI Automated Dependency & Model Installer")
    parser.add_argument("--all", action="store_true", help="Install nodes, inputs, and essential models")
    parser.add_argument("--nodes", action="store_true", help="Clone custom node packs and install pip dependencies")
    parser.add_argument("--inputs", action="store_true", help="Copy exploded OpenPose templates to ComfyUI input folder")
    parser.add_argument("--models", action="store_true", help="Download essential models (ControlNet, LoRA, LayerDiffuse)")
    parser.add_argument("--checkpoint", action="store_true", help="Download large SDXL base checkpoint (6.6 GB)")
    parser.add_argument("--check", action="store_true", help="Check installation status")
    parser.add_argument("--comfy-dir", default="", help="Explicit ComfyUI root directory")
    args = parser.parse_args()

    comfy_root, custom_nodes, models_dir, py_bin = find_comfyui_paths(args.comfy_dir)

    if args.check:
        check_status()
        return

    if not any([args.all, args.nodes, args.inputs, args.models, args.checkpoint]):
        # Default behavior: run check and show help
        check_status()
        print("\nTo install components, run:")
        print("  python scripts/setup_comfyui.py --all           # Install nodes, inputs, and models")
        print("  python scripts/setup_comfyui.py --checkpoint    # Also download the 6.6GB SDXL checkpoint")
        return

    if args.all or args.nodes:
        if custom_nodes:
            install_custom_nodes(custom_nodes, py_bin)
        else:
            print("[ERROR] Could not locate custom_nodes directory.")

    if args.all or args.inputs:
        install_inputs(comfy_root)

    if args.all or args.models or args.checkpoint:
        if models_dir:
            install_models(models_dir, include_checkpoint=(args.checkpoint or (args.all and args.checkpoint)))
        else:
            print("[ERROR] Could not locate ComfyUI models directory.")


if __name__ == "__main__":
    main()
