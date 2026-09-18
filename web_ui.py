#!/usr/bin/env python3
"""
web_ui.py - Godot 2D Auto Spriter & Rigger Web Dashboard

A self-contained, browser-based graphical user interface for:
- Creating 2D humanoid and quadruped character rosters
- Configuring custom prompts, archetypes, seeds, and control parameters
- Triggering ComfyUI or offline sprite generation
- Auto-assembling Godot 4 Skeleton2D character scenes
- Inspecting generated transparent limb cutouts in an interactive gallery

Can be run via:
  python web_ui.py
  launch_ui.bat
  Godot2dAutoSpriterUI.exe (compiled PyInstaller standalone)
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

def _check_comfyui_status() -> dict:
    comfy_url = "http://127.0.0.1:8188/object_info"
    try:
        req = urllib.request.Request(comfy_url)
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "online": True,
                "node_count": len(data),
                "has_layerdiffuse": "LayeredDiffusionApply" in data,
                "has_controlnet": "ControlNetLoader" in data
            }
    except Exception:
        return {"online": False, "node_count": 0, "has_layerdiffuse": False, "has_controlnet": False}


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
            godot_exe = _find_godot_executable()
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
                char_name = "warrior"
            
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
            # Serve local sprite files safely
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
            char_name = payload.get("character", "warrior")
            folder = PROJECT_ROOT / "sprites" / char_name
            if folder.is_dir():
                os.startfile(str(folder))
                self._send_json({"status": "opened", "path": str(folder)})
            else:
                self._send_json({"status": "not_found", "path": str(folder)}, 404)
            return

        elif path == "/api/open_godot":
            scene_path = payload.get("scene", "")
            godot_exe = _find_godot_executable()
            if godot_exe and scene_path:
                full_scene = PROJECT_ROOT / scene_path.replace("res://", "")
                if full_scene.is_file():
                    subprocess.Popen([godot_exe, "--editor", str(full_scene)], cwd=str(PROJECT_ROOT))
                    self._send_json({"status": "launched", "scene": str(full_scene)})
                    return
            self._send_json({"status": "error", "message": "Could not launch scene"}, 400)
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
        char_name = payload.get("character_name", "cyber_warrior").strip().lower().replace(" ", "_")
        if not char_name:
            char_name = "cyber_warrior"
        concept = payload.get("concept", "cyberpunk warrior alien with glowing neon visor, modular armor, plasma blade")
        archetype = payload.get("archetype", "warrior")
        rig_type = payload.get("rig_type", "biped")
        mode = payload.get("mode", "auto")
        seed = int(payload.get("seed", -1))
        auto_rig = payload.get("auto_rig", True)

        sprites_dir = PROJECT_ROOT / "sprites" / char_name
        sprites_dir.mkdir(parents=True, exist_ok=True)

        logs = []
        logs.append(f"[INIT] Creating character '{char_name}' (Archetype: {archetype.upper()}, Rig: {rig_type.upper()})")
        logs.append(f"[PROMPT] {concept}")

        comfy_used = False
        if mode in ["auto", "comfyui"]:
            comfy_status = _check_comfyui_status()
            if comfy_status.get("online", False):
                logs.append(f"[COMFYUI] Connected to host (127.0.0.1:8188). Dispatching generation workflow...")
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

        if not comfy_used:
            logs.append(f"[GENERATOR] Generating stylized cut-out limb sprite set (alpha transparent RGBA)...")
            from scripts.generate_sample_sprites import generate_all, generate_quadruped
            if rig_type == "quadruped" or archetype == "beast":
                parts = generate_quadruped(str(sprites_dir), prefix=char_name, archetype="assassin" if archetype == "beast" else archetype)
            else:
                parts = generate_all(str(sprites_dir), prefix=char_name, archetype=archetype)
            parts = parts or []
            logs.append(f"[GENERATOR] Generated {len(parts)} limb sprites in: res://sprites/{char_name}")

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
# Modern Embedded Web Dashboard (Single-File Autonomous Front-End)
# ==============================================================================
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Godot 2D Auto Spriter & Rigger</title>
<style>
  :root {
    --bg-dark: #0f1117;
    --bg-card: #181c26;
    --bg-input: #12151d;
    --border: #283042;
    --border-glow: #388bfd;
    --primary: #58a6ff;
    --primary-hover: #1f6feb;
    --accent: #2ea043;
    --accent-purple: #bc8cff;
    --text: #e6edf3;
    --text-muted: #8b949e;
    --console-bg: #090b10;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  body { background-color: var(--bg-dark); color: var(--text); padding: 20px; line-height: 1.5; }
  .container { max-width: 1200px; margin: 0 auto; }
  
  header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 20px; border-bottom: 1px solid var(--border); margin-bottom: 24px; }
  .logo { display: flex; align-items: center; gap: 12px; }
  .logo-icon { width: 36px; height: 36px; background: linear-gradient(135deg, var(--primary), var(--accent-purple)); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: bold; color: white; font-size: 20px; }
  .logo-text h1 { font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }
  .logo-text p { font-size: 12px; color: var(--text-muted); }
  
  .badges { display: flex; gap: 8px; }
  .badge { padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; display: flex; align-items: center; gap: 6px; border: 1px solid transparent; }
  .badge-dot { width: 8px; height: 8px; border-radius: 50%; }
  .badge-online { background: rgba(46, 160, 67, 0.15); color: #3fb950; border-color: rgba(46, 160, 67, 0.3); }
  .badge-online .badge-dot { background: #3fb950; box-shadow: 0 0 6px #3fb950; }
  .badge-offline { background: rgba(248, 81, 73, 0.15); color: #f85149; border-color: rgba(248, 81, 73, 0.3); }
  .badge-offline .badge-dot { background: #f85149; }

  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }
  @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }

  .card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
  .card-title { font-size: 15px; font-weight: 600; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; color: var(--primary); }

  .form-group { margin-bottom: 14px; }
  label { display: block; font-size: 12px; font-weight: 600; color: var(--text-muted); margin-bottom: 6px; }
  input[type="text"], select, textarea { width: 100%; background: var(--bg-input); border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px; color: var(--text); font-size: 13px; transition: border-color 0.2s; }
  input[type="text"]:focus, select:focus, textarea:focus { border-color: var(--primary); outline: none; box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.15); }
  textarea { resize: vertical; min-height: 70px; }

  .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }

  .btn { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 10px 16px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; transition: all 0.2s; }
  .btn-primary { background: var(--primary); color: #0d1117; width: 100%; font-size: 14px; padding: 12px; }
  .btn-primary:hover { background: #79b8ff; transform: translateY(-1px); }
  .btn-secondary { background: #21262d; border: 1px solid var(--border); color: var(--text); }
  .btn-secondary:hover { background: #30363d; border-color: #8b949e; }

  .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 14px; }

  .accordion { border: 1px solid var(--border); border-radius: 8px; margin-top: 14px; overflow: hidden; }
  .accordion-header { background: #131720; padding: 10px 14px; font-size: 12px; font-weight: 600; color: var(--text-muted); cursor: pointer; display: flex; justify-content: space-between; user-select: none; }
  .accordion-content { padding: 14px; background: var(--bg-card); display: none; }
  .accordion-content.open { display: block; }

  .console { background: var(--console-bg); border: 1px solid var(--border); border-radius: 8px; padding: 12px; font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; font-size: 12px; color: #7ee787; height: 260px; overflow-y: auto; white-space: pre-wrap; line-height: 1.4; }
  .console .info { color: #58a6ff; }
  .console .warn { color: #d29922; }
  .console .err { color: #f85149; }

  .gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(90px, 1fr)); gap: 10px; max-height: 260px; overflow-y: auto; padding: 4px; }
  .sprite-card { background: #131720; border: 1px solid var(--border); border-radius: 6px; padding: 6px; text-align: center; }
  .sprite-thumb { width: 100%; height: 70px; object-fit: contain; background: repeating-conic-gradient(#1f2430 0% 25%, #161a22 0% 50%) 50% / 12px 12px; border-radius: 4px; }
  .sprite-name { font-size: 10px; color: var(--text-muted); margin-top: 4px; word-break: break-all; }

  .quick-presets { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
  .preset-pill { font-size: 11px; padding: 3px 8px; border-radius: 12px; background: #21262d; border: 1px solid var(--border); cursor: pointer; color: var(--text-muted); }
  .preset-pill:hover { border-color: var(--primary); color: var(--primary); }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo">
      <div class="logo-icon">2D</div>
      <div class="logo-text">
        <h1>Godot 2D Auto Spriter & Rigger</h1>
        <p>Automated Sprite Generation, SAM Modular Slicing & Godot 4 Skeletal Assembly</p>
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
        <span>Character Specifications</span>
        <span style="font-size: 11px; color: var(--text-muted);">Pipeline Controls</span>
      </div>

      <div class="form-group">
        <label>Quick Concept Presets:</label>
        <div class="quick-presets">
          <span class="preset-pill" onclick="applyPreset('cyber_warrior', 'cyberpunk warrior alien with neon visor and plasma blade', 'warrior', 'biped')">Cyber Alien</span>
          <span class="preset-pill" onclick="applyPreset('ice_sorceress', 'ice sorceress in crystalline glowing silk robes with frost staff', 'mage', 'biped')">Ice Mage</span>
          <span class="preset-pill" onclick="applyPreset('shadow_ninja', 'shadow ninja shinobi with oni mask and dual crimson kunai', 'assassin', 'biped')">Shadow Rogue</span>
          <span class="preset-pill" onclick="applyPreset('titan_mech', 'heavy dieselpunk mech juggernaut with furnace core and hazard stripes', 'mech', 'biped')">Heavy Mech</span>
          <span class="preset-pill" onclick="applyPreset('fenrir_wolf', 'mythical shadow beast dire wolf with predatory glowing eyes and multi tail', 'beast', 'quadruped')">Fenrir Beast</span>
        </div>
      </div>

      <div class="form-group">
        <label for="concept">Character Concept Description (Prompt):</label>
        <textarea id="concept">cyberpunk warrior alien with glowing neon visor, modular armor, plasma blade</textarea>
      </div>

      <div class="row-2">
        <div class="form-group">
          <label for="char-name">Character Identifier:</label>
          <input type="text" id="char-name" value="cyber_warrior">
        </div>
        <div class="form-group">
          <label for="archetype">Visual Archetype:</label>
          <select id="archetype">
            <option value="warrior" selected>Warrior (Paladin / Heavy Armor)</option>
            <option value="mage">Mage (Caster / Arcane Robes)</option>
            <option value="assassin">Assassin (Ninja / Stealth Cowl)</option>
            <option value="ranger">Ranger (Archer / Forest Scout)</option>
            <option value="mech">Mech (Juggernaut / Reactor Core)</option>
            <option value="beast">Beast (Wolf / Quadruped Creature)</option>
          </select>
        </div>
      </div>

      <div class="row-2">
        <div class="form-group">
          <label for="rig-type">Rig Architecture:</label>
          <select id="rig-type">
            <option value="biped" selected>Humanoid Biped (15 bones)</option>
            <option value="quadruped">Beast / Quadruped (20 bones)</option>
          </select>
        </div>
        <div class="form-group">
          <label for="engine-mode">Generation Engine:</label>
          <select id="engine-mode">
            <option value="auto" selected>Auto (ComfyUI with Local Fallback)</option>
            <option value="local">Local Vector/Pixel Generator (Offline)</option>
            <option value="comfyui">ComfyUI Generative Diffusion Only</option>
          </select>
        </div>
      </div>

      <!-- Advanced Accordion -->
      <div class="accordion">
        <div class="accordion-header" onclick="toggleAccordion()">
          <span>Advanced Tuning Parameters (Seed, Steps, Paths)</span>
          <span id="accordion-arrow">▼</span>
        </div>
        <div id="accordion-body" class="accordion-content">
          <div class="row-3">
            <div class="form-group">
              <label for="seed">Random Seed:</label>
              <input type="text" id="seed" value="-1">
            </div>
            <div class="form-group">
              <label for="steps">Sampling Steps:</label>
              <input type="text" id="steps" value="28">
            </div>
            <div class="form-group">
              <label for="cfg">CFG Scale:</label>
              <input type="text" id="cfg" value="7.0">
            </div>
          </div>
          <div class="form-group">
            <label for="target-scene">Target Godot Scene:</label>
            <input type="text" id="target-scene" value="res://scenes/cyber_warrior_character.tscn">
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
        <button class="btn btn-secondary" onclick="runPipeline('rig_only')">🦴 Auto-Rig Selected Skeletons</button>
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
        <div id="console" class="console">[System Ready] Enter a character concept or pick a preset above to begin.</div>
      </div>

      <!-- Assets Preview Card -->
      <div class="card" style="flex: 1;">
        <div class="card-title">
          <span>Extracted Cutout Sprites</span>
          <div style="display: flex; gap: 6px;">
            <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="openExplorer()">📁 Open Folder</button>
            <button class="btn btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="openInGodot()">🎮 Open in Godot</button>
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
  let currentCharacter = "cyber_warrior";

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

  function applyPreset(name, concept, arch, rig) {
    document.getElementById("char-name").value = name;
    document.getElementById("concept").value = concept;
    document.getElementById("archetype").value = arch;
    document.getElementById("rig-type").value = rig;
    document.getElementById("target-scene").value = `res://scenes/${name}_character.tscn`;
    currentCharacter = name;
    log(`[PRESET] Applied '${name}' (${arch.toUpperCase()}, ${rig.toUpperCase()})`, "info");
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
        cBadge.className = "badge badge-online";
        cBadge.innerHTML = `<span class="badge-dot"></span> ComfyUI: Online (${d.comfyui.node_count} nodes)`;
      } else {
        cBadge.className = "badge badge-offline";
        cBadge.innerHTML = '<span class="badge-dot"></span> ComfyUI: Offline (Using Local)';
      }
    } catch (e) {
      console.warn("Status error:", e);
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
        g.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 40px 0; font-size: 12px;">No sprites extracted yet. Click Generate above!</div>';
      }
    } catch (e) {}
  }

  async function runPipeline(actionType) {
    const btn = document.getElementById("btn-generate");
    const name = document.getElementById("char-name").value.trim().toLowerCase().replace(/\\s+/g, '_');
    const concept = document.getElementById("concept").value.trim();
    const archetype = document.getElementById("archetype").value;
    const rig = document.getElementById("rig-type").value;
    const mode = document.getElementById("engine-mode").value;
    const seed = document.getElementById("seed").value;

    btn.disabled = true;
    document.getElementById("status-pill").textContent = "Processing...";
    log(`\\n========================================================`, "info");
    log(`Starting Pipeline execution for '${name}'...`, "info");

    try {
      const r = await fetch('/api/generate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          character_name: name,
          concept: concept,
          archetype: archetype,
          rig_type: rig,
          mode: mode,
          seed: seed,
          auto_rig: (actionType !== 'sprites_only')
        })
      });
      const res = await r.json();
      if (res.logs) {
        res.logs.forEach(l => log(l));
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
    await fetch('/api/open_folder', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({character: name})
    });
  }

  async function openInGodot() {
    const scene = document.getElementById("target-scene").value.trim();
    await fetch('/api/open_godot', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({scene: scene})
    });
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
