#!/usr/bin/env python3
"""
web_ui.py - Godot 2D Auto Spriter & Rigger Web Dashboard

A self-contained, browser-based graphical user interface for:
- Creating 2D humanoid and creature character rosters
- Presets: Cyber Alien, Elf Mage, Demon Fiend, Skeleton Lich, Dragonkin, Dire Beast, Mantis, Paladin, Heavy Mech
- Full "✨ Custom" mode with interactive anatomy mix & match, appendages (wings/tail), and color pickers
- Triggering ComfyUI diffusion or procedural multi-species sprite generation
- Auto-assembling Godot 4 Skeleton2D character scenes (.tscn)
- 1-click launching directly into the active 2D Godot 4 editor viewport
- Inspecting generated transparent limb cutouts in an interactive gallery

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
import subprocess
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
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
    try:
        req = urllib.request.Request(comfy_url)
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ckpts = data.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
            return {
                "online": True,
                "node_count": len(data),
                "has_layerdiffuse": "LayeredDiffusionApply" in data,
                "has_controlnet": "ControlNetLoader" in data,
                "checkpoints": ckpts,
                "has_checkpoint": len(ckpts) > 0
            }
    except Exception:
        return {"online": False, "node_count": 0, "has_layerdiffuse": False, "has_controlnet": False, "checkpoints": [], "has_checkpoint": False}


class AutoSpriterHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence default server access spam in console
        pass

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

        elif path == "/api/sprites":
            qs = urllib.parse.parse_qs(parsed.query)
            char_name = qs.get("char", [""])[0].strip().lower().replace(" ", "_")
            if not char_name:
                char_name = "cyber_alien"
            
            sprites_dir = PROJECT_ROOT / "sprites" / char_name
            files = []
            if sprites_dir.is_dir():
                for p in sorted(sprites_dir.glob("*.png")):
                    files.append({
                        "name": p.name,
                        "bone": p.stem[len(char_name)+1:] if p.stem.startswith(char_name + "_") else p.stem,
                        "url": f"/sprites/{char_name}/{p.name}",
                        "size_bytes": p.stat().st_size
                    })
            self._send_json({"character": char_name, "count": len(files), "sprites": files})
            return

        elif path.startswith("/sprites/"):
            rel = urllib.parse.unquote(path[len("/sprites/"):])
            file_path = PROJECT_ROOT / "sprites" / rel
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

            # If the target scene file doesn't exist yet, auto-assemble it if sprites exist!
            if full_scene and not full_scene.is_file():
                if not char_name:
                    char_name = full_scene.stem.replace("_character", "").replace("_rigged", "")
                sprites_dir = PROJECT_ROOT / "sprites" / char_name
                if sprites_dir.is_dir() and any(sprites_dir.glob("*.png")):
                    import server
                    rig_type = "quadruped" if "quadruped" in str(full_scene).lower() or char_name == "fenrir" else "biped"
                    server.assemble_godot_rig(
                        character_name=char_name,
                        assets_dir=f"res://sprites/{char_name}",
                        target_scene_path=f"res://scenes/{full_scene.name}",
                        rig_type=rig_type
                    )

            if full_scene and full_scene.is_file():
                res_scene = f"res://scenes/{full_scene.name}"
                rel_scene = f"scenes/{full_scene.name}"

                # 1. Write open scene request for Godot editor plugin
                try:
                    (PROJECT_ROOT / ".godot").mkdir(parents=True, exist_ok=True)
                    with open(PROJECT_ROOT / ".godot" / "open_scene_request.txt", "w", encoding="utf-8") as f:
                        f.write(res_scene)
                    with open(PROJECT_ROOT / "open_scene_request.txt", "w", encoding="utf-8") as f:
                        f.write(res_scene)
                except Exception:
                    pass

                # 2. Update project_metadata.cfg
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

                # 3. Launch Godot Editor GUI with --open-scene arg
                subprocess.Popen([godot_exe, "--path", str(PROJECT_ROOT), "-e", "--", "--open-scene", res_scene], cwd=str(PROJECT_ROOT))
                self._send_json({"status": "launched", "scene": str(full_scene), "message": f"Successfully launched Godot 4 Editor. Opening '{full_scene.name}' in 2D Viewport..."})
                return
            else:
                subprocess.Popen([godot_exe, "--path", str(PROJECT_ROOT), "-e"], cwd=str(PROJECT_ROOT))
                self._send_json({"status": "launched", "scene": "project", "message": "Opened Godot project in Godot 4 Editor."})
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

        custom_colors = payload.get("custom_colors")
        custom_features = payload.get("custom_features")

        sprites_dir = PROJECT_ROOT / "sprites" / char_name
        sprites_dir.mkdir(parents=True, exist_ok=True)

        logs = []
        logs.append(f"[INIT] Creating character '{char_name}' (Archetype: {archetype.upper()}, Rig: {rig_type.upper()})")
        logs.append(f"[CONCEPT] \"{concept}\"")

        comfy_used = False
        if mode in ["auto", "comfyui"]:
            comfy_status = _check_comfyui_status()
            if comfy_status.get("online", False) and comfy_status.get("has_checkpoint", False):
                logs.append(f"[COMFYUI] Connected to host (127.0.0.1:8188). Dispatching diffusion workflow...")
                try:
                    import server
                    gen_res_str = server.generate_character_sprites(
                        character_name=char_name,
                        archetype_prompt=concept,
                        seed=seed,
                        rig_type=rig_type
                    )
                    gen_res = json.loads(gen_res_str)
                    logs.append(f"[COMFYUI] Status: {gen_res.get('status')} (Source: {gen_res.get('source')})")
                    comfy_used = (gen_res.get("source") == "comfyui_api")
                except Exception as e:
                    logs.append(f"[COMFYUI-WARN] API error: {e}")
            elif comfy_status.get("online", False) and not comfy_status.get("has_checkpoint", False):
                logs.append(f"[COMFYUI-NOTICE] ComfyUI online but animagineXL checkpoint is missing. Engaging Advanced Procedural Spriter...")

        if not comfy_used:
            from scripts.generate_sample_sprites import generate_all, generate_quadruped, detect_species
            detected_sp = species if (species and species != "auto") else detect_species(concept, archetype)
            logs.append(f"[GENERATOR] Synthesizing {detected_sp.upper()} anatomy for '{char_name}' (Seed: {seed if seed >= 0 else 'Procedural'})...")
            
            if rig_type == "quadruped" or archetype == "beast" or detected_sp == "beast":
                parts = generate_quadruped(str(sprites_dir), prefix=char_name, archetype=archetype, prompt=concept, seed=seed)
            else:
                parts = generate_all(
                    str(sprites_dir),
                    prefix=char_name,
                    archetype=archetype,
                    prompt=concept,
                    seed=seed,
                    custom_colors=custom_colors,
                    custom_features=custom_features
                )
            parts = parts or []
            logs.append(f"[GENERATOR] Created {len(parts)} {detected_sp.upper()} transparent limb cutouts in: res://sprites/{char_name}")

        # Assemble Godot rig if requested
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
                    logs.append(f"[GODOT] Scene assembled and saved successfully -> {scene_path}")
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
# Modern Embedded Web Dashboard
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
    --text: #e6edf3;
    --text-muted: #8b949e;
    --console-bg: #07090e;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  body { background-color: var(--bg-dark); color: var(--text); padding: 20px; line-height: 1.5; }
  .container { max-width: 1240px; margin: 0 auto; }
  
  header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 18px; border-bottom: 1px solid var(--border); margin-bottom: 22px; flex-wrap: wrap; gap: 12px; }
  .logo { display: flex; align-items: center; gap: 12px; }
  .logo-icon { width: 38px; height: 38px; background: linear-gradient(135deg, var(--primary), var(--accent-purple)); border-radius: 9px; display: flex; align-items: center; justify-content: center; font-weight: 800; color: white; font-size: 18px; }
  .logo-text h1 { font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
  .logo-text p { font-size: 12px; color: var(--text-muted); }
  
  .badges { display: flex; gap: 8px; flex-wrap: wrap; }
  .badge { padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 6px; border: 1px solid transparent; }
  .badge-dot { width: 8px; height: 8px; border-radius: 50%; }
  .badge-online { background: rgba(46, 160, 67, 0.15); color: #3fb950; border-color: rgba(46, 160, 67, 0.3); }
  .badge-online .badge-dot { background: #3fb950; box-shadow: 0 0 6px #3fb950; }
  .badge-offline { background: rgba(248, 81, 73, 0.15); color: #f85149; border-color: rgba(248, 81, 73, 0.3); }
  .badge-offline .badge-dot { background: #f85149; }
  .badge-notice { background: rgba(210, 153, 34, 0.15); color: #d29922; border-color: rgba(210, 153, 34, 0.3); }
  .badge-notice .badge-dot { background: #d29922; }

  .grid { display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 24px; margin-bottom: 24px; }
  @media (max-width: 950px) { .grid { grid-template-columns: 1fr; } }

  .card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.35); }
  .card-title { font-size: 15px; font-weight: 600; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; color: var(--primary); }

  .form-group { margin-bottom: 14px; }
  label { display: block; font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px; }
  input[type="text"], select, textarea { width: 100%; background: var(--bg-input); border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px; color: var(--text); font-size: 13px; transition: border-color 0.2s; }
  input[type="text"]:focus, select:focus, textarea:focus { border-color: var(--primary); outline: none; box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.15); }
  textarea { resize: vertical; min-height: 75px; }

  .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
  .row-4 { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 8px; }

  .btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 10px 16px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; transition: all 0.2s; }
  .btn-primary { background: var(--primary); color: #07090e; width: 100%; font-size: 14px; padding: 12px; font-weight: 700; }
  .btn-primary:hover { background: var(--primary-hover); transform: translateY(-1px); }
  .btn-secondary { background: #1c222e; border: 1px solid var(--border); color: var(--text); }
  .btn-secondary:hover { background: #262e3d; border-color: #8b949e; }
  .btn-icon { padding: 6px 10px; font-size: 12px; }

  .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 14px; }

  .accordion { border: 1px solid var(--border); border-radius: 8px; margin-top: 14px; overflow: hidden; }
  .accordion-header { background: #11141c; padding: 10px 14px; font-size: 12px; font-weight: 600; color: var(--text-muted); cursor: pointer; display: flex; justify-content: space-between; user-select: none; }
  .accordion-header:hover { color: var(--text); }
  .accordion-content { padding: 14px; background: var(--bg-card); display: none; }
  .accordion-content.open { display: block; }

  .console { background: var(--console-bg); border: 1px solid var(--border); border-radius: 8px; padding: 12px; font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: 12px; color: #7ee787; height: 260px; overflow-y: auto; white-space: pre-wrap; line-height: 1.45; }
  .console .info { color: #58a6ff; }
  .console .warn { color: #d29922; }
  .console .err { color: #f85149; }

  .gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(95px, 1fr)); gap: 10px; max-height: 280px; overflow-y: auto; padding: 4px; }
  .sprite-card { background: #10131b; border: 1px solid var(--border); border-radius: 6px; padding: 6px; text-align: center; }
  .sprite-thumb { width: 100%; height: 74px; object-fit: contain; background: repeating-conic-gradient(#1a1f2c 0% 25%, #121620 0% 50%) 50% / 12px 12px; border-radius: 4px; }
  .sprite-name { font-size: 10px; color: var(--text-muted); margin-top: 4px; word-break: break-all; font-weight: 500; }

  .quick-presets { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 14px; }
  .preset-pill { font-size: 11px; padding: 5px 11px; border-radius: 14px; background: #191f2b; border: 1px solid var(--border); cursor: pointer; color: var(--text-muted); transition: all 0.15s; }
  .preset-pill:hover { border-color: var(--primary); color: var(--primary); transform: translateY(-1px); }
  .preset-custom { background: rgba(227, 179, 65, 0.15); border-color: rgba(227, 179, 65, 0.4); color: #f0c654; font-weight: 700; }
  .preset-custom:hover { background: rgba(227, 179, 65, 0.25); border-color: #f0c654; color: #ffd666; }

  .color-picker-box { display: flex; align-items: center; gap: 8px; background: var(--bg-input); padding: 6px 10px; border-radius: 6px; border: 1px solid var(--border); }
  .color-picker-box input[type="color"] { border: none; width: 28px; height: 28px; border-radius: 4px; background: transparent; cursor: pointer; }
  .color-picker-box span { font-size: 11px; color: var(--text-muted); font-weight: 600; }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">
      <div class="logo-icon">2D</div>
      <div class="logo-text">
        <h1>Godot 2D Auto Spriter & Rigger</h1>
        <p>Dynamic Multi-Species Creature & Humanoid Generator with 1-Click Godot 4 Auto-Rigging</p>
      </div>
    </div>
    <div class="badges">
      <div id="badge-godot" class="badge badge-offline"><span class="badge-dot"></span> Godot 4: Checking...</div>
      <div id="badge-comfy" class="badge badge-offline"><span class="badge-dot"></span> ComfyUI: Checking...</div>
    </div>
  </header>

  <div class="grid">
    <!-- Configuration Column -->
    <div class="card">
      <div class="card-title">
        <span>Character & Creature Creator</span>
        <span style="font-size: 11px; color: var(--text-muted);">Procedural & Diffusion Controls</span>
      </div>

      <div class="form-group">
        <label>Archetype & Creature Presets:</label>
        <div class="quick-presets">
          <span class="preset-pill preset-custom" onclick="applyCustomMode()">✨ Custom Creature</span>
          <span class="preset-pill" onclick="applyPreset('cyber_alien', 'cyberpunk warrior alien with neon bioluminescent crest, plasma blade and chitin plates', 'warrior', 'biped', 'alien')">👾 Cyber Alien</span>
          <span class="preset-pill" onclick="applyPreset('elven_sorceress', 'female elf sorceress with flowing purple hair, arcane glowing robes and crystal staff', 'mage', 'biped', 'humanoid')">🧝 Elf Mage</span>
          <span class="preset-pill" onclick="applyPreset('winged_demon', 'crimson demon lord with obsidian curved horns, runic chest brand, shadow talons and wings', 'assassin', 'biped', 'demon')">😈 Demon Fiend</span>
          <span class="preset-pill" onclick="applyPreset('skeleton_lich', 'undead skeleton lich with glowing cyan soul eyes, bone ribcage and tattered shroud', 'mage', 'biped', 'undead')">💀 Skeleton Lich</span>
          <span class="preset-pill" onclick="applyPreset('dragonkin_brawler', 'emerald dragonkin warrior with horned brow, ridge scales and reptilian claws', 'warrior', 'biped', 'reptilian')">🦎 Dragonkin</span>
          <span class="preset-pill" onclick="applyPreset('celestial_wolf', 'mythical celestial dire wolf with emerald predator eyes, multi tail and fur ruff', 'beast', 'quadruped', 'beast')">🐺 Dire Beast</span>
          <span class="preset-pill" onclick="applyPreset('mantis_stalker', 'insectoid mantis assassin with compound phosphor eyes, chitin carapace and scythe claws', 'assassin', 'biped', 'insectoid')">🦗 Mantis</span>
          <span class="preset-pill" onclick="applyPreset('holy_paladin', 'noble human paladin in regal blue and gold armor with glowing blade', 'warrior', 'biped', 'humanoid')">⚔️ Paladin</span>
          <span class="preset-pill" onclick="applyPreset('diesel_mech', 'heavy dieselpunk mech juggernaut with caution hazard stripes and furnace core', 'mech', 'biped', 'mech')">🤖 Heavy Mech</span>
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
          <label for="species">Species & Anatomy:</label>
          <select id="species" onchange="onSpeciesDropdownChanged()">
            <option value="custom">✨ Custom / Hybrid (User-Defined Anatomy)</option>
            <option value="alien" selected>👾 Cyber Alien (Elongated Cranium, Bio-Crest, Talons)</option>
            <option value="humanoid">🧝 Human / Elf (Anime Face, Hair, Tunic/Robes, Boots)</option>
            <option value="demon">😈 Demon / Fiend (Curved Horns, Runic Brand, Talons)</option>
            <option value="undead">💀 Undead / Skeleton (Bone Skull, Ribcage, Soul Core)</option>
            <option value="reptilian">🦎 Dragonkin (Snout, Ridge Horns, Scales)</option>
            <option value="beast">🐺 Dire Beast (Predatory Snout, Paws, Fur)</option>
            <option value="insectoid">🦗 Mantis (Antennae, Compound Eyes, Carapace)</option>
            <option value="mech">🤖 Heavy Mech (Visor Slits, Armor Plates, Pistons)</option>
            <option value="auto">Auto-Detect from Concept Prompt</option>
          </select>
        </div>
      </div>

      <!-- Custom Design Studio (Anatomy Mix & Match & Colors) -->
      <div id="custom-studio" class="accordion" style="border-color: rgba(227, 179, 65, 0.35);">
        <div class="accordion-header" style="background: rgba(227, 179, 65, 0.1); color: #f0c654;" onclick="toggleCustomStudio()">
          <span>🎨 Custom Creature Studio (Anatomy Mixing, Wings/Tail & Colors)</span>
          <span id="custom-studio-arrow">▼</span>
        </div>
        <div id="custom-studio-body" class="accordion-content">
          <div class="row-2" style="margin-bottom: 12px;">
            <div class="form-group">
              <label for="custom-head">Head Shape / Style:</label>
              <select id="custom-head" onchange="syncCustomPrompt()">
                <option value="alien">👾 Alien Cranium (Bio-Crest & Vents)</option>
                <option value="humanoid">🧝 Humanoid / Elf (Anime Hair & Face)</option>
                <option value="demon">😈 Demon Horns & Fangs</option>
                <option value="undead">💀 Bony Skull & Soul Flame</option>
                <option value="reptilian">🦎 Dragon Brow Horns & Snout</option>
                <option value="insectoid">🦗 Mantis Antennae & Compound Eyes</option>
                <option value="beast">🐺 Beast / Wolf Snout & Ears</option>
                <option value="mech">🤖 Mech Visor & Armor Helmet</option>
              </select>
            </div>
            <div class="form-group">
              <label for="custom-torso">Torso Style:</label>
              <select id="custom-torso" onchange="syncCustomPrompt()">
                <option value="alien">Biomechanical Carapace & Core</option>
                <option value="humanoid">Cloth Tunic / Robes / Vest</option>
                <option value="demon">Muscular Demonic Runic Brand</option>
                <option value="undead">Exposed Skeletal Ribcage</option>
                <option value="reptilian">Overlapping Dragon Scutes</option>
                <option value="insectoid">Segmented Chitin Thorax</option>
                <option value="mech">Plated Armor & Furnace</option>
              </select>
            </div>
          </div>

          <div class="row-2" style="margin-bottom: 12px;">
            <div class="form-group">
              <label for="custom-hands">Hands / Claws Style:</label>
              <select id="custom-hands" onchange="syncCustomPrompt()">
                <option value="alien">Alien Elongated Talons</option>
                <option value="humanoid">Humanoid Articulated Fingers</option>
                <option value="demon">Sharp Obsidian Demonic Claws</option>
                <option value="undead">Bony Skeletal Digits</option>
                <option value="reptilian">Heavy Dragon Claws</option>
              </select>
            </div>
            <div class="form-group">
              <label for="custom-feet">Feet / Base Style:</label>
              <select id="custom-feet" onchange="syncCustomPrompt()">
                <option value="alien">Digitigrade Alien Talons</option>
                <option value="humanoid">Adventurer Boots / Sandals</option>
                <option value="demon">Cloven Hooves / Raptor Spurs</option>
                <option value="undead">Skeletal Foot Bones</option>
                <option value="reptilian">Raptor / Dragon Claw Feet</option>
              </select>
            </div>
          </div>

          <div class="row-2" style="margin-bottom: 14px;">
            <div class="form-group">
              <label>Custom Appendages:</label>
              <div style="display: flex; gap: 16px; align-items: center; padding-top: 4px;">
                <label style="display: flex; align-items: center; gap: 6px; cursor: pointer; color: var(--text);">
                  <input type="checkbox" id="custom-wings" onchange="syncCustomPrompt()"> 🪽 Add Wings
                </label>
                <label style="display: flex; align-items: center; gap: 6px; cursor: pointer; color: var(--text);">
                  <input type="checkbox" id="custom-tail" onchange="syncCustomPrompt()"> 🐉 Add Tail
                </label>
              </div>
            </div>
          </div>

          <label style="margin-bottom: 8px;">Interactive Custom Color Palette:</label>
          <div class="row-4" style="margin-bottom: 6px;">
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

      <div class="row-2" style="margin-top: 14px;">
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
            <option value="warrior" selected>Warrior (Paladin Cobalt & Regal Amber Gold)</option>
            <option value="mage">Mage (Deep Arcane Violet & Arcane Magenta)</option>
            <option value="assassin">Assassin (Midnight Obsidian & Crimson Blood)</option>
            <option value="ranger">Ranger (Forest Greens & Emerald Nature)</option>
            <option value="mech">Mech (Gunmetal & Amber Furnace Core)</option>
            <option value="beast">Beast (Shadow Fur & Emerald Core)</option>
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
              <label for="seed">Variation Seed (-1 for Random):</label>
              <div style="display: flex; gap: 8px;">
                <input type="text" id="seed" value="-1">
                <button type="button" class="btn btn-secondary btn-icon" onclick="randomizeSeed()" title="Roll new random seed">🎲 Random</button>
              </div>
            </div>
            <div class="form-group">
              <label for="engine-mode">Generation Engine:</label>
              <select id="engine-mode">
                <option value="auto" selected>Auto (ComfyUI with Smart Spriter Fallback)</option>
                <option value="local">Smart Procedural Spriter (Offline / Instant)</option>
                <option value="comfyui">ComfyUI Generative Diffusion Only</option>
              </select>
            </div>
          </div>
          <div class="form-group">
            <label for="target-scene">Target Godot Scene Destination:</label>
            <input type="text" id="target-scene" value="res://scenes/cyber_alien_character.tscn">
          </div>
        </div>
      </div>

      <div style="margin-top: 18px;">
        <button id="btn-generate" class="btn btn-primary" onclick="runPipeline('generate')">
          🚀 Generate & Assemble Full Character Scene
        </button>
      </div>

      <div class="actions">
        <button class="btn btn-secondary" onclick="runPipeline('sprites_only')">🎨 Generate Sprites Only</button>
        <button class="btn btn-secondary" onclick="runPipeline('rig_only')">🦴 Auto-Rig Skeleton Scene</button>
      </div>
    </div>

    <!-- Live Console & Asset Output Column -->
    <div style="display: flex; flex-direction: column; gap: 24px;">
      <!-- Console Card -->
      <div class="card">
        <div class="card-title">
          <span>Execution Log Console</span>
          <span id="status-pill" style="font-size: 11px; color: var(--text-muted);">Idle</span>
        </div>
        <div id="console" class="console">[System Ready] Enter a character concept, choose a preset, or click ✨ Custom Creature!</div>
      </div>

      <!-- Assets Preview Card -->
      <div class="card" style="flex: 1;">
        <div class="card-title">
          <span>Transparent Limb Cutouts</span>
          <div style="display: flex; gap: 6px;">
            <button class="btn btn-secondary" style="padding: 5px 12px; font-size: 11px;" onclick="openExplorer()">📁 Open Folder</button>
            <button class="btn btn-secondary" style="padding: 5px 12px; font-size: 11px;" onclick="openInGodot()">🎮 Open in Godot</button>
          </div>
        </div>
        <div id="sprite-gallery" class="gallery">
          <!-- Filled dynamically via JS -->
        </div>
      </div>
    </div>
  </div>
</div>

<script>
  let currentCharacter = "cyber_alien";

  function log(msg, type = "normal") {
    const c = document.getElementById("console");
    const span = document.createElement("span");
    if (type === "info") span.className = "info";
    if (type === "warn") span.className = "warn";
    if (type === "err") span.className = "err";
    span.textContent = msg + "\\n";
    c.appendChild(span);
    c.scrollTop = c.scrollHeight;
  }

  function randomizeSeed() {
    const newSeed = Math.floor(Math.random() * 2147483647);
    document.getElementById("seed").value = newSeed;
    log(`[SEED] Generated random variation seed: ${newSeed}`, "info");
  }

  function toggleAccordion() {
    const b = document.getElementById("accordion-body");
    const arr = document.getElementById("accordion-arrow");
    if (b.classList.contains("open")) {
      b.classList.remove("open");
      arr.textContent = "▼";
    } else {
      b.classList.add("open");
      arr.textContent = "▲";
    }
  }

  function toggleCustomStudio(forceOpen = false) {
    const b = document.getElementById("custom-studio-body");
    const arr = document.getElementById("custom-studio-arrow");
    if (forceOpen || !b.classList.contains("open")) {
      b.classList.add("open");
      arr.textContent = "▲";
    } else {
      b.classList.remove("open");
      arr.textContent = "▼";
    }
  }

  function applyCustomMode() {
    document.getElementById("char-name").value = "custom_creature";
    document.getElementById("species").value = "custom";
    document.getElementById("target-scene").value = `res://scenes/custom_creature_character.tscn`;
    toggleCustomStudio(true);
    syncCustomPrompt();
    log(`[CUSTOM] Activated Custom Creature Studio. Customize anatomy, wings, and colors!`, "info");
    refreshGallery();
  }

  function onSpeciesDropdownChanged() {
    const sp = document.getElementById("species").value;
    if (sp === "custom") {
      toggleCustomStudio(true);
    }
  }

  function syncCustomPrompt() {
    const head = document.getElementById("custom-head").value;
    const torso = document.getElementById("custom-torso").value;
    const wings = document.getElementById("custom-wings").checked;
    const tail = document.getElementById("custom-tail").checked;
    const pCol = document.getElementById("col-primary").value;
    const gCol = document.getElementById("col-glow").value;

    let desc = `custom hybrid creature with ${head} head silhouette, ${torso} body`;
    if (wings) desc += ", large spreading wings";
    if (tail) desc += ", articulated tail";
    desc += `, primary color ${pCol} and glowing core ${gCol}`;

    document.getElementById("concept").value = desc;
  }

  function applyPreset(name, concept, arch, rig, species = "auto") {
    document.getElementById("char-name").value = name;
    document.getElementById("concept").value = concept;
    document.getElementById("archetype").value = arch;
    document.getElementById("rig-type").value = rig;
    document.getElementById("species").value = species;
    document.getElementById("target-scene").value = `res://scenes/${name}_character.tscn`;
    currentCharacter = name;

    // Adjust studio defaults for visual convenience
    if (species === "alien") {
      document.getElementById("custom-head").value = "alien";
      document.getElementById("custom-torso").value = "alien";
      document.getElementById("col-primary").value = "#2b4764";
      document.getElementById("col-glow").value = "#00f0ff";
    } else if (species === "demon") {
      document.getElementById("custom-head").value = "demon";
      document.getElementById("custom-torso").value = "demon";
      document.getElementById("col-primary").value = "#5f1c2a";
      document.getElementById("col-glow").value = "#ff2d1e";
    } else if (species === "undead") {
      document.getElementById("custom-head").value = "undead";
      document.getElementById("custom-torso").value = "undead";
      document.getElementById("col-primary").value = "#a09b91";
      document.getElementById("col-glow").value = "#00f0ff";
    }

    log(`[PRESET] Loaded '${name}' (${species.toUpperCase()}, ${rig.toUpperCase()})`, "info");
    refreshGallery();
  }

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
          cBadge.innerHTML = `<span class="badge-dot"></span> ComfyUI: Online (Using Smart Spriter)`;
        }
      } else {
        cBadge.className = "badge badge-offline";
        cBadge.innerHTML = '<span class="badge-dot"></span> ComfyUI: Offline (Using Smart Spriter)';
      }
    } catch (e) {
      console.warn("Status check failed:", e);
    }
  }

  async function refreshGallery() {
    const name = document.getElementById("char-name").value.trim().toLowerCase().replace(/\\s+/g, '_');
    currentCharacter = name;
    try {
      const r = await fetch(`/api/sprites?char=${name}`);
      const d = await r.json();
      const g = document.getElementById("sprite-gallery");
      g.innerHTML = "";
      if (d.sprites && d.sprites.length > 0) {
        d.sprites.forEach(s => {
          const card = document.createElement("div");
          card.className = "sprite-card";
          card.innerHTML = `
            <img class="sprite-thumb" src="${s.url}?t=${Date.now()}" alt="${s.bone}">
            <div class="sprite-name">${s.bone}</div>
          `;
          g.appendChild(card);
        });
      } else {
        g.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 45px 0; font-size: 12px;">No limb cutouts extracted for this character yet. Click Generate above!</div>';
      }
    } catch (e) {}
  }

  async function runPipeline(actionType) {
    const btn = document.getElementById("btn-generate");
    const name = document.getElementById("char-name").value.trim().toLowerCase().replace(/\\s+/g, '_');
    const concept = document.getElementById("concept").value.trim();
    const archetype = document.getElementById("archetype").value;
    const rig = document.getElementById("rig-type").value;
    const species = document.getElementById("species").value;
    const mode = document.getElementById("engine-mode").value;
    const seed = document.getElementById("seed").value;

    const customColors = {
      primary: document.getElementById("col-primary").value,
      accent: document.getElementById("col-accent").value,
      glow: document.getElementById("col-glow").value,
      outline: document.getElementById("col-outline").value
    };

    const customFeatures = {
      head_style: document.getElementById("custom-head").value,
      torso_style: document.getElementById("custom-torso").value,
      hand_style: document.getElementById("custom-hands").value,
      foot_style: document.getElementById("custom-feet").value,
      has_wings: document.getElementById("custom-wings").checked,
      has_tail: document.getElementById("custom-tail").checked
    };

    btn.disabled = true;
    document.getElementById("status-pill").textContent = "Processing...";
    log(`\\n========================================================`, "info");
    log(`[PIPELINE] Starting generation sequence for '${name}'...`, "info");

    try {
      const r = await fetch('/api/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          character_name: name,
          concept: concept,
          archetype: archetype,
          rig_type: rig,
          species: species,
          custom_colors: (species === "custom" ? customColors : null),
          custom_features: (species === "custom" ? customFeatures : null),
          mode: mode,
          seed: seed,
          auto_rig: (actionType !== 'sprites_only')
        })
      });
      const res = await r.json();
      if (res.logs) {
        res.logs.forEach(l => {
          if (l.includes("ERROR") || l.includes("Failed")) log(l, "err");
          else if (l.includes("WARN") || l.includes("NOTICE")) log(l, "warn");
          else log(l, "info");
        });
      }
      document.getElementById("status-pill").textContent = res.status === "success" ? "Done" : "Error";
      refreshGallery();
    } catch (e) {
      log(`[ERROR] Pipeline exception: ${e}`, "err");
      document.getElementById("status-pill").textContent = "Failed";
    } finally {
      btn.disabled = false;
    }
  }

  async function openExplorer() {
    const name = document.getElementById("char-name").value.trim();
    try {
      const resp = await fetch('/api/open_folder', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({character: name})
      });
      const data = await resp.json();
      if (resp.ok) {
        log(`[SYSTEM] Opened Explorer to sprites directory: ${data.path}`, "info");
      } else {
        log(`[WARN] Sprite folder not found for '${name}'. Generate sprites first!`, "warn");
      }
    } catch (e) {
      log(`[ERROR] Could not open folder: ${e}`, "err");
    }
  }

  async function openInGodot() {
    const scene = document.getElementById("target-scene").value.trim();
    const name = document.getElementById("char-name").value.trim();
    log(`[GODOT] Requesting Godot 4 Editor for '${scene}'...`, "info");
    try {
      const resp = await fetch('/api/open_godot', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({scene: scene, character: name})
      });
      const data = await resp.json();
      if (resp.ok) {
        log(`[GODOT] ${data.message || 'Godot 4 Editor launched successfully!'}`, "info");
      } else {
        log(`[GODOT-ERROR] ${data.message || 'Failed to launch Godot'}`, "err");
      }
    } catch (e) {
      log(`[GODOT-ERROR] Failed to connect to server: ${e}`, "err");
    }
  }

  // Initial load
  checkStatus();
  refreshGallery();
  setInterval(checkStatus, 6000);
</script>
</body>
</html>
"""

def run_server(port=PORT, open_browser=True):
    actual_port = port
    server = None
    for p in range(port, port + 10):
        try:
            server = HTTPServer((HOST, p), AutoSpriterHandler)
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
