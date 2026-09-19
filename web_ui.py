#!/usr/bin/env python3
"""
web_ui.py - Godot 2D Auto Spriter & Rigger Web Dashboard

A self-contained, browser-based graphical user interface for:
- Creating 2D humanoid and creature character rosters
- Presets: Cyber Alien, Elf Mage, Demon Fiend, Skeleton Lich, Dragonkin, Dire Beast, Mantis, Paladin, Heavy Mech
- Full "Custom" mode with interactive anatomy mix & match, appendages (wings/tail), and color pickers
- Triggering ComfyUI diffusion or procedural multi-species sprite generation
- Auto-assembling Godot 4 Skeleton2D character scenes (.tscn)
- 1-click launching directly into the active 2D Godot 4 editor viewport
- Asset Library tab for browsing all generated characters and inspecting limb sprites

Can be run via:
  python web_ui.py
  launch_ui.bat
  dist/Godot2dAutoSpriterUI.exe
"""

import os
import sys
import json
import time
import shutil
import urllib.request
import urllib.error
import urllib.parse
import subprocess
import webbrowser
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from server import get_project_root, PROJECT_ROOT
HOST = "127.0.0.1"
PORT = 8080

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def _find_godot_executable() -> str:
    from server import _find_godot_executable as s_find
    return s_find()

def _find_godot_editor_executable() -> str:
    from server import _find_godot_editor_executable as s_find
    return s_find()

def _check_comfyui_status() -> dict:
    comfy_url = "http://127.0.0.1:8188/object_info"
    from scripts.download_models import find_comfyui_models_directory
    mdir = find_comfyui_models_directory()
    disk_ckpts = []
    if mdir:
        ckpt_dir = mdir / "checkpoints"
        if ckpt_dir.is_dir():
            for f in ckpt_dir.glob("*.safetensors"):
                disk_ckpts.append(f.name)
            for f in ckpt_dir.glob("*.ckpt"):
                disk_ckpts.append(f.name)

    try:
        req = urllib.request.Request(comfy_url)
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ckpts = data.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
            all_ckpts = sorted(list(set(ckpts + disk_ckpts)))
            return {
                "online": True,
                "node_count": len(data),
                "has_layerdiffuse": "LayeredDiffusionApply" in data,
                "has_controlnet": "ControlNetLoader" in data,
                "checkpoints": all_ckpts,
                "has_checkpoint": len(all_ckpts) > 0
            }
    except Exception:
        return {
            "online": False,
            "node_count": 0,
            "has_layerdiffuse": False,
            "has_controlnet": False,
            "checkpoints": disk_ckpts,
            "has_checkpoint": len(disk_ckpts) > 0
        }


_DOWNLOAD_STATE = {
    "active": False,
    "model": "",
    "pct": 0.0,
    "downloaded_mb": 0.0,
    "total_mb": 0.0,
    "speed_mbps": 0.0,
    "status": "idle",
    "message": ""
}

def _bg_download(model_key: str):
    global _DOWNLOAD_STATE
    _DOWNLOAD_STATE["active"] = True
    _DOWNLOAD_STATE["model"] = model_key
    _DOWNLOAD_STATE["pct"] = 0.0
    _DOWNLOAD_STATE["downloaded_mb"] = 0.0
    _DOWNLOAD_STATE["total_mb"] = 0.0
    _DOWNLOAD_STATE["speed_mbps"] = 0.0
    _DOWNLOAD_STATE["status"] = "downloading"
    _DOWNLOAD_STATE["message"] = f"Downloading {model_key}..."

    def cb(pct, mb_done, mb_tot, speed):
        _DOWNLOAD_STATE["pct"] = round(pct, 1)
        _DOWNLOAD_STATE["downloaded_mb"] = round(mb_done, 1)
        _DOWNLOAD_STATE["total_mb"] = round(mb_tot, 1)
        _DOWNLOAD_STATE["speed_mbps"] = round(speed, 1)

    try:
        from scripts.download_models import download_model
        ok, msg = download_model(model_key, progress_callback=cb)
        _DOWNLOAD_STATE["active"] = False
        _DOWNLOAD_STATE["status"] = "complete" if ok else "error"
        _DOWNLOAD_STATE["message"] = msg
    except Exception as e:
        _DOWNLOAD_STATE["active"] = False
        _DOWNLOAD_STATE["status"] = "error"
        _DOWNLOAD_STATE["message"] = str(e)


class AutoSpriterHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Silence default server access spam

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            return

        elif path == "/api/status":
            godot_exe = _find_godot_editor_executable() or _find_godot_executable()
            comfy_info = _check_comfyui_status()
            res = {
                "godot_available": bool(godot_exe and os.path.isfile(godot_exe)),
                "godot_bin": godot_exe or "Not Found",
                "comfyui": comfy_info,
                "project_root": str(PROJECT_ROOT)
            }
            self._send_json(res)
            return

        elif path == "/api/models/status":
            from scripts.download_models import get_model_status, find_comfyui_models_directory
            mdir = find_comfyui_models_directory()
            self._send_json({"models_dir": str(mdir), "catalog": get_model_status(mdir), "download_state": _DOWNLOAD_STATE})
            return

        elif path == "/api/models/progress":
            self._send_json(_DOWNLOAD_STATE)
            return

        elif path == "/api/sprites":
            qs = urllib.parse.parse_qs(parsed.query)
            char_name = qs.get("char", [""])[0].strip().lower().replace(" ", "_")
            if not char_name:
                char_name = "cyber_alien"

            sprites_dir = PROJECT_ROOT / "sprites" / char_name
            files = []
            if sprites_dir.is_dir():
                for p in sorted(sprites_dir.glob("*.png")):
                    bone = p.stem[len(char_name)+1:] if p.stem.startswith(char_name + "_") else p.stem
                    try:
                        from PIL import Image as PILImage
                        img = PILImage.open(p)
                        pw, ph = img.size
                    except Exception:
                        pw, ph = 0, 0
                    files.append({
                        "name": p.name,
                        "bone": bone,
                        "url": f"/sprites/{char_name}/{p.name}",
                        "size_bytes": p.stat().st_size,
                        "width": pw,
                        "height": ph
                    })
            self._send_json({"character": char_name, "count": len(files), "sprites": files})
            return

        elif path == "/api/characters":
            # List all generated characters
            import server as srv
            result_str = srv.list_generated_characters()
            self._send_json(json.loads(result_str))
            return

        elif path == "/api/queue/status":
            import server as srv
            result_str = srv.get_queue_status()
            self._send_json(json.loads(result_str))
            return

        elif path.startswith("/sprites/"):
            rel = urllib.parse.unquote(path[len("/sprites/"):])
            file_path = PROJECT_ROOT / "sprites" / rel

            # If requesting full preview and not yet on disk, generate on the fly
            if not file_path.is_file() and rel.endswith("_full.png"):
                parts = rel.split("/")
                if len(parts) >= 2:
                    char_name = parts[0]
                    char_dir = PROJECT_ROOT / "sprites" / char_name
                    if char_dir.is_dir():
                        try:
                            from scripts.generate_sample_sprites import create_character_assembled_preview
                            create_character_assembled_preview(char_dir, prefix=char_name)
                        except Exception:
                            pass

            if file_path.is_file() and str(file_path.resolve()).startswith(str((PROJECT_ROOT / "sprites").resolve())):
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_response(404)
                self.end_headers()
                return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(length)
        payload = {}
        if post_data:
            try:
                payload = json.loads(post_data.decode("utf-8"))
            except Exception:
                pass

        if path == "/api/generate":
            result = self._handle_generate(payload)
            self._send_json(result)
            return

        elif path == "/api/queue/add":
            import server as srv
            items = payload.get("characters") or ([payload] if payload.get("character_name") else [])
            created = srv.add_to_queue(items)
            self._send_json({"status": "ok", "queued": len(created), "jobs": created})
            return

        elif path == "/api/queue/cancel":
            import server as srv
            job_id = payload.get("job_id", "")
            success = srv.cancel_job(job_id)
            self._send_json({"status": "ok", "cancelled": success, "job_id": job_id})
            return

        elif path == "/api/queue/clear":
            import server as srv
            cleared = srv.clear_completed_queue_jobs()
            self._send_json({"status": "ok", "cleared": cleared})
            return

        elif path == "/api/assemble":
            result = self._handle_assemble(payload)
            self._send_json(result)
            return

        elif path == "/api/comfy_setup":
            from scripts.setup_comfyui import check_status, install_custom_nodes, install_inputs, find_comfyui_paths
            action = payload.get("action", "check")
            comfy_root, custom_nodes, models_dir, py_bin = find_comfyui_paths()

            if action == "install_nodes" and custom_nodes:
                install_custom_nodes(custom_nodes, py_bin)
            elif action == "install_inputs":
                install_inputs(comfy_root)

            res = {
                "comfy_detected": comfy_root is not None,
                "custom_nodes": str(custom_nodes) if custom_nodes else None,
                "models_dir": str(models_dir) if models_dir else None
            }
            self._send_json(res)
            return

        elif path == "/api/models/download":
            model_key = payload.get("model", "counterfeit_v3")
            if _DOWNLOAD_STATE["active"]:
                self._send_json({"status": "in_progress", "message": f"Already downloading {_DOWNLOAD_STATE['model']}"})
                return
            t = threading.Thread(target=_bg_download, args=(model_key,), daemon=True)
            t.start()
            self._send_json({"status": "started", "model": model_key})
            return

        elif path == "/api/open_folder":
            char_name = payload.get("character", "cyber_alien").strip().lower().replace(" ", "_")
            folder = PROJECT_ROOT / "sprites" / char_name
            if folder.is_dir():
                os.startfile(str(folder))
                self._send_json({"status": "opened", "path": str(folder)})
            else:
                self._send_json({"status": "not_found", "path": str(folder)}, 404)
            return

        elif path == "/api/open_godot":
            scene_path = payload.get("scene", "").strip()
            char_name = payload.get("character", "").strip().lower().replace(" ", "_")
            godot_exe = _find_godot_editor_executable()

            if not godot_exe or not os.path.isfile(godot_exe):
                self._send_json({"status": "error", "message": "Godot 4 executable was not found on your system."}, 404)
                return

            full_scene = None
            if scene_path:
                full_scene = PROJECT_ROOT / scene_path.replace("res://", "")
            elif char_name:
                full_scene = PROJECT_ROOT / "scenes" / f"{char_name}_character.tscn"

            # Auto-assemble if the scene file doesn't exist but sprites do
            if full_scene and not full_scene.is_file():
                if not char_name:
                    char_name = full_scene.stem.replace("_character", "").replace("_rigged", "")
                sprites_dir = PROJECT_ROOT / "sprites" / char_name
                if sprites_dir.is_dir() and any(sprites_dir.glob("*.png")):
                    import server
                    rig_type = "quadruped" if char_name in ("fenrir", "celestial_wolf") else "biped"
                    server.assemble_godot_rig(
                        character_name=char_name,
                        assets_dir=f"res://sprites/{char_name}",
                        target_scene_path=f"res://scenes/{full_scene.name}",
                        rig_type=rig_type
                    )

            if full_scene and full_scene.is_file():
                res_scene = f"res://scenes/{full_scene.name}"

                try:
                    (PROJECT_ROOT / ".godot").mkdir(parents=True, exist_ok=True)
                    with open(PROJECT_ROOT / ".godot" / "open_scene_request.txt", "w", encoding="utf-8") as f:
                        f.write(res_scene)
                    with open(PROJECT_ROOT / "open_scene_request.txt", "w", encoding="utf-8") as f:
                        f.write(res_scene)
                except Exception:
                    pass

                try:
                    meta_path = PROJECT_ROOT / ".godot" / "editor" / "project_metadata.cfg"
                    if meta_path.is_file():
                        content = meta_path.read_text(encoding="utf-8")
                        if "[editor_metadata]" in content:
                            content = content.replace("[editor_metadata]", f'[editor_metadata]\nopen_scenes=["{res_scene}"]\ncurrent_scene="{res_scene}"')
                        else:
                            content += f'\n[editor_metadata]\nopen_scenes=["{res_scene}"]\ncurrent_scene="{res_scene}"\n'
                        meta_path.write_text(content, encoding="utf-8")
                except Exception:
                    pass

                subprocess.Popen([godot_exe, "--path", str(PROJECT_ROOT), "-e", "--", "--open-scene", res_scene], cwd=str(PROJECT_ROOT))
                self._send_json({"status": "launched", "scene": str(full_scene), "message": f"Launched Godot 4 Editor — opening '{full_scene.name}'..."})
                return
            else:
                subprocess.Popen([godot_exe, "--path", str(PROJECT_ROOT), "-e"], cwd=str(PROJECT_ROOT))
                self._send_json({"status": "launched", "scene": "project", "message": "Opened Godot project in Godot 4 Editor."})
                return

        elif path == "/api/character/delete":
            char_name = payload.get("character_name", "").strip().lower().replace(" ", "_")
            if not char_name:
                self._send_json({"status": "error", "message": "character_name is required"}, 400)
                return
            import server as srv
            result_str = srv.delete_character(char_name, delete_scene=True)
            self._send_json(json.loads(result_str))
            return

        elif path == "/api/regenerate":
            char_name = payload.get("character_name", "").strip().lower().replace(" ", "_")
            if not char_name:
                self._send_json({"status": "error", "message": "character_name is required"}, 400)
                return
            # Re-run procedural generation
            import server as srv
            from scripts.generate_sample_sprites import generate_all
            sprites_dir = PROJECT_ROOT / "sprites" / char_name
            sprites_dir.mkdir(parents=True, exist_ok=True)
            try:
                parts = generate_all(str(sprites_dir), prefix=char_name)
                self._send_json({"status": "success", "character_name": char_name, "limb_count": len(parts or [])})
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)}, 500)
            return

        self.send_response(404)
        self.end_headers()

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/queue/clear":
            import server as srv
            cleared = srv.clear_completed_queue_jobs()
            self._send_json({"status": "ok", "cleared": cleared})
            return
        self.send_response(404)
        self.end_headers()

    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _handle_generate(self, payload: dict) -> dict:
        char_name = payload.get("character_name", "cyber_alien").strip().lower().replace(" ", "_")
        if not char_name:
            char_name = "cyber_alien"
        concept = payload.get("concept", "cyberpunk warrior alien with glowing neon crest, modular chitin armor, plasma blade")
        archetype = payload.get("archetype", "warrior")
        rig_type = payload.get("rig_type", "biped")
        species = payload.get("species", "auto")
        mode = payload.get("mode", "auto")
        seed = int(payload.get("seed", -1))
        auto_rig = payload.get("auto_rig", True)
        art_style = payload.get("art_style", "anime")
        detail_level = int(payload.get("detail_level", 3))

        custom_colors = payload.get("custom_colors")
        custom_features = payload.get("custom_features") or {}
        custom_features["detail_level"] = detail_level

        sprites_dir = PROJECT_ROOT / "sprites" / char_name
        sprites_dir.mkdir(parents=True, exist_ok=True)

        logs = []
        logs.append(f"[INIT] Creating character '{char_name}' (Archetype: {archetype.upper()}, Rig: {rig_type.upper()}, Style: {art_style.upper()}, Detail: {detail_level})")
        logs.append(f"[CONCEPT] \"{concept}\"")

        checkpoint = payload.get("checkpoint", "").strip() or "animagineXL_v31.safetensors"
        comfy_used = False

        if mode in ["auto", "comfyui"]:
            comfy_status = _check_comfyui_status()
            if comfy_status.get("online", False) and comfy_status.get("has_checkpoint", False):
                logs.append(f"[COMFYUI] Connected to host (127.0.0.1:8188). Dispatching diffusion workflow using model '{checkpoint}' ({art_style})...")
                try:
                    import server
                    gen_res_str = server.generate_character_sprites(
                        character_name=char_name,
                        archetype_prompt=concept,
                        seed=seed,
                        rig_type=rig_type,
                        checkpoint=checkpoint,
                        art_style=art_style,
                        detail_level=detail_level
                    )
                    gen_res = json.loads(gen_res_str)
                    source = gen_res.get("source", "")
                    logs.append(f"[COMFYUI] Status: {gen_res.get('status')} (Source: {source})")
                    comfy_used = (source == "comfyui_api")
                    if comfy_used:
                        limbs = gen_res.get("limbs_sliced", "?")
                        logs.append(f"[COMFYUI] Successfully sliced {limbs} diffusion limbs into: res://sprites/{char_name}")
                    else:
                        logs.append(f"[COMFYUI-WARN] {gen_res.get('note', 'Diffusion could not complete; fallback engaged.')}")
                except Exception as e:
                    logs.append(f"[COMFYUI-WARN] API error: {e}")
            elif comfy_status.get("online", False) and not comfy_status.get("has_checkpoint", False):
                logs.append(f"[COMFYUI-NOTICE] ComfyUI online but no checkpoint found. Using Smart Procedural Spriter...")
            elif mode == "comfyui":
                logs.append(f"[COMFYUI-ERROR] ComfyUI is offline on 127.0.0.1:8188. Start ComfyUI to use diffusion mode.")

        if not comfy_used:
            if mode == "comfyui":
                logs.append(f"[FALLBACK] Generating procedural sprites (ComfyUI diffusion unavailable).")
            from scripts.generate_sample_sprites import generate_all, generate_quadruped, detect_species
            detected_sp = species if (species and species not in ("auto", "custom")) else detect_species(concept, archetype)
            logs.append(f"[GENERATOR] Synthesizing {detected_sp.upper()} anatomy for '{char_name}' (Seed: {seed if seed >= 0 else 'Random'}, Style: {art_style})...")

            if rig_type.lower() == "quadruped":
                parts = generate_quadruped(str(sprites_dir), prefix=char_name, archetype=archetype, prompt=concept, seed=seed, art_style=art_style, detail_level=detail_level)
            else:
                parts = generate_all(
                    str(sprites_dir),
                    prefix=char_name,
                    archetype=archetype,
                    prompt=concept,
                    seed=seed,
                    custom_colors=custom_colors,
                    custom_features=custom_features,
                    art_style=art_style
                )
            parts = parts or []
            logs.append(f"[GENERATOR] Created {len(parts)} transparent limb cutouts in: res://sprites/{char_name}")

        # Ensure full assembled preview exists
        try:
            from scripts.generate_sample_sprites import create_character_assembled_preview
            create_character_assembled_preview(sprites_dir, prefix=char_name, rig_type=rig_type)
        except Exception as e:
            pass

        # Assemble Godot rig
        scene_path = f"res://scenes/{char_name}_character.tscn"
        godot_success = False
        if auto_rig:
            logs.append(f"[GODOT] Invoking headless builder for {rig_type} skeleton...")
            import server
            rig_res_str = server.assemble_godot_rig(
                character_name=char_name,
                assets_dir=f"res://sprites/{char_name}",
                target_scene_path=scene_path,
                rig_type=rig_type
            )
            try:
                rig_res = json.loads(rig_res_str)
                godot_success = (rig_res.get("status") == "success")
                if godot_success:
                    logs.append(f"[GODOT] Scene assembled and saved -> {scene_path}")
                else:
                    logs.append(f"[GODOT-ERROR] {rig_res.get('message', 'Rig build failed')}")
                    if rig_res.get("stderr"):
                        logs.append(f"  stderr: {rig_res.get('stderr')}")
            except Exception as e:
                logs.append(f"[GODOT-WARN] {e}")

        return {
            "status": "success",
            "character_name": char_name,
            "archetype": archetype,
            "rig_type": rig_type,
            "scene_path": scene_path,
            "sprites_dir": f"res://sprites/{char_name}",
            "godot_rigged": godot_success,
            "comfy_used": comfy_used,
            "logs": logs
        }

    def _handle_assemble(self, payload: dict) -> dict:
        char_name = payload.get("character_name", "warrior").strip().lower().replace(" ", "_")
        rig_type = payload.get("rig_type", "biped")
        scene_path = f"res://scenes/{char_name}_character.tscn"

        import server
        res_str = server.assemble_godot_rig(
            character_name=char_name,
            assets_dir=f"res://sprites/{char_name}",
            target_scene_path=scene_path,
            rig_type=rig_type
        )
        return json.loads(res_str)


# ==============================================================================
# Web Dashboard HTML
# ==============================================================================
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Godot 2D Auto Spriter & Rigger</title>
<style>
  :root {
    --bg-dark: #0b0d13;
    --bg-card: #151922;
    --bg-input: #0f1219;
    --border: #242c3d;
    --primary: #58a6ff;
    --primary-hover: #79b8ff;
    --accent: #2ea043;
    --accent-purple: #bc8cff;
    --accent-gold: #e3b341;
    --danger: #f85149;
    --text: #e6edf3;
    --text-muted: #8b949e;
    --console-bg: #07090e;
    --tab-active: #151922;
    --tab-inactive: #0f1219;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  body { background-color: var(--bg-dark); color: var(--text); padding: 20px; line-height: 1.5; }
  .container { max-width: 1280px; margin: 0 auto; }

  /* Header */
  header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 16px; border-bottom: 1px solid var(--border); margin-bottom: 18px; flex-wrap: wrap; gap: 12px; }
  .logo { display: flex; align-items: center; gap: 12px; }
  .logo-icon { width: 38px; height: 38px; background: linear-gradient(135deg, var(--primary), var(--accent-purple)); border-radius: 9px; display: flex; align-items: center; justify-content: center; font-weight: 800; color: white; font-size: 18px; flex-shrink: 0; }
  .logo-text h1 { font-size: 19px; font-weight: 700; letter-spacing: -0.5px; }
  .logo-text p { font-size: 11px; color: var(--text-muted); }

  /* Badges */
  .badges { display: flex; gap: 8px; flex-wrap: wrap; }
  .badge { padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 6px; border: 1px solid transparent; }
  .badge-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .badge-online { background: rgba(46,160,67,0.15); color: #3fb950; border-color: rgba(46,160,67,0.3); }
  .badge-online .badge-dot { background: #3fb950; box-shadow: 0 0 6px #3fb950; animation: pulse-green 2s infinite; }
  .badge-offline { background: rgba(248,81,73,0.15); color: #f85149; border-color: rgba(248,81,73,0.3); }
  .badge-offline .badge-dot { background: #f85149; }
  .badge-notice { background: rgba(210,153,34,0.15); color: #d29922; border-color: rgba(210,153,34,0.3); }
  .badge-notice .badge-dot { background: #d29922; }
  @keyframes pulse-green { 0%,100%{box-shadow:0 0 4px #3fb950;} 50%{box-shadow:0 0 10px #3fb950;} }

  /* Tab Navigation */
  .tab-nav { display: flex; gap: 2px; margin-bottom: 20px; border-bottom: 1px solid var(--border); }
  .tab-btn { padding: 9px 20px; background: var(--tab-inactive); border: 1px solid var(--border); border-bottom: none; border-radius: 8px 8px 0 0; color: var(--text-muted); font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s; display: flex; align-items: center; gap: 7px; }
  .tab-btn:hover { background: var(--bg-card); color: var(--text); }
  .tab-btn.active { background: var(--tab-active); color: var(--primary); border-color: var(--border); border-bottom: 1px solid var(--tab-active); position: relative; bottom: -1px; }
  .tab-content { display: none; }
  .tab-content.active { display: block; }

  /* Cards & Layout */
  .grid { display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 22px; }
  @media (max-width: 950px) { .grid { grid-template-columns: 1fr; } }
  .card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 18px 20px; }
  .card-title { font-size: 14px; font-weight: 600; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; color: var(--primary); }

  /* Form elements */
  .form-group { margin-bottom: 13px; }
  label { display: block; font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 5px; }
  input[type="text"], select, textarea { width: 100%; background: var(--bg-input); border: 1px solid var(--border); border-radius: 6px; padding: 9px 11px; color: var(--text); font-size: 13px; transition: border-color 0.2s; }
  input[type="text"]:focus, select:focus, textarea:focus { border-color: var(--primary); outline: none; box-shadow: 0 0 0 3px rgba(88,166,255,0.12); }
  textarea { resize: vertical; min-height: 72px; }
  .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .row-4 { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 8px; }

  /* Buttons */
  .btn { display: inline-flex; align-items: center; justify-content: center; gap: 7px; padding: 9px 15px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; transition: all 0.18s; white-space: nowrap; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none !important; }
  .btn-primary { background: linear-gradient(135deg, var(--primary), #4890e0); color: #07090e; width: 100%; font-size: 14px; padding: 12px; font-weight: 700; letter-spacing: 0.2px; }
  .btn-primary:hover:not(:disabled) { background: linear-gradient(135deg, var(--primary-hover), #58a6ff); transform: translateY(-1px); box-shadow: 0 4px 15px rgba(88,166,255,0.3); }
  .btn-secondary { background: #1c222e; border: 1px solid var(--border); color: var(--text); }
  .btn-secondary:hover:not(:disabled) { background: #232b3a; border-color: #8b949e; }
  .btn-danger { background: rgba(248,81,73,0.15); border: 1px solid rgba(248,81,73,0.35); color: var(--danger); }
  .btn-danger:hover:not(:disabled) { background: rgba(248,81,73,0.25); }
  .btn-sm { padding: 5px 11px; font-size: 11px; }
  .btn-icon { padding: 6px 10px; font-size: 12px; }
  .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; }

  /* Presets */
  .quick-presets { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 14px; }
  .preset-pill { font-size: 11px; padding: 5px 11px; border-radius: 14px; background: #191f2b; border: 1px solid var(--border); cursor: pointer; color: var(--text-muted); transition: all 0.15s; user-select: none; }
  .preset-pill:hover { border-color: var(--primary); color: var(--primary); transform: translateY(-1px); }
  .preset-pill.active { background: rgba(88,166,255,0.18); border-color: var(--primary); color: var(--primary); font-weight: 700; }
  .preset-custom { border-color: rgba(227,179,65,0.35); color: #f0c654; }
  .preset-custom:hover, .preset-custom.active { background: rgba(227,179,65,0.2); border-color: #f0c654; color: #ffd666; font-weight: 700; }

  /* Accordion */
  .accordion { border: 1px solid var(--border); border-radius: 8px; margin-top: 13px; overflow: hidden; }
  .accordion-header { background: #11141c; padding: 10px 14px; font-size: 12px; font-weight: 600; color: var(--text-muted); cursor: pointer; display: flex; justify-content: space-between; user-select: none; transition: color 0.15s; }
  .accordion-header:hover { color: var(--text); }
  .accordion-content { padding: 14px; background: var(--bg-card); display: none; }
  .accordion-content.open { display: block; }

  /* Console */
  .console { background: var(--console-bg); border: 1px solid var(--border); border-radius: 8px; padding: 12px; font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: 11.5px; color: #7ee787; height: 220px; overflow-y: auto; white-space: pre-wrap; line-height: 1.5; }
  .console .ci { color: #58a6ff; } /* comfyui */
  .console .gi { color: #a371f7; } /* godot */
  .console .ok { color: #3fb950; } /* success */
  .console .warn { color: #d29922; }
  .console .err { color: #f85149; }
  .console .gen { color: #79c0ff; } /* generator */
  .console-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
  .console-toolbar span { font-size: 12px; font-weight: 600; color: var(--primary); }

  /* Gallery */
  .gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(88px, 1fr)); gap: 8px; max-height: 240px; overflow-y: auto; padding: 2px; }
  .sprite-card { background: #10131b; border: 1px solid var(--border); border-radius: 6px; padding: 5px; text-align: center; cursor: pointer; transition: border-color 0.15s; }
  .sprite-card:hover { border-color: var(--primary); }
  .sprite-thumb { width: 100%; height: 68px; object-fit: contain; background: repeating-conic-gradient(#1a1f2c 0% 25%, #121620 0% 50%) 50% / 12px 12px; border-radius: 4px; }
  .sprite-name { font-size: 9.5px; color: var(--text-muted); margin-top: 3px; word-break: break-all; }

  /* Color pickers */
  .color-picker-box { display: flex; align-items: center; gap: 7px; background: var(--bg-input); padding: 5px 9px; border-radius: 6px; border: 1px solid var(--border); }
  .color-picker-box input[type="color"] { border: none; width: 26px; height: 26px; border-radius: 4px; background: transparent; cursor: pointer; padding: 0; }
  .color-picker-box span { font-size: 10.5px; color: var(--text-muted); font-weight: 600; }

  /* Progress bar */
  .progress-container { width: 100%; background: #07090e; border: 1px solid var(--border); border-radius: 5px; height: 14px; overflow: hidden; position: relative; margin-top: 7px; }
  .progress-bar { height: 100%; background: linear-gradient(90deg, var(--primary), #a371f7); width: 0%; transition: width 0.3s; }
  .progress-text { position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; font-size: 9.5px; font-weight: 700; color: #fff; text-shadow: 0 1px 2px rgba(0,0,0,0.8); }

  /* Spinner */
  @keyframes spin { to { transform: rotate(360deg); } }
  .spinner { width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spin 0.7s linear infinite; display: inline-block; flex-shrink: 0; }

  /* ==== ASSET LIBRARY TAB ==== */
  .library-layout { display: grid; grid-template-columns: 320px 1fr; gap: 20px; min-height: 600px; }
  @media (max-width: 900px) { .library-layout { grid-template-columns: 1fr; } }

  .char-roster { display: flex; flex-direction: column; gap: 8px; max-height: 620px; overflow-y: auto; padding-right: 4px; }
  .char-roster-item { background: #10131b; border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; cursor: pointer; transition: all 0.15s; display: flex; align-items: center; gap: 10px; }
  .char-roster-item:hover { border-color: var(--primary); background: #141822; }
  .char-roster-item.selected { border-color: var(--primary); background: rgba(88,166,255,0.08); }
  .char-roster-thumb { width: 48px; height: 48px; object-fit: contain; background: repeating-conic-gradient(#1a1f2c 0% 25%, #121620 0% 50%) 50% / 8px 8px; border-radius: 5px; flex-shrink: 0; }
  .char-roster-thumb-placeholder { width: 48px; height: 48px; background: #1a1f2c; border-radius: 5px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 20px; }
  .char-roster-info { flex: 1; min-width: 0; }
  .char-roster-name { font-size: 13px; font-weight: 600; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .char-roster-meta { font-size: 11px; color: var(--text-muted); margin-top: 2px; display: flex; gap: 8px; flex-wrap: wrap; }
  .lib-badge { font-size: 10px; padding: 2px 7px; border-radius: 10px; font-weight: 600; }
  .lib-badge-scene { background: rgba(46,160,67,0.2); color: #3fb950; border: 1px solid rgba(46,160,67,0.3); }
  .lib-badge-no-scene { background: rgba(210,153,34,0.15); color: #d29922; border: 1px solid rgba(210,153,34,0.3); }

  /* Viewer */
  .viewer-panel { display: flex; flex-direction: column; gap: 14px; }
  .viewer-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
  .viewer-title { font-size: 16px; font-weight: 700; color: var(--text); }
  .viewer-actions { display: flex; gap: 8px; flex-wrap: wrap; }
  .viewer-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 10px; max-height: 480px; overflow-y: auto; padding: 2px; }
  .viewer-sprite-card { background: #10131b; border: 1px solid var(--border); border-radius: 8px; padding: 8px; text-align: center; cursor: pointer; transition: all 0.15s; }
  .viewer-sprite-card:hover { border-color: var(--primary); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(88,166,255,0.2); }
  .viewer-sprite-img { width: 100%; height: 90px; object-fit: contain; background: repeating-conic-gradient(#1a1f2c 0% 25%, #121620 0% 50%) 50% / 12px 12px; border-radius: 5px; }
  .viewer-sprite-name { font-size: 10px; color: var(--text-muted); margin-top: 5px; font-weight: 500; }
  .viewer-sprite-size { font-size: 9px; color: #4a5568; }
  .viewer-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 300px; color: var(--text-muted); gap: 10px; font-size: 13px; }
  .viewer-empty-icon { font-size: 42px; opacity: 0.5; }

  /* Library filters */
  .lib-toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
  .lib-search { flex: 1; min-width: 120px; background: var(--bg-input); border: 1px solid var(--border); border-radius: 6px; padding: 7px 11px; color: var(--text); font-size: 12px; }
  .lib-search:focus { border-color: var(--primary); outline: none; }

  /* Lightbox */
  .lightbox { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.88); z-index: 9999; align-items: center; justify-content: center; flex-direction: column; gap: 16px; padding: 20px; }
  .lightbox.open { display: flex; }
  .lightbox-img-wrap { background: repeating-conic-gradient(#1a1f2c 0% 25%, #121620 0% 50%) 50% / 16px 16px; border-radius: 10px; padding: 20px; display: flex; align-items: center; justify-content: center; max-width: 80vw; max-height: 70vh; }
  .lightbox-img { max-width: 100%; max-height: 65vh; object-fit: contain; border-radius: 4px; }
  .lightbox-meta { color: var(--text); text-align: center; }
  .lightbox-meta h3 { font-size: 16px; font-weight: 700; }
  .lightbox-meta p { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
  .lightbox-close { position: absolute; top: 16px; right: 20px; background: rgba(255,255,255,0.1); border: none; color: var(--text); font-size: 22px; width: 38px; height: 38px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background 0.15s; }
  .lightbox-close:hover { background: rgba(255,255,255,0.2); }

  /* Tooltip */
  .tooltip-wrap { position: relative; display: inline-flex; }
  .tooltip-wrap .tip { display: none; position: absolute; bottom: 130%; left: 50%; transform: translateX(-50%); background: #1c2333; border: 1px solid var(--border); border-radius: 6px; padding: 7px 10px; font-size: 11px; color: var(--text-muted); white-space: nowrap; z-index: 100; max-width: 260px; white-space: normal; text-align: center; line-height: 1.4; pointer-events: none; }
  .tooltip-wrap:hover .tip { display: block; }
  .help-icon { width: 18px; height: 18px; border-radius: 50%; background: #1c2333; border: 1px solid var(--border); color: var(--text-muted); font-size: 11px; font-weight: 700; cursor: default; display: inline-flex; align-items: center; justify-content: center; margin-left: 5px; }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">
      <div class="logo-icon">2D</div>
      <div class="logo-text">
        <h1>Godot 2D Auto Spriter &amp; Rigger</h1>
        <p>Multi-Species Character Generator with Godot 4 Auto-Rigging &amp; Asset Library</p>
      </div>
    </div>
    <div class="badges">
      <div id="badge-godot" class="badge badge-offline"><span class="badge-dot"></span> Godot 4: Checking...</div>
      <div id="badge-comfy" class="badge badge-offline"><span class="badge-dot"></span> ComfyUI: Checking...</div>
    </div>
  </header>

  <!-- Tab Navigation -->
  <div class="tab-nav">
    <button class="tab-btn active" onclick="switchTab('generator')" id="tab-btn-generator">🚀 Generator</button>
    <button class="tab-btn" onclick="switchTab('library')" id="tab-btn-library">📦 Asset Library</button>
    <button class="tab-btn" onclick="switchTab('models')" id="tab-btn-models">🤖 AI Models</button>
  </div>

  <!-- ======================================================= -->
  <!-- TAB 1: GENERATOR                                        -->
  <!-- ======================================================= -->
  <div class="tab-content active" id="tab-generator">
    <div class="grid">
      <!-- Left: Character Creation Form -->
      <div class="card">
        <div class="card-title">
          <span>Character &amp; Creature Creator</span>
          <span style="font-size: 11px; color: var(--text-muted);">Procedural &amp; Diffusion Controls</span>
        </div>

        <div class="form-group">
          <label>Archetype &amp; Creature Presets:</label>
          <div class="quick-presets" id="preset-container">
            <span class="preset-pill preset-custom" id="pill-custom" onclick="applyCustomMode()">✨ Custom Creature</span>
            <span class="preset-pill" id="pill-random" onclick="randomizeCreature()" style="background:linear-gradient(135deg,rgba(188,140,255,0.25),rgba(88,166,255,0.25));border-color:var(--accent-purple);color:#d2a8ff;font-weight:600;">🎲 Random Hybrid</span>
            <span class="preset-pill" id="pill-cyber_alien" onclick="applyPreset('cyber_alien','cyberpunk warrior alien with neon bioluminescent crest, plasma blade and chitin plates','warrior','biped','alien')">👾 Cyber Alien</span>
            <span class="preset-pill" id="pill-elven_sorceress" onclick="applyPreset('elven_sorceress','female elf sorceress with flowing purple hair, arcane glowing robes and crystal staff','mage','biped','humanoid')">🧝 Elf Mage</span>
            <span class="preset-pill" id="pill-winged_demon" onclick="applyPreset('winged_demon','crimson demon lord with obsidian curved horns, runic chest brand, shadow talons and wings','assassin','biped','demon')">😈 Demon Fiend</span>
            <span class="preset-pill" id="pill-skeleton_lich" onclick="applyPreset('skeleton_lich','undead skeleton lich with glowing cyan soul eyes, bone ribcage and tattered shroud','mage','biped','undead')">💀 Skeleton Lich</span>
            <span class="preset-pill" id="pill-dragonkin_brawler" onclick="applyPreset('dragonkin_brawler','emerald dragonkin warrior with horned brow, ridge scales and reptilian claws','warrior','biped','reptilian')">🦎 Dragonkin</span>
            <span class="preset-pill" id="pill-celestial_wolf" onclick="applyPreset('celestial_wolf','mythical celestial dire wolf with emerald predator eyes, multi tail and fur ruff','beast','quadruped','beast')">🐺 Dire Beast</span>
            <span class="preset-pill" id="pill-mantis_stalker" onclick="applyPreset('mantis_stalker','insectoid mantis assassin with compound phosphor eyes, chitin carapace and scythe claws','assassin','biped','insectoid')">🦗 Mantis</span>
            <span class="preset-pill" id="pill-holy_paladin" onclick="applyPreset('holy_paladin','noble human paladin in regal blue and gold armor with glowing blade','warrior','biped','humanoid')">⚔️ Paladin</span>
            <span class="preset-pill" id="pill-diesel_mech" onclick="applyPreset('diesel_mech','heavy dieselpunk mech juggernaut with caution hazard stripes and furnace core','mech','biped','mech')">🤖 Heavy Mech</span>
            <span class="preset-pill" id="pill-necromancer" onclick="applyPreset('necromancer','undead death priest in tattered purple and obsidian robes with bone staff','mage','biped','undead')">💀 Necromancer</span>
            <span class="preset-pill" id="pill-berserker" onclick="applyPreset('berserker','raging barbarian warrior with war paint, double battle axes and spiked iron armor','warrior','biped','humanoid')">🪓 Berserker</span>
            <span class="preset-pill" id="pill-trickster" onclick="applyPreset('trickster','shadow rogue trickster in emerald and violet dual cloaks with venom daggers','assassin','biped','humanoid')">🎭 Trickster</span>
            <span class="preset-pill" id="pill-pyromancer" onclick="applyPreset('pyromancer','fire elemental sorcerer enveloped in blazing magma robes with ember crown','mage','biped','demon')">🔥 Pyromancer</span>
            <span class="preset-pill" id="pill-cryomancer" onclick="applyPreset('cryomancer','frost elemental mage in arctic crystal ice armor with frozen staff','mage','biped','alien')">❄️ Cryomancer</span>
            <span class="preset-pill" id="pill-shadow_shinobi" onclick="applyPreset('shadow_shinobi','stealth shadow shinobi ninja in hooded dark silk with glowing cyan eyes, dual kunai blades and smoke shrouds','assassin','biped','humanoid')">🥷 Shadow Shinobi</span>
            <span class="preset-pill" id="pill-storm_valkyrie" onclick="applyPreset('storm_valkyrie','mythical valkyrie celestial warrior with radiant silver armor, spreading feathered wings and crackling thunder spear','warrior','biped','humanoid')">⚡ Storm Valkyrie</span>
            <span class="preset-pill" id="pill-steampunk_artificer" onclick="applyPreset('steampunk_artificer','victorian clockwork artificer with brass goggles, heavy leather toolbelt and portable steam dynamo pack','mech','biped','humanoid')">⚙️ Steampunk Artificer</span>
            <span class="preset-pill" id="pill-sand_golem" onclick="applyPreset('sand_golem','ancient monolith stone golem with glowing runic glyphs, floating sandstone boulders and heavy fists','mech','biped','beast')">🗿 Sand Golem</span>
            <span class="preset-pill" id="pill-abyssal_siren" onclick="applyPreset('abyssal_siren','deep ocean siren sorceress with bioluminescent fins, iridescent scales, coral crown and hydro-trident','mage','biped','alien')">🧜 Abyssal Siren</span>
            <span class="preset-pill" id="pill-plague_doctor" onclick="applyPreset('plague_doctor','alchemist plague doctor with beaked leather mask, wide-brim hat, long dark apothecary duster and glowing potion phials','assassin','biped','humanoid')">🎭 Plague Doctor</span>
            <span class="preset-pill" id="pill-wandering_ronin" onclick="applyPreset('wandering_ronin','lone masterless ronin swordsman in weathered haori robes, straw kasa hat and cherry blossom katana','warrior','biped','humanoid')">🗡️ Wandering Ronin</span>
            <span class="preset-pill" id="pill-void_reaver" onclick="applyPreset('void_reaver','cosmic void reaver wrapped in tattered dark rift fabric with single crimson eye and spatial tear scythe','assassin','biped','alien')">🌌 Void Reaver</span>
            <span class="preset-pill" id="pill-forest_druid" onclick="applyPreset('forest_druid','ancient wild druid with stag antler headpiece, living moss cloak, wooden bark armor and blooming vine staff','mage','biped','humanoid')">🌿 Forest Druid</span>
            <span class="preset-pill" id="pill-vampire_lord" onclick="applyPreset('vampire_lord','aristocratic vampire noble with high velvet collared cape, bat silhouette pauldrons and ruby rapier','warrior','biped','humanoid')">🧛 Vampire Lord</span>
            <span class="preset-pill" id="pill-spore_myconid" onclick="applyPreset('spore_myconid','sentient fungal mushroom shaman with wide bioluminescent spotted cap, spore satchel and root tendrils','mage','biped','alien')">🍄 Spore Myconid</span>
            <span class="preset-pill" id="pill-gorgon_occultist" onclick="applyPreset('gorgon_occultist','venomous gorgon serpent sorceress with emerald scaled coils, viper crown and glowing poison orb','mage','biped','reptilian')">🐍 Gorgon Occultist</span>
          </div>
          <div style="font-size:11px;color:var(--text-muted);margin-top:6px;line-height:1.4;">
            💡 <b>Creative Freedom:</b> Presets are flexible starting points — modify the visual prompt, mix anatomical parts in the Studio, or roll the 🎲 Random Hybrid anytime. You are never restricted by presets!
          </div>
        </div>

        <div class="form-group">
          <label for="concept">Visual Concept Description (Free-Form Text Prompt):</label>
          <textarea id="concept">cyberpunk warrior alien with neon bioluminescent crest, modular chitin armor, plasma blade</textarea>
        </div>

        <div class="row-2">
          <div class="form-group">
            <label for="char-name">Character Identifier:</label>
            <input type="text" id="char-name" value="cyber_alien">
          </div>
          <div class="form-group">
            <label for="species">Species &amp; Anatomy:</label>
            <select id="species" onchange="onSpeciesDropdownChanged()">
              <option value="custom">✨ Custom / Hybrid (User-Defined)</option>
              <option value="alien" selected>👾 Cyber Alien (Cranium, Bio-Crest, Talons)</option>
              <option value="humanoid">🧝 Human / Elf (Anime Face, Hair, Boots)</option>
              <option value="demon">😈 Demon / Fiend (Horns, Runic Brand, Talons)</option>
              <option value="undead">💀 Undead / Skeleton (Skull, Ribcage, Soul)</option>
              <option value="reptilian">🦎 Dragonkin (Snout, Ridge Horns, Scales)</option>
              <option value="beast">🐺 Dire Beast (Predatory Snout, Paws, Fur)</option>
              <option value="insectoid">🦗 Mantis (Antennae, Compound Eyes, Carapace)</option>
              <option value="mech">🤖 Heavy Mech (Visor, Armor Plates, Pistons)</option>
              <option value="auto">Auto-Detect from Prompt</option>
            </select>
          </div>
        </div>

        <!-- Render Style & Detail Controls -->
        <div class="row-2" style="margin-bottom:14px;">
          <div class="form-group" style="margin-bottom:0;">
            <label for="art-style">Render Style:</label>
            <select id="art-style" onchange="syncCustomPrompt()">
              <option value="anime" selected>✨ Anime Cel-Shading (Vibrant &amp; Sparkling Eyes)</option>
              <option value="pixel_8bit">👾 Retro 8-Bit Pixel Art (Quantized 16 Colors)</option>
              <option value="pixel_16bit">🎮 Classic 16-Bit Pixel Art (32 Colors Clean Grid)</option>
              <option value="dark_fantasy">🗡️ Dark Fantasy (Deep Shadows &amp; Grim Contrast)</option>
              <option value="cyberpunk">⚡ Cyberpunk Neon (Intense Glows &amp; Circuits)</option>
              <option value="comic_ink">🖋️ Comic Ink &amp; Halftone (Bold Dynamic Outlines)</option>
            </select>
          </div>
          <div class="form-group" style="margin-bottom:0;">
            <label for="detail-level">Detail Level: <span id="detail-val" style="color:#78c8ff;font-weight:600;">3 (Detailed)</span></label>
            <input type="range" id="detail-level" min="1" max="5" value="3" step="1" style="width:100%;margin-top:8px;" oninput="document.getElementById('detail-val').textContent = ['1 (Flat Silhouette)', '2 (Simple Minimal)', '3 (Detailed)', '4 (High Intricacy)', '5 (Masterpiece Ultra)'][this.value-1]">
          </div>
        </div>

        <!-- Custom Design Studio -->
        <div id="custom-studio" class="accordion" style="border-color: rgba(227,179,65,0.35);">
          <div class="accordion-header" style="background: rgba(227,179,65,0.08); color: #f0c654;" onclick="toggleCustomStudio()">
            <span>🎨 Custom Creature Studio (30+ Anatomical Parts, Appendages &amp; Colors)</span>
            <span id="custom-studio-arrow">▼</span>
          </div>
          <div id="custom-studio-body" class="accordion-content">
            <div class="row-2" style="margin-bottom:12px;">
              <div class="form-group">
                <label for="custom-head">Head Shape / Style (32 Styles):</label>
                <select id="custom-head" onchange="syncCustomPrompt()">
                  <option value="humanoid" selected>🧝 Humanoid / Elf (Anime Hair &amp; Face)</option>
                  <option value="vampire">🧛 Vampire Lord (Fangs &amp; Piercing Eyes)</option>
                  <option value="undead">💀 Bony Skull &amp; Soul Flame</option>
                  <option value="lich">👑 Ancient Lich Crown &amp; Ghostly Eyes</option>
                  <option value="orc">👹 Orc Warlord (War Paint &amp; Heavy Tusks)</option>
                  <option value="goblin">👺 Goblin Trickster (Pointed Ears &amp; Goggles)</option>
                  <option value="sorcerer">🧙 Dark Sorcerer (Deep Hood &amp; Shadow Eyes)</option>
                  <option value="angel">👼 Angelic Seraph (Golden Halo &amp; Fair Tresses)</option>
                  <option value="kitsune">🦊 Kitsune Fox Spirit (Fox Ears &amp; Whiskers)</option>
                  <option value="minotaur">🐂 Minotaur Bull (Curved Heavy Horns)</option>
                  <option value="alien">👾 Alien Cranium (Bio-Crest &amp; Vents)</option>
                  <option value="xenomorph">👽 Xenomorph Dome (Elongated Biomechanical)</option>
                  <option value="void_wraith">👤 Void Stalker (Faceless Obsidian Mask)</option>
                  <option value="demon">😈 Demon Horns &amp; Obsidian Fangs</option>
                  <option value="oni">👹 Oni Demon (Twin Horns &amp; Crimson Brow)</option>
                  <option value="reptilian">🦎 Dragon Brow Horns &amp; Reptile Snout</option>
                  <option value="basilisk">🐍 Basilisk Crest (Slit Golden Eyes)</option>
                  <option value="insectoid">🦗 Mantis Antennae &amp; Compound Eyes</option>
                  <option value="spider_queen">🕷️ Arachnid Queen (Multi-Beaded Eyes)</option>
                  <option value="beast">🐺 Beast / Wolf Snout &amp; Pointed Ears</option>
                  <option value="lion">🦁 Lion Sovereign (Full Majestic Mane)</option>
                  <option value="griffin">🦅 Griffin / Birdfolk (Curved Hooked Beak)</option>
                  <option value="mech">🤖 Mech Visor &amp; LED Armor Helmet</option>
                  <option value="clockwork">⚙️ Clockwork Automaton (Brass Gears &amp; Monocle)</option>
                  <option value="siren">🧜 Deep Sea Siren (Fin-Ears &amp; Coral Crown)</option>
                  <option value="crystal_golem">💎 Crystal Golem (Faceted Gemstone Head)</option>
                  <option value="flame_elemental">🔥 Blazing Fire Elemental (Fire Crown)</option>
                  <option value="plague_doctor">🎭 Plague Doctor (Beaked Leather Mask)</option>
                  <option value="samurai">🥷 Samurai Kabuto (Crested Menpo Mask)</option>
                  <option value="pharaoh">🐕 Jackal God (Anubis Mask &amp; Nemes)</option>
                  <option value="myconid">🍄 Fungal Myconid (Spotted Mushroom Cap)</option>
                  <option value="astronaut">🚀 Void Astronaut (Gold Bubble Visor)</option>
                </select>
              </div>
              <div class="form-group">
                <label for="custom-torso">Torso Style (32 Styles):</label>
                <select id="custom-torso" onchange="syncCustomPrompt()">
                  <option value="plate_armor">Noble Steel Cuirass &amp; Gold Filigree</option>
                  <option value="mage_robe">Enchanted Silk Robe &amp; Rune Collar</option>
                  <option value="leather_jerkin">Adventurer Leather Jerkin &amp; Straps</option>
                  <option value="shadow_cloak">Assassin Shadow Cloak &amp; Tattered Wraps</option>
                  <option value="fur_harness">Berserker Wolf Fur &amp; Iron Studs</option>
                  <option value="paladin_tabard">Paladin Sacred Tabard &amp; Chainmail</option>
                  <option value="undead" selected>Exposed Skeletal Ribcage &amp; Shroud</option>
                  <option value="demon">Muscular Demonic Obsidian &amp; Runic Brand</option>
                  <option value="dragon_scutes">Overlapping Dragon Scutes &amp; Flame Scales</option>
                  <option value="alien">Biomechanical Carapace &amp; Core</option>
                  <option value="xeno_ribs">Ribbed Xenomorph Chitin Exoskeleton</option>
                  <option value="insectoid">Segmented Glossy Mantis Chitin Thorax</option>
                  <option value="mech">Heavy Hydraulic Mech Chest &amp; Arc Reactor</option>
                  <option value="nanosuit">Cyberpunk Fibre Nanosuit &amp; Glowing Circuits</option>
                  <option value="clockwork_brass">Clockwork Brass Torso &amp; Rotating Gears</option>
                  <option value="crystal_core">Prismatic Crystal Geode &amp; Gem Clusters</option>
                  <option value="sea_coral">Living Sea-Coral &amp; Barnacle Breastplate</option>
                  <option value="dryad_wood">Living Wood Dryad Bark &amp; Woven Vines</option>
                  <option value="bioluminescent_jelly">Bioluminescent Translucent Jelly Torso</option>
                  <option value="volcanic_magma">Cracked Obsidian Plates &amp; Molten Lava Core</option>
                  <option value="glacial_ice">Solid Glacial Rime Ice &amp; Frost Crystals</option>
                  <option value="celestial_weave">Star-Woven Constellation Robes</option>
                  <option value="bone_armor">Bone-Forged Linked Vertebrae &amp; Talismans</option>
                  <option value="corset_doublet">Royal Brocade Doublet &amp; Velvet Coat</option>
                  <option value="gladiator_harness">Gladiator Leather Harness &amp; Medallion</option>
                  <option value="nomad_linen">Desert Nomad Linen Wraps &amp; Sand Scarves</option>
                  <option value="tactical_vest">Spec-Ops Kevlar Plate Carrier &amp; Pouches</option>
                  <option value="vampire_waistcoat">Vampire Brocade Waistcoat &amp; Cravat</option>
                  <option value="fungal_spores">Mycelium Spore-Cap &amp; Shelf Mushrooms</option>
                  <option value="origami_paper">Folded Origami Lacquered Paper Armor</option>
                  <option value="ethereal_mist">Ghostly Translucent Spectral Ribcage</option>
                  <option value="sunburst_gold">Solar Sunburst Medallion Cuirass</option>
                </select>
              </div>
            </div>
            <div class="row-2" style="margin-bottom:12px;">
              <div class="form-group">
                <label for="custom-hands">Hands / Claws Style (26 Styles):</label>
                <select id="custom-hands" onchange="syncCustomPrompt()">
                  <option value="humanoid" selected>Humanoid Articulated Fingers</option>
                  <option value="leather_gloves">Adventurer Leather Gloves &amp; Wraps</option>
                  <option value="steel_gauntlets">Steel Knight Plate Gauntlets</option>
                  <option value="arcane_rings">Mage Ringed Hands &amp; Palm Runes</option>
                  <option value="demon">Sharp Obsidian Demonic Claws</option>
                  <option value="undead">Bony Skeletal Digits</option>
                  <option value="reptilian">Heavy Dragon Claws &amp; Scaled Talons</option>
                  <option value="alien">Alien Elongated Four-Joint Talons</option>
                  <option value="scythe_blades">Mantis Serrated Scythe Sickles</option>
                  <option value="pincer_servo">Cybernetic Hydraulic Pincer Grip</option>
                  <option value="power_fists">Heavy Mech Pneumatic Power Fists</option>
                  <option value="flame_fists">Blazing Flame-Wreathed Fists</option>
                  <option value="frost_claws">Sub-Zero Frost Rime Ice Claws</option>
                  <option value="lightning_knuckles">Lightning Arc Conduit Knuckles</option>
                  <option value="shadow_tendrils">Billowing Smoke Shadow Tendril Hands</option>
                  <option value="vine_claws">Thorn-Wrapped Poisonous Vine Claws</option>
                  <option value="crab_pincers">Crustacean Heavy Chitin Crab Pincers</option>
                  <option value="wing_fingers">Feathered Harpy Wing-Tip Claw Fingers</option>
                  <option value="crystal_shards">Prismatic Crystal Gem Spike Claws</option>
                  <option value="silk_gloves">Gilded Silk Noble Lace Gloves</option>
                  <option value="calligraphy_pens">Needle Calligrapher Ink Claws</option>
                  <option value="wood_knuckles">Dryad Wooden Branch Knuckles</option>
                  <option value="suction_pods">Translucent Jelly Suction Pods</option>
                  <option value="brass_calipers">Clockwork Brass Cogs &amp; Calipers</option>
                  <option value="chem_sprayers">Toxic Chem-Sprayer Nozzle Gauntlets</option>
                  <option value="gladiator_cestus">Spiked Gladiator Iron Brawling Cestus</option>
                </select>
              </div>
              <div class="form-group">
                <label for="custom-feet">Feet / Base Style (26 Styles):</label>
                <select id="custom-feet" onchange="syncCustomPrompt()">
                  <option value="humanoid">Adventurer Cuffed Leather Boots</option>
                  <option value="knight_sabatons">Steel Knight Segmented Sabatons</option>
                  <option value="cloven_hooves">Cloven Demon / Minotaur Hooves</option>
                  <option value="undead" selected>Bare Skeletal Foot Bones</option>
                  <option value="reptilian">Raptor / Dragon Talon Feet</option>
                  <option value="alien">Digitigrade Reversed Alien Talons</option>
                  <option value="wolf_paws">Padded Beast Wolf Paws &amp; Claws</option>
                  <option value="mech_pistons">Industrial Mech Hydraulic Stomp Boots</option>
                  <option value="hover_jets">Anti-Gravity Cybernetic Hover Thrusters</option>
                  <option value="serpent_tail">Naga Scaled Serpent Coiled Lower Body</option>
                  <option value="spider_legs">Octopod Segmented Arachnid Stilts</option>
                  <option value="centaur_base">Centaur Equine Four-Legged Stallion Base</option>
                  <option value="crystal_pillars">Crystal Stalagmite Mineral Pillars</option>
                  <option value="whirlwind_base">Floating Elemental Whirlwind Tornado</option>
                  <option value="spectral_tail">Legless Spectral Mist Floating Shroud</option>
                  <option value="mermaid_tail">Mermaid Iridescent Fluke Tail</option>
                  <option value="lava_pillar">Bubbling Volcanic Magma Pillar</option>
                  <option value="ice_skates">Glacial Solid Ice Rime Blades</option>
                  <option value="mycelium_stem">Rooted Fungal Mycelium Stem Mat</option>
                  <option value="mangrove_roots">Living Mangrove Tangled Woody Roots</option>
                  <option value="monowheel">Clockwork Brass Rolling Monowheel</option>
                  <option value="maglev_skids">High-Tech Mag-Lev Hover Skids</option>
                  <option value="harpy_talons">Avian Harpy Perching Talons</option>
                  <option value="gladiator_sandals">Gladiator Strapped Shin Sandals</option>
                  <option value="trench_boots">Reinforced Armored Mud Tread Boots</option>
                  <option value="slime_base">Translucent Gelatinous Amoeba Mass</option>
                </select>
              </div>
            </div>
            <div class="form-group" style="margin-bottom:14px;">
              <label>Custom Appendages &amp; Accents:</label>
              <div style="display:flex;flex-wrap:wrap;gap:18px;align-items:center;padding-top:4px;">
                <label style="display:flex;align-items:center;gap:6px;cursor:pointer;color:var(--text);font-size:13px;font-weight:500;">
                  <input type="checkbox" id="custom-wings" onchange="syncCustomPrompt()"> 🪽 Wings
                </label>
                <label style="display:flex;align-items:center;gap:6px;cursor:pointer;color:var(--text);font-size:13px;font-weight:500;">
                  <input type="checkbox" id="custom-tail" onchange="syncCustomPrompt()"> 🐉 Articulated Tail
                </label>
                <label style="display:flex;align-items:center;gap:6px;cursor:pointer;color:var(--text);font-size:13px;font-weight:500;">
                  <input type="checkbox" id="custom-halo" onchange="syncCustomPrompt()"> 😇 Glowing Halo / Crest
                </label>
                <label style="display:flex;align-items:center;gap:6px;cursor:pointer;color:var(--text);font-size:13px;font-weight:500;">
                  <input type="checkbox" id="custom-pauldrons" onchange="syncCustomPrompt()"> 🛡️ Heavy Pauldrons
                </label>
              </div>
            </div>
            <label style="margin-bottom:8px;display:block;">Interactive Custom Color Palette:</label>
            <div class="row-4" style="margin-bottom:4px;">
              <div class="color-picker-box">
                <input type="color" id="col-primary" value="#2b4764" onchange="syncCustomPrompt()">
                <span>Body / Skin</span>
              </div>
              <div class="color-picker-box">
                <input type="color" id="col-accent" value="#d79c29" onchange="syncCustomPrompt()">
                <span>Cloth / Hair</span>
              </div>
              <div class="color-picker-box">
                <input type="color" id="col-glow" value="#00f0ff" onchange="syncCustomPrompt()">
                <span>Glow / Eyes</span>
              </div>
              <div class="color-picker-box">
                <input type="color" id="col-outline" value="#121824" onchange="syncCustomPrompt()">
                <span>Outline</span>
              </div>
            </div>
          </div>
        </div>

        <div class="row-2" style="margin-top:14px;">
          <div class="form-group">
            <label for="rig-type">Rig Architecture:</label>
            <select id="rig-type">
              <option value="biped" selected>Humanoid Biped (15 bones)</option>
              <option value="quadruped">Beast / Quadruped (20 bones)</option>
            </select>
          </div>
          <div class="form-group">
            <label for="archetype">Color Accent Fallback:</label>
            <select id="archetype">
              <option value="warrior" selected>Warrior (Cobalt &amp; Amber Gold)</option>
              <option value="mage">Mage (Deep Arcane Violet &amp; Magenta)</option>
              <option value="assassin">Assassin (Midnight Obsidian &amp; Crimson)</option>
              <option value="ranger">Ranger (Forest Greens &amp; Emerald)</option>
              <option value="mech">Mech (Gunmetal &amp; Amber Furnace)</option>
              <option value="beast">Beast (Shadow Fur &amp; Emerald Core)</option>
            </select>
          </div>
        </div>

        <!-- Advanced Tuning -->
        <div class="accordion">
          <div class="accordion-header" onclick="toggleAccordion()">
            <span>Advanced Tuning Parameters (Seed, Engine, Paths)</span>
            <span id="accordion-arrow">▼</span>
          </div>
          <div id="accordion-body" class="accordion-content">
            <div class="row-2">
              <div class="form-group">
                <label>Generation Engine:
                  <span class="tooltip-wrap"><span class="help-icon">?</span>
                    <span class="tip">Auto: tries ComfyUI diffusion first, falls back to procedural spriter.<br>ComfyUI Only: fails if ComfyUI is offline.<br>Procedural: fast offline Pillow-based spriter, always works.</span>
                  </span>
                </label>
                <select id="engine-mode">
                  <option value="auto" selected>Auto (ComfyUI with Smart Spriter Fallback)</option>
                  <option value="comfyui">ComfyUI Generative Diffusion Only</option>
                  <option value="local">Smart Procedural Spriter (Offline / Instant)</option>
                </select>
              </div>
              <div class="form-group">
                <label>AI Model Checkpoint:
                  <span class="tooltip-wrap"><span class="help-icon">?</span>
                    <span class="tip">Select the ComfyUI checkpoint to use for AI generation. Only active when using ComfyUI engine mode. Installed models shown with [INSTALLED].</span>
                  </span>
                </label>
                              <select id="model-checkpoint">
                  <option value="animagineXL_v31.safetensors" selected>Animagine XL 3.1 (SDXL Premier Anime) [INSTALLED]</option>
                  <option value="waifuDiffusion_v14.safetensors">Waifu Diffusion 1.4 (SD 1.5 2D Anime)</option>
                  <option value="anythingV5_PrtRE.safetensors">AnythingV5 (SD 1.5 High-Quality Anime)</option>
                  <option value="toonyou_beta6.safetensors">ToonYou Beta 6 (SD 1.5 Cartoon Cel-Shading)</option>
                  <option value="rpg_V5.safetensors">RPG v5 (SD 1.5 RPG Concept Art)</option>
                  <option value="mixProV4.safetensors">MIX-Pro v4 (SD 1.5 Hyper-Detailed)</option>
                  <option value="pixelArtXL_v11.safetensors">Pixel Art XL (SDXL Pixel Sprite Sheet)</option>
                  <option value="counterfeit_v3.safetensors">Counterfeit V3.0 (SD 1.5 Lightweight Anime)</option>
                  <option value="dreamshaper_8.safetensors">DreamShaper 8 (SD 1.5 Game Concept Art)</option>
                </select>
              </div>
            </div>
            <div class="row-2">
              <div class="form-group">
                <label>Variation Seed (-1 for Random):</label>
                <div style="display:flex;gap:8px;">
                  <input type="text" id="seed" value="-1">
                  <button type="button" class="btn btn-secondary btn-icon" onclick="randomizeSeed()" title="Roll random seed">🎲</button>
                </div>
              </div>
              <div class="form-group">
                <label>Target Godot Scene Destination:</label>
                <input type="text" id="target-scene" value="res://scenes/cyber_alien_character.tscn">
              </div>
            </div>
          </div>
        </div>

        <div style="margin-top:18px;display:flex;gap:12px;">
          <button id="btn-generate" class="btn btn-primary" style="flex:1;" onclick="runPipeline('generate')">
            🚀 Generate &amp; Assemble Character
          </button>
          <button id="btn-add-queue" class="btn btn-secondary" style="border-color:var(--accent);color:#f0c654;display:flex;align-items:center;gap:6px;" onclick="addToQueue()">
            ➕ Add to Queue
          </button>
        </div>
        <div class="actions">
          <button class="btn btn-secondary" onclick="runPipeline('sprites_only')">🎨 Generate Sprites Only</button>
          <button class="btn btn-secondary" onclick="runPipeline('rig_only')">🦴 Auto-Rig Skeleton Scene</button>
        </div>

        <!-- Generation Queue Panel -->
        <div id="queue-panel" class="card" style="margin-top:16px;border-color:rgba(120,200,255,0.25);">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <div style="font-weight:600;font-size:13px;display:flex;align-items:center;gap:8px;">
              <span>📦 Generation Queue</span>
              <span id="queue-badge" class="lib-badge lib-badge-scene" style="display:none;">0 active</span>
            </div>
            <div style="display:flex;gap:8px;">
              <button class="btn btn-secondary btn-sm" onclick="clearCompletedQueue()">Clear Finished</button>
            </div>
          </div>
          <div id="queue-empty" style="text-align:center;color:var(--text-muted);padding:14px 0;font-size:12px;">
            Queue is empty. Click "➕ Add to Queue" to batch multiple character generations!
          </div>
          <div id="queue-list" style="display:none;max-height:220px;overflow-y:auto;gap:8px;flex-direction:column;"></div>
        </div>
      </div>

      <!-- Right: Console + Asset Preview -->
      <div style="display:flex;flex-direction:column;gap:20px;">
        <!-- Console -->
        <div class="card">
          <div class="console-toolbar">
            <span>Execution Log Console</span>
            <div style="display:flex;align-items:center;gap:10px;">
              <span id="status-pill" style="font-size:11px;color:var(--text-muted);">Idle</span>
              <button class="btn btn-secondary btn-sm" onclick="clearConsole()">Clear</button>
            </div>
          </div>
          <div id="console" class="console">
            <div class="console-line ci">[READY] Godot 2D Auto Spriter Dashboard initialized.</div>
            <div class="console-line ci">[INFO] Select a preset or customize anatomy, wings, and colors above.</div>
          </div>
        </div>

        <!-- Sprite Gallery / Output Preview -->
        <div class="card" id="gallery-card">
          <div class="card-title">
            <span id="gallery-title">Generated Sprite Sheet Parts (cyber_alien)</span>
            <span id="gallery-count" style="font-size:11px;color:var(--text-muted);">0 parts</span>
          </div>
          <div id="gallery-empty" class="gallery-empty">
            No sprites generated yet for this character. Click Generate to build them!
          </div>
          <div id="gallery-grid" class="sprite-grid" style="display:none;"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- ======================================================= -->
  <!-- TAB 2: ASSET LIBRARY & VIEWER                           -->
  <!-- ======================================================= -->
  <div class="tab-content" id="tab-library">
    <div class="lib-header">
      <div class="lib-title">Generated Characters &amp; Limb Library <span id="lib-char-count" style="font-size:12px;color:var(--text-muted);font-weight:normal;margin-left:8px;"></span></div>
      <div style="display:flex;gap:8px;">
        <button class="btn btn-secondary btn-sm" onclick="refreshLibrary()">🔄 Refresh Library</button>
      </div>
    </div>
    <div class="library-layout">
      <!-- Roster -->
      <div>
        <div class="lib-toolbar">
          <input class="lib-search" type="text" id="lib-search" placeholder="🔍 Filter characters..." oninput="filterRoster()">
        </div>
        <div id="char-roster" class="char-roster">
          <div style="text-align:center;color:var(--text-muted);padding:40px 0;font-size:13px;">Loading characters...</div>
        </div>
      </div>

      <!-- Viewer -->
      <div class="card viewer-panel">
        <div id="viewer-empty" class="viewer-empty">
          <div class="viewer-empty-icon">🎮</div>
          <div>Select a character from the roster to view their sprites.</div>
        </div>
        <div id="viewer-content" style="display:none;">
          <div class="viewer-header">
            <div>
              <div class="viewer-title" id="viewer-char-name">—</div>
              <div style="font-size:12px;color:var(--text-muted);margin-top:2px;" id="viewer-char-meta"></div>
            </div>
            <div class="viewer-actions">
              <button class="btn btn-secondary btn-sm" onclick="openExplorerFor(viewingChar)">📁 Folder</button>
              <button class="btn btn-secondary btn-sm" onclick="openGodotFor(viewingChar)">🎮 Godot</button>
              <button class="btn btn-secondary btn-sm" onclick="rerigChar(viewingChar)">🦴 Re-Rig</button>
              <button class="btn btn-danger btn-sm" onclick="deleteChar(viewingChar)">🗑️ Delete</button>
            </div>
          </div>

          <!-- Full Assembled Character Body Preview Card -->
          <div id="viewer-full-body-card" style="margin-bottom:16px;background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:8px;padding:14px;display:flex;align-items:center;gap:20px;">
            <div style="background:repeating-conic-gradient(#141824 0% 25%, #0e111a 0% 50%) 50% / 14px 14px;border-radius:6px;padding:10px;display:flex;align-items:center;justify-content:center;min-width:140px;min-height:160px;border:1px solid rgba(255,255,255,0.06);cursor:pointer;" onclick="openLightbox(document.getElementById('viewer-full-img').src, viewingChar + ' (Full Body)')">
              <img id="viewer-full-img" src="" alt="Full Body Sprite" style="max-height:180px;max-width:160px;object-fit:contain;filter:drop-shadow(0 4px 10px rgba(0,0,0,0.6));">
            </div>
            <div style="flex:1;">
              <div style="font-size:14px;font-weight:600;color:var(--text);margin-bottom:4px;">Full Connected Sprite Preview</div>
              <div style="font-size:12px;color:var(--text-muted);margin-bottom:10px;">Assembled puppet body showing all connected limb attachments and joints.</div>
              <button class="btn btn-secondary btn-sm" onclick="openLightbox(document.getElementById('viewer-full-img').src, viewingChar + ' (Full Body)')">🔍 Inspect High-Res</button>
            </div>
          </div>

          <div style="font-size:12px;font-weight:600;color:var(--text-muted);margin-bottom:8px;">Individual Sliced Limb Parts:</div>
          <div id="viewer-grid" class="viewer-grid"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- ======================================================= -->
  <!-- TAB 3: AI MODELS                                    -->
  <!-- ======================================================= -->
  <div class="tab-content" id="tab-models">
    <div class="card">
      <div class="card-title">
        <span>AI Diffusion Checkpoints</span>
        <span id="model-status-pill" style="font-size:11px;color:var(--text-muted);">Checking...</span>
      </div>
      <p style="font-size:12px;color:var(--text-muted);margin-bottom:14px;">
        Download state-of-the-art anime AI checkpoints into ComfyUI for local generative diffusion.
        These models run entirely locally — no internet connection required after download.
      </p>
      <div class="row-2" style="margin-bottom:8px;max-width:600px;">
        <div class="form-group" style="margin-bottom:0;">
          <select id="model-select">
            <option value="pixel_lora">PixelArt Redmond LoRA SD 1.5 (~26 MB - Retro Pixel Sprites)</option>
            <option value="pixel_lora_xl">Pixel Art XL LoRA SDXL (~170 MB - High-Res Pixel Sprites)</option>
            <option value="animagine_xl">Animagine XL 3.1 (SDXL ~6.6 GB - Premier Anime)</option>
            <option value="pony_xl">Pony Diffusion XL v6 (SDXL ~6.5 GB - Expressive Game Art)</option>
            <option value="anything_v5">AnythingV5 (SD 1.5 ~2 GB - Clean Anime)</option>
            <option value="counterfeit_v3">Counterfeit V3.0 (SD 1.5 ~2 GB - Fast Anime)</option>
            <option value="dreamshaper_8">DreamShaper 8 (SD 1.5 ~2 GB - Game Concept)</option>
            <option value="toonyou">ToonYou Alpha 3 (SD 1.5 ~2 GB - Cel-Shaded Game Cartoon)</option>
            <option value="rpg_v5">RPG Remix v5 (SD 1.5 ~4 GB - RPG Concept Character Art)</option>
            <option value="cuteyuki_v2">CuteYukiMix Adorable v2 (SD 1.5 ~2 GB - Anime Character Art)</option>
            <option value="anything_v3">Anything V3.0 (SD 1.5 ~2 GB - Benchmark Anime)</option>
            <option value="flat_anime_lora">Flat 2D Anime LoRA (~218 MB - Style Modifier)</option>
            <option value="controlnet_openpose">ControlNet OpenPose XL (~2.4 GB - Pose Guidance)</option>
            <option value="layer_conv">LayerDiffuse SDXL Conv (~3.4 GB - Transparent RGBA)</option>
            <option value="vae_decoder">LayerDiffuse VAE Decoder (~198 MB - Alpha Decoder)</option>
          </select>
        </div>
        <button id="btn-download-model" class="btn btn-secondary" onclick="startModelDownload()">⬇️ Download Model</button>
      </div>
      <div id="model-progress-wrap" style="display:none;margin-top:8px;max-width:600px;">
        <div class="progress-container">
          <div id="model-progress-bar" class="progress-bar"></div>
          <div id="model-progress-text" class="progress-text">0%</div>
        </div>
        <div style="font-size:11px;color:var(--text-muted);margin-top:4px;display:flex;justify-content:space-between;">
          <span id="model-dl-info">Starting...</span>
          <span id="model-dl-speed">0.0 MB/s</span>
        </div>
      </div>

      <div style="margin-top:24px;">
        <div style="font-size:13px;font-weight:600;color:var(--text);margin-bottom:12px;">Model Status</div>
        <div id="model-catalog-list" style="display:flex;flex-direction:column;gap:8px;max-width:700px;">
          <div style="color:var(--text-muted);font-size:12px;">Loading...</div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Lightbox -->
<div class="lightbox" id="lightbox" onclick="closeLightbox(event)">
  <button class="lightbox-close" onclick="closeLightboxDirect()">&times;</button>
  <div class="lightbox-img-wrap">
    <img class="lightbox-img" id="lightbox-img" src="" alt="">
  </div>
  <div class="lightbox-meta">
    <h3 id="lightbox-title"></h3>
    <p id="lightbox-meta"></p>
  </div>
</div>

<script>
// ---- Global State ----
let currentCharacter = "cyber_alien";
let viewingChar = "";
let allLibraryChars = [];

// ---- Tab Switching ----
function switchTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.getElementById('tab-btn-' + name).classList.add('active');
  if (name === 'library') refreshLibrary();
  if (name === 'models') checkModelStatus();
}

// ---- Console ----
function log(msg, type = "normal") {
  const c = document.getElementById("console");
  const span = document.createElement("span");
  if (type === "ci") span.className = "ci";
  else if (type === "gi") span.className = "gi";
  else if (type === "ok") span.className = "ok";
  else if (type === "warn") span.className = "warn";
  else if (type === "err") span.className = "err";
  else if (type === "gen") span.className = "gen";
  span.textContent = msg + "\\n";
  c.appendChild(span);
  c.scrollTop = c.scrollHeight;
}
function clearConsole() {
  document.getElementById("console").innerHTML = "";
  log("[Console cleared]", "warn");
}

// ---- Helpers ----
function randomizeSeed() {
  const s = Math.floor(Math.random() * 2147483647);
  document.getElementById("seed").value = s;
  log(`[SEED] New variation seed: ${s}`, "ci");
}

function toggleAccordion() {
  const b = document.getElementById("accordion-body");
  const a = document.getElementById("accordion-arrow");
  b.classList.toggle("open");
  a.textContent = b.classList.contains("open") ? "▲" : "▼";
}

function toggleCustomStudio(forceOpen) {
  const b = document.getElementById("custom-studio-body");
  const a = document.getElementById("custom-studio-arrow");
  if (forceOpen === true) {
    b.classList.add("open");
    a.textContent = "▲";
  } else if (forceOpen === false) {
    b.classList.remove("open");
    a.textContent = "▼";
  } else {
    b.classList.toggle("open");
    a.textContent = b.classList.contains("open") ? "▲" : "▼";
  }
}

function setActivePill(pillId) {
  document.querySelectorAll('.preset-pill').forEach(el => el.classList.remove('active'));
  const p = document.getElementById(pillId);
  if (p) p.classList.add('active');
}

// ---- Preset Logic ----
function applyCustomMode() {
  setActivePill('pill-custom');
  document.getElementById("char-name").value = "custom_creature";
  document.getElementById("species").value = "custom";
  document.getElementById("target-scene").value = "res://scenes/custom_creature_character.tscn";
  toggleCustomStudio(true);
  syncCustomPrompt(true);
  log("[CUSTOM] Activated Custom Creature Studio — mix anatomy, add wings/tail, set colors!", "ci");
  refreshGallery();
}

function onSpeciesDropdownChanged() {
  const sp = document.getElementById("species").value;
  if (sp === "custom") {
    setActivePill('pill-custom');
    toggleCustomStudio(true);
  } else {
    // Don't auto-open studio for non-custom selections
    toggleCustomStudio(false);
  }
}

function syncCustomPrompt(force = false) {
  const sp = document.getElementById("species").value;
  if (!force && sp !== "custom") return;
  const head  = document.getElementById("custom-head").value;
  const torso = document.getElementById("custom-torso").value;
  const hands = document.getElementById("custom-hands") ? document.getElementById("custom-hands").value : "humanoid";
  const feet  = document.getElementById("custom-feet") ? document.getElementById("custom-feet").value : "humanoid";
  const wings = document.getElementById("custom-wings").checked;
  const tail  = document.getElementById("custom-tail").checked;
  const halo  = document.getElementById("custom-halo") ? document.getElementById("custom-halo").checked : false;
  const pauldrons = document.getElementById("custom-pauldrons") ? document.getElementById("custom-pauldrons").checked : false;
  const artStyle = document.getElementById("art-style") ? document.getElementById("art-style").value : "anime";
  const pCol  = document.getElementById("col-primary").value;
  const gCol  = document.getElementById("col-glow").value;

  let desc = `custom creature in ${artStyle} style with ${head} head silhouette, ${torso} body, ${hands} hands, ${feet} base`;
  if (wings) desc += ", large spreading wings";
  if (tail)  desc += ", articulated tail";
  if (halo)  desc += ", glowing ethereal halo";
  if (pauldrons) desc += ", heavy armor pauldrons";
  desc += `, primary color ${pCol} and glowing core ${gCol}`;
  document.getElementById("concept").value = desc;
}

function applyPreset(name, concept, arch, rig, species = "auto") {
  setActivePill(`pill-${name}`);
  document.getElementById("char-name").value = name;
  document.getElementById("concept").value = concept;
  document.getElementById("archetype").value = arch;
  document.getElementById("rig-type").value = rig;
  document.getElementById("species").value = species;
  document.getElementById("target-scene").value = `res://scenes/${name}_character.tscn`;
  currentCharacter = name;

  // Collapse custom studio (not for custom presets)
  toggleCustomStudio(false);

  // Update color pickers to match species
  const colorMap = {
    alien:               { p: "#2b4764", g: "#00f0ff" },
    demon:               { p: "#5f1c2a", g: "#ff2d1e" },
    undead:              { p: "#a09b91", g: "#00eeff" },
    reptilian:           { p: "#1e4a20", g: "#8eff52" },
    beast:               { p: "#3b2a1e", g: "#00cc44" },
    humanoid:            { p: "#e8c9a0", g: "#a071f7" },
    insectoid:           { p: "#2a3e1a", g: "#aaff00" },
    mech:                { p: "#3c4454", g: "#ff9900" },
    necromancer:         { p: "#381a4d", g: "#00f0ff" },
    berserker:           { p: "#5c1d1d", g: "#ff4d4d" },
    trickster:           { p: "#1a4030", g: "#b438d9" },
    pyromancer:          { p: "#61220a", g: "#ff6600" },
    cryomancer:          { p: "#1c3c54", g: "#8fe9ff" },
    shadow_shinobi:      { p: "#141822", g: "#00e5ff" },
    storm_valkyrie:      { p: "#40507a", g: "#ffd700" },
    steampunk_artificer: { p: "#5c3d1e", g: "#ffaa00" },
    sand_golem:          { p: "#78613f", g: "#00ffcc" },
    abyssal_siren:       { p: "#0b2c3d", g: "#00ffb7" },
    plague_doctor:       { p: "#22252a", g: "#39ff14" },
    wandering_ronin:     { p: "#3d3228", g: "#ff77aa" },
    void_reaver:         { p: "#160b24", g: "#ff0055" },
    forest_druid:        { p: "#263e20", g: "#76ff03" },
    vampire_lord:        { p: "#3d141e", g: "#ff1744" },
    spore_myconid:       { p: "#332038", g: "#00e676" },
    gorgon_occultist:    { p: "#183624", g: "#d500f9" }
  };
  if (colorMap[species] || colorMap[name]) {
    const pal = colorMap[species] || colorMap[name];
    document.getElementById("col-primary").value = pal.p;
    document.getElementById("col-glow").value = pal.g;
  }

  log(`[PRESET] Loaded '${name}' (${species.toUpperCase()}, ${rig.toUpperCase()})`, "ci");
  refreshGallery();
}

function randomizeCreature() {
  setActivePill('pill-random');
  toggleCustomStudio(true);

  const speciesList = ["alien", "humanoid", "demon", "undead", "reptilian", "beast", "insectoid", "mech", "custom"];
  const archetypes = ["warrior", "mage", "assassin", "ranger", "mech", "beast"];
  const artStyles = ["anime", "pixel_8bit", "pixel_16bit", "dark_fantasy", "cyberpunk", "comic_ink"];

  const headSelect = document.getElementById("custom-head");
  const torsoSelect = document.getElementById("custom-torso");
  const handSelect = document.getElementById("custom-hands");
  const footSelect = document.getElementById("custom-feet");

  const pickRandom = (sel) => {
    if (!sel || !sel.options || sel.options.length === 0) return "";
    const idx = Math.floor(Math.random() * sel.options.length);
    sel.selectedIndex = idx;
    return sel.options[idx].value;
  };

  const rHead = pickRandom(headSelect);
  const rTorso = pickRandom(torsoSelect);
  const rHand = pickRandom(handSelect);
  const rFoot = pickRandom(footSelect);

  document.getElementById("custom-wings").checked = (Math.random() > 0.55);
  document.getElementById("custom-tail").checked = (Math.random() > 0.5);
  if (document.getElementById("custom-halo")) document.getElementById("custom-halo").checked = (Math.random() > 0.7);
  if (document.getElementById("custom-pauldrons")) document.getElementById("custom-pauldrons").checked = (Math.random() > 0.6);

  const randomColor = () => '#' + Math.floor(Math.random()*16777215).toString(16).padStart(6, '0');
  document.getElementById("col-primary").value = randomColor();
  document.getElementById("col-accent").value = randomColor();
  document.getElementById("col-glow").value = randomColor();
  document.getElementById("col-outline").value = "#121824";

  const rSpecies = speciesList[Math.floor(Math.random() * speciesList.length)];
  const rArch = archetypes[Math.floor(Math.random() * archetypes.length)];
  const rStyle = artStyles[Math.floor(Math.random() * artStyles.length)];
  const rSeed = Math.floor(Math.random() * 2147483647);

  document.getElementById("species").value = "custom";
  document.getElementById("archetype").value = rArch;
  if (document.getElementById("art-style")) document.getElementById("art-style").value = rStyle;
  document.getElementById("seed").value = rSeed;

  const adjectives = ["astral", "void", "neon", "phantom", "cyber", "infernal", "prismatic", "dread", "chrono", "solar", "lunar", "abyssal", "toxic", "titan", "storm", "celestial"];
  const nouns = ["stalker", "sovereign", "warden", "reaper", "sentinel", "wraith", "blade", "colossus", "chimera", "vanguard", "herald", "scion", "valkyrie", "templar"];
  const randAdj = adjectives[Math.floor(Math.random() * adjectives.length)];
  const randNoun = nouns[Math.floor(Math.random() * nouns.length)];
  const randNum = Math.floor(Math.random() * 900) + 100;
  const newName = `${randAdj}_${randNoun}_${randNum}`;

  document.getElementById("char-name").value = newName;
  document.getElementById("target-scene").value = `res://scenes/${newName}_character.tscn`;

  syncCustomPrompt(true);

  log(`[RANDOM] Generated unique hybrid '${newName}' (${rStyle.toUpperCase()}, Seed: ${rSeed}) — customize anything freely!`, "ci");
  refreshGallery();
}

// ---- Status check ----
async function checkStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();

    const gBadge = document.getElementById("badge-godot");
    if (d.godot_available) {
      gBadge.className = "badge badge-online";
      gBadge.innerHTML = '<span class="badge-dot"></span> Godot 4: Ready';
    } else {
      gBadge.className = "badge badge-offline";
      gBadge.innerHTML = '<span class="badge-dot"></span> Godot 4: Not Found';
    }

    const cBadge = document.getElementById("badge-comfy");
    if (d.comfyui && d.comfyui.online) {
      if (d.comfyui.has_checkpoint) {
        cBadge.className = "badge badge-online";
        cBadge.innerHTML = `<span class="badge-dot"></span> ComfyUI: Ready (${d.comfyui.node_count} nodes)`;
      } else {
        cBadge.className = "badge badge-notice";
        cBadge.innerHTML = '<span class="badge-dot"></span> ComfyUI: Online (No Checkpoint)';
      }
    } else {
      cBadge.className = "badge badge-offline";
      cBadge.innerHTML = '<span class="badge-dot"></span> ComfyUI: Offline';
    }

    // Populate model checkpoint selector
    if (d.comfyui && d.comfyui.checkpoints && d.comfyui.checkpoints.length > 0) {
      const sel = document.getElementById("model-checkpoint");
      if (sel) {
        const currentVal = sel.value;
        const knownCkpts = [
          {val: "animagineXL_v31.safetensors", label: "Animagine XL 3.1 (SDXL Premier Anime)"},
          {val: "counterfeit_v3.safetensors",  label: "Counterfeit V3.0 (SD 1.5 Lightweight Anime)"},
          {val: "dreamshaper_8.safetensors",   label: "DreamShaper 8 (SD 1.5 Game Concept Art)"}
        ];
        d.comfyui.checkpoints.forEach(c => {
          if (!knownCkpts.some(k => k.val === c)) knownCkpts.push({val: c, label: c});
        });
        sel.innerHTML = "";
        knownCkpts.forEach(k => {
          const opt = document.createElement("option");
          opt.value = k.val;
          const isInst = d.comfyui.checkpoints.includes(k.val);
          opt.textContent = isInst ? `${k.label} [INSTALLED]` : k.label;
          if (k.val === currentVal || (!currentVal && k.val === "animagineXL_v31.safetensors")) opt.selected = true;
          sel.appendChild(opt);
        });
      }
    }
  } catch(e) {
    console.warn("[STATUS] Status check failed:", e);
    const gBadge = document.getElementById("badge-godot");
    const cBadge = document.getElementById("badge-comfy");
    if (gBadge && gBadge.textContent.includes("Checking")) {
      gBadge.className = "badge badge-offline";
      gBadge.innerHTML = '<span class="badge-dot"></span> Godot 4: Offline';
    }
    if (cBadge && cBadge.textContent.includes("Checking")) {
      cBadge.className = "badge badge-offline";
      cBadge.innerHTML = '<span class="badge-dot"></span> ComfyUI: Offline';
    }
  }
}

// ---- Gallery ----
async function refreshGallery() {
  const nameInput = document.getElementById("char-name");
  const name = nameInput ? nameInput.value.trim().toLowerCase().replace(/\\s+/g, '_') : currentCharacter;
  currentCharacter = name;
  try {
    const r = await fetch(`/api/sprites?char=${encodeURIComponent(name)}`);
    const d = await r.json();
    const grid = document.getElementById("gallery-grid");
    const empty = document.getElementById("gallery-empty");
    const title = document.getElementById("gallery-title");
    const count = document.getElementById("gallery-count");
    if (title) title.textContent = `Generated Sprite Sheet Parts (${name})`;
    if (!grid) return;
    grid.innerHTML = "";
    if (d.sprites && d.sprites.length > 0) {
      if (empty) empty.style.display = "none";
      grid.style.display = "grid";
      if (count) count.textContent = `${d.sprites.length} parts`;
      d.sprites.forEach(s => {
        const card = document.createElement("div");
        card.className = "sprite-card";
        card.onclick = () => openLightbox(s.url, s.bone, `${s.width}×${s.height}px — ${(s.size_bytes/1024).toFixed(1)} KB`);
        card.innerHTML = `
          <img class="sprite-thumb" src="${s.url}?t=${Date.now()}" alt="${s.bone}" loading="lazy">
          <div class="sprite-name">${s.bone}</div>
        `;
        grid.appendChild(card);
      });
    } else {
      grid.style.display = "none";
      if (empty) {
        empty.style.display = "block";
        empty.textContent = "No sprites generated yet for this character. Click Generate above to build them!";
      }
      if (count) count.textContent = "0 parts";
    }
  } catch(e) {
    console.error("[GALLERY] Error refreshing gallery:", e);
  }
}

// ---- Pipeline runner ----
async function runPipeline(actionType) {
  const btn = document.getElementById("btn-generate");
  const name = document.getElementById("char-name").value.trim().toLowerCase().replace(/\\s+/g, '_');
  const concept   = document.getElementById("concept").value.trim();
  const archetype = document.getElementById("archetype").value;
  const rig       = document.getElementById("rig-type").value;
  const species   = document.getElementById("species").value;
  const mode      = document.getElementById("engine-mode").value;
  const ckpt      = document.getElementById("model-checkpoint") ? document.getElementById("model-checkpoint").value : "";
  const seed      = document.getElementById("seed").value;
  const artStyle  = document.getElementById("art-style") ? document.getElementById("art-style").value : "anime";
  const detailLevel = document.getElementById("detail-level") ? parseInt(document.getElementById("detail-level").value) : 3;

  if (!name) { log("[ERROR] Character Identifier is required.", "err"); return; }

  const customColors = {
    primary: document.getElementById("col-primary").value,
    accent:  document.getElementById("col-accent").value,
    glow:    document.getElementById("col-glow").value,
    outline: document.getElementById("col-outline").value
  };
  const customFeatures = {
    head_style:    document.getElementById("custom-head").value,
    torso_style:   document.getElementById("custom-torso").value,
    hand_style:    document.getElementById("custom-hands").value,
    foot_style:    document.getElementById("custom-feet").value,
    has_wings:     document.getElementById("custom-wings").checked,
    has_tail:      document.getElementById("custom-tail").checked,
    has_halo:      document.getElementById("custom-halo") ? document.getElementById("custom-halo").checked : false,
    has_pauldrons: document.getElementById("custom-pauldrons") ? document.getElementById("custom-pauldrons").checked : false,
    detail_level:  detailLevel
  };

  btn.disabled = true;
  const origBtnHtml = btn.innerHTML;
  btn.innerHTML = '<span class="spinner"></span> Generating...';
  const startPill = document.getElementById("status-pill");
  startPill.textContent = "⏳ Processing...";
  startPill.style.color = "#d29922";

  const t0 = Date.now();

  // For rig_only, just call assemble endpoint
  if (actionType === 'rig_only') {
    log("\\n---", "warn");
    log(`[RIG] Re-rigging skeleton for '${name}' (${rig})...`, "gi");
    try {
      const r = await fetch('/api/assemble', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({character_name: name, rig_type: rig})
      });
      const res = await r.json();
      if (res.status === 'success') {
        log(`[GODOT] ✓ Scene assembled -> res://scenes/${name}_character.tscn`, "ok");
      } else {
        log(`[GODOT-ERROR] ${res.message || 'Rig build failed.'}`, "err");
        if (res.stderr) log(`  stderr: ${res.stderr}`, "err");
      }
    } catch(e) { log(`[ERROR] ${e}`, "err"); }
    const elapsed = ((Date.now() - t0)/1000).toFixed(1);
    startPill.textContent = `Done (${elapsed}s)`;
    startPill.style.color = "#3fb950";
    btn.innerHTML = origBtnHtml;
    btn.disabled = false;
    return;
  }

  log("\\n========================================================", "ci");
  log(`[PIPELINE] Starting generation for '${name}'...`, "ci");
  log(`[ENGINE] Mode: ${mode.toUpperCase()} | Style: ${artStyle.toUpperCase()} | Detail: ${detailLevel}${actionType === 'sprites_only' ? ' | Sprites Only' : ''}`, "ci");

  try {
    const r = await fetch('/api/generate', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        character_name: name, concept, archetype,
        rig_type: rig, species, mode,
        checkpoint: ckpt, seed,
        art_style: artStyle,
        detail_level: detailLevel,
        auto_rig: (actionType !== 'sprites_only'),
        custom_colors:   (species === "custom" ? customColors   : null),
        custom_features: (species === "custom" ? customFeatures : null),
      })
    });
    const res = await r.json();

    if (res.logs) {
      res.logs.forEach(l => {
        if (l.includes("[COMFYUI]") || l.includes("[DOWNLOAD]"))      log(l, "ci");
        else if (l.includes("[GODOT]"))                                log(l, "gi");
        else if (l.includes("ERROR") || l.includes("Failed"))         log(l, "err");
        else if (l.includes("WARN") || l.includes("NOTICE") || l.includes("FALLBACK")) log(l, "warn");
        else if (l.includes("[GENERATOR]"))                            log(l, "gen");
        else if (l.includes("assembled") || l.includes("success"))    log(l, "ok");
        else                                                           log(l);
      });
    }

    const elapsed = ((Date.now() - t0)/1000).toFixed(1);
    if (res.status === "success") {
      startPill.textContent = `✓ Done (${elapsed}s)`;
      startPill.style.color = "#3fb950";
    } else {
      startPill.textContent = `✗ Error (${elapsed}s)`;
      startPill.style.color = "#f85149";
    }

    refreshGallery();
  } catch(e) {
    log(`[ERROR] Pipeline exception: ${e}`, "err");
    startPill.textContent = "✗ Failed";
    startPill.style.color = "#f85149";
  } finally {
    btn.innerHTML = origBtnHtml;
    btn.disabled = false;
  }
}

// ---- Generation Queue Functions ----
let queuePollTimer = null;

async function addToQueue() {
  const name = document.getElementById("char-name").value.trim().toLowerCase().replace(/\\s+/g, '_') || "custom_character";
  const concept = document.getElementById("concept").value.trim();
  const rig = document.getElementById("rig-type").value;
  const artStyle = document.getElementById("art-style") ? document.getElementById("art-style").value : "anime";
  const detailLevel = document.getElementById("detail-level") ? parseInt(document.getElementById("detail-level").value) : 3;
  const seed = parseInt(document.getElementById("seed").value) || -1;
  const ckpt = document.getElementById("model-checkpoint") ? document.getElementById("model-checkpoint").value : "";

  const job = {
    character_name: name,
    concept: concept,
    rig_type: rig,
    art_style: artStyle,
    detail_level: detailLevel,
    seed: seed,
    checkpoint: ckpt,
    auto_rig: true
  };

  try {
    const r = await fetch('/api/queue/add', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(job)
    });
    const d = await r.json();
    log(`[QUEUE] Added '${name}' to background generation queue.`, "ok");
    pollQueue();
  } catch (e) {
    log(`[QUEUE] Error queuing job: ${e}`, "err");
  }
}

async function pollQueue() {
  try {
    const r = await fetch('/api/queue/status');
    const d = await r.json();
    renderQueue(d);

    const hasActive = d.jobs && d.jobs.some(j => j.status === 'pending' || j.status === 'running');
    if (hasActive) {
      if (!queuePollTimer) {
        queuePollTimer = setInterval(pollQueue, 2500);
      }
    } else {
      if (queuePollTimer) {
        clearInterval(queuePollTimer);
        queuePollTimer = null;
      }
    }
  } catch (e) {}
}

function renderQueue(data) {
  const list = document.getElementById("queue-list");
  const empty = document.getElementById("queue-empty");
  const badge = document.getElementById("queue-badge");

  if (!list || !empty || !badge) return;

  if (!data.jobs || data.jobs.length === 0) {
    list.style.display = "none";
    empty.style.display = "block";
    badge.style.display = "none";
    return;
  }

  empty.style.display = "none";
  list.style.display = "flex";

  const activeCount = data.counts ? (data.counts.pending + data.counts.running) : 0;
  badge.textContent = `${activeCount} active`;
  badge.style.display = activeCount > 0 ? "inline-block" : "none";

  list.innerHTML = "";
  data.jobs.forEach(j => {
    const row = document.createElement("div");
    row.style.cssText = "display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:6px;font-size:12px;gap:8px;";

    let statusColor = "var(--text-muted)";
    let statusText = j.status.toUpperCase();
    if (j.status === "running") { statusColor = "#d29922"; statusText = "⚡ RUNNING"; }
    else if (j.status === "done") { statusColor = "#3fb950"; statusText = "✓ DONE"; }
    else if (j.status === "error") { statusColor = "#f85149"; statusText = "✕ ERROR"; }
    else if (j.status === "pending") { statusColor = "#78c8ff"; statusText = "⏳ PENDING"; }

    row.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;min-width:0;flex:1;">
        <span style="font-size:11px;font-weight:600;color:${statusColor};white-space:nowrap;">${statusText}</span>
        <strong style="color:var(--text);white-space:nowrap;">${j.character_name}</strong>
        <span style="color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px;">${j.concept}</span>
      </div>
      <div style="display:flex;align-items:center;gap:6px;">
        ${(j.status === 'pending' || j.status === 'running') ? `<button class="btn btn-danger btn-sm" onclick="cancelQueueJob('${j.id}')">Cancel</button>` : ''}
        ${j.status === 'done' ? `<button class="btn btn-secondary btn-sm" onclick="switchTab('library');viewCharacter('${j.character_name}')">View</button>` : ''}
      </div>
    `;
    list.appendChild(row);
  });
}

async function cancelQueueJob(jobId) {
  try {
    await fetch('/api/queue/cancel', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({job_id: jobId})
    });
    pollQueue();
  } catch (e) {}
}

async function clearCompletedQueue() {
  try {
    await fetch('/api/queue/clear', {method: 'DELETE'});
    pollQueue();
  } catch (e) {}
}

// ---- Folder & Godot actions ----
async function openExplorer() {
  const name = document.getElementById("char-name").value.trim();
  await _openFolderFor(name);
}
async function openExplorerFor(name) { await _openFolderFor(name); }
async function _openFolderFor(name) {
  try {
    const resp = await fetch('/api/open_folder', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({character: name})
    });
    const d = await resp.json();
    if (resp.ok) log(`[SYSTEM] Opened Explorer: ${d.path}`, "ci");
    else log(`[WARN] Sprite folder not found for '${name}'.`, "warn");
  } catch(e) { log(`[ERROR] ${e}`, "err"); }
}

async function openInGodot() {
  const scene = document.getElementById("target-scene").value.trim();
  const name  = document.getElementById("char-name").value.trim();
  await _openGodotFor(name, scene);
}
async function openGodotFor(name) { await _openGodotFor(name, ""); }
async function _openGodotFor(name, scene) {
  log(`[GODOT] Launching Godot 4 Editor for '${name}'...`, "gi");
  try {
    const resp = await fetch('/api/open_godot', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({scene, character: name})
    });
    const d = await resp.json();
    if (resp.ok) log(`[GODOT] ${d.message || 'Godot 4 launched!'}`, "ok");
    else         log(`[GODOT-ERROR] ${d.message || 'Failed to launch.'}`, "err");
  } catch(e) { log(`[GODOT-ERROR] ${e}`, "err"); }
}

async function rerigChar(name) {
  const rig = document.getElementById("rig-type")?.value || "biped";
  log(`[RIG] Re-rigging '${name}'...`, "gi");
  try {
    const r = await fetch('/api/assemble', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({character_name: name, rig_type: rig})
    });
    const res = await r.json();
    if (res.status === 'success') {
      log(`[GODOT] ✓ Re-rig complete -> res://scenes/${name}_character.tscn`, "ok");
      refreshLibrary();
    } else {
      log(`[GODOT-ERROR] ${res.message || 'Re-rig failed.'}`, "err");
    }
  } catch(e) { log(`[ERROR] ${e}`, "err"); }
}

// ---- Model download ----
async function checkModelStatus() {
  try {
    const r = await fetch('/api/models/status');
    const d = await r.json();
    const pill = document.getElementById("model-status-pill");
    const cat = d.catalog || {};
    const installed = Object.values(cat).filter(m => m.installed && m.subfolder === "checkpoints");
    pill.style.color = installed.length > 0 ? "#3fb950" : "#d29922";
    pill.textContent = installed.length > 0 ? `${installed.length} Checkpoint(s) Ready` : "No Checkpoint Installed";

    // Update model catalog list
    const listEl = document.getElementById("model-catalog-list");
    if (listEl) {
      const items = Object.entries(cat);
      if (items.length === 0) {
        listEl.innerHTML = '<div style="color:var(--text-muted);font-size:12px;">No models found.</div>';
      } else {
        listEl.innerHTML = items.map(([key, m]) => `
          <div style="display:flex;align-items:center;gap:12px;padding:10px 14px;background:#10131b;border:1px solid ${m.installed ? 'rgba(46,160,67,0.3)' : 'var(--border)'};border-radius:8px;">
            <span style="font-size:18px;">${m.installed ? '✅' : '⭕'}</span>
            <div style="flex:1;min-width:0;">
              <div style="font-size:13px;font-weight:600;color:var(--text);">${m.desc || key}</div>
              <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">
                ${m.installed ? `${m.size_mb} MB installed` : `~${m.expected_mb} MB required`} • ${m.subfolder || 'models'}
              </div>
            </div>
            ${m.installed ? '<span style="font-size:11px;color:#3fb950;font-weight:600;">INSTALLED</span>' : `<span style="font-size:11px;color:var(--text-muted);">Not installed</span>`}
          </div>
        `).join('');
      }
    }

    if (d.download_state && d.download_state.active) {
      showDownloadProgress(d.download_state);
      if (!dlPollInterval) dlPollInterval = setInterval(pollDownloadProgress, 1000);
    }
  } catch(e) {}
}

let dlPollInterval = null;
async function startModelDownload() {
  const sel = document.getElementById("model-select").value;
  const btn = document.getElementById("btn-download-model");
  btn.disabled = true;
  log(`[DOWNLOAD] Requesting download for '${sel}'...`, "ci");
  try {
    const r = await fetch('/api/models/download', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({model: sel})
    });
    const d = await r.json();
    if (d.status === "started" || d.status === "in_progress") {
      document.getElementById("model-progress-wrap").style.display = "block";
      if (!dlPollInterval) dlPollInterval = setInterval(pollDownloadProgress, 1000);
    } else {
      log(`[DOWNLOAD] ${d.message || d.status}`, "warn");
      btn.disabled = false;
    }
  } catch(e) {
    log(`[DOWNLOAD-ERROR] ${e}`, "err");
    btn.disabled = false;
  }
}

async function pollDownloadProgress() {
  try {
    const r = await fetch('/api/models/progress');
    const st = await r.json();
    showDownloadProgress(st);
    if (!st.active) {
      clearInterval(dlPollInterval);
      dlPollInterval = null;
      document.getElementById("btn-download-model").disabled = false;
      checkModelStatus();
      checkStatus();
      if (st.status === "complete") log(`[DOWNLOAD] ✓ ${st.message || 'Model download complete!'}`, "ok");
      else if (st.status === "error") log(`[DOWNLOAD-ERROR] ${st.message || 'Download failed.'}`, "err");
    }
  } catch(e) {}
}

function showDownloadProgress(st) {
  document.getElementById("model-progress-wrap").style.display = "block";
  document.getElementById("model-progress-bar").style.width = `${st.pct}%`;
  document.getElementById("model-progress-text").textContent = `${st.pct}%`;
  document.getElementById("model-dl-info").textContent = `${st.model}: ${st.downloaded_mb || 0} / ${st.total_mb || 0} MB`;
  document.getElementById("model-dl-speed").textContent = `${st.speed_mbps || 0} MB/s`;
}

// ---- Lightbox ----
function openLightbox(url, title, meta) {
  const lb = document.getElementById("lightbox");
  document.getElementById("lightbox-img").src = url + "?t=" + Date.now();
  document.getElementById("lightbox-title").textContent = title;
  document.getElementById("lightbox-meta").textContent = meta || "";
  lb.classList.add("open");
}
function closeLightbox(e) {
  if (e.target === document.getElementById("lightbox")) closeLightboxDirect();
}
function closeLightboxDirect() {
  document.getElementById("lightbox").classList.remove("open");
}
document.addEventListener("keydown", e => { if (e.key === "Escape") closeLightboxDirect(); });

// ---- Asset Library ----
async function refreshLibrary() {
  const roster = document.getElementById("char-roster");
  roster.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:30px 0;font-size:12px;">🔄 Loading...</div>';
  try {
    const r = await fetch('/api/characters');
    const d = await r.json();
    allLibraryChars = d.characters || [];
    const countEl = document.getElementById("lib-char-count");
    if (countEl) countEl.textContent = `(${allLibraryChars.length} character${allLibraryChars.length === 1 ? '' : 's'})`;
    renderRoster(allLibraryChars);
  } catch(e) {
    console.error("[LIBRARY] Refresh error:", e);
    roster.innerHTML = '<div style="text-align:center;color:var(--danger);padding:30px 0;font-size:12px;">Failed to load characters. Check console for details.</div>';
  }
}

function filterRoster() {
  const q = document.getElementById("lib-search").value.toLowerCase();
  const filtered = allLibraryChars.filter(c => c.name.includes(q));
  renderRoster(filtered);
}

function renderRoster(chars) {
  const roster = document.getElementById("char-roster");
  if (!chars || chars.length === 0) {
    roster.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:40px 0;font-size:13px;">No characters found.<br>Generate one in the Generator tab!</div>';
    return;
  }
  roster.innerHTML = "";
  chars.forEach(c => {
    const item = document.createElement("div");
    item.className = "char-roster-item" + (c.name === viewingChar ? " selected" : "");
    item.onclick = () => viewCharacter(c.name);

    // Thumb: Use FULL CONNECTED BODY SPRITE PREVIEW, not just head!
    const fullUrl = c.full_preview_url || `/sprites/${c.name}/${c.name}_full.png`;
    const limbNames = (c.limbs || []).filter(l => !l.includes("_exploded") && !l.includes("_full"));
    const fallbackLimb = limbNames.find(l => l.includes("_head")) || limbNames.find(l => l.includes("_torso")) || (limbNames[0] || "");
    const fallbackUrl = fallbackLimb ? `/sprites/${c.name}/${fallbackLimb}` : '';

    const thumbHtml = `
      <img class="char-roster-thumb"
           src="${fullUrl}?t=${Date.now()}"
           alt="${c.name}"
           loading="lazy"
           onerror="this.onerror=null;${fallbackUrl ? `this.src='${fallbackUrl}?t=${Date.now()}';` : `this.style.display='none';`}">
    `;

    const sceneBadge = c.has_godot_scene
      ? '<span class="lib-badge lib-badge-scene">🎮 Scene</span>'
      : '<span class="lib-badge lib-badge-no-scene">No Scene</span>';

    item.innerHTML = `
      ${thumbHtml}
      <div class="char-roster-info">
        <div class="char-roster-name">${c.name.replace(/_/g, ' ')}</div>
        <div class="char-roster-meta">
          <span>${c.limb_count} limbs</span>
          ${sceneBadge}
        </div>
      </div>
    `;
    roster.appendChild(item);
  });
}

async function viewCharacter(name) {
  viewingChar = name;

  // Update roster selection
  document.querySelectorAll('.char-roster-item').forEach(el => el.classList.remove('selected'));
  const clickedItems = document.querySelectorAll('.char-roster-item');
  clickedItems.forEach(el => {
    if (el.querySelector('.char-roster-name')?.textContent === name.replace(/_/g, ' ')) {
      el.classList.add('selected');
    }
  });

  document.getElementById("viewer-empty").style.display = "none";
  document.getElementById("viewer-content").style.display = "block";

  const charInfo = allLibraryChars.find(c => c.name === name);
  document.getElementById("viewer-char-name").textContent = name.replace(/_/g, ' ');
  document.getElementById("viewer-char-meta").textContent = charInfo
    ? `${charInfo.limb_count} limb cutouts • ${charInfo.has_godot_scene ? 'Godot scene available' : 'No scene yet'}`
    : '';

  // Update full assembled body preview
  const fullImg = document.getElementById("viewer-full-img");
  if (fullImg) {
    fullImg.src = `/sprites/${name}/${name}_full.png?t=${Date.now()}`;
  }

  // Load sprites
  try {
    const r = await fetch(`/api/sprites?char=${encodeURIComponent(name)}`);
    const d = await r.json();
    const grid = document.getElementById("viewer-grid");
    grid.innerHTML = "";
    if (d.sprites && d.sprites.length > 0) {
      d.sprites.forEach(s => {
        const card = document.createElement("div");
        card.className = "viewer-sprite-card";
        card.onclick = () => openLightbox(s.url, s.bone, `${s.width}×${s.height}px — ${(s.size_bytes/1024).toFixed(1)} KB`);
        card.innerHTML = `
          <img class="viewer-sprite-img" src="${s.url}?t=${Date.now()}" alt="${s.bone}" loading="lazy">
          <div class="viewer-sprite-name">${s.bone}</div>
          <div class="viewer-sprite-size">${s.width}×${s.height}px</div>
        `;
        grid.appendChild(card);
      });
    } else {
      grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:var(--text-muted);padding:40px;font-size:12px;">No sprites found for this character.</div>';
    }
  } catch(e) {}
}

async function deleteChar(name) {
  if (!name) return;
  if (!confirm(`Delete character "${name}" and all its sprites/scene? This cannot be undone.`)) return;
  log(`[SYSTEM] Deleting character '${name}'...`, "warn");
  try {
    const r = await fetch('/api/character/delete', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({character_name: name})
    });
    const d = await r.json();
    if (d.status === 'success') {
      log(`[SYSTEM] ✓ Deleted: ${d.deleted.join(', ')}`, "ok");
      viewingChar = "";
      document.getElementById("viewer-empty").style.display = "flex";
      document.getElementById("viewer-content").style.display = "none";
      refreshLibrary();
    } else {
      log(`[WARN] Character '${name}' not found on disk.`, "warn");
    }
  } catch(e) { log(`[ERROR] Delete failed: ${e}`, "err"); }
}

// ---- Init ----
setActivePill('pill-cyber_alien');
checkStatus();
checkModelStatus();
refreshGallery();
pollQueue();
setInterval(checkStatus, 7000);
setInterval(checkModelStatus, 12000);
setInterval(pollQueue, 3500);
</script>
</body>
</html>
"""

def run_server(port=PORT, open_browser=True):
    actual_port = port
    server = None
    for p in range(port, port + 10):
        try:
            server = ThreadingHTTPServer((HOST, p), AutoSpriterHandler)
            server.daemon_threads = True
            actual_port = p
            break
        except OSError:
            continue

    if not server:
        print(f"[ERROR] Could not bind to any port in range {port}-{port+10}")
        return

    url = f"http://localhost:{actual_port}"
    print("\n========================================================")
    print(f"[DASHBOARD] Godot 2D Auto Spriter Dashboard Running")
    print(f"   URL: {url}")
    print(f"   Press Ctrl+C to stop")
    print("========================================================\n")

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard...")
        server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Godot 2D Auto Spriter Web Dashboard")
    parser.add_argument("--port", type=int, default=PORT, help="Port to listen on")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    args = parser.parse_args()
    run_server(port=args.port, open_browser=not args.no_browser)
