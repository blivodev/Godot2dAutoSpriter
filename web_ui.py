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

        elif path == "/api/animations":
            try:
                from scripts.generate_rig_animations import ANIMATION_DEFS
                self._send_json({"status": "ok", "count": len(ANIMATION_DEFS), "animations": ANIMATION_DEFS})
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)})
            return

        elif path == "/api/rerig_all":
            try:
                from scripts.generate_rig_animations import rerig_all_existing_scenes
                updated = rerig_all_existing_scenes()
                self._send_json({"status": "success", "count": len(updated), "characters": updated})
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)})
            return

        elif path == "/api/special_catalog":
            try:
                from scripts.generate_rig_animations import get_special_moves_catalog
                cat = get_special_moves_catalog()
                self._send_json({"status": "ok", "count": len(cat), "specials": cat})
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)})
            return

        elif path == "/api/factions":
            try:
                roster_path = PROJECT_ROOT / "sprites" / "faction_roster.json"
                if roster_path.is_file():
                    with open(roster_path, "r", encoding="utf-8") as f:
                        self._send_json(json.load(f))
                else:
                    self._send_json({"status": "error", "message": "Faction roster not generated yet"})
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)})
            return

        elif path == "/api/weapons":
            try:
                import server as srv
                res_str = srv.list_weapons_and_projectiles()
                self._send_json(json.loads(res_str))
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)})
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
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
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

        elif path == "/api/rerig_all":
            try:
                from scripts.generate_rig_animations import rerig_all_existing_scenes
                updated = rerig_all_existing_scenes()
                self._send_json({"status": "success", "count": len(updated), "characters": updated})
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)})
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

        elif path == "/api/generate/weapon":
            try:
                w_name = payload.get("name", "custom_weapon").strip().lower().replace(" ", "_")
                w_type = payload.get("weapon_type", "assault_rifle")
                faction = payload.get("faction", "directorate")
                from scripts.generate_weapon_projectiles import create_weapon
                res = create_weapon(w_name, w_type, faction)
                self._send_json(res)
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)}, 500)
            return

        elif path == "/api/generate/projectile":
            try:
                p_name = payload.get("name", "custom_projectile").strip().lower().replace(" ", "_")
                p_type = payload.get("projectile_type", "plasma_bolt")
                faction = payload.get("faction", "directorate")
                from scripts.generate_weapon_projectiles import create_projectile
                res = create_projectile(p_name, p_type, faction)
                self._send_json(res)
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)}, 500)
            return

        elif path == "/api/character/specials":
            try:
                char_name = payload.get("character_name", "").strip().lower().replace(" ", "_")
                specials = payload.get("specials", [])
                meta_file = PROJECT_ROOT / "sprites" / char_name / "metadata.json"
                meta = {}
                if meta_file.is_file():
                    with open(meta_file, "r", encoding="utf-8") as mf:
                        meta = json.load(mf)
                meta["specials"] = specials
                from scripts.generate_rig_animations import SPECIAL_MOVES_CATALOG
                meta["special_details"] = [
                    {
                        "slot": f"special_{i+1:02d}",
                        "key": k,
                        "name": SPECIAL_MOVES_CATALOG.get(k, {}).get("name", k),
                        "desc": SPECIAL_MOVES_CATALOG.get(k, {}).get("desc", ""),
                        "category": SPECIAL_MOVES_CATALOG.get(k, {}).get("category", "combat")
                    }
                    for i, k in enumerate(specials)
                ]
                with open(meta_file, "w", encoding="utf-8") as mf:
                    json.dump(meta, mf, indent=2)
                self._send_json({"status": "success", "character": char_name, "specials": specials, "metadata": meta})
            except Exception as e:
                self._send_json({"status": "error", "message": str(e)}, 500)
            return

        elif path == "/api/character/equip_weapon":
            try:
                char_name = payload.get("character_name", "").strip().lower().replace(" ", "_")
                weapon_name = payload.get("weapon_name", "").strip()
                hand = payload.get("hand", "R").strip().upper()
                import server as srv
                res_str = srv.equip_character_weapon(char_name, weapon_name, hand)
                self._send_json(json.loads(res_str))
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

        # Handle custom or randomized Special Moves (4 slots)
        specials = payload.get("specials")
        if not specials or not isinstance(specials, list) or len(specials) != 4:
            from scripts.generate_rig_animations import randomize_character_specials
            specials = randomize_character_specials(seed if seed >= 0 else None)

        try:
            from scripts.generate_rig_animations import SPECIAL_MOVES_CATALOG
            meta_file = sprites_dir / "metadata.json"
            meta = {}
            if meta_file.is_file():
                try:
                    with open(meta_file, "r", encoding="utf-8") as mf:
                        meta = json.load(mf)
                except Exception:
                    pass
            meta["character_name"] = char_name
            meta["archetype"] = archetype
            meta["rig_type"] = rig_type
            meta["specials"] = specials
            meta["special_details"] = [
                {
                    "slot": f"special_{idx+1:02d}",
                    "key": sp,
                    "name": SPECIAL_MOVES_CATALOG.get(sp, {}).get("name", sp),
                    "desc": SPECIAL_MOVES_CATALOG.get(sp, {}).get("desc", ""),
                    "category": SPECIAL_MOVES_CATALOG.get(sp, {}).get("category", "combat")
                }
                for idx, sp in enumerate(specials)
            ]
            with open(meta_file, "w", encoding="utf-8") as mf:
                json.dump(meta, mf, indent=2)
            logs.append(f"[SPECIALS] Configured 4 signature moves: {', '.join([meta['special_details'][i]['name'] for i in range(4)])}")
        except Exception as e:
            logs.append(f"[SPECIALS-WARN] {e}")

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
            "specials": specials,
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
  .library-layout { display: grid; grid-template-columns: 320px 1fr; gap: 20px; min-height: 640px; }
  @media (max-width: 960px) { .library-layout { grid-template-columns: 1fr; } }

  .roster-filter-bar { display: flex; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
  .filter-chip { font-size: 11px; padding: 4px 10px; border-radius: 12px; background: rgba(255,255,255,0.04); border: 1px solid var(--border); color: var(--text-muted); cursor: pointer; transition: all 0.15s; }
  .filter-chip:hover { border-color: var(--primary); color: var(--text); }
  .filter-chip.active { background: rgba(88,166,255,0.18); border-color: var(--primary); color: var(--primary); font-weight: 600; }

  .char-roster { display: flex; flex-direction: column; gap: 8px; max-height: 640px; overflow-y: auto; padding-right: 4px; }
  .char-roster-item { background: #10131b; border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; cursor: pointer; transition: all 0.15s; display: flex; align-items: center; gap: 10px; }
  .char-roster-item:hover { border-color: var(--primary); background: #141822; }
  .char-roster-item.selected { border-color: var(--primary); background: rgba(88,166,255,0.08); }
  .char-roster-thumb { width: 48px; height: 48px; object-fit: contain; background: repeating-conic-gradient(#1a1f2c 0% 25%, #121620 0% 50%) 50% / 8px 8px; border-radius: 5px; flex-shrink: 0; }
  .char-roster-thumb-placeholder { width: 48px; height: 48px; background: #1a1f2c; border-radius: 5px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 20px; }
  .char-roster-info { flex: 1; min-width: 0; }
  .char-roster-name { font-size: 13px; font-weight: 600; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .char-roster-meta { font-size: 11px; color: var(--text-muted); margin-top: 2px; display: flex; gap: 6px; flex-wrap: wrap; }
  .lib-badge { font-size: 10px; padding: 2px 7px; border-radius: 10px; font-weight: 600; }
  .lib-badge-scene { background: rgba(46,160,67,0.2); color: #3fb950; border: 1px solid rgba(46,160,67,0.3); }
  .lib-badge-no-scene { background: rgba(210,153,34,0.15); color: #d29922; border: 1px solid rgba(210,153,34,0.3); }
  .lib-badge-anim { background: rgba(163,113,247,0.2); color: #d2a8ff; border: 1px solid rgba(163,113,247,0.3); }

  /* Viewer */
  .viewer-panel { display: flex; flex-direction: column; gap: 14px; }
  .viewer-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
  .viewer-title { font-size: 17px; font-weight: 700; color: var(--text); }
  .viewer-actions { display: flex; gap: 8px; flex-wrap: wrap; }

  /* Subnav */
  .viewer-subnav { display: flex; gap: 6px; border-bottom: 1px solid var(--border); padding-bottom: 8px; flex-wrap: wrap; }
  .subnav-btn { background: none; border: 1px solid transparent; font-size: 12.5px; font-weight: 600; color: var(--text-muted); padding: 6px 12px; border-radius: 6px; cursor: pointer; transition: all 0.15s; display: flex; align-items: center; gap: 6px; }
  .subnav-btn:hover { color: var(--text); background: rgba(255,255,255,0.04); }
  .subnav-btn.active { color: var(--primary); background: rgba(88,166,255,0.12); border-color: rgba(88,166,255,0.3); }

  .viewer-subpane { display: none; }
  .viewer-subpane.active { display: block; }

  /* Animation Player */
  .anim-stage-container { display: flex; flex-direction: column; gap: 12px; }
  .anim-viewport { background: repeating-conic-gradient(#141824 0% 25%, #0e111a 0% 50%) 50% / 16px 16px; border: 1px solid var(--border); border-radius: 8px; height: 380px; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center; }
  #anim-canvas { width: 100%; height: 100%; display: block; }
  .anim-viewport-overlay { position: absolute; top: 12px; left: 14px; pointer-events: none; display: flex; flex-direction: column; gap: 3px; }
  .anim-curr-title { font-size: 14px; font-weight: 700; color: #fff; text-shadow: 0 1px 4px rgba(0,0,0,0.8); }
  .anim-curr-sub { font-size: 11px; color: var(--text-muted); text-shadow: 0 1px 3px rgba(0,0,0,0.8); }
  .anim-controls-bar { display: flex; align-items: center; gap: 10px; background: #10131b; border: 1px solid var(--border); border-radius: 8px; padding: 10px 14px; flex-wrap: wrap; }
  .anim-scrub-wrap { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 180px; }
  .anim-scrub { flex: 1; accent-color: var(--primary); cursor: pointer; }
  .anim-time-label { font-size: 11px; color: var(--text-muted); font-variant-numeric: tabular-nums; min-width: 75px; text-align: right; }
  
  .anim-chip-groups { display: flex; flex-direction: column; gap: 10px; margin-top: 4px; }
  .anim-group-title { font-size: 11px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
  .anim-chip-row { display: flex; flex-wrap: wrap; gap: 6px; }
  .anim-chip { font-size: 11px; padding: 5px 11px; border-radius: 12px; background: #10131b; border: 1px solid var(--border); color: var(--text-muted); cursor: pointer; transition: all 0.15s; display: inline-flex; align-items: center; gap: 4px; }
  .anim-chip:hover { border-color: var(--primary); color: #fff; transform: translateY(-1px); }
  .anim-chip.active { background: linear-gradient(135deg, rgba(88,166,255,0.25), rgba(163,113,247,0.25)); border-color: var(--primary); color: #fff; font-weight: 600; box-shadow: 0 0 12px rgba(88,166,255,0.35); }

  /* Sliced Limbs Grid */
  .viewer-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 10px; max-height: 480px; overflow-y: auto; padding: 2px; }
  .viewer-sprite-card { background: #10131b; border: 1px solid var(--border); border-radius: 8px; padding: 8px; text-align: center; cursor: pointer; transition: all 0.15s; }
  .viewer-sprite-card:hover { border-color: var(--primary); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(88,166,255,0.2); }
  .viewer-sprite-img { width: 100%; height: 90px; object-fit: contain; background: repeating-conic-gradient(#1a1f2c 0% 25%, #121620 0% 50%) 50% / 12px 12px; border-radius: 5px; }
  .viewer-sprite-name { font-size: 10px; color: var(--text-muted); margin-top: 5px; font-weight: 500; }
  .viewer-sprite-size { font-size: 9px; color: #4a5568; }

  /* Master Exploded Sheet */
  .exploded-sheet-wrap { background: repeating-conic-gradient(#141824 0% 25%, #0e111a 0% 50%) 50% / 16px 16px; border: 1px solid var(--border); border-radius: 8px; padding: 16px; display: flex; align-items: center; justify-content: center; max-height: 440px; overflow: hidden; cursor: pointer; }
  .exploded-sheet-img { max-height: 400px; max-width: 100%; object-fit: contain; border-radius: 6px; box-shadow: 0 4px 16px rgba(0,0,0,0.6); transition: transform 0.2s; }
  .exploded-sheet-img:hover { transform: scale(1.02); }

  /* Godot Specs Table */
  .spec-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; margin-bottom: 14px; }
  .spec-card { background: #10131b; border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
  .spec-card-label { font-size: 11px; color: var(--text-muted); margin-bottom: 4px; }
  .spec-card-value { font-size: 13px; font-weight: 600; color: var(--text); }
  .anim-table-wrap { max-height: 360px; overflow-y: auto; border: 1px solid var(--border); border-radius: 8px; }
  .anim-table { width: 100%; border-collapse: collapse; font-size: 12px; background: #10131b; }
  .anim-table th, .anim-table td { padding: 9px 12px; text-align: left; border-bottom: 1px solid var(--border); }
  .anim-table th { background: #141824; color: var(--text-muted); font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.5px; position: sticky; top: 0; }
  .anim-table tr:hover td { background: rgba(255,255,255,0.02); }

  .viewer-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 380px; color: var(--text-muted); gap: 10px; font-size: 13px; }
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

  /* Weapons & Projectiles Studio */
  .arsenal-card { background: #10131b; border: 1px solid var(--border); border-radius: 8px; padding: 10px; display: flex; flex-direction: column; gap: 8px; transition: all 0.15s; }
  .arsenal-card:hover { border-color: var(--primary); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(88,166,255,0.15); }
  .arsenal-thumb-wrap { width: 100%; height: 95px; background: repeating-conic-gradient(#1a1f2c 0% 25%, #121620 0% 50%) 50% / 12px 12px; border-radius: 6px; display: flex; align-items: center; justify-content: center; overflow: hidden; cursor: pointer; }
  .arsenal-thumb { max-height: 85px; max-width: 90%; object-fit: contain; filter: drop-shadow(0 2px 6px rgba(0,0,0,0.6)); transition: transform 0.2s; }
  .arsenal-thumb:hover { transform: scale(1.08); }
  .arsenal-card-title { font-size: 11.5px; font-weight: 600; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .arsenal-tag { font-size: 9.5px; padding: 2px 6px; border-radius: 4px; font-weight: 600; text-transform: uppercase; }
  .role-badge { font-size: 10px; padding: 1px 6px; border-radius: 4px; font-weight: 600; background: rgba(88,166,255,0.12); color: #79b8ff; border: 1px solid rgba(88,166,255,0.25); }

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
    <button class="tab-btn" onclick="switchTab('weapons')" id="tab-btn-weapons">⚔️ Weapons &amp; Projectiles</button>
    <button class="tab-btn" onclick="switchTab('arena')" id="tab-btn-arena">🎯 RTS Arena</button>
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

        <!-- Special & Signature Moves Customizer -->
        <div class="card" style="margin-top:14px;background:#0d111a;border:1px solid rgba(188,140,255,0.3);padding:14px;border-radius:8px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <div style="font-weight:600;font-size:13px;color:#d2a8ff;display:flex;align-items:center;gap:6px;">
              <span>⚡ Special &amp; Signature Moves (4 Slots)</span>
              <span class="tooltip-wrap"><span class="help-icon">?</span>
                <span class="tip">Customize or roll 4 tactical abilities from the 22-move catalog. These will be rigged into the character's Godot 4 scene!</span>
              </span>
            </div>
            <button type="button" class="btn btn-secondary btn-sm" onclick="randomizeSpecialsInForm()" style="border-color:var(--accent-purple);color:#d2a8ff;">🎲 Randomize 4</button>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <div class="form-group" style="margin-bottom:0;">
              <label style="font-size:10.5px;color:var(--text-muted);">Special Slot 1:</label>
              <select id="spec-slot-1" style="font-size:11.5px;padding:6px 8px;"></select>
            </div>
            <div class="form-group" style="margin-bottom:0;">
              <label style="font-size:10.5px;color:var(--text-muted);">Special Slot 2:</label>
              <select id="spec-slot-2" style="font-size:11.5px;padding:6px 8px;"></select>
            </div>
            <div class="form-group" style="margin-bottom:0;">
              <label style="font-size:10.5px;color:var(--text-muted);">Special Slot 3:</label>
              <select id="spec-slot-3" style="font-size:11.5px;padding:6px 8px;"></select>
            </div>
            <div class="form-group" style="margin-bottom:0;">
              <label style="font-size:10.5px;color:var(--text-muted);">Special Slot 4:</label>
              <select id="spec-slot-4" style="font-size:11.5px;padding:6px 8px;"></select>
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
      <div>
        <div class="lib-title">Generated Characters &amp; Rigged Asset Library <span id="lib-char-count" style="font-size:12px;color:var(--text-muted);font-weight:normal;margin-left:8px;"></span></div>
        <div style="font-size:12px;color:var(--text-muted);margin-top:2px;">Complete character roster with 23 skeletal animations, master exploded sheets, limb cutouts &amp; Godot 4 scenes.</div>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        <button class="btn btn-primary btn-sm" id="btn-batch-rerig" onclick="batchRerigAll()">🦴 Batch Re-Rig All (23 Anims)</button>
        <button class="btn btn-secondary btn-sm" onclick="refreshLibrary()">🔄 Refresh Library</button>
      </div>
    </div>
    <div class="library-layout">
      <!-- Roster (Left Column) -->
      <div>
        <div class="roster-filter-bar">
          <button class="filter-chip active" id="chip-filter-all" onclick="setRosterFilter('all')">All (<span id="count-all">0</span>)</button>
          <button class="filter-chip" id="chip-filter-neotokyo" onclick="setRosterFilter('neotokyo')" style="border-color:#00f0ff;color:#00f0ff;font-weight:600;">🎌 Neo-Tokyo (<span id="count-neotokyo">0</span>)</button>
          <button class="filter-chip" id="chip-filter-abyssal" onclick="setRosterFilter('abyssal')" style="border-color:#e67e22;color:#e67e22;font-weight:600;">☣️ Abyssal (<span id="count-abyssal">0</span>)</button>
          <button class="filter-chip" id="chip-filter-orbital" onclick="setRosterFilter('orbital')" style="border-color:#2ecc71;color:#2ecc71;font-weight:600;">🛰️ Orbital Ops (<span id="count-orbital">0</span>)</button>
          <button class="filter-chip" id="chip-filter-aetherium" onclick="setRosterFilter('aetherium')" style="border-color:#9b59b6;color:#d2a8ff;font-weight:600;">🔮 Aetherium (<span id="count-aetherium">0</span>)</button>
          <button class="filter-chip" id="chip-filter-neonglitch" onclick="setRosterFilter('neonglitch')" style="border-color:#ff007f;color:#ff79c6;font-weight:600;">⚡ Neon Glitch (<span id="count-neonglitch">0</span>)</button>
          <button class="filter-chip" id="chip-filter-pixel_anime" onclick="setRosterFilter('pixel_anime')" style="border-color:#ff78cb;color:#ff9cd6;font-weight:600;">✨ Pixel/Anime (50)</button>
          <button class="filter-chip" id="chip-filter-directorate" onclick="setRosterFilter('directorate')" style="border-color:#58a6ff;">🏛️ Directorate</button>
          <button class="filter-chip" id="chip-filter-syndicate" onclick="setRosterFilter('syndicate')" style="border-color:#e68c14;">⚙️ Syndicate</button>
          <button class="filter-chip" id="chip-filter-covenant" onclick="setRosterFilter('covenant')" style="border-color:#bc8cff;">🧠 Covenant</button>
          <button class="filter-chip" id="chip-filter-bioforge" onclick="setRosterFilter('bioforge')" style="border-color:#2ea043;">🧬 Bio-Forge</button>
          <button class="filter-chip" id="chip-filter-silicon" onclick="setRosterFilter('silicon')" style="border-color:#f85149;">⚡ Silicon</button>
          <button class="filter-chip" id="chip-filter-ghost_protocol" onclick="setRosterFilter('ghost_protocol')" style="border-color:#39c5bb;">🥷 Ghost Protocol</button>
          <button class="filter-chip" id="chip-filter-iron_valkyrie" onclick="setRosterFilter('iron_valkyrie')" style="border-color:#d29922;">🛡️ Iron Valkyrie</button>
          <button class="filter-chip" id="chip-filter-neon_outcasts" onclick="setRosterFilter('neon_outcasts')" style="border-color:#f778ba;">🔥 Neon Outcasts</button>
          <button class="filter-chip" id="chip-filter-apex_transhumans" onclick="setRosterFilter('apex_transhumans')" style="border-color:#a371f7;">🔮 Apex Transhumans</button>
          <button class="filter-chip" id="chip-filter-synth_corp" onclick="setRosterFilter('synth_corp')" style="border-color:#ff7b72;">🤖 Synth-Corp</button>
          <button class="filter-chip" id="chip-filter-scenes" onclick="setRosterFilter('scenes')">🎮 Scenes (<span id="count-scenes">0</span>)</button>
          <button class="filter-chip" id="chip-filter-exploded" onclick="setRosterFilter('exploded')">🖼️ Sheets (<span id="count-exploded">0</span>)</button>
        </div>
        <div class="lib-toolbar">
          <input class="lib-search" type="text" id="lib-search" placeholder="🔍 Filter characters..." oninput="filterRoster()">
        </div>
        <div id="char-roster" class="char-roster">
          <div style="text-align:center;color:var(--text-muted);padding:40px 0;font-size:13px;">Loading characters...</div>
        </div>
      </div>

      <!-- Viewer Panel (Right Column) -->
      <div class="card viewer-panel">
        <div id="viewer-empty" class="viewer-empty">
          <div class="viewer-empty-icon">🎮</div>
          <div style="font-size:14px;font-weight:600;color:var(--text);">Select a character from the roster</div>
          <div style="font-size:12px;">Inspect 23 live animations, master diffusion sheets, individual limb cutouts, or Godot 4 scene specs.</div>
        </div>
        <div id="viewer-content" style="display:none;">
          <!-- Top Header -->
          <div class="viewer-header">
            <div>
              <div class="viewer-title" id="viewer-char-name">—</div>
              <div style="font-size:12px;color:var(--text-muted);margin-top:2px;" id="viewer-char-meta"></div>
            </div>
            <div class="viewer-actions">
              <button class="btn btn-secondary btn-sm" onclick="openExplorerFor(viewingChar)">📁 Folder</button>
              <button class="btn btn-secondary btn-sm" onclick="openGodotFor(viewingChar)">🎮 Godot</button>
              <button class="btn btn-secondary btn-sm" onclick="rerigChar(viewingChar)">🦴 Re-Rig (23 Anims)</button>
              <button class="btn btn-danger btn-sm" onclick="deleteChar(viewingChar)">🗑️ Delete</button>
            </div>
          </div>

          <!-- Multi-Pane Navigation Tabs -->
          <div class="viewer-subnav">
            <button class="subnav-btn active" id="subnav-anim" onclick="switchViewerSubTab('anim')">🎬 Live Animation Player (23)</button>
            <button class="subnav-btn" id="subnav-limbs" onclick="switchViewerSubTab('limbs')">🧩 Sliced Limbs</button>
            <button class="subnav-btn" id="subnav-exploded" onclick="switchViewerSubTab('exploded')">🖼️ Master Exploded Sheet</button>
            <button class="subnav-btn" id="subnav-godot" onclick="switchViewerSubTab('godot')">📋 Godot Scene &amp; Rig Specs</button>
          </div>

          <!-- SUBPANE 1: LIVE ANIMATION PLAYER -->
          <div class="viewer-subpane active" id="subpane-anim">
            <div class="anim-stage-container">
              <!-- Canvas Viewport -->
              <div class="anim-viewport">
                <canvas id="anim-canvas" width="700" height="380"></canvas>
                <div class="anim-viewport-overlay">
                  <span class="anim-curr-title" id="anim-overlay-title">idle</span>
                  <span class="anim-curr-sub" id="anim-overlay-desc">Breathing rest stance with gentle head and arm sway</span>
                </div>
              </div>

              <!-- Playback Controls Bar -->
              <div class="anim-controls-bar">
                <button class="btn btn-secondary btn-sm" id="btn-anim-play" onclick="togglePlayPause()">⏸ Pause</button>
                <button class="btn btn-secondary btn-sm" onclick="restartAnimation()">⏮ Restart</button>
                <div class="anim-scrub-wrap">
                  <input type="range" class="anim-scrub" id="anim-scrub" min="0" max="100" value="0" oninput="onScrubInput(this.value)">
                  <span class="anim-time-label" id="anim-time-display">0.00s / 1.80s</span>
                </div>
                <div style="display:flex;align-items:center;gap:6px;font-size:11px;color:var(--text-muted);">
                  <label for="anim-speed" style="margin-bottom:0;">Speed:</label>
                  <select id="anim-speed" style="padding:4px 8px;font-size:11px;background:var(--bg-input);border:1px solid var(--border);border-radius:4px;color:var(--text);" onchange="animSpeed = parseFloat(this.value)">
                    <option value="0.25">0.25x</option>
                    <option value="0.5">0.5x</option>
                    <option value="1.0" selected>1.0x (Normal)</option>
                    <option value="1.5">1.5x</option>
                    <option value="2.0">2.0x</option>
                  </select>
                </div>
                <!-- Render Mode Selector -->
                <div style="display:flex;align-items:center;gap:3px;background:rgba(0,0,0,0.3);padding:2px 4px;border-radius:6px;border:1px solid var(--border);">
                  <button class="btn btn-sm btn-secondary" id="btn-mode-limbs" style="font-size:10.5px;padding:3px 7px;" onclick="setRenderMode('limbs')">🧩 Sliced Rig</button>
                  <button class="btn btn-sm btn-primary" id="btn-mode-full" style="font-size:10.5px;padding:3px 7px;" onclick="setRenderMode('full')">🧍 Full Model</button>
                </div>
                <!-- Auto-Loop Toggle -->
                <label style="display:inline-flex;align-items:center;gap:4px;font-size:11px;color:var(--text-muted);cursor:pointer;margin-bottom:0;">
                  <input type="checkbox" id="anim-auto-loop" checked onchange="autoLoop = this.checked"> 🔁 Auto-Loop
                </label>
                <!-- Skeleton Overlay Toggle -->
                <label style="display:inline-flex;align-items:center;gap:4px;font-size:11px;color:var(--text-muted);cursor:pointer;margin-bottom:0;">
                  <input type="checkbox" id="anim-show-skeleton" onchange="showSkeletonOverlay = this.checked"> 🦴 Bones
                </label>
              </div>

              <!-- Quick Animation Selector Chips (All 23 Animations categorized) -->
              <div class="anim-chip-groups">
                <div>
                  <div class="anim-group-title">🏃 Locomotion &amp; Agility (9)</div>
                  <div class="anim-chip-row" style="margin-top:4px;">
                    <span class="anim-chip active" data-anim="idle" onclick="selectAnim('idle')">🌱 idle</span>
                    <span class="anim-chip" data-anim="walk" onclick="selectAnim('walk')">🚶 walk</span>
                    <span class="anim-chip" data-anim="run" onclick="selectAnim('run')">🏃 run</span>
                    <span class="anim-chip" data-anim="jump" onclick="selectAnim('jump')">🦘 jump</span>
                    <span class="anim-chip" data-anim="double_jump" onclick="selectAnim('double_jump')">✨ double_jump</span>
                    <span class="anim-chip" data-anim="dash" onclick="selectAnim('dash')">💨 dash</span>
                    <span class="anim-chip" data-anim="slide" onclick="selectAnim('slide')">🛹 slide</span>
                    <span class="anim-chip" data-anim="crouch" onclick="selectAnim('crouch')">🧘 crouch</span>
                    <span class="anim-chip" data-anim="crouch_walk" onclick="selectAnim('crouch_walk')">🥷 crouch_walk</span>
                  </div>
                </div>

                <div>
                  <div class="anim-group-title">⚔️ Combat &amp; Attacks (6)</div>
                  <div class="anim-chip-row" style="margin-top:4px;">
                    <span class="anim-chip" data-anim="punch" onclick="selectAnim('punch')">👊 punch</span>
                    <span class="anim-chip" data-anim="hit" onclick="selectAnim('hit')">⚔️ hit (slash)</span>
                    <span class="anim-chip" data-anim="kick" onclick="selectAnim('kick')">🦵 kick</span>
                    <span class="anim-chip" data-anim="jump_kick" onclick="selectAnim('jump_kick')">🥋 jump_kick</span>
                    <span class="anim-chip" data-anim="crouch_kick" onclick="selectAnim('crouch_kick')">🧹 crouch_kick</span>
                    <span class="anim-chip" data-anim="fire_weapon" onclick="selectAnim('fire_weapon')">🔫 fire_weapon</span>
                  </div>
                </div>

                <div>
                  <div class="anim-group-title">💥 Status &amp; Reactions (4)</div>
                  <div class="anim-chip-row" style="margin-top:4px;">
                    <span class="anim-chip" data-anim="get_hit" onclick="selectAnim('get_hit')">💢 get_hit</span>
                    <span class="anim-chip" data-anim="get_stunned" onclick="selectAnim('get_stunned')">💫 get_stunned</span>
                    <span class="anim-chip" data-anim="drink_potion" onclick="selectAnim('drink_potion')">🧪 drink_potion</span>
                    <span class="anim-chip" data-anim="death" onclick="selectAnim('death')">☠️ death</span>
                  </div>
                </div>

                <div>
                  <div class="anim-group-title">⚡ Special &amp; Signature Moves (4)</div>
                  <div class="anim-chip-row" style="margin-top:4px;">
                    <span class="anim-chip" data-anim="special_01" onclick="selectAnim('special_01')">💥 special_01 (Ground Slam)</span>
                    <span class="anim-chip" data-anim="special_02" onclick="selectAnim('special_02')">🌪️ special_02 (Whirlwind)</span>
                    <span class="anim-chip" data-anim="special_03" onclick="selectAnim('special_03')">🔮 special_03 (Power Charge)</span>
                    <span class="anim-chip" data-anim="special_04" onclick="selectAnim('special_04')">👑 special_04 (Victory Flourish)</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- SUBPANE 2: SLICED LIMBS -->
          <div class="viewer-subpane" id="subpane-limbs">
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

          <!-- SUBPANE 3: MASTER EXPLODED SHEET -->
          <div class="viewer-subpane" id="subpane-exploded">
            <div style="display:flex;flex-direction:column;gap:14px;">
              <div style="font-size:13px;color:var(--text-muted);">
                The master generative texture sheet containing all 15 limb cutouts arranged on a 1024×1024 canvas before automatic slicing and padding.
              </div>
              <div class="exploded-sheet-wrap" id="exploded-wrap" onclick="openExplodedLightbox()">
                <img id="viewer-exploded-img" class="exploded-sheet-img" src="" alt="Master Exploded Sheet">
              </div>
              <div id="exploded-meta-card" style="display:flex;align-items:center;justify-content:space-between;background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:8px;padding:12px 16px;flex-wrap:wrap;gap:10px;">
                <div>
                  <div style="font-size:13px;font-weight:600;color:var(--text);" id="exploded-char-title">Master Sheet</div>
                  <div style="font-size:11px;color:var(--text-muted);margin-top:2px;">1024×1024 RGBA • Alpha transparent background • 15 limb grid</div>
                </div>
                <div style="display:flex;gap:8px;">
                  <button class="btn btn-secondary btn-sm" onclick="openExplodedLightbox()">🔍 Inspect 1024×1024</button>
                  <a id="btn-download-exploded" class="btn btn-secondary btn-sm" href="#" target="_blank" download>⬇️ Download Sheet</a>
                </div>
              </div>
              <div id="exploded-empty" style="display:none;text-align:center;padding:40px;color:var(--text-muted);font-size:13px;">
                No master exploded sheet found for this character.
              </div>
            </div>
          </div>

          <!-- SUBPANE 4: GODOT SCENE & RIG SPECS -->
          <div class="viewer-subpane" id="subpane-godot">
            <div style="display:flex;flex-direction:column;gap:16px;">
              <div class="spec-grid">
                <div class="spec-card">
                  <div class="spec-card-label">Godot 4 Scene</div>
                  <div class="spec-card-value" id="spec-scene-path" style="font-size:12px;font-family:monospace;word-break:break-all;">res://scenes/...</div>
                </div>
                <div class="spec-card">
                  <div class="spec-card-label">Rig Architecture</div>
                  <div class="spec-card-value">Humanoid Biped (15 Bones)</div>
                </div>
                <div class="spec-card">
                  <div class="spec-card-label">Animation Library</div>
                  <div class="spec-card-value">AnimationLibrary_char</div>
                </div>
                <div class="spec-card">
                  <div class="spec-card-label">Total Animations</div>
                  <div class="spec-card-value" style="color:#3fb950;">23 Default Moves</div>
                </div>
              </div>

              <div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                  <div style="font-size:13px;font-weight:600;color:var(--text);">AnimationPlayer Track Catalog</div>
                  <div style="font-size:11px;color:var(--text-muted);">23 procedural &amp; skeletal tracks bundled into scene</div>
                </div>
                <div class="anim-table-wrap">
                  <table class="anim-table">
                    <thead>
                      <tr>
                        <th>Animation</th>
                        <th>Category</th>
                        <th>Length</th>
                        <th>Loop</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody id="spec-anim-table-body"></tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>
  </div>

  <!-- ======================================================= -->
  <!-- TAB: WEAPONS & PROJECTILES STUDIO                       -->
  <!-- ======================================================= -->
  <div class="tab-content" id="tab-weapons">
    <div class="lib-header">
      <div>
        <div class="lib-title">⚔️ Weapons &amp; Projectiles Studio <span id="weapons-count-badge" style="font-size:12px;color:var(--text-muted);font-weight:normal;margin-left:8px;"></span></div>
        <div style="font-size:12px;color:var(--text-muted);margin-top:2px;">
          Procedural Sci-Fi Cyberpunk Arsenals: Static/Animated Weapon Sprites, Multi-Frame Projectiles &amp; Godot 4 .tscn Scenes with Interactive Firing Range.
        </div>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        <button class="btn btn-secondary btn-sm" onclick="refreshArsenal()">🔄 Refresh Arsenal</button>
      </div>
    </div>

    <div class="weapons-grid-layout" style="display:grid;grid-template-columns:360px 1fr;gap:20px;min-height:640px;">
      <!-- Left Column: Weapon & Projectile Generator -->
      <div style="display:flex;flex-direction:column;gap:16px;">
        <div class="card">
          <div class="card-title">
            <span>Arsenal Creator</span>
            <span style="font-size:11px;color:var(--primary);">Static &amp; Animated</span>
          </div>

          <!-- Type Switch -->
          <div style="display:flex;gap:8px;margin-bottom:14px;">
            <button type="button" id="btn-arsenal-mode-weapon" class="btn btn-primary btn-sm" style="flex:1;" onclick="setArsenalType('weapon')">🔫 Weapon</button>
            <button type="button" id="btn-arsenal-mode-proj" class="btn btn-secondary btn-sm" style="flex:1;" onclick="setArsenalType('projectile')">💥 Projectile</button>
          </div>

          <div class="form-group">
            <label for="arsenal-item-name">Identifier (Slug):</label>
            <input type="text" id="arsenal-item-name" value="plasma_carbine" placeholder="e.g. plasma_carbine">
          </div>

          <!-- Weapon Type Select -->
          <div class="form-group" id="group-weapon-type">
            <label for="arsenal-weapon-type">Weapon Class &amp; Archetype:</label>
            <select id="arsenal-weapon-type">
              <option value="assault_rifle" selected>Assault Rifle (Full-Auto Kinetic / Laser)</option>
              <option value="sniper_rifle">Sniper Rifle (High-Velocity Piercing Railgun)</option>
              <option value="grenade_launcher">Grenade Launcher (Arcing Heavy Shrapnel)</option>
              <option value="rocket_launcher">Rocket Launcher (Heavy Ordnance Pod)</option>
              <option value="submachine_gun">Submachine Gun (Rapid Spray PDW)</option>
              <option value="shotgun">Shotgun (Wide-Spread Buckshot / Flechette)</option>
              <option value="flamethrower">Flamethrower (Pressurized Caustic Stream)</option>
              <option value="psi_emitter">Psionic Emitter (Neural Distortion Conduit)</option>
              <option value="drone_pad">Drone Pad (Wrist UAV Uplink Console)</option>
              <option value="flak_cannon">Flak Cannon (Heavy Radar-Fused Airburst)</option>
              <option value="pistol">Pistol (Compact Sidearm Blaster)</option>
              <option value="melee_blade">Vibro-Blade / Katana (Thermal Edge Melee)</option>
            </select>
          </div>

          <!-- Projectile Type Select -->
          <div class="form-group" id="group-projectile-type" style="display:none;">
            <label for="arsenal-proj-type">Projectile Dynamics &amp; VFX:</label>
            <select id="arsenal-proj-type">
              <option value="plasma_bolt" selected>Plasma Bolt (Animated 4-Frame Pulsing Core)</option>
              <option value="flame_jet">Flame Jet (Animated 4-Frame Turbulent Stream)</option>
              <option value="psi_singularity">Psionic Singularity (Animated 6-Frame Warp Orb)</option>
              <option value="flak_burst">Flak Burst (Animated 4-Frame Shrapnel Detonation)</option>
              <option value="bullet">High-Velocity Bullet (Static Tracer Round)</option>
              <option value="sniper_beam">Sniper Beam (Static Piercing Collimated Beam)</option>
              <option value="grenade">Grenade (Static Cylindrical Canister)</option>
              <option value="missile">Missile (Static Fin-Stabilized Rocket)</option>
              <option value="drone">Hunter Drone (Autonomous Mini Quad-Rotor)</option>
            </select>
          </div>

          <div class="form-group">
            <label for="arsenal-faction">Faction Aesthetics &amp; Palette:</label>
            <select id="arsenal-faction">
              <option value="neotokyo" selected>🎌 Neo-Tokyo Cyber-Corps (Titanium White / Tachyon Cyan)</option>
              <option value="abyssal">☣️ Abyssal Sector Outcasts (Wasteland Rust / Toxic Amber)</option>
              <option value="orbital">🛰️ Orbital Black-Ops Legion (Matte Carbon / NVG Green)</option>
              <option value="aetherium">🔮 Aetherium Psionic Syndicate (Astral Obsidian / Amethyst)</option>
              <option value="neonglitch">⚡ Neon Glitch Underground (Hot Magenta / Electric Teal)</option>
              <option value="ghost_protocol">🥷 Ghost Protocol (Stealth Slate / Tactical Cyan)</option>
              <option value="iron_valkyrie">🛡️ Iron Valkyrie (Golden Titanium / Amber)</option>
              <option value="neon_outcasts">🔥 Neon Outcasts (Synth Pink / Smog Carbon)</option>
              <option value="apex_transhumans">🔮 Apex Transhumans (Neural Violet / Platinum)</option>
              <option value="synth_corp">🤖 Synth-Corp (Chassis Charcoal / Laser Red)</option>
              <option value="directorate">🏛️ Neo-Terra Directorate (Gunmetal / Cyan)</option>
              <option value="syndicate">⚙️ Rust Syndicate (Welded Iron / Orange)</option>
              <option value="covenant">🧠 Neuro-Covenant (Matte Carbon / Magenta)</option>
              <option value="bioforge">🧬 Bio-Forge Legion (Bio-Chitin / Acid Slime)</option>
              <option value="silicon">⚡ Silicon Hive (Matte Black / Crimson)</option>
            </select>
          </div>

          <div class="form-group" id="group-animated-toggle">
            <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:12px;">
              <input type="checkbox" id="arsenal-animated" checked style="accent-color:var(--primary);width:16px;height:16px;">
              <span>Include Animated Frames &amp; Strip (.png + .tscn)</span>
            </label>
          </div>

          <button id="btn-generate-arsenal" class="btn btn-primary" style="width:100%;margin-top:6px;" onclick="generateArsenalItem()">
            🚀 Create &amp; Assemble Godot Scene
          </button>
        </div>

        <!-- Quick Equip to Active Character -->
        <div class="card" style="background:#0d111a;border:1px solid var(--border);">
          <div style="font-size:12px;font-weight:600;color:var(--text);margin-bottom:6px;">🔗 Equip to Selected Character</div>
          <div style="font-size:11px;color:var(--text-muted);margin-bottom:10px;">Select a character in Asset Library, then click "Equip" on any weapon below to bind it to their WeaponSlot marker.</div>
          <div style="display:flex;align-items:center;justify-content:space-between;background:rgba(255,255,255,0.03);padding:8px 12px;border-radius:6px;">
            <span style="font-size:12px;color:var(--text-muted);">Active Character:</span>
            <span id="equip-active-char-name" style="font-size:12px;font-weight:600;color:var(--primary);">None selected</span>
          </div>
        </div>
      </div>

      <!-- Right Column: Interactive Firing Range & Arsenal Gallery -->
      <div style="display:flex;flex-direction:column;gap:18px;">
        <!-- Interactive Live Firing Range -->
        <div class="card" style="padding:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px;">
            <div style="font-size:14px;font-weight:700;color:#fff;display:flex;align-items:center;gap:8px;">
              <span>🎯 Live Cyberpunk Firing Range</span>
              <span class="lib-badge lib-badge-anim">Real-time Ballistics</span>
            </div>
            <div style="display:flex;gap:8px;align-items:center;">
              <select id="range-select-weapon" style="font-size:11.5px;padding:4px 8px;background:var(--bg-input);border:1px solid var(--border);color:var(--text);border-radius:5px;" onchange="onRangeWeaponChanged()">
                <option value="">Load weapon...</option>
              </select>
              <select id="range-select-proj" style="font-size:11.5px;padding:4px 8px;background:var(--bg-input);border:1px solid var(--border);color:var(--text);border-radius:5px;" onchange="onRangeProjChanged()">
                <option value="">Load projectile...</option>
              </select>
              <button class="btn btn-primary btn-sm" onclick="fireRangeWeapon()" id="btn-fire-range">🔥 FIRE</button>
            </div>
          </div>

          <div class="firing-range-wrap" style="position:relative;background:#080b11;border:1px solid var(--border);border-radius:8px;height:260px;overflow:hidden;cursor:crosshair;" onclick="fireRangeWeaponAt(event)">
            <canvas id="range-canvas" width="860" height="260" style="width:100%;height:100%;display:block;"></canvas>
            <div style="position:absolute;bottom:8px;left:12px;font-size:10px;color:rgba(255,255,255,0.4);pointer-events:none;">
              CLICK ANYWHERE ON RANGE TO TARGET • SPACEBAR TO FIRE
            </div>
          </div>
        </div>

        <!-- Arsenal Gallery -->
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px;">
            <div style="display:flex;gap:6px;flex-wrap:wrap;">
              <button class="filter-chip active" id="chip-arsenal-all" onclick="setArsenalFilter('all')">All (<span id="arsenal-cnt-all">0</span>)</button>
              <button class="filter-chip" id="chip-arsenal-weapons" onclick="setArsenalFilter('weapons')">🔫 Weapons (<span id="arsenal-cnt-weapons">0</span>)</button>
              <button class="filter-chip" id="chip-arsenal-projectiles" onclick="setArsenalFilter('projectiles')">💥 Projectiles (<span id="arsenal-cnt-proj">0</span>)</button>
            </div>
            <div style="display:flex;gap:6px;flex-wrap:wrap;">
              <button class="filter-chip" id="chip-af-neotokyo" onclick="setArsenalFaction('neotokyo')" style="border-color:#00f0ff;color:#00f0ff;">🎌 Neo-Tokyo</button>
              <button class="filter-chip" id="chip-af-abyssal" onclick="setArsenalFaction('abyssal')" style="border-color:#e67e22;color:#e67e22;">☣️ Abyssal</button>
              <button class="filter-chip" id="chip-af-orbital" onclick="setArsenalFaction('orbital')" style="border-color:#2ecc71;color:#2ecc71;">🛰️ Orbital Ops</button>
              <button class="filter-chip" id="chip-af-aetherium" onclick="setArsenalFaction('aetherium')" style="border-color:#9b59b6;color:#d2a8ff;">🔮 Aetherium</button>
              <button class="filter-chip" id="chip-af-neonglitch" onclick="setArsenalFaction('neonglitch')" style="border-color:#ff007f;color:#ff79c6;">⚡ Neon Glitch</button>
              <button class="filter-chip" id="chip-af-directorate" onclick="setArsenalFaction('directorate')" style="border-color:#58a6ff;">🏛️ Directorate</button>
              <button class="filter-chip" id="chip-af-syndicate" onclick="setArsenalFaction('syndicate')" style="border-color:#e68c14;">⚙️ Syndicate</button>
              <button class="filter-chip" id="chip-af-covenant" onclick="setArsenalFaction('covenant')" style="border-color:#bc8cff;">🧠 Covenant</button>
              <button class="filter-chip" id="chip-af-bioforge" onclick="setArsenalFaction('bioforge')" style="border-color:#2ea043;">🧬 Bio-Forge</button>
              <button class="filter-chip" id="chip-af-silicon" onclick="setArsenalFaction('silicon')" style="border-color:#f85149;">⚡ Silicon</button>
              <button class="filter-chip" id="chip-af-clear" onclick="setArsenalFaction('all')">Clear</button>
            </div>
          </div>

          <div style="display:flex;gap:10px;margin-bottom:12px;">
            <input type="text" id="arsenal-search" class="lib-search" placeholder="🔍 Search weapons and projectiles..." oninput="renderArsenalGrid()">
          </div>

          <div id="arsenal-grid" class="arsenal-grid" style="display:grid;grid-template-columns:repeat(auto-fill, minmax(170px, 1fr));gap:12px;max-height:480px;overflow-y:auto;padding-right:4px;">
            <div style="text-align:center;color:var(--text-muted);padding:40px 0;grid-column:1/-1;">Loading arsenal...</div>
          </div>
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

  <!-- ======================================================= -->
  <!-- TAB: RTS SKIRMISH ARENA                                 -->
  <!-- ======================================================= -->
  <div class="tab-content" id="tab-arena">
    <div class="lib-header">
      <div>
        <div class="lib-title">🎯 Cyberpunk RTS Skirmish Arena <span id="arena-status-badge" style="font-size:12px;color:var(--text-muted);font-weight:normal;margin-left:8px;">(Ready)</span></div>
        <div style="font-size:12px;color:var(--text-muted);margin-top:2px;">
          Live Tactical Skirmish Simulator: Pit custom squads from all 15 Cyberpunk Factions against each other. Units march, detect targets, fire equipped weapons, trigger ballistics VFX, launch signature moves, and battle to the last survivor.
        </div>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        <button class="btn btn-primary btn-sm" id="btn-arena-start" onclick="startArenaBattle()">⚔️ Start Skirmish</button>
        <button class="btn btn-secondary btn-sm" id="btn-arena-pause" onclick="toggleArenaPause()">⏸️ Pause</button>
        <button class="btn btn-secondary btn-sm" onclick="resetArenaBattle()">🔄 Reset Arena</button>
        <button class="btn btn-secondary btn-sm" id="btn-arena-fog" onclick="toggleArenaFogOfWar()" style="border-color:rgba(0,240,255,0.4);color:#00f0ff;">👁️ Fog: OFF</button>
        <button class="btn btn-secondary btn-sm" id="btn-arena-stance" onclick="toggleArenaStance()" style="border-color:rgba(46,204,113,0.4);color:#2ecc71;">🛡️ Stance: Assault</button>
        <button class="btn btn-secondary btn-sm" id="btn-arena-audio" onclick="toggleArenaAudio()" style="border-color:rgba(0,240,255,0.4);color:#00f0ff;">🔊 SFX: ON</button>
        <button class="btn btn-secondary btn-sm" onclick="launchGodotMainScene()" style="border-color:rgba(88,166,255,0.4);color:#79c0ff;">🎮 Play in Godot 4</button>
      </div>
    </div>

    <div class="arena-grid-layout" style="display:grid;grid-template-columns:340px 1fr;gap:20px;min-height:640px;">
      <!-- Left Column: Squad Setup & Deployment -->
      <div style="display:flex;flex-direction:column;gap:16px;">
        <!-- Team 1 Setup (Blue / Alliance) -->
        <div class="card" style="border-left:4px solid #00f0ff;">
          <div class="card-title" style="display:flex;justify-content:space-between;align-items:center;">
            <span style="color:#00f0ff;">Team 1 (Blue Alliance)</span>
            <span id="arena-t1-alive-badge" class="lib-badge lib-badge-scene" style="background:#00f0ff22;color:#00f0ff;border-color:#00f0ff44;">0 Units</span>
          </div>
          <div class="form-group">
            <label for="arena-t1-faction">Faction:</label>
            <select id="arena-t1-faction" onchange="onArenaFactionChanged()">
              <option value="neotokyo" selected>🎌 Neo-Tokyo Cyber-Corps</option>
              <option value="orbital">🛰️ Orbital Black-Ops Legion</option>
              <option value="aetherium">🔮 Aetherium Psionic Syndicate</option>
              <option value="ghost_protocol">🥷 Ghost Protocol</option>
              <option value="directorate">🏛️ Neo-Terra Directorate</option>
              <option value="covenant">🧠 Neuro-Covenant</option>
              <option value="iron_valkyrie">🛡️ Iron Valkyrie</option>
              <option value="abyssal">☣️ Abyssal Sector Outcasts</option>
              <option value="neonglitch">⚡ Neon Glitch Underground</option>
              <option value="syndicate">⚙️ Rust Syndicate</option>
              <option value="silicon">🤖 Silicon Hive</option>
              <option value="bioforge">🧬 Bio-Forge Legion</option>
              <option value="neon_outcasts">🔥 Neon Outcasts</option>
              <option value="apex_transhumans">🧬 Apex Transhumans</option>
              <option value="synth_corp">🦾 Synth-Corp</option>
            </select>
          </div>
          <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">Quick-Deploy Unit to Team 1:</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;">
            <button class="btn btn-secondary btn-sm" style="font-size:10px;padding:3px 7px;" onclick="deployArenaUnit('blue', 'soldier')">+ Soldier</button>
            <button class="btn btn-secondary btn-sm" style="font-size:10px;padding:3px 7px;" onclick="deployArenaUnit('blue', 'sniper')">+ Sniper</button>
            <button class="btn btn-secondary btn-sm" style="font-size:10px;padding:3px 7px;" onclick="deployArenaUnit('blue', 'rocket')">+ Rocket</button>
            <button class="btn btn-secondary btn-sm" style="font-size:10px;padding:3px 7px;" onclick="deployArenaUnit('blue', 'flame')">+ Flame</button>
          </div>
        </div>

        <!-- Team 2 Setup (Red / Opponents) -->
        <div class="card" style="border-left:4px solid #e67e22;">
          <div class="card-title" style="display:flex;justify-content:space-between;align-items:center;">
            <span style="color:#e67e22;">Team 2 (Red Syndicate)</span>
            <span id="arena-t2-alive-badge" class="lib-badge lib-badge-anim" style="background:#e67e2222;color:#e67e22;border-color:#e67e2244;">0 Units</span>
          </div>
          <div class="form-group">
            <label for="arena-t2-faction">Faction:</label>
            <select id="arena-t2-faction" onchange="onArenaFactionChanged()">
              <option value="abyssal" selected>☣️ Abyssal Sector Outcasts</option>
              <option value="neonglitch">⚡ Neon Glitch Underground</option>
              <option value="syndicate">⚙️ Rust Syndicate</option>
              <option value="silicon">🤖 Silicon Hive</option>
              <option value="bioforge">🧬 Bio-Forge Legion</option>
              <option value="neon_outcasts">🔥 Neon Outcasts</option>
              <option value="apex_transhumans">🧬 Apex Transhumans</option>
              <option value="synth_corp">🦾 Synth-Corp</option>
              <option value="neotokyo">🎌 Neo-Tokyo Cyber-Corps</option>
              <option value="orbital">🛰️ Orbital Black-Ops Legion</option>
              <option value="aetherium">🔮 Aetherium Psionic Syndicate</option>
              <option value="ghost_protocol">🥷 Ghost Protocol</option>
              <option value="directorate">🏛️ Neo-Terra Directorate</option>
              <option value="covenant">🧠 Neuro-Covenant</option>
              <option value="iron_valkyrie">🛡️ Iron Valkyrie</option>
            </select>
          </div>
          <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">Quick-Deploy Unit to Team 2:</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;">
            <button class="btn btn-secondary btn-sm" style="font-size:10px;padding:3px 7px;" onclick="deployArenaUnit('red', 'soldier')">+ Soldier</button>
            <button class="btn btn-secondary btn-sm" style="font-size:10px;padding:3px 7px;" onclick="deployArenaUnit('red', 'sniper')">+ Sniper</button>
            <button class="btn btn-secondary btn-sm" style="font-size:10px;padding:3px 7px;" onclick="deployArenaUnit('red', 'rocket')">+ Rocket</button>
            <button class="btn btn-secondary btn-sm" style="font-size:10px;padding:3px 7px;" onclick="deployArenaUnit('red', 'flame')">+ Flame</button>
          </div>
        </div>

        <!-- Simulation Controls -->
        <div class="card">
          <div style="font-size:12px;font-weight:600;color:var(--text);margin-bottom:8px;">⚙️ Skirmish Configuration</div>
          <div class="row-2" style="margin-bottom:8px;">
            <div class="form-group" style="margin-bottom:0;">
              <label for="arena-squad-size">Squad Size:</label>
              <select id="arena-squad-size">
                <option value="3">3 vs 3 (Skirmish)</option>
                <option value="5" selected>5 vs 5 (Full Strike Team)</option>
                <option value="8">8 vs 8 (Battalion)</option>
              </select>
            </div>
            <div class="form-group" style="margin-bottom:0;">
              <label for="arena-sim-speed">Simulation Speed:</label>
              <select id="arena-sim-speed" onchange="setArenaSpeed(this.value)">
                <option value="1">1.0x Normal</option>
                <option value="1.5">1.5x Fast</option>
                <option value="2.0">2.0x Blitz</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Column: Interactive Battlefield & Combat Intel -->
      <div style="display:flex;flex-direction:column;gap:18px;">
        <!-- Interactive Battlefield Canvas Card -->
        <div class="card" style="padding:14px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <div style="display:flex;align-items:center;gap:10px;">
              <span style="font-size:13px;font-weight:700;color:var(--text);">Arena Battlefield (880×440)</span>
              <span id="arena-score-display" style="font-size:12px;font-weight:700;color:#fff;">Blue: 0  |  Red: 0</span>
            </div>
            <div style="font-size:11px;color:var(--text-muted);">
              CLICK UNIT TO INSPECT • RIGHT CLICK TO DIRECT TARGET
            </div>
          </div>

          <div style="position:relative;background:#090d14;border:1px solid var(--border);border-radius:8px;height:440px;overflow:hidden;">
            <canvas id="arena-canvas" width="880" height="440" style="width:100%;height:100%;display:block;cursor:crosshair;" onmousedown="onArenaMouseDown(event)" onmousemove="onArenaMouseMove(event)" onmouseup="onArenaMouseUp(event)" onclick="onArenaCanvasClick(event)" oncontextmenu="onArenaCanvasContextMenu(event)"></canvas>
            <div id="arena-banner" style="display:none;position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:rgba(10,14,22,0.92);border:2px solid #00f0ff;border-radius:10px;padding:16px 32px;text-align:center;box-shadow:0 8px 32px rgba(0,240,255,0.3);z-index:10;">
              <div id="arena-banner-title" style="font-size:22px;font-weight:800;color:#00f0ff;text-transform:uppercase;">VICTORY</div>
              <div id="arena-banner-subtitle" style="font-size:12px;color:var(--text-muted);margin-top:4px;">All opposing forces eliminated</div>
              <button class="btn btn-primary btn-sm" style="margin-top:12px;" onclick="resetArenaBattle()">Play Next Round</button>
            </div>
          </div>
        </div>

        <!-- Selected Unit Tactical Command Bar -->
        <div class="card" id="arena-unit-command-bar" style="display:none;padding:10px 14px;border-left:4px solid #00f0ff;background:rgba(13,20,32,0.85);">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;flex-wrap:wrap;gap:8px;">
            <div style="display:flex;align-items:center;gap:10px;">
              <span id="cmd-unit-title" style="font-size:13px;font-weight:700;color:#00f0ff;">Selected Unit: Kinetic Hunter</span>
              <span id="cmd-unit-role" class="lib-badge lib-badge-anim" style="font-size:10px;padding:2px 6px;">Soldier</span>
              <span id="cmd-unit-hp-text" style="font-size:11px;color:var(--text-muted);">HP: 140/140</span>
            </div>
            <div style="font-size:10px;color:#79c0ff;letter-spacing:0.5px;">
              CLICK CANVAS (RIGHT-CLICK) TO MOVE / TARGET
            </div>
          </div>
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
            <span style="font-size:11px;font-weight:600;color:var(--text-muted);">Unleash Special Move:</span>
            <button class="btn btn-secondary btn-sm" id="cmd-move-0" onclick="triggerManualSpecialMove(0)" style="font-size:10px;padding:2px 7px;border-color:rgba(0,240,255,0.4);color:#00f0ff;">⚡ Overload Burst</button>
            <button class="btn btn-secondary btn-sm" id="cmd-move-1" onclick="triggerManualSpecialMove(1)" style="font-size:10px;padding:2px 7px;border-color:rgba(255,0,127,0.4);color:#ff007f;">🎯 Hyper-Focus Crit</button>
            <button class="btn btn-secondary btn-sm" id="cmd-move-2" onclick="triggerManualSpecialMove(2)" style="font-size:10px;padding:2px 7px;border-color:rgba(255,195,0,0.4);color:#ffc300;">💥 Orbital Strike</button>
            <button class="btn btn-secondary btn-sm" id="cmd-move-3" onclick="triggerManualSpecialMove(3)" style="font-size:10px;padding:2px 7px;border-color:rgba(46,204,113,0.4);color:#2ecc71;">🛡️ Kinetic Surge</button>
            <button class="btn btn-secondary btn-sm" id="cmd-move-4" onclick="triggerManualSpecialMove(4)" style="font-size:10px;padding:2px 7px;border-color:rgba(168,85,247,0.4);color:#a855f7;">⚡ EMP Nova</button>
            <button class="btn btn-secondary btn-sm" id="cmd-move-5" onclick="triggerManualSpecialMove(5)" style="font-size:10px;padding:2px 7px;border-color:rgba(140,255,40,0.4);color:#8cff28;">☣️ Nanite Swarm</button>
          </div>
        </div>

        <!-- Combat Intel Log & Action Feed -->
        <div class="card" style="padding:12px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <span style="font-size:12px;font-weight:600;color:var(--text);">📡 Live Tactical Battle Intel</span>
            <button class="btn btn-secondary btn-sm" style="font-size:10px;padding:2px 6px;" onclick="clearArenaLog()">Clear Feed</button>
          </div>
          <div id="arena-combat-feed" style="background:#06080e;border:1px solid var(--border);border-radius:6px;height:120px;overflow-y:auto;padding:8px 10px;font-family:monospace;font-size:11px;display:flex;flex-direction:column;gap:4px;">
            <div style="color:var(--text-muted);">[ARENA READY] Select factions and click "Start Skirmish" to deploy units into combat.</div>
          </div>
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
  const targetContent = document.getElementById('tab-' + name);
  const targetBtn = document.getElementById('tab-btn-' + name);
  if (targetContent) targetContent.classList.add('active');
  if (targetBtn) targetBtn.classList.add('active');
  if (name === 'library') refreshLibrary();
  if (name === 'weapons') { refreshArsenal(); initFiringRangeCanvas(); }
  if (name === 'models') checkModelStatus();
  if (name === 'arena') initArena();
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
        specials: [
          document.getElementById("spec-slot-1")?.value || "special_ground_slam",
          document.getElementById("spec-slot-2")?.value || "special_whirlwind",
          document.getElementById("spec-slot-3")?.value || "special_power_charge",
          document.getElementById("spec-slot-4")?.value || "special_victory_flourish"
        ],
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

// ---- Asset Library & 23-Animation Player Engine ----
let rosterFilter = "all";
let currentViewerSubTab = "anim";
let animCatalog = null;
let currentAnimName = "idle";
let animCurrentTime = 0.0;
let animSpeed = 1.0;
let animIsPlaying = true;
let showSkeletonOverlay = false;
let animLastFrameTime = performance.now();
let loadedLimbImages = {};
let animRafId = null;

const ANIM_CATEGORIES = {
  idle: "Locomotion", walk: "Locomotion", run: "Locomotion", jump: "Locomotion", double_jump: "Locomotion",
  dash: "Locomotion", slide: "Locomotion", crouch: "Locomotion", crouch_walk: "Locomotion",
  punch: "Combat", hit: "Combat", kick: "Combat", jump_kick: "Combat", crouch_kick: "Combat", fire_weapon: "Combat",
  get_hit: "Status", get_stunned: "Status", drink_potion: "Status", death: "Status",
  special_01: "Special", special_02: "Special", special_03: "Special", special_04: "Special"
};

// Built-in fallback animation catalog with 23 animations
const FALLBACK_ANIM_DEFS = {
  idle: { length: 1.8, loop: 1, desc: "Breathing rest stance with gentle head and arm sway", tracks: { "Skeleton2D/pelvis/torso:position": [[0,[0,-40]],[0.9,[0,-42]],[1.8,[0,-40]]], "Skeleton2D/pelvis/torso/head:rotation": [[0,0],[0.9,-0.035],[1.8,0]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0],[0.9,0.045],[1.8,0]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,0],[0.9,-0.045],[1.8,0]] } },
  walk: { length: 0.8, loop: 1, desc: "Natural biped walk cycle with counter-swinging arms and legs", tracks: { "Skeleton2D/pelvis:position": [[0,[0,0]],[0.2,[0,-3]],[0.4,[0,0]],[0.6,[0,-3]],[0.8,[0,0]]], "Skeleton2D/pelvis/torso:rotation": [[0,-0.04],[0.4,0.04],[0.8,-0.04]], "Skeleton2D/pelvis/leg_upper_L:rotation": [[0,-0.45],[0.2,0.1],[0.4,0.45],[0.6,-0.1],[0.8,-0.45]], "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [[0,0.1],[0.2,0.6],[0.4,0],[0.6,0.2],[0.8,0.1]], "Skeleton2D/pelvis/leg_upper_R:rotation": [[0,0.45],[0.2,-0.1],[0.4,-0.45],[0.6,0.1],[0.8,0.45]], "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [[0,0],[0.2,0.2],[0.4,0.1],[0.6,0.6],[0.8,0]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0.4],[0.4,-0.4],[0.8,0.4]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,-0.4],[0.4,0.4],[0.8,-0.4]] } },
  run: { length: 0.5, loop: 1, desc: "High-speed athletic sprint with forward lean and high knees", tracks: { "Skeleton2D/pelvis:position": [[0,[0,0]],[0.125,[0,-7]],[0.25,[0,2]],[0.375,[0,-7]],[0.5,[0,0]]], "Skeleton2D/pelvis/torso:rotation": [[0,-0.18],[0.25,-0.15],[0.5,-0.18]], "Skeleton2D/pelvis/leg_upper_L:rotation": [[0,-0.85],[0.125,-0.2],[0.25,0.7],[0.375,0.1],[0.5,-0.85]], "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [[0,0.3],[0.125,1.1],[0.25,0],[0.375,0.6],[0.5,0.3]], "Skeleton2D/pelvis/leg_upper_R:rotation": [[0,0.7],[0.125,0.1],[0.25,-0.85],[0.375,-0.2],[0.5,0.7]], "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [[0,0],[0.125,0.6],[0.25,0.3],[0.375,1.1],[0.5,0]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0.75],[0.25,-0.75],[0.5,0.75]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,-0.75],[0.25,0.75],[0.5,-0.75]] } },
  jump: { length: 0.6, loop: 0, desc: "Anticipation dip, vertical thrust, airborne knee tuck", tracks: { "Skeleton2D/pelvis:position": [[0,[0,0]],[0.1,[0,8]],[0.3,[0,-32]],[0.6,[0,-20]]], "Skeleton2D/pelvis/torso:rotation": [[0,0],[0.1,0.1],[0.3,-0.1],[0.6,-0.05]], "Skeleton2D/pelvis/leg_upper_L:rotation": [[0,0],[0.1,-0.5],[0.3,-0.7],[0.6,-0.3]], "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [[0,0],[0.1,0.8],[0.3,1.1],[0.6,0.4]], "Skeleton2D/pelvis/leg_upper_R:rotation": [[0,0],[0.1,-0.5],[0.3,-0.5],[0.6,-0.2]], "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [[0,0],[0.1,0.8],[0.3,0.9],[0.6,0.3]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0],[0.1,0.5],[0.3,-1.4],[0.6,-0.8]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,0],[0.1,0.5],[0.3,-1.4],[0.6,-0.8]] } },
  double_jump: { length: 0.5, loop: 0, desc: "Mid-air somersault tuck and explosive secondary boost", tracks: { "Skeleton2D/pelvis:position": [[0,[0,0]],[0.2,[0,-18]],[0.5,[0,-35]]], "Skeleton2D/pelvis/torso:rotation": [[0,0],[0.15,-1.6],[0.3,-3.14],[0.5,0]], "Skeleton2D/pelvis/leg_upper_L:rotation": [[0,-0.3],[0.2,-1.3],[0.5,-0.2]], "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [[0,0.4],[0.2,1.6],[0.5,0.2]], "Skeleton2D/pelvis/leg_upper_R:rotation": [[0,-0.2],[0.2,-1.2],[0.5,-0.1]], "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [[0,0.3],[0.2,1.5],[0.5,0.2]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,-0.5],[0.2,-2.0],[0.5,-0.6]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,-0.5],[0.2,-2.0],[0.5,-0.6]] } },
  crouch: { length: 0.4, loop: 0, desc: "Drops pelvis, knees bend, defensive low profile", tracks: { "Skeleton2D/pelvis:position": [[0,[0,0]],[0.4,[0,18]]], "Skeleton2D/pelvis/torso:rotation": [[0,0],[0.4,-0.15]], "Skeleton2D/pelvis/leg_upper_L:rotation": [[0,0],[0.4,-0.75]], "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [[0,0],[0.4,1.35]], "Skeleton2D/pelvis/leg_upper_R:rotation": [[0,0],[0.4,-0.75]], "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [[0,0],[0.4,1.35]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0],[0.4,-0.4]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,0],[0.4,-0.4]] } },
  crouch_walk: { length: 0.9, loop: 1, desc: "Stealth low shuffle with crouched knees and tucked arms", tracks: { "Skeleton2D/pelvis:position": [[0,[0,16]],[0.45,[0,14]],[0.9,[0,16]]], "Skeleton2D/pelvis/torso:rotation": [[0,-0.12],[0.45,-0.16],[0.9,-0.12]], "Skeleton2D/pelvis/leg_upper_L:rotation": [[0,-0.9],[0.45,-0.4],[0.9,-0.9]], "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [[0,1.4],[0.45,1.1],[0.9,1.4]], "Skeleton2D/pelvis/leg_upper_R:rotation": [[0,-0.4],[0.45,-0.9],[0.9,-0.4]], "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [[0,1.1],[0.45,1.4],[0.9,1.1]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,-0.2],[0.45,-0.5],[0.9,-0.2]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,-0.5],[0.45,-0.2],[0.9,-0.5]] } },
  dash: { length: 0.35, loop: 0, desc: "High velocity speed dash, aerodynamic forward thrust", tracks: { "Skeleton2D/pelvis:position": [[0,[0,0]],[0.1,[12,-4]],[0.35,[20,0]]], "Skeleton2D/pelvis/torso:rotation": [[0,0],[0.1,-0.35],[0.35,-0.2]], "Skeleton2D/pelvis/leg_upper_L:rotation": [[0,0],[0.15,-0.9],[0.35,-0.4]], "Skeleton2D/pelvis/leg_upper_R:rotation": [[0,0],[0.15,0.8],[0.35,0.3]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0],[0.15,0.95],[0.35,0.4]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,0],[0.15,0.85],[0.35,0.3]] } },
  slide: { length: 0.5, loop: 0, desc: "Baseball action slide on ground, lead leg straight", tracks: { "Skeleton2D/pelvis:position": [[0,[0,0]],[0.15,[0,26]],[0.5,[0,24]]], "Skeleton2D/pelvis/torso:rotation": [[0,0],[0.2,0.42],[0.5,0.35]], "Skeleton2D/pelvis/leg_upper_L:rotation": [[0,0],[0.2,-1.25],[0.5,-1.15]], "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [[0,0],[0.2,0.1],[0.5,0.05]], "Skeleton2D/pelvis/leg_upper_R:rotation": [[0,0],[0.2,0.65],[0.5,0.6]], "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [[0,0],[0.2,1.55],[0.5,1.5]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0],[0.2,-0.6],[0.5,-0.4]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,0],[0.2,0.9],[0.5,0.7]] } },
  fire_weapon: { length: 0.4, loop: 0, desc: "Quick weapon draw, forward aim and crisp recoil kick", tracks: { "Skeleton2D/pelvis/torso:rotation": [[0,0],[0.08,-0.05],[0.15,0.08],[0.4,0]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0],[0.08,-1.45],[0.15,-1.65],[0.4,0]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,0],[0.08,-1.1],[0.15,-1.25],[0.4,0]] } },
  punch: { length: 0.35, loop: 0, desc: "Explosive straight jab punch with fast snap-back", tracks: { "Skeleton2D/pelvis/torso:rotation": [[0,0],[0.08,0.15],[0.16,-0.25],[0.35,0]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0],[0.08,0.3],[0.16,-1.4],[0.35,0]], "Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L:rotation": [[0,0],[0.08,-1.3],[0.16,0],[0.35,0]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,0],[0.16,0.4],[0.35,0]] } },
  hit: { length: 0.45, loop: 0, desc: "Heavy melee weapon downward cleaving strike", tracks: { "Skeleton2D/pelvis/torso:position": [[0,[0,-40]],[0.15,[0,-44]],[0.25,[0,-38]],[0.45,[0,-40]]], "Skeleton2D/pelvis/torso:rotation": [[0,0],[0.15,0.2],[0.25,-0.25],[0.45,0]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0],[0.15,-1.8],[0.25,0.6],[0.45,0]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,0],[0.15,-1.5],[0.25,0.4],[0.45,0]] } },
  kick: { length: 0.45, loop: 0, desc: "High snap kick with lead leg extension", tracks: { "Skeleton2D/pelvis:position": [[0,[0,0]],[0.18,[0,-4]],[0.45,[0,0]]], "Skeleton2D/pelvis/torso:rotation": [[0,0],[0.18,0.25],[0.45,0]], "Skeleton2D/pelvis/leg_upper_L:rotation": [[0,0],[0.1,-1.1],[0.2,-1.45],[0.3,-1.0],[0.45,0]], "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [[0,0],[0.1,1.4],[0.2,0],[0.3,0.9],[0.45,0]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0],[0.2,0.5],[0.45,0]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,0],[0.2,-0.6],[0.45,0]] } },
  jump_kick: { length: 0.55, loop: 0, desc: "Aerial flying dropkick with horizontal body extension", tracks: { "Skeleton2D/pelvis:position": [[0,[0,0]],[0.2,[0,-28]],[0.55,[0,0]]], "Skeleton2D/pelvis/torso:rotation": [[0,0],[0.2,-0.55],[0.55,0]], "Skeleton2D/pelvis/leg_upper_L:rotation": [[0,0],[0.2,-1.5],[0.55,0]], "Skeleton2D/pelvis/leg_upper_R:rotation": [[0,0],[0.2,0.7],[0.55,0]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0],[0.2,0.8],[0.55,0]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,0],[0.2,0.7],[0.55,0]] } },
  crouch_kick: { length: 0.4, loop: 0, desc: "Low floor sweep kick sweeping forward along ground", tracks: { "Skeleton2D/pelvis:position": [[0,[0,18]],[0.18,[0,22]],[0.4,[0,18]]], "Skeleton2D/pelvis/torso:rotation": [[0,-0.15],[0.18,0.3],[0.4,-0.15]], "Skeleton2D/pelvis/leg_upper_L:rotation": [[0,-0.75],[0.18,-1.3],[0.4,-0.75]], "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [[0,1.35],[0.18,0.1],[0.4,1.35]], "Skeleton2D/pelvis/leg_upper_R:rotation": [[0,-0.75],[0.18,0.4],[0.4,-0.75]], "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [[0,1.35],[0.18,1.6],[0.4,1.35]] } },
  get_hit: { length: 0.35, loop: 0, desc: "Impact hurt flinch, head snapped back and torso recoil", tracks: { "Skeleton2D/pelvis:position": [[0,[0,0]],[0.08,[-10,-2]],[0.35,[0,0]]], "Skeleton2D/pelvis/torso:rotation": [[0,0],[0.08,0.28],[0.35,0]], "Skeleton2D/pelvis/torso/head:rotation": [[0,0],[0.08,0.35],[0.35,0]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0],[0.08,-0.75],[0.35,0]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,0],[0.08,0.75],[0.35,0]] } },
  get_stunned: { length: 1.0, loop: 1, desc: "Dazed dizzy wobble loop with limp arms and swaying head", tracks: { "Skeleton2D/pelvis:position": [[0,[0,0]],[0.25,[3,-2]],[0.5,[0,2]],[0.75,[-3,-2]],[1.0,[0,0]]], "Skeleton2D/pelvis/torso:rotation": [[0,-0.08],[0.5,0.08],[1.0,-0.08]], "Skeleton2D/pelvis/torso/head:rotation": [[0,0.2],[0.5,-0.2],[1.0,0.2]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0.15],[0.5,-0.15],[1.0,0.15]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,-0.15],[0.5,0.15],[1.0,-0.15]] } },
  death: { length: 0.8, loop: 0, desc: "Knees buckle, body goes limp and collapses to floor", tracks: { "Skeleton2D/pelvis:position": [[0,[0,0]],[0.25,[0,15]],[0.55,[0,36]],[0.8,[0,36]]], "Skeleton2D/pelvis/torso:rotation": [[0,0],[0.25,0.4],[0.55,1.45],[0.8,1.55]], "Skeleton2D/pelvis/torso/head:rotation": [[0,0],[0.25,0.2],[0.55,0.5],[0.8,0.5]], "Skeleton2D/pelvis/leg_upper_L:rotation": [[0,0],[0.25,0.6],[0.55,1.4],[0.8,1.45]], "Skeleton2D/pelvis/leg_upper_R:rotation": [[0,0],[0.25,0.5],[0.55,1.3],[0.8,1.35]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0],[0.25,-0.4],[0.55,1.2],[0.8,1.3]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,0],[0.25,0.4],[0.55,1.0],[0.8,1.1]] } },
  drink_potion: { length: 1.0, loop: 0, desc: "Raise potion vial to mouth, head tilts back to chug", tracks: { "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0],[0.25,-1.35],[0.6,-1.45],[1.0,0]], "Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L:rotation": [[0,0],[0.25,-1.5],[0.6,-1.6],[1.0,0]], "Skeleton2D/pelvis/torso/head:rotation": [[0,0],[0.25,0],[0.5,0.38],[0.75,0.38],[1.0,0]], "Skeleton2D/pelvis/torso:rotation": [[0,0],[0.5,0.08],[1.0,0]] } },
  special_01: { length: 0.8, loop: 0, desc: "Ground Slam: high airborne leap with dual overhead strike", tracks: { "Skeleton2D/pelvis:position": [[0,[0,0]],[0.2,[0,-25]],[0.45,[0,16]],[0.8,[0,0]]], "Skeleton2D/pelvis/torso:rotation": [[0,0],[0.2,0.3],[0.45,-0.35],[0.8,0]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0],[0.2,-2.1],[0.45,0.75],[0.8,0]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,0],[0.2,-2.1],[0.45,0.75],[0.8,0]], "Skeleton2D/pelvis/leg_upper_L:rotation": [[0,0],[0.2,-0.6],[0.45,-0.8],[0.8,0]], "Skeleton2D/pelvis/leg_upper_R:rotation": [[0,0],[0.2,-0.6],[0.45,-0.8],[0.8,0]] } },
  special_02: { length: 0.6, loop: 1, desc: "Whirlwind Spin: rapid 360-degree blade spin with arms out", tracks: { "Skeleton2D/pelvis:position": [[0,[0,-2]],[0.3,[0,-4]],[0.6,[0,-2]]], "Skeleton2D/pelvis/torso:rotation": [[0,-0.05],[0.15,0.05],[0.3,-0.05],[0.45,0.05],[0.6,-0.05]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,-1.55],[0.3,-1.6],[0.6,-1.55]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,1.55],[0.3,1.6],[0.6,1.55]], "Skeleton2D/pelvis/leg_upper_L:rotation": [[0,-0.3],[0.3,0.3],[0.6,-0.3]], "Skeleton2D/pelvis/leg_upper_R:rotation": [[0,0.3],[0.3,-0.3],[0.6,0.3]] } },
  special_03: { length: 1.2, loop: 1, desc: "Arcane Power Charge: chest arched, surging energy", tracks: { "Skeleton2D/pelvis:position": [[0,[0,0]],[0.3,[0,4]],[0.6,[0,-1]],[0.9,[0,4]],[1.2,[0,0]]], "Skeleton2D/pelvis/torso:position": [[0,[0,-40]],[0.3,[0,-38]],[0.6,[0,-42]],[0.9,[0,-38]],[1.2,[0,-40]]], "Skeleton2D/pelvis/torso:rotation": [[0,0],[0.3,0.12],[0.6,0.15],[0.9,0.12],[1.2,0]], "Skeleton2D/pelvis/torso/head:rotation": [[0,0],[0.3,0.28],[0.6,0.35],[0.9,0.28],[1.2,0]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0],[0.3,-0.65],[0.6,-0.75],[0.9,-0.65],[1.2,0]], "Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L:rotation": [[0,0],[0.3,-1.25],[0.6,-1.35],[0.9,-1.25],[1.2,0]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,0],[0.3,0.65],[0.6,0.75],[0.9,0.65],[1.2,0]], "Skeleton2D/pelvis/torso/arm_upper_R/arm_lower_R:rotation": [[0,0],[0.3,-1.25],[0.6,-1.35],[0.9,-1.25],[1.2,0]] } },
  special_04: { length: 1.1, loop: 0, desc: "Heroic Victory Flourish: spin weapon, crisp hip sheath", tracks: { "Skeleton2D/pelvis/torso:position": [[0,[0,-40]],[0.4,[0,-40]],[0.7,[0,-43]],[1.1,[0,-42]]], "Skeleton2D/pelvis/torso:rotation": [[0,0],[0.4,-0.1],[0.7,-0.05],[1.1,-0.05]], "Skeleton2D/pelvis/torso/head:rotation": [[0,0],[0.4,0.1],[0.7,-0.08],[1.1,-0.05]], "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [[0,0],[0.3,-1.6],[0.6,0.3],[0.85,-1.2],[1.1,-0.8]], "Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L:rotation": [[0,0],[0.3,-0.3],[0.6,-0.8],[0.85,-0.5],[1.1,-0.3]], "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [[0,0],[0.4,0.2],[0.7,-0.4],[1.1,-0.3]] } }
};

async function initAnimCatalog() {
  try {
    const r = await fetch('/api/animations');
    const d = await r.json();
    if (d.status === 'ok' && d.animations) {
      animCatalog = d.animations;
    } else {
      animCatalog = FALLBACK_ANIM_DEFS;
    }
  } catch(e) {
    animCatalog = FALLBACK_ANIM_DEFS;
  }
}

function setRosterFilter(f) {
  rosterFilter = f;
  document.querySelectorAll('.roster-filter-bar .filter-chip').forEach(el => el.classList.remove('active'));
  const chip = document.getElementById(`chip-filter-${f}`);
  if (chip) chip.classList.add('active');
  filterRoster();
}

function filterRoster() {
  const q = (document.getElementById("lib-search")?.value || "").toLowerCase().trim();
  let filtered = allLibraryChars;
  const knownFactions = [
    "neotokyo", "abyssal", "orbital", "aetherium", "neonglitch",
    "directorate", "syndicate", "covenant", "bioforge", "silicon",
    "ghost_protocol", "iron_valkyrie", "neon_outcasts", "apex_transhumans", "synth_corp"
  ];
  if (rosterFilter === "scenes") {
    filtered = filtered.filter(c => c.has_godot_scene);
  } else if (rosterFilter === "exploded") {
    filtered = filtered.filter(c => c.has_exploded_sheet);
  } else if (rosterFilter === "pixel_anime") {
    filtered = filtered.filter(c => (c.art_style || "").toLowerCase() === "pixel_anime" || ["ghost_protocol", "iron_valkyrie", "neon_outcasts", "apex_transhumans", "synth_corp", "neonglitch"].includes((c.faction_id || "").toLowerCase()));
  } else if (knownFactions.includes(rosterFilter)) {
    filtered = filtered.filter(c => (c.faction_id || "").toLowerCase() === rosterFilter);
  }

  if (q) {
    filtered = filtered.filter(c =>
      c.name.toLowerCase().includes(q) ||
      (c.display_name && c.display_name.toLowerCase().includes(q)) ||
      (c.role && c.role.toLowerCase().includes(q)) ||
      (c.faction_name && c.faction_name.toLowerCase().includes(q)) ||
      (c.model_engine && c.model_engine.toLowerCase().includes(q))
    );
  }
  renderRoster(filtered);
}

async function refreshLibrary() {
  const roster = document.getElementById("char-roster");
  roster.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:30px 0;font-size:12px;">🔄 Loading...</div>';
  try {
    const r = await fetch('/api/characters');
    const d = await r.json();
    allLibraryChars = d.characters || [];
    const countEl = document.getElementById("lib-char-count");
    if (countEl) countEl.textContent = `(${allLibraryChars.length} character${allLibraryChars.length === 1 ? '' : 's'})`;

    // Update filter counts
    const cntAll = allLibraryChars.length;
    const cntScenes = allLibraryChars.filter(c => c.has_godot_scene).length;
    const cntExploded = allLibraryChars.filter(c => c.has_exploded_sheet).length;
    const elAll = document.getElementById("count-all"); if (elAll) elAll.textContent = cntAll;
    const elSc = document.getElementById("count-scenes"); if (elSc) elSc.textContent = cntScenes;
    const elEx = document.getElementById("count-exploded"); if (elEx) elEx.textContent = cntExploded;

    ['neotokyo', 'abyssal', 'orbital', 'aetherium', 'neonglitch'].forEach(k => {
      const el = document.getElementById(`count-${k}`);
      if (el) el.textContent = allLibraryChars.filter(c => (c.faction_id || '').toLowerCase() === k).length;
    });

    filterRoster();

    // If viewing a character, re-render view; otherwise pick the first available
    if (viewingChar && allLibraryChars.some(c => c.name === viewingChar)) {
      viewCharacter(viewingChar);
    } else if (allLibraryChars.length > 0 && !viewingChar) {
      viewCharacter(allLibraryChars[0].name);
    }
  } catch(e) {
    console.error("[LIBRARY] Refresh error:", e);
    roster.innerHTML = '<div style="text-align:center;color:var(--danger);padding:30px 0;font-size:12px;">Failed to load characters. Check console for details.</div>';
  }
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
    item.dataset.name = c.name;
    item.onclick = () => viewCharacter(c.name);

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

    const fid = (c.faction_id || '').toLowerCase();
    const factionColor = fid === 'neotokyo'         ? '#00f0ff' :
                         fid === 'abyssal'          ? '#e67e22' :
                         fid === 'orbital'          ? '#2ecc71' :
                         fid === 'aetherium'        ? '#9b59b6' :
                         fid === 'neonglitch'       ? '#ff007f' :
                         fid === 'directorate'      ? '#58a6ff' :
                         fid === 'syndicate'        ? '#e68c14' :
                         fid === 'covenant'         ? '#bc8cff' :
                         fid === 'bioforge'         ? '#2ea043' :
                         fid === 'silicon'          ? '#f85149' :
                         fid === 'ghost_protocol'   ? '#39c5bb' :
                         fid === 'iron_valkyrie'    ? '#d29922' :
                         fid === 'neon_outcasts'    ? '#f778ba' :
                         fid === 'apex_transhumans' ? '#a371f7' :
                         fid === 'synth_corp'       ? '#ff7b72' : '#8b949e';

    const roleBadge = c.role ? `<span class="role-badge" style="border-color:${factionColor}44;color:${factionColor};background:${factionColor}12;">${c.role}</span>` : '';
    const modelBadge = c.model_key ? `<span class="role-badge" style="border-color:#388bfd44;color:#79c0ff;background:#388bfd12;">${c.model_key.replace('_', ' ')}</span>` : '';
    const factionDot = c.faction_name ? `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${factionColor};margin-right:4px;" title="${c.faction_name}"></span>` : '';
    const displayName = c.display_name || c.name.replace(/_/g, ' ');

    const sceneBadge = c.has_godot_scene
      ? '<span class="lib-badge lib-badge-scene">🎮 Scene</span>'
      : '<span class="lib-badge lib-badge-no-scene">No Scene</span>';
    const animBadge = '<span class="lib-badge lib-badge-anim">23 Anims</span>';

    item.innerHTML = `
      ${thumbHtml}
      <div class="char-roster-info">
        <div class="char-roster-name" style="display:flex;align-items:center;">${factionDot}${displayName}</div>
        <div class="char-roster-meta">
          ${roleBadge}
          ${modelBadge}
          <span>${c.limb_count} limbs</span>
          ${animBadge}
          ${sceneBadge}
        </div>
      </div>
    `;
    roster.appendChild(item);
  });
}

function switchViewerSubTab(tabName) {
  currentViewerSubTab = tabName;
  document.querySelectorAll('.subnav-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.viewer-subpane').forEach(p => p.classList.remove('active'));
  const btn = document.getElementById(`subnav-${tabName}`);
  const pane = document.getElementById(`subpane-${tabName}`);
  if (btn) btn.classList.add('active');
  if (pane) pane.classList.add('active');
}

async function viewCharacter(name) {
  viewingChar = name;

  // Highlight selected in roster
  document.querySelectorAll('.char-roster-item').forEach(el => el.classList.remove('selected'));
  document.querySelectorAll('.char-roster-item').forEach(el => {
    if (el.dataset.name === name || el.querySelector('.char-roster-name')?.textContent.includes(name.replace(/_/g, ' '))) {
      el.classList.add('selected');
    }
  });

  document.getElementById("viewer-empty").style.display = "none";
  document.getElementById("viewer-content").style.display = "block";

  const charInfo = allLibraryChars.find(c => c.name === name) || {};
  const displayName = charInfo.display_name || name.replace(/_/g, ' ');
  document.getElementById("viewer-char-name").textContent = displayName;
  document.getElementById("viewer-char-meta").textContent =
    `${charInfo.limb_count || 15} limb cutouts • 23 Skeletal Animations • ${charInfo.has_godot_scene ? 'Godot 4 Scene Ready' : 'Scene Pending'}${charInfo.role ? ' • Role: ' + charInfo.role : ''}${charInfo.faction_name ? ' • Faction: ' + charInfo.faction_name : ''}${charInfo.model_engine ? ' • Model: ' + charInfo.model_engine : ''}`;

  const equipActiveEl = document.getElementById("equip-active-char-name");
  if (equipActiveEl) equipActiveEl.textContent = displayName;

  // Dynamically update the 4 Special & Signature Moves chips in the Animation Player
  const specials = charInfo.specials || ["special_ground_slam", "special_whirlwind", "special_power_charge", "special_victory_flourish"];
  const details = charInfo.special_details || [];
  for (let i = 1; i <= 4; i++) {
    const chip = document.querySelector(`.anim-chip[data-anim="special_0${i}"]`);
    if (chip) {
      const spKey = specials[i-1] || `special_0${i}`;
      const det = details[i-1] || (specialMovesCatalog && specialMovesCatalog[spKey]) || {};
      const spName = det.name || spKey.replace(/^special_/, '').replace(/_/g, ' ').replace(/\\b\\w/g, l => l.toUpperCase());
      const icon = i === 1 ? '💥' : i === 2 ? '🌪️' : i === 3 ? '⚡' : '👑';
      chip.textContent = `${icon} special_0${i} (${spName})`;
      chip.title = det.desc || spKey;
    }
  }

  // Update full assembled body preview
  const fullImg = document.getElementById("viewer-full-img");
  if (fullImg) {
    fullImg.src = `/sprites/${name}/${name}_full.png?t=${Date.now()}`;
  }

  // Populate Master Exploded Sheet pane
  const expWrap = document.getElementById("exploded-wrap");
  const expEmpty = document.getElementById("exploded-empty");
  const expImg = document.getElementById("viewer-exploded-img");
  const expMeta = document.getElementById("exploded-meta-card");
  const expDl = document.getElementById("btn-download-exploded");
  const expTitle = document.getElementById("exploded-char-title");

  if (charInfo.has_exploded_sheet || true) {
    const expUrl = `/sprites/${name}/${name}_exploded.png`;
    expImg.src = `${expUrl}?t=${Date.now()}`;
    expWrap.style.display = "flex";
    expMeta.style.display = "flex";
    expEmpty.style.display = "none";
    expTitle.textContent = `${name.replace(/_/g, ' ')} Master Exploded Diffusion Sheet`;
    expDl.href = expUrl;
    expDl.setAttribute("download", `${name}_exploded.png`);
  }

  // Populate Godot Scene Specs pane
  const scenePathEl = document.getElementById("spec-scene-path");
  if (scenePathEl) scenePathEl.textContent = charInfo.scene_path || `res://scenes/${name}_character.tscn`;
  populateAnimTable();

  // Load Sprites Grid for Subpane 2
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
      grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:var(--text-muted);padding:40px;font-size:12px;">No individual cutouts found.</div>';
    }
  } catch(e) {}

  // Load Sprites Grid for Subpane 2 AND populate loadedLimbImages with verified URLs
  try {
    const r = await fetch(`/api/sprites?char=${encodeURIComponent(name)}`);
    const d = await r.json();
    const grid = document.getElementById("viewer-grid");
    grid.innerHTML = "";
    if (d.sprites && d.sprites.length > 0) {
      d.sprites.forEach(s => {
        // Register image in loadedLimbImages map directly from exact URL
        const limbImg = new Image();
        limbImg.src = `${s.url}?t=${Date.now()}`;
        limbImg.onload = () => {
          loadedLimbImages[s.bone] = limbImg;
          loadedLimbImages[s.bone.toLowerCase()] = limbImg;
        };

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
      grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:var(--text-muted);padding:40px;font-size:12px;">No individual cutouts found.</div>';
    }
  } catch(e) {}

  // Load limbs into memory for 2D Live Animation Player
  loadLimbImagesForChar(name);
  selectAnim(currentAnimName || "idle");
  ensureAnimLoopRunning();
}

function openExplodedLightbox() {
  if (!viewingChar) return;
  const expUrl = `/sprites/${viewingChar}/${viewingChar}_exploded.png`;
  openLightbox(expUrl, `${viewingChar.replace(/_/g, ' ')} (Master Exploded Sheet)`, '1024×1024 RGBA Generative Sheet');
}

function populateAnimTable() {
  const tbody = document.getElementById("spec-anim-table-body");
  if (!tbody) return;
  tbody.innerHTML = "";
  const cat = animCatalog || FALLBACK_ANIM_DEFS;
  Object.entries(cat).forEach(([key, data]) => {
    const tr = document.createElement("tr");
    const category = ANIM_CATEGORIES[key] || "Movement";
    const loopStr = data.loop ? "🔁 Yes" : "⏹ One-Shot";
    tr.innerHTML = `
      <td><strong style="color:var(--text);">${key}</strong><div style="font-size:10.5px;color:var(--text-muted);">${data.desc || ''}</div></td>
      <td><span style="font-size:11px;padding:2px 6px;border-radius:4px;background:rgba(255,255,255,0.04);border:1px solid var(--border);">${category}</span></td>
      <td>${data.length}s</td>
      <td>${loopStr}</td>
      <td><button class="btn btn-secondary btn-sm" onclick="selectAnim('${key}');switchViewerSubTab('anim');">▶ Play</button></td>
    `;
    tbody.appendChild(tr);
  });
}

// ---- 2D Animation Player Canvas Engine ----
const BONE_LIMBS = ["head", "torso", "arm_upper_L", "arm_lower_L", "hand_L", "arm_upper_R", "arm_lower_R", "hand_R", "leg_upper_L", "leg_lower_L", "foot_L", "leg_upper_R", "leg_lower_R", "foot_R", "pelvis"];

let renderMode = "full"; // "limbs" | "full"
let autoLoop = true;

function setRenderMode(m) {
  renderMode = m;
  const btnLimbs = document.getElementById("btn-mode-limbs");
  const btnFull = document.getElementById("btn-mode-full");
  if (m === "limbs") {
    if (btnLimbs) btnLimbs.className = "btn btn-sm btn-primary";
    if (btnFull) btnFull.className = "btn btn-sm btn-secondary";
  } else {
    if (btnLimbs) btnLimbs.className = "btn btn-sm btn-secondary";
    if (btnFull) btnFull.className = "btn btn-sm btn-primary";
  }
}

function loadLimbImagesForChar(charName) {
  loadedLimbImages = {};

  // 1. Full assembled body preview
  const fullImg = new Image();
  fullImg.src = `/sprites/${charName}/${charName}_full.png?t=${Date.now()}`;
  fullImg.onload = () => { loadedLimbImages["_full"] = fullImg; };
  fullImg.onerror = () => {
    const altFull = new Image();
    altFull.src = `/sprites/${charName}/full.png?t=${Date.now()}`;
    altFull.onload = () => { loadedLimbImages["_full"] = altFull; };
  };

  // 1.5. Equipped Weapon Sprite
  const charInfo = allLibraryChars.find(c => c.name === charName);
  const wpnName = (charInfo && (charInfo.equipped_weapon || charInfo.weapon_id)) || "";
  if (wpnName) {
    const wpnImg = new Image();
    wpnImg.src = `/sprites/weapons/${wpnName}.png?t=${Date.now()}`;
    wpnImg.onload = () => { loadedLimbImages["_weapon"] = wpnImg; };
    wpnImg.onerror = () => {
      if (charInfo.faction_id && !wpnName.includes("_")) {
        const altWpn = new Image();
        altWpn.src = `/sprites/weapons/${charInfo.faction_id}_${wpnName}.png?t=${Date.now()}`;
        altWpn.onload = () => { loadedLimbImages["_weapon"] = altWpn; };
      }
    };
  }

  // 2. Load all standard limbs trying prefixed format first (cyber_scion_829_head.png) then plain (head.png)
  BONE_LIMBS.forEach(bone => {
    const prefixedImg = new Image();
    prefixedImg.src = `/sprites/${charName}/${charName}_${bone}.png?t=${Date.now()}`;
    prefixedImg.onload = () => {
      loadedLimbImages[bone] = prefixedImg;
      loadedLimbImages[bone.toLowerCase()] = prefixedImg;
    };
    prefixedImg.onerror = () => {
      // Fallback: plain bone name
      const plainImg = new Image();
      plainImg.src = `/sprites/${charName}/${bone}.png?t=${Date.now()}`;
      plainImg.onload = () => {
        loadedLimbImages[bone] = plainImg;
        loadedLimbImages[bone.toLowerCase()] = plainImg;
      };
      plainImg.onerror = () => {
        // Fallback: lowercase prefixed
        const lowerImg = new Image();
        lowerImg.src = `/sprites/${charName}/${charName}_${bone.toLowerCase()}.png?t=${Date.now()}`;
        lowerImg.onload = () => {
          loadedLimbImages[bone] = lowerImg;
          loadedLimbImages[bone.toLowerCase()] = lowerImg;
        };
      };
    };
  });
}

function getEffectiveAnimDef() {
  let effectiveKey = currentAnimName;
  if (currentAnimName.startsWith("special_") && viewingChar) {
    const charInfo = allLibraryChars.find(c => c.name === viewingChar);
    if (charInfo && charInfo.specials && charInfo.specials.length >= 4) {
      const idx = parseInt(currentAnimName.split("_")[1]) - 1;
      const spKey = charInfo.specials[idx];
      if (spKey && (specialMovesCatalog[spKey] || (animCatalog && animCatalog[spKey]))) {
        effectiveKey = spKey;
      }
    }
  }
  return (specialMovesCatalog && specialMovesCatalog[effectiveKey]) ||
         (animCatalog || FALLBACK_ANIM_DEFS)[effectiveKey] ||
         (animCatalog || FALLBACK_ANIM_DEFS)[currentAnimName] ||
         { length: 1.0, loop: 1, tracks: {} };
}

function selectAnim(name) {
  currentAnimName = name;
  animCurrentTime = 0.0;
  animIsPlaying = true;
  document.querySelectorAll('.anim-chip').forEach(el => {
    if (el.dataset.anim === name) el.classList.add('active');
    else el.classList.remove('active');
  });
  const def = getEffectiveAnimDef();
  const charInfo = allLibraryChars.find(c => c.name === viewingChar);
  const displayName = charInfo ? (charInfo.display_name || viewingChar.replace(/_/g, ' ')) : 'Character';
  let moveLabel = name;
  if (name.startsWith("special_") && charInfo && charInfo.specials) {
    const idx = parseInt(name.split("_")[1]) - 1;
    const spKey = charInfo.specials[idx];
    const spObj = (specialMovesCatalog && specialMovesCatalog[spKey]) || (charInfo.special_details && charInfo.special_details[idx]);
    if (spObj && spObj.name) moveLabel = `${name} (${spObj.name})`;
  }
  const titleEl = document.getElementById("anim-overlay-title");
  if (titleEl) titleEl.textContent = `${displayName} • ${moveLabel}`;
  const descEl = document.getElementById("anim-overlay-desc");
  if (descEl) descEl.textContent = def.desc || "";
  const playBtn = document.getElementById("btn-anim-play");
  if (playBtn) playBtn.textContent = "⏸ Pause";
}

function togglePlayPause() {
  animIsPlaying = !animIsPlaying;
  const playBtn = document.getElementById("btn-anim-play");
  if (playBtn) playBtn.textContent = animIsPlaying ? "⏸ Pause" : "▶ Play";
}

function restartAnimation() {
  animCurrentTime = 0.0;
  animIsPlaying = true;
  const playBtn = document.getElementById("btn-anim-play");
  if (playBtn) playBtn.textContent = "⏸ Pause";
}

function onScrubInput(val) {
  const def = getEffectiveAnimDef();
  animCurrentTime = (parseFloat(val) / 100.0) * (def.length || 1.0);
}

function evalKeyframes(keyframes, t) {
  if (!keyframes || keyframes.length === 0) return 0;
  if (keyframes.length === 1) return keyframes[0][1];
  if (t <= keyframes[0][0]) return keyframes[0][1];
  if (t >= keyframes[keyframes.length - 1][0]) return keyframes[keyframes.length - 1][1];

  for (let i = 0; i < keyframes.length - 1; i++) {
    const t0 = keyframes[i][0];
    const t1 = keyframes[i+1][0];
    if (t >= t0 && t <= t1) {
      const v0 = keyframes[i][1];
      const v1 = keyframes[i+1][1];
      const f = (t - t0) / (t1 - t0);
      if (Array.isArray(v0)) {
        return [v0[0] + f * (v1[0] - v0[0]), v0[1] + f * (v1[1] - v0[1])];
      }
      return v0 + f * (v1 - v0);
    }
  }
  return keyframes[0][1];
}

function getTrackVal(trackPath, defVal) {
  const def = getEffectiveAnimDef();
  if (!def || !def.tracks || !def.tracks[trackPath]) return defVal;
  return evalKeyframes(def.tracks[trackPath], animCurrentTime);
}

function ensureAnimLoopRunning() {
  if (!animRafId) {
    animLastFrameTime = performance.now();
    animRafId = requestAnimationFrame(animRenderLoop);
  }
}

function countLoadedLimbs() {
  let count = 0;
  BONE_LIMBS.forEach(b => {
    const im = loadedLimbImages[b] || loadedLimbImages[b.toLowerCase()];
    if (im && im.complete && im.naturalWidth > 0) count++;
  });
  return count;
}

function animRenderLoop(now) {
  const dt = Math.min((now - animLastFrameTime) / 1000.0, 0.1);
  animLastFrameTime = now;

  const canvas = document.getElementById("anim-canvas");
  if (canvas) {
    const ctx = canvas.getContext("2d");
    const def = (animCatalog || FALLBACK_ANIM_DEFS)[currentAnimName] || { length: 1.0, loop: 1 };
    const animLen = def.length || 1.0;

    // Advance time with auto-loop support
    if (animIsPlaying) {
      animCurrentTime += dt * animSpeed;
      if (animCurrentTime >= animLen) {
        if (autoLoop || def.loop) {
          animCurrentTime = animCurrentTime % animLen;
        } else {
          animCurrentTime = animLen;
          animIsPlaying = false;
          const playBtn = document.getElementById("btn-anim-play");
          if (playBtn) playBtn.textContent = "▶ Play";
        }
      }
    }

    // Update UI controls
    const scrub = document.getElementById("anim-scrub");
    if (scrub) scrub.value = (animCurrentTime / animLen) * 100;
    const timeDisp = document.getElementById("anim-time-display");
    if (timeDisp) timeDisp.textContent = `${animCurrentTime.toFixed(2)}s / ${animLen.toFixed(2)}s`;

    // Clear Canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Floor Shadow & Grid Markings
    const rootX = canvas.width / 2;
    const rootY = canvas.height / 2 + 65;

    ctx.save();
    ctx.beginPath();
    ctx.ellipse(rootX, rootY + 68, 65, 12, 0, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
    ctx.fill();
    ctx.restore();

    // Evaluate Animated Tracks
    const pelvisPos = getTrackVal("Skeleton2D/pelvis:position", [0, 0]);
    const torsoPos  = getTrackVal("Skeleton2D/pelvis/torso:position", [0, -40]);
    const torsoRot  = getTrackVal("Skeleton2D/pelvis/torso:rotation", 0);
    const headRot   = getTrackVal("Skeleton2D/pelvis/torso/head:rotation", 0);

    const armLRot   = getTrackVal("Skeleton2D/pelvis/torso/arm_upper_L:rotation", 0);
    const armLLowRot= getTrackVal("Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L:rotation", 0);
    const armRRot   = getTrackVal("Skeleton2D/pelvis/torso/arm_upper_R:rotation", 0);
    const armRLowRot= getTrackVal("Skeleton2D/pelvis/torso/arm_upper_R/arm_lower_R:rotation", 0);

    const legLRot   = getTrackVal("Skeleton2D/pelvis/leg_upper_L:rotation", 0);
    const legLLowRot= getTrackVal("Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation", 0);
    const legRRot   = getTrackVal("Skeleton2D/pelvis/leg_upper_R:rotation", 0);
    const legRLowRot= getTrackVal("Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation", 0);

    const px = rootX + pelvisPos[0] * 1.5;
    const py = rootY + pelvisPos[1] * 1.5;

    const numLimbs = countLoadedLimbs();
    const fullImg = loadedLimbImages["_full"];
    const useFullBody = (renderMode === "full" || numLimbs < 3) && fullImg && fullImg.complete && fullImg.naturalWidth > 0;

    if (useFullBody) {
      // ---- RENDER ASSEMBLED FULL MODEL (COHESIVE PUPPET) ----
      const aspect = fullImg.naturalWidth / fullImg.naturalHeight;
      const targetH = 240;
      const targetW = targetH * aspect;
      ctx.save();
      ctx.translate(px, py + torsoPos[1] * 0.5);
      ctx.rotate(torsoRot * 0.65);

      // Dynamic squash & stretch depending on action
      let scaleX = 1.0;
      let scaleY = 1.0;
      if (currentAnimName === "crouch" || currentAnimName === "crouch_walk" || currentAnimName === "slide") {
        scaleY = 0.82; scaleX = 1.12;
      } else if (currentAnimName === "jump" || currentAnimName === "double_jump" || currentAnimName === "jump_kick") {
        scaleY = 1.08; scaleX = 0.94;
      } else if (currentAnimName === "get_hit" || currentAnimName === "death") {
        scaleX = 0.96;
      }
      ctx.scale(scaleX, scaleY);
      ctx.drawImage(fullImg, -targetW / 2, -targetH + 65, targetW, targetH);
      ctx.restore();

      // Render equipped weapon in full body mode during combat or attacks
      const wpnImgFull = loadedLimbImages["_weapon"];
      if (wpnImgFull && wpnImgFull.complete && wpnImgFull.naturalWidth > 0 && (currentAnimName === "fire_weapon" || currentAnimName === "punch" || currentAnimName === "hit" || currentAnimName.startsWith("special_"))) {
        ctx.save();
        ctx.translate(px + 28, py + torsoPos[1] + 12);
        ctx.rotate(torsoRot * 0.7);
        ctx.drawImage(wpnImgFull, 0, -16, 54, 28);
        ctx.restore();
      }

      // Optional skeleton overlay on top of full model
      if (showSkeletonOverlay) {
        drawSkeletonBones(ctx, px, py, torsoPos, torsoRot, headRot, armLRot, armLLowRot, armRRot, armRLowRot, legLRot, legLLowRot, legRRot, legRLowRot);
      }
    } else {
      // ---- RENDER SLICED LIMBS RIG (FORWARD KINEMATICS) ----
      function drawPart(boneName, imgName, targetW, targetH, ox, oy) {
        const img = loadedLimbImages[imgName] ||
                    loadedLimbImages[boneName] ||
                    loadedLimbImages[boneName.toLowerCase()];

        if (img && img.complete && img.naturalWidth > 0) {
          const aspect = img.naturalWidth / img.naturalHeight;
          let dw = targetW;
          let dh = targetH;
          if (aspect > 1) {
            dh = targetW / aspect;
          } else {
            dw = targetH * aspect;
          }
          ctx.drawImage(img, -dw / 2 + ox, -dh / 2 + oy, dw, dh);
        } else {
          // If this individual limb isn't loaded yet, draw a subtle bone connection
          ctx.beginPath();
          ctx.arc(0, 0, 4, 0, Math.PI * 2);
          ctx.fillStyle = "#d2a8ff";
          ctx.fill();
          ctx.beginPath();
          ctx.moveTo(0, 0);
          ctx.lineTo(ox, oy);
          ctx.lineWidth = 4;
          ctx.strokeStyle = "rgba(88,166,255,0.7)";
          ctx.lineCap = "round";
          ctx.stroke();
        }

        // If Skeleton Overlay is active, overlay bone joints directly on top of the limb!
        if (showSkeletonOverlay) {
          ctx.save();
          ctx.beginPath();
          ctx.arc(0, 0, 4, 0, Math.PI * 2);
          ctx.fillStyle = "#ff7b72";
          ctx.fill();
          ctx.beginPath();
          ctx.moveTo(0, 0);
          ctx.lineTo(ox, oy);
          ctx.lineWidth = 2.5;
          ctx.strokeStyle = "rgba(121, 192, 255, 0.85)";
          ctx.stroke();
          ctx.restore();
        }
      }

      // 1. Right Arm (Back Layer)
      ctx.save();
      ctx.translate(px, py + torsoPos[1]);
      ctx.rotate(torsoRot);
      ctx.translate(22, -32);
      ctx.rotate(armRRot);
      drawPart("arm_upper_R", "arm_upper_R", 38, 52, 6, 16);
      ctx.translate(10, 26);
      ctx.rotate(armRLowRot);
      drawPart("arm_lower_R", "arm_lower_R", 34, 48, 4, 14);
      ctx.translate(4, 22);
      drawPart("hand_R", "hand_R", 26, 26, 0, 0);
      const wpnImgHand = loadedLimbImages["_weapon"];
      if (wpnImgHand && wpnImgHand.complete && wpnImgHand.naturalWidth > 0) {
        ctx.save();
        ctx.translate(8, 6);
        ctx.drawImage(wpnImgHand, 0, -16, 54, 28);
        ctx.restore();
      }
      ctx.restore();

      // 2. Right Leg (Back Layer)
      ctx.save();
      ctx.translate(px, py);
      ctx.translate(14, 4);
      ctx.rotate(legRRot);
      drawPart("leg_upper_R", "leg_upper_R", 36, 56, 0, 16);
      ctx.translate(0, 30);
      ctx.rotate(legRLowRot);
      drawPart("leg_lower_R", "leg_lower_R", 32, 52, 0, 16);
      ctx.translate(2, 28);
      drawPart("foot_R", "foot_R", 38, 26, 6, 0);
      ctx.restore();

      // 3. Pelvis & Torso (Core)
      ctx.save();
      ctx.translate(px, py);
      drawPart("pelvis", "pelvis", 52, 38, 0, 0);
      ctx.translate(torsoPos[0], torsoPos[1]);
      ctx.rotate(torsoRot);
      drawPart("torso", "torso", 70, 80, 0, 0);

      // 4. Head
      ctx.save();
      ctx.translate(0, -42);
      ctx.rotate(headRot);
      drawPart("head", "head", 74, 74, 0, -8);
      ctx.restore();

      ctx.restore(); // end torso / core

      // 5. Left Leg (Front Layer)
      ctx.save();
      ctx.translate(px, py);
      ctx.translate(-14, 4);
      ctx.rotate(legLRot);
      drawPart("leg_upper_L", "leg_upper_L", 36, 56, 0, 16);
      ctx.translate(0, 30);
      ctx.rotate(legLLowRot);
      drawPart("leg_lower_L", "leg_lower_L", 32, 52, 0, 16);
      ctx.translate(-2, 28);
      drawPart("foot_L", "foot_L", 38, 26, -6, 0);
      ctx.restore();

      // 6. Left Arm (Front Layer)
      ctx.save();
      ctx.translate(px, py + torsoPos[1]);
      ctx.rotate(torsoRot);
      ctx.translate(-22, -32);
      ctx.rotate(armLRot);
      drawPart("arm_upper_L", "arm_upper_L", 38, 52, -6, 16);
      ctx.translate(-10, 26);
      ctx.rotate(armLLowRot);
      drawPart("arm_lower_L", "arm_lower_L", 34, 48, -4, 14);
      ctx.translate(-4, 22);
      drawPart("hand_L", "hand_L", 26, 26, 0, 0);
      ctx.restore();
    }
  }

  animRafId = requestAnimationFrame(animRenderLoop);
}

function drawSkeletonBones(ctx, px, py, torsoPos, torsoRot, headRot, armLRot, armLLowRot, armRRot, armRLowRot, legLRot, legLLowRot, legRRot, legRLowRot) {
  ctx.save();
  ctx.lineWidth = 3;
  ctx.strokeStyle = "rgba(88, 166, 255, 0.75)";
  ctx.fillStyle = "#d2a8ff";

  function pt(x, y) {
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
  }

  // Pelvis
  pt(px, py);

  // Torso
  const tx = px + torsoPos[0];
  const ty = py + torsoPos[1];
  ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(tx, ty); ctx.stroke();
  pt(tx, ty);

  // Head
  const hx = tx - Math.sin(torsoRot + headRot) * 45;
  const hy = ty - Math.cos(torsoRot + headRot) * 45;
  ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(hx, hy); ctx.stroke();
  pt(hx, hy);

  ctx.restore();
}

// ---- Batch Re-Rig All Characters ----
async function batchRerigAll() {
  const btn = document.getElementById("btn-batch-rerig");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Re-Rigging All...';
  }
  log("\\n========================================================", "ci");
  log("[RIG] Batch re-rigging all characters with 23 default animations...", "gi");
  try {
    const r = await fetch('/api/rerig_all', { method: 'POST' });
    const d = await r.json();
    if (d.status === 'success') {
      log(`[GODOT] ✓ Successfully re-rigged ${d.count || 0} characters with 23 default animations!`, "ok");
      refreshLibrary();
    } else {
      log(`[GODOT-ERROR] Batch re-rig failed: ${d.message || ''}`, "err");
    }
  } catch(e) {
    log(`[ERROR] Batch re-rig error: ${e}`, "err");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '🦴 Batch Re-Rig All (23 Anims)';
    }
  }
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

// =============================================================================
// WEAPONS & PROJECTILES STUDIO + LIVE FIRING RANGE ENGINE
// =============================================================================
let loadedWeapons = [];
let loadedProjectiles = [];
let specialMovesCatalog = {};
let activeArsenalType = "weapon";
let activeArsenalFilter = "all";
let activeArsenalFaction = "all";

// Special Moves Catalog init & randomize
async function initSpecialCatalog() {
  try {
    const r = await fetch('/api/special_catalog');
    const d = await r.json();
    if (d.status === 'ok' && d.specials) {
      specialMovesCatalog = d.specials;
      populateSpecialDropdowns();
    }
  } catch(e) {
    console.warn("[SPECIALS] Catalog fetch error:", e);
  }
}

function populateSpecialDropdowns() {
  const keys = Object.keys(specialMovesCatalog);
  if (keys.length === 0) return;

  const defaults = ["special_ground_slam", "special_whirlwind", "special_power_charge", "special_victory_flourish"];
  for (let slot = 1; slot <= 4; slot++) {
    const sel = document.getElementById(`spec-slot-${slot}`);
    if (!sel) continue;
    sel.innerHTML = keys.map(k => {
      const item = specialMovesCatalog[k];
      const isDef = (k === defaults[slot - 1]);
      return `<option value="${k}" ${isDef ? 'selected' : ''}>${item.name} (${(item.category || 'combat').toUpperCase()})</option>`;
    }).join('');
  }
}

function randomizeSpecialsInForm() {
  const keys = Object.keys(specialMovesCatalog);
  if (keys.length < 4) return;
  const shuffled = [...keys].sort(() => 0.5 - Math.random());
  for (let slot = 1; slot <= 4; slot++) {
    const sel = document.getElementById(`spec-slot-${slot}`);
    if (sel) sel.value = shuffled[slot - 1];
  }
  log("[SPECIALS] 🎲 Randomized 4 tactical abilities for character!", "ci");
}

function setArsenalType(t) {
  activeArsenalType = t;
  const btnW = document.getElementById("btn-arsenal-mode-weapon");
  const btnP = document.getElementById("btn-arsenal-mode-proj");
  const grpW = document.getElementById("group-weapon-type");
  const grpP = document.getElementById("group-projectile-type");
  const nameInput = document.getElementById("arsenal-item-name");

  if (t === "weapon") {
    if (btnW) btnW.className = "btn btn-primary btn-sm";
    if (btnP) btnP.className = "btn btn-secondary btn-sm";
    if (grpW) grpW.style.display = "block";
    if (grpP) grpP.style.display = "none";
    if (nameInput && nameInput.value.includes("projectile")) nameInput.value = "custom_rifle";
  } else {
    if (btnW) btnW.className = "btn btn-secondary btn-sm";
    if (btnP) btnP.className = "btn btn-primary btn-sm";
    if (grpW) grpW.style.display = "none";
    if (grpP) grpP.style.display = "block";
    if (nameInput && (nameInput.value.includes("rifle") || nameInput.value.includes("carbine"))) nameInput.value = "custom_bolt";
  }
}

function setArsenalFilter(f) {
  activeArsenalFilter = f;
  document.querySelectorAll('#tab-weapons .filter-chip').forEach(el => {
    if (el.id.startsWith('chip-arsenal-')) el.classList.remove('active');
  });
  const chip = document.getElementById(`chip-arsenal-${f}`);
  if (chip) chip.classList.add('active');
  renderArsenalGrid();
}

function setArsenalFaction(fac) {
  activeArsenalFaction = fac;
  document.querySelectorAll('#tab-weapons .filter-chip').forEach(el => {
    if (el.id.startsWith('chip-af-')) el.classList.remove('active');
  });
  const chip = document.getElementById(fac === 'all' ? 'chip-af-clear' : `chip-af-${fac}`);
  if (chip) chip.classList.add('active');
  renderArsenalGrid();
}

async function refreshArsenal() {
  try {
    const r = await fetch('/api/weapons');
    const d = await r.json();
    loadedWeapons = d.weapons || [];
    loadedProjectiles = d.projectiles || [];

    const badge = document.getElementById("weapons-count-badge");
    if (badge) badge.textContent = `(${loadedWeapons.length} weapons, ${loadedProjectiles.length} projectiles)`;

    const elAll = document.getElementById("arsenal-cnt-all");
    const elW = document.getElementById("arsenal-cnt-weapons");
    const elP = document.getElementById("arsenal-cnt-proj");
    if (elAll) elAll.textContent = loadedWeapons.length + loadedProjectiles.length;
    if (elW) elW.textContent = loadedWeapons.length;
    if (elP) elP.textContent = loadedProjectiles.length;

    populateRangeSelects();
    renderArsenalGrid();
  } catch(e) {
    console.error("[ARSENAL] Error refreshing weapons:", e);
  }
}

function populateRangeSelects() {
  const wSel = document.getElementById("range-select-weapon");
  const pSel = document.getElementById("range-select-proj");
  if (wSel && loadedWeapons.length > 0) {
    const curr = wSel.value;
    wSel.innerHTML = loadedWeapons.map(w => `<option value="${w.name}" ${w.name === curr ? 'selected' : ''}>${w.name.replace(/_/g, ' ')}</option>`).join('');
    if (!curr && loadedWeapons[0]) wSel.value = loadedWeapons[0].name;
    onRangeWeaponChanged();
  }
  if (pSel && loadedProjectiles.length > 0) {
    const curr = pSel.value;
    pSel.innerHTML = loadedProjectiles.map(p => `<option value="${p.name}" ${p.name === curr ? 'selected' : ''}>${p.name.replace(/_/g, ' ')}</option>`).join('');
    if (!curr && loadedProjectiles[0]) pSel.value = loadedProjectiles[0].name;
    onRangeProjChanged();
  }
}

function renderArsenalGrid() {
  const grid = document.getElementById("arsenal-grid");
  const searchQ = (document.getElementById("arsenal-search")?.value || "").toLowerCase().trim();
  if (!grid) return;

  let items = [];
  if (activeArsenalFilter === "all" || activeArsenalFilter === "weapons") {
    items = items.concat(loadedWeapons.map(w => ({ ...w, itemType: "weapon" })));
  }
  if (activeArsenalFilter === "all" || activeArsenalFilter === "projectiles") {
    items = items.concat(loadedProjectiles.map(p => ({ ...p, itemType: "projectile" })));
  }

  if (activeArsenalFaction !== "all") {
    items = items.filter(it => it.name.startsWith(activeArsenalFaction + "_"));
  }

  if (searchQ) {
    items = items.filter(it => it.name.toLowerCase().includes(searchQ));
  }

  if (items.length === 0) {
    grid.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:40px 0;grid-column:1/-1;">No weapons or projectiles match the selected filter.</div>';
    return;
  }

  grid.innerHTML = items.map(it => {
    const isW = it.itemType === "weapon";
    const tagBg = isW ? "rgba(88,166,255,0.15)" : "rgba(248,81,73,0.15)";
    const tagCol = isW ? "#79b8ff" : "#ff7b72";
    const cleanTitle = it.name.replace(/_/g, ' ');

    let facName = "Independent";
    let facCol = "#8b949e";
    if (it.name.startsWith("neotokyo_")) { facName = "Neo-Tokyo"; facCol = "#00f0ff"; }
    else if (it.name.startsWith("abyssal_")) { facName = "Abyssal"; facCol = "#e67e22"; }
    else if (it.name.startsWith("orbital_")) { facName = "Orbital Ops"; facCol = "#2ecc71"; }
    else if (it.name.startsWith("aetherium_")) { facName = "Aetherium"; facCol = "#9b59b6"; }
    else if (it.name.startsWith("neonglitch_")) { facName = "Neon Glitch"; facCol = "#ff007f"; }
    else if (it.name.startsWith("ghost_protocol_")) { facName = "Ghost Protocol"; facCol = "#39c5bb"; }
    else if (it.name.startsWith("iron_valkyrie_")) { facName = "Iron Valkyrie"; facCol = "#d29922"; }
    else if (it.name.startsWith("neon_outcasts_")) { facName = "Neon Outcasts"; facCol = "#f778ba"; }
    else if (it.name.startsWith("apex_transhumans_")) { facName = "Apex Transhumans"; facCol = "#a371f7"; }
    else if (it.name.startsWith("synth_corp_")) { facName = "Synth-Corp"; facCol = "#ff7b72"; }
    else if (it.name.startsWith("directorate_")) { facName = "Directorate"; facCol = "#58a6ff"; }
    else if (it.name.startsWith("syndicate_")) { facName = "Syndicate"; facCol = "#e68c14"; }
    else if (it.name.startsWith("covenant_")) { facName = "Covenant"; facCol = "#bc8cff"; }
    else if (it.name.startsWith("bioforge_")) { facName = "Bio-Forge"; facCol = "#2ea043"; }
    else if (it.name.startsWith("silicon_")) { facName = "Silicon"; facCol = "#f85149"; }

    return `
      <div class="arsenal-card">
        <div class="arsenal-thumb-wrap" onclick="openLightbox('${it.sprite}', '${cleanTitle}', '${it.scene_path || ''}')">
          <img class="arsenal-thumb" src="${it.sprite}?t=${Date.now()}" alt="${it.name}" loading="lazy">
        </div>
        <div class="arsenal-card-title" title="${cleanTitle}">${cleanTitle}</div>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span class="arsenal-tag" style="background:${facCol}18;color:${facCol};">${facName}</span>
          <span class="arsenal-tag" style="background:${tagBg};color:${tagCol};">${isW ? 'WEAPON' : (it.is_strip ? 'ANIM STRIP' : 'PROJECTILE')}</span>
        </div>
        <div style="display:flex;gap:4px;margin-top:2px;">
          <button class="btn btn-secondary btn-sm" style="flex:1;padding:3px 6px;font-size:10px;" onclick="selectRangeItem('${it.itemType}', '${it.name}')">🎯 Test</button>
          ${isW ? `<button class="btn btn-secondary btn-sm" style="flex:1;padding:3px 6px;font-size:10px;border-color:rgba(46,160,67,0.3);color:#3fb950;" onclick="equipWeaponToCurrent('${it.name}')">🔗 Equip</button>` : ''}
          <button class="btn btn-secondary btn-sm" style="padding:3px 6px;font-size:10px;" onclick="openLightbox('${it.sprite}', '${cleanTitle}', '${it.scene_path || ''}')">🔍</button>
        </div>
      </div>
    `;
  }).join('');
}

function selectRangeItem(itemType, name) {
  if (itemType === "weapon") {
    const sel = document.getElementById("range-select-weapon");
    if (sel) { sel.value = name; onRangeWeaponChanged(); }
  } else {
    const sel = document.getElementById("range-select-proj");
    if (sel) { sel.value = name; onRangeProjChanged(); }
  }
  const canvas = document.getElementById("range-canvas");
  if (canvas) canvas.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function generateArsenalItem() {
  const btn = document.getElementById("btn-generate-arsenal");
  const name = document.getElementById("arsenal-item-name").value.trim().toLowerCase().replace(/\\s+/g, '_') || "custom_item";
  const faction = document.getElementById("arsenal-faction").value;

  btn.disabled = true;
  const origText = btn.innerHTML;
  btn.innerHTML = '<span class="spinner"></span> Creating...';

  try {
    if (activeArsenalType === "weapon") {
      const weaponType = document.getElementById("arsenal-weapon-type").value;
      log(`[ARSENAL] Creating weapon '${name}' (${weaponType}, ${faction})...`, "ci");
      const r = await fetch('/api/generate/weapon', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name, weapon_type: weaponType, faction })
      });
      const d = await r.json();
      if (d.status === 'success') {
        log(`[GODOT] ✓ Weapon scene created -> ${d.scene_path}`, "ok");
      }
    } else {
      const projType = document.getElementById("arsenal-proj-type").value;
      log(`[ARSENAL] Creating projectile '${name}' (${projType}, ${faction})...`, "ci");
      const r = await fetch('/api/generate/projectile', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ name, projectile_type: projType, faction })
      });
      const d = await r.json();
      if (d.status === 'success') {
        log(`[GODOT] ✓ Projectile scene created -> ${d.scene_path}`, "ok");
      }
    }
    refreshArsenal();
  } catch(e) {
    log(`[ERROR] Failed to generate arsenal item: ${e}`, "err");
  } finally {
    btn.disabled = false;
    btn.innerHTML = origText;
  }
}

async function equipWeaponToCurrent(weaponName) {
  if (!viewingChar) {
    log("[EQUIP] Please select a character from the Asset Library first!", "warn");
    alert("Please select a character in the Asset Library tab first!");
    return;
  }
  log(`[EQUIP] Attaching weapon '${weaponName}' to '${viewingChar}'...`, "ci");
  try {
    const r = await fetch('/api/character/equip_weapon', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ character_name: viewingChar, weapon_name: weaponName, hand: 'R' })
    });
    const d = await r.json();
    if (d.status === 'equipped' || d.status === 'success') {
      log(`[GODOT] ✓ Weapon equipped to ${viewingChar}!`, "ok");
      const charInfo = allLibraryChars.find(c => c.name === viewingChar);
      if (charInfo) charInfo.equipped_weapon = weaponName;
      const wpnImg = new Image();
      wpnImg.src = `/sprites/weapons/${weaponName}.png?t=${Date.now()}`;
      wpnImg.onload = () => { loadedLimbImages["_weapon"] = wpnImg; };
      refreshLibrary();
    } else {
      log(`[WARN] ${d.message || 'Failed to equip.'}`, "warn");
    }
  } catch(e) {
    log(`[ERROR] Equip failed: ${e}`, "err");
  }
}

// -----------------------------------------------------------------------------
// Interactive Live Firing Range Simulation
// -----------------------------------------------------------------------------
let rangeCanvasInited = false;
let rangeCtx = null;
let rangeWeaponImg = null;
let rangeProjImg = null;
let rangeBullets = [];
let rangeParticles = [];
let rangeDamageTexts = [];
let rangeRecoil = 0;
let rangeMuzzleFlash = 0;
let rangeTargetShake = 0;
let rangeTargetHealth = 100;
let rangeLastTime = performance.now();

function initFiringRangeCanvas() {
  if (rangeCanvasInited) return;
  const canvas = document.getElementById("range-canvas");
  if (!canvas) return;
  rangeCtx = canvas.getContext("2d");
  rangeCanvasInited = true;
  requestAnimationFrame(rangeRenderLoop);
}

function onRangeWeaponChanged() {
  const wSel = document.getElementById("range-select-weapon");
  if (!wSel) return;
  const wName = wSel.value;
  const w = loadedWeapons.find(item => item.name === wName);
  if (w && w.sprite) {
    const img = new Image();
    img.src = `${w.sprite}?t=${Date.now()}`;
    img.onload = () => { rangeWeaponImg = img; };
  }
}

function onRangeProjChanged() {
  const pSel = document.getElementById("range-select-proj");
  if (!pSel) return;
  const pName = pSel.value;
  const p = loadedProjectiles.find(item => item.name === pName);
  if (p && p.sprite) {
    const img = new Image();
    img.src = `${p.sprite}?t=${Date.now()}`;
    img.onload = () => { rangeProjImg = img; };
  }
}

function fireRangeWeaponAt(e) {
  const canvas = document.getElementById("range-canvas");
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const targetX = (e.clientX - rect.left) * scaleX;
  const targetY = (e.clientY - rect.top) * scaleY;
  fireRangeWeapon(targetX, targetY);
}

function fireRangeWeapon(tx = 720, ty = 130) {
  const startX = 135;
  const startY = 130;
  const dx = tx - startX;
  const dy = ty - startY;
  const dist = Math.sqrt(dx * dx + dy * dy) || 1;
  const speed = 22.0;
  const vx = (dx / dist) * speed;
  const vy = (dy / dist) * speed;

  const wSel = document.getElementById("range-select-weapon");
  const pSel = document.getElementById("range-select-proj");
  const wName = wSel ? wSel.value : "";
  const pName = pSel ? pSel.value : "";

  let bulletColor = "#58a6ff";
  if (wName.includes("syndicate") || pName.includes("flame") || pName.includes("napalm")) bulletColor = "#ff9800";
  else if (wName.includes("covenant") || pName.includes("psi")) bulletColor = "#bc8cff";
  else if (wName.includes("bioforge") || pName.includes("acid")) bulletColor = "#39d353";
  else if (wName.includes("silicon") || pName.includes("missile")) bulletColor = "#ff3b30";

  rangeBullets.push({
    x: startX,
    y: startY,
    vx: vx,
    vy: vy,
    targetX: tx,
    targetY: ty,
    color: bulletColor,
    life: 0,
    maxLife: 70
  });

  rangeRecoil = 14;
  rangeMuzzleFlash = 5;

  // Muzzle particles
  for (let i = 0; i < 8; i++) {
    rangeParticles.push({
      x: startX + 10,
      y: startY,
      vx: (Math.random() * 4 - 1),
      vy: (Math.random() * 4 - 2),
      color: bulletColor,
      size: Math.random() * 3 + 2,
      alpha: 1.0,
      decay: 0.12
    });
  }
}

function rangeRenderLoop(now) {
  const dt = Math.min((now - rangeLastTime) / 1000, 0.1);
  rangeLastTime = now;

  const canvas = document.getElementById("range-canvas");
  if (canvas && rangeCtx) {
    const ctx = rangeCtx;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Range Grid Background
    ctx.fillStyle = "#080b11";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = "rgba(88, 166, 255, 0.08)";
    ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 40) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += 40) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
    }

    // Distance Yard Markers
    ctx.fillStyle = "rgba(255, 255, 255, 0.25)";
    ctx.font = "9px monospace";
    [150, 300, 450, 600, 720].forEach((dx, i) => {
      ctx.fillText(`${(i + 1) * 10}M`, dx, 24);
      ctx.beginPath(); ctx.moveTo(dx, 0); ctx.lineTo(dx, 10); ctx.strokeStyle = "rgba(255,255,255,0.2)"; ctx.stroke();
    });

    // Aiming Laser Beam
    ctx.save();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = "rgba(88, 166, 255, 0.35)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(140, 130);
    ctx.lineTo(720, 130);
    ctx.stroke();
    ctx.restore();

    // Target Dummy on the Right
    const targetX = 720 + (rangeTargetShake > 0 ? (Math.random() * 8 - 4) : 0);
    const targetY = 130 + (rangeTargetShake > 0 ? (Math.random() * 6 - 3) : 0);
    if (rangeTargetShake > 0) rangeTargetShake--;

    // Target Drone Silhouette
    ctx.save();
    ctx.translate(targetX, targetY);
    ctx.fillStyle = "rgba(255, 60, 60, 0.2)";
    ctx.strokeStyle = "#ff4d4d";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(0, 0, 28, 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();

    // Inner Bullseye Rings
    ctx.strokeStyle = "rgba(255, 255, 255, 0.4)";
    ctx.beginPath(); ctx.arc(0, 0, 18, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath(); ctx.arc(0, 0, 8, 0, Math.PI * 2); ctx.stroke();
    ctx.fillStyle = "#ff4d4d";
    ctx.beginPath(); ctx.arc(0, 0, 3, 0, Math.PI * 2); ctx.fill();

    // Floating Drone Wings
    ctx.fillStyle = "#333b4d";
    ctx.fillRect(-38, -6, 12, 12);
    ctx.fillRect(26, -6, 12, 12);
    ctx.restore();

    // Weapon on the Left with Recoil
    const recoilOffset = rangeRecoil;
    if (rangeRecoil > 0) rangeRecoil = Math.max(0, rangeRecoil - 1.2);

    ctx.save();
    ctx.translate(85 - recoilOffset, 130);
    if (rangeWeaponImg && rangeWeaponImg.complete && rangeWeaponImg.naturalWidth > 0) {
      const aspect = rangeWeaponImg.naturalWidth / rangeWeaponImg.naturalHeight;
      const w = 110;
      const h = w / aspect;
      ctx.drawImage(rangeWeaponImg, -w / 2, -h / 2, w, h);
    } else {
      // Clean Procedural Weapon Silhouette
      ctx.fillStyle = "#58a6ff";
      ctx.fillRect(-40, -8, 80, 16);
      ctx.fillStyle = "#1e2638";
      ctx.fillRect(-30, 8, 16, 24);
    }

    // Muzzle Flash
    if (rangeMuzzleFlash > 0) {
      rangeMuzzleFlash--;
      ctx.beginPath();
      ctx.arc(60, 0, 16 + Math.random() * 6, 0, Math.PI * 2);
      ctx.fillStyle = "#ffffff";
      ctx.fill();
      ctx.beginPath();
      ctx.arc(60, 0, 26 + Math.random() * 8, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(88, 166, 255, 0.5)";
      ctx.fill();
    }
    ctx.restore();

    // Update & Draw Bullets
    for (let i = rangeBullets.length - 1; i >= 0; i--) {
      const b = rangeBullets[i];
      b.x += b.vx;
      b.y += b.vy;
      b.life++;

      // Projectile Trail Particle
      rangeParticles.push({
        x: b.x,
        y: b.y,
        vx: (Math.random() * 1.5 - 0.75),
        vy: (Math.random() * 1.5 - 0.75),
        color: b.color,
        size: Math.random() * 3 + 2,
        alpha: 0.8,
        decay: 0.08
      });

      // Draw Bullet
      ctx.save();
      ctx.beginPath();
      ctx.arc(b.x, b.y, 5, 0, Math.PI * 2);
      ctx.fillStyle = "#ffffff";
      ctx.shadowColor = b.color;
      ctx.shadowBlur = 12;
      ctx.fill();
      ctx.restore();

      // Check hit on target dummy
      const hitDist = Math.hypot(b.x - targetX, b.y - targetY);
      if (hitDist < 34 || b.x >= targetX || b.life >= b.maxLife) {
        // Hit explosion
        rangeTargetShake = 8;
        for (let p = 0; p < 22; p++) {
          const angle = Math.random() * Math.PI * 2;
          const spd = Math.random() * 6 + 2;
          rangeParticles.push({
            x: targetX,
            y: targetY,
            vx: Math.cos(angle) * spd,
            vy: Math.sin(angle) * spd,
            color: b.color,
            size: Math.random() * 4 + 2,
            alpha: 1.0,
            decay: 0.045
          });
        }

        // Damage Number
        const dmg = Math.floor(Math.random() * 1800 + 1200);
        const isCrit = Math.random() > 0.45;
        rangeDamageTexts.push({
          x: targetX + (Math.random() * 30 - 15),
          y: targetY - 20,
          text: isCrit ? `CRIT! ${dmg.toLocaleString()}` : `${dmg.toLocaleString()}`,
          color: isCrit ? "#ffc107" : "#fff",
          alpha: 1.0,
          vy: -1.2
        });

        rangeBullets.splice(i, 1);
      }
    }

    // Update & Draw Particles
    for (let i = rangeParticles.length - 1; i >= 0; i--) {
      const p = rangeParticles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.alpha -= p.decay;
      if (p.alpha <= 0) {
        rangeParticles.splice(i, 1);
        continue;
      }
      ctx.save();
      ctx.globalAlpha = p.alpha;
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    // Update & Draw Damage Texts
    for (let i = rangeDamageTexts.length - 1; i >= 0; i--) {
      const dt = rangeDamageTexts[i];
      dt.y += dt.vy;
      dt.alpha -= 0.025;
      if (dt.alpha <= 0) {
        rangeDamageTexts.splice(i, 1);
        continue;
      }
      ctx.save();
      ctx.globalAlpha = dt.alpha;
      ctx.fillStyle = dt.color;
      ctx.font = "bold 13px -apple-system, sans-serif";
      ctx.shadowColor = "rgba(0,0,0,0.8)";
      ctx.shadowBlur = 4;
      ctx.fillText(dt.text, dt.x, dt.y);
      ctx.restore();
    }
  }

  requestAnimationFrame(rangeRenderLoop);
}

// Spacebar listener to fire weapon when on Weapons tab
document.addEventListener("keydown", e => {
  if (e.code === "Space") {
    const weaponsTab = document.getElementById("tab-weapons");
    if (weaponsTab && weaponsTab.classList.contains("active")) {
      const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : "";
      if (tag !== "input" && tag !== "textarea" && tag !== "select") {
        e.preventDefault();
        fireRangeWeapon();
      }
    }
  }
});

// ==============================================================================
// RTS SKIRMISH ARENA JAVASCRIPT ENGINE
// ==============================================================================

let arenaUnits = [];
let arenaProjectiles = [];
let arenaParticles = [];
let arenaDamageTexts = [];
let arenaWaypoints = [];
let arenaAbilityFX = [];
let arenaInitialized = false;
let arenaRunning = false;
let arenaPaused = false;
let arenaFogOfWar = false;
let arenaStance = 'assault'; // 'assault', 'hold', 'retreat'
let arenaSimSpeed = 1.0;
let arenaSelectedUnitIds = [];
let arenaSelectedUnitId = null;
let arenaAnimReq = null;
let arenaLoadedImages = {};
let arenaScore = { blue: 0, red: 0 };
let arenaIsBoxDragging = false;
let arenaDragBoxStart = { x: 0, y: 0 };
let arenaDragBoxCurrent = { x: 0, y: 0 };

// Audio Synthesis State
let arenaAudioCtx = null;
let arenaAudioEnabled = true;

function getAudioContext() {
  if (!arenaAudioCtx) {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext) arenaAudioCtx = new AudioContext();
  }
  if (arenaAudioCtx && arenaAudioCtx.state === 'suspended') {
    arenaAudioCtx.resume();
  }
  return arenaAudioCtx;
}

function toggleArenaAudio() {
  arenaAudioEnabled = !arenaAudioEnabled;
  const btn = document.getElementById('btn-arena-audio');
  if (btn) {
    btn.textContent = arenaAudioEnabled ? '🔊 SFX: ON' : '🔇 SFX: OFF';
    btn.style.color = arenaAudioEnabled ? '#00f0ff' : 'var(--text-muted)';
  }
  logArena(arenaAudioEnabled ? "[AUDIO] Battlefield audio synthesized SFX enabled." : "[AUDIO] SFX muted.", "#79c0ff");
}

function playSfxLaser(isSpecial = false) {
  if (!arenaAudioEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = isSpecial ? 'sawtooth' : 'sine';
    osc.frequency.setValueAtTime(isSpecial ? 1200 : 880, now);
    osc.frequency.exponentialRampToValueAtTime(isSpecial ? 150 : 120, now + 0.12);
    gain.gain.setValueAtTime(0.18, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.12);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.13);
  } catch (_) {}
}

function playSfxPlasma() {
  if (!arenaAudioEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(650, now);
    osc.frequency.exponentialRampToValueAtTime(80, now + 0.16);
    gain.gain.setValueAtTime(0.2, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.16);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.17);
  } catch (_) {}
}

function playSfxRailgun() {
  if (!arenaAudioEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(1800, now);
    osc.frequency.exponentialRampToValueAtTime(60, now + 0.28);
    gain.gain.setValueAtTime(0.26, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.28);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.29);
  } catch (_) {}
}

function playSfxExplosion(heavy = false) {
  if (!arenaAudioEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    const dur = heavy ? 0.45 : 0.25;
    const bufferSize = Math.floor(ctx.sampleRate * dur);
    const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (ctx.sampleRate * (heavy ? 0.18 : 0.09)));
    }
    const noise = ctx.createBufferSource();
    noise.buffer = buffer;
    const filter = ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.setValueAtTime(heavy ? 350 : 600, now);
    filter.frequency.exponentialRampToValueAtTime(40, now + dur);
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(heavy ? 0.35 : 0.2, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + dur);
    noise.connect(filter);
    filter.connect(gain);
    gain.connect(ctx.destination);
    noise.start(now);
  } catch (_) {}
}

function playSfxSpecialMove() {
  if (!arenaAudioEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    const notes = [440, 554.37, 659.25, 880];
    notes.forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      const t = now + idx * 0.05;
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, t);
      gain.gain.setValueAtTime(0.16, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.18);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.2);
    });
  } catch (_) {}
}

function playSfxShieldDeflect() {
  if (!arenaAudioEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(1400, now);
    osc.frequency.exponentialRampToValueAtTime(320, now + 0.14);
    gain.gain.setValueAtTime(0.18, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.14);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.15);
  } catch (_) {}
}

function playSfxEmpShock() {
  if (!arenaAudioEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(800, now);
    osc.frequency.exponentialRampToValueAtTime(80, now + 0.35);
    gain.gain.setValueAtTime(0.25, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.36);
  } catch (_) {}
}

function playSfxOrbitalBeam() {
  if (!arenaAudioEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(180, now);
    osc.frequency.linearRampToValueAtTime(1600, now + 0.2);
    osc.frequency.exponentialRampToValueAtTime(60, now + 0.45);
    gain.gain.setValueAtTime(0.32, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.46);
  } catch (_) {}
}

function playSfxVictory() {
  if (!arenaAudioEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    const notes = [523.25, 659.25, 783.99, 1046.50];
    notes.forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      const t = now + idx * 0.12;
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(freq, t);
      gain.gain.setValueAtTime(0.24, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.4);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.42);
    });
  } catch (_) {}
}

function playSfxWaypoint() {
  if (!arenaAudioEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(900, now);
    osc.frequency.exponentialRampToValueAtTime(1400, now + 0.08);
    gain.gain.setValueAtTime(0.12, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.09);
  } catch (_) {}
}

const ARENA_ROLES = {
  soldier: {
    title: "Soldier",
    hp: 140,
    speed: 1.15,
    attackRange: 180,
    damage: 18,
    cooldownMax: 40,
    weaponType: "assault_rifle",
    projType: "plasma_bolt",
    radius: 16
  },
  sniper: {
    title: "Sniper",
    hp: 80,
    speed: 0.85,
    attackRange: 340,
    damage: 52,
    cooldownMax: 85,
    weaponType: "sniper_rifle",
    projType: "railgun_slug",
    radius: 14
  },
  rocket: {
    title: "Rocketeer",
    hp: 120,
    speed: 0.95,
    attackRange: 230,
    damage: 36,
    aoe: 45,
    cooldownMax: 70,
    weaponType: "rocket_launcher",
    projType: "seeker_rocket",
    radius: 16
  },
  flame: {
    title: "Flamethrower",
    hp: 170,
    speed: 1.35,
    attackRange: 110,
    damage: 9,
    cooldownMax: 12,
    weaponType: "flamethrower",
    projType: "flame_jet",
    radius: 18
  }
};

const ARENA_SPECIAL_MOVES = [
  { name: "⚡ Overload Burst", type: "overload", multiplier: 2.2, color: "#00f0ff" },
  { name: "🎯 Hyper-Focus Crit", type: "crit", multiplier: 2.8, color: "#ff007f" },
  { name: "💥 Orbital Strike", type: "orbital", multiplier: 3.4, color: "#ffc300" },
  { name: "🛡️ Kinetic Surge", type: "kinetic", multiplier: 1.8, color: "#2ecc71" },
  { name: "⚡ EMP Nova", type: "emp", multiplier: 2.0, color: "#a855f7" },
  { name: "☣️ Nanite Swarm", type: "nanite", multiplier: 2.5, color: "#8cff28" }
];

const ARENA_BARRIERS = [
  { x: 290, y: 80, w: 40, h: 120 },
  { x: 550, y: 240, w: 40, h: 120 }
];

function getArenaCharImage(charName) {
  const url = `/sprites/${charName}/${charName}_full.png`;
  if (!arenaLoadedImages[url]) {
    const img = new Image();
    img.src = url;
    arenaLoadedImages[url] = img;
  }
  return arenaLoadedImages[url];
}

function getArenaWeaponImage(faction, weaponType) {
  const url = `/sprites/weapons/${faction}_${weaponType}.png`;
  if (!arenaLoadedImages[url]) {
    const img = new Image();
    img.src = url;
    arenaLoadedImages[url] = img;
  }
  return arenaLoadedImages[url];
}

function initArena() {
  const canvas = document.getElementById('arena-canvas');
  if (!canvas) return;

  if (!arenaInitialized) {
    arenaInitialized = true;
    logArena("[ARENA ONLINE] Cyberpunk Tactical Skirmish Simulator initialized.", "#00f0ff");

    if (!allLibraryChars || allLibraryChars.length === 0) {
      fetch('/api/characters')
        .then(r => r.json())
        .then(d => {
          allLibraryChars = d.characters || [];
          populateInitialArenaSquads();
        })
        .catch(() => populateInitialArenaSquads());
    } else {
      populateInitialArenaSquads();
    }
  }

  if (!arenaAnimReq) {
    arenaAnimReq = requestAnimationFrame(arenaRenderLoop);
  }
}

function populateInitialArenaSquads() {
  if (arenaUnits.length > 0) return;
  const squadSize = parseInt(document.getElementById('arena-squad-size')?.value || '5', 10);
  const roles = squadSize === 3 ? ['soldier', 'sniper', 'rocket']
    : squadSize === 8 ? ['soldier', 'soldier', 'soldier', 'sniper', 'sniper', 'rocket', 'rocket', 'flame']
    : ['soldier', 'soldier', 'sniper', 'rocket', 'flame'];

  roles.forEach(r => {
    deployArenaUnit('blue', r, false);
    deployArenaUnit('red', r, false);
  });
  updateArenaBadges();
  logArena(`[STAGING] Deployed initial squads (${squadSize} vs ${squadSize}). Ready to skirmish!`, "#79c0ff");
}

function deployArenaUnit(team, roleKey, logDeploy = true) {
  const role = ARENA_ROLES[roleKey] || ARENA_ROLES.soldier;
  const factionSelectId = team === 'blue' ? 'arena-t1-faction' : 'arena-t2-faction';
  const faction = document.getElementById(factionSelectId)?.value || (team === 'blue' ? 'neotokyo' : 'abyssal');

  let charMatch = null;
  if (allLibraryChars && allLibraryChars.length > 0) {
    charMatch = allLibraryChars.find(c => {
      const f = (c.faction_id || '').toLowerCase();
      const r = (c.role || c.name || '').toLowerCase();
      return f === faction.toLowerCase() && (
        r.includes(roleKey) ||
        (roleKey === 'flame' && (r.includes('pyro') || r.includes('zealot') || r.includes('flare'))) ||
        (roleKey === 'rocket' && (r.includes('heavy') || r.includes('grenad') || r.includes('buster') || r.includes('raider'))) ||
        (roleKey === 'sniper' && (r.includes('phantom') || r.includes('recon') || r.includes('valkyrie'))) ||
        (roleKey === 'soldier' && (r.includes('hunter') || r.includes('striker') || r.includes('nomad') || r.includes('gunner')))
      );
    });

    if (!charMatch) {
      charMatch = allLibraryChars.find(c => (c.faction_id || '').toLowerCase() === faction.toLowerCase());
    }
    if (!charMatch) {
      charMatch = allLibraryChars[Math.floor(Math.random() * allLibraryChars.length)];
    }
  }

  const charName = charMatch ? charMatch.name : `${faction}_${roleKey}`;
  const displayName = charMatch ? (charMatch.display_name || charMatch.name.replace(/_/g, ' ')) : `${faction} ${role.title}`;

  const canvas = document.getElementById('arena-canvas');
  const w = canvas ? canvas.width : 880;
  const h = canvas ? canvas.height : 440;

  const existingTeamUnits = arenaUnits.filter(u => u.team === team);
  const idx = existingTeamUnits.length;

  const x = team === 'blue'
    ? 60 + (idx % 2) * 55 + Math.random() * 20
    : w - 90 - (idx % 2) * 55 - Math.random() * 20;
  const y = 70 + ((idx * 65) % (h - 140)) + Math.random() * 15;

  const unitId = 'u_' + Math.random().toString(36).substr(2, 9);
  const unit = {
    id: unitId,
    name: displayName,
    charName: charName,
    team: team,
    roleKey: roleKey,
    roleTitle: role.title,
    faction: faction,
    x: x,
    y: y,
    moveTargetX: null,
    moveTargetY: null,
    targetEnemyId: null,
    maxHp: role.hp,
    hp: role.hp,
    maxShield: Math.round(role.hp * 0.45),
    shield: Math.round(role.hp * 0.45),
    shieldRegenDelay: 0,
    isStunned: 0,
    visionRadius: roleKey === 'sniper' ? 340 : 230,
    speed: role.speed * 1.3,
    attackRange: role.attackRange,
    damage: role.damage,
    cooldownMax: role.cooldownMax,
    cooldown: Math.floor(Math.random() * 25),
    radius: role.radius,
    weaponType: role.weaponType,
    projType: role.projType,
    alive: true,
    facing: team === 'blue' ? 1 : -1,
    walkFrame: Math.random() * 10,
    recoil: 0,
    state: 'idle',
    spriteImg: getArenaCharImage(charName),
    weaponImg: getArenaWeaponImage(faction, role.weaponType)
  };

  arenaUnits.push(unit);
  updateArenaBadges();

  if (logDeploy) {
    const teamColor = team === 'blue' ? '#00f0ff' : '#e67e22';
    logArena(`[DEPLOY] ${team === 'blue' ? 'Team Blue' : 'Team Red'} deployed ${displayName} (${role.title})`, teamColor);
  }
  return unit;
}

function startArenaBattle() {
  getAudioContext(); // Initialize Web Audio on user gesture
  const blueCount = arenaUnits.filter(u => u.team === 'blue' && u.alive).length;
  const redCount = arenaUnits.filter(u => u.team === 'red' && u.alive).length;

  if (blueCount === 0 || redCount === 0) {
    resetArenaBattle(false);
  }

  arenaRunning = true;
  arenaPaused = false;
  const pBtn = document.getElementById('btn-arena-pause');
  if (pBtn) pBtn.textContent = '⏸️ Pause';
  hideArenaBanner();
  updateArenaStatusBadge("(Combat Active)", "#00f0ff");
  logArena("[ENGAGEMENT] Combat initiated! Units advancing to engage.", "#00f0ff");
}

function toggleArenaPause() {
  if (!arenaRunning) return;
  arenaPaused = !arenaPaused;
  const pBtn = document.getElementById('btn-arena-pause');
  if (pBtn) pBtn.textContent = arenaPaused ? '▶️ Resume' : '⏸️ Pause';
  updateArenaStatusBadge(arenaPaused ? "(Paused)" : "(Combat Active)", arenaPaused ? "#f1c40f" : "#00f0ff");
  logArena(arenaPaused ? "[PAUSED] Battle simulation paused." : "[RESUMED] Battle simulation resumed.", "#f1c40f");
}

function resetArenaBattle(clearFeed = false) {
  arenaUnits = [];
  arenaProjectiles = [];
  arenaParticles = [];
  arenaDamageTexts = [];
  arenaWaypoints = [];
  arenaAbilityFX = [];
  arenaSelectedUnitIds = [];
  arenaSelectedUnitId = null;
  arenaIsBoxDragging = false;
  arenaRunning = false;
  arenaPaused = false;
  hideArenaBanner();
  const cmdBar = document.getElementById('arena-unit-command-bar');
  if (cmdBar) cmdBar.style.display = 'none';
  const pBtn = document.getElementById('btn-arena-pause');
  if (pBtn) pBtn.textContent = '⏸️ Pause';
  updateArenaStatusBadge("(Ready)", "var(--text-muted)");
  populateInitialArenaSquads();
  if (clearFeed) clearArenaLog();
}

function toggleArenaFogOfWar() {
  arenaFogOfWar = !arenaFogOfWar;
  const btn = document.getElementById('btn-arena-fog');
  if (btn) {
    btn.textContent = arenaFogOfWar ? '👁️ Fog: ON' : '👁️ Fog: OFF';
    btn.style.color = arenaFogOfWar ? '#00f0ff' : 'var(--text-muted)';
  }
  logArena(arenaFogOfWar ? "[TACTICAL] Fog of War activated. Shrouding battlefield outside allied sensors." : "[TACTICAL] Fog of War deactivated. Full battlefield visual acquired.", "#79c0ff");
}

function toggleArenaStance() {
  if (arenaStance === 'assault') arenaStance = 'hold';
  else if (arenaStance === 'hold') arenaStance = 'retreat';
  else arenaStance = 'assault';

  const btn = document.getElementById('btn-arena-stance');
  let title = 'Assault';
  let color = '#2ecc71';
  if (arenaStance === 'hold') {
    title = 'Hold Position';
    color = '#f1c40f';
  } else if (arenaStance === 'retreat') {
    title = 'Fall Back';
    color = '#e74c3c';
  }

  if (btn) {
    btn.textContent = `🛡️ Stance: ${title}`;
    btn.style.color = color;
    btn.style.borderColor = color;
  }
  logArena(`[TACTICAL SQUAD ORDER] Alliance squad stance switched to ${title.toUpperCase()}`, color);
}

function setArenaSpeed(speed) {
  arenaSimSpeed = parseFloat(speed) || 1.0;
  logArena(`[SIM SPEED] Simulation speed set to ${arenaSimSpeed}x`, "#cbd5e1");
}

function onArenaFactionChanged() {
  const f1 = document.getElementById('arena-t1-faction')?.value || 'neotokyo';
  const f2 = document.getElementById('arena-t2-faction')?.value || 'abyssal';
  logArena(`[FACTION] Matchup updated: ${f1.toUpperCase()} vs ${f2.toUpperCase()}`, "#cbd5e1");
  if (!arenaRunning) {
    resetArenaBattle(false);
  }
}

async function launchGodotMainScene() {
  logArena("[GODOT] Launching Godot 4 RTS Skirmish Arena (res://scenes/rts_battle_demo.tscn)...", "#79c0ff");
  try {
    const res = await fetch('/api/open_godot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scene: 'res://scenes/rts_battle_demo.tscn' })
    });
    const d = await res.json();
    if (d.status === 'launched') {
      logArena(`[GODOT SUCCESS] ${d.message || 'Launched scene in Godot 4 editor!'}`, "#2ecc71");
    } else {
      logArena(`[GODOT NOTICE] ${d.message || JSON.stringify(d)}`, "#f1c40f");
    }
  } catch (err) {
    logArena(`[GODOT ERROR] Failed to launch Godot: ${err.message}`, "#ff4d4d");
  }
}

function onArenaMouseDown(event) {
  if (event.button !== 0) return;
  const canvas = document.getElementById('arena-canvas');
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  arenaDragBoxStart = { x: (event.clientX - rect.left) * scaleX, y: (event.clientY - rect.top) * scaleY };
  arenaDragBoxCurrent = { ...arenaDragBoxStart };
  arenaIsBoxDragging = true;
}

function onArenaMouseMove(event) {
  if (!arenaIsBoxDragging) return;
  const canvas = document.getElementById('arena-canvas');
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  arenaDragBoxCurrent = { x: (event.clientX - rect.left) * scaleX, y: (event.clientY - rect.top) * scaleY };
}

function onArenaMouseUp(event) {
  if (!arenaIsBoxDragging) return;
  arenaIsBoxDragging = false;
  const dx = Math.abs(arenaDragBoxCurrent.x - arenaDragBoxStart.x);
  const dy = Math.abs(arenaDragBoxCurrent.y - arenaDragBoxStart.y);
  if (dx > 8 || dy > 8) {
    const minX = Math.min(arenaDragBoxStart.x, arenaDragBoxCurrent.x);
    const maxX = Math.max(arenaDragBoxStart.x, arenaDragBoxCurrent.x);
    const minY = Math.min(arenaDragBoxStart.y, arenaDragBoxCurrent.y);
    const maxY = Math.max(arenaDragBoxStart.y, arenaDragBoxCurrent.y);

    arenaSelectedUnitIds = [];
    for (const u of arenaUnits) {
      if (u.team === 'blue' && u.alive && u.x >= minX && u.x <= maxX && u.y >= minY && u.y <= maxY) {
        arenaSelectedUnitIds.push(u.id);
      }
    }
    if (arenaSelectedUnitIds.length > 0) {
      arenaSelectedUnitId = arenaSelectedUnitIds[0];
      logArena(`[SQUAD SELECTION] Selected ${arenaSelectedUnitIds.length} units in tactical formation.`, "#00f0ff");
      showCommandBarForSelection();
    }
  }
}

function showCommandBarForSelection() {
  const cmdBar = document.getElementById('arena-unit-command-bar');
  if (!cmdBar) return;
  const selUnit = arenaUnits.find(u => u.id === arenaSelectedUnitId && u.alive);
  if (!selUnit) {
    cmdBar.style.display = 'none';
    return;
  }
  cmdBar.style.display = 'block';
  cmdBar.style.borderLeftColor = selUnit.team === 'blue' ? '#00f0ff' : '#e67e22';
  const title = document.getElementById('cmd-unit-title');
  const role = document.getElementById('cmd-unit-role');
  const hp = document.getElementById('cmd-unit-hp-text');
  if (title) {
    title.textContent = arenaSelectedUnitIds.length > 1
      ? `Squad Selected: ${arenaSelectedUnitIds.length} Units (Lead: ${selUnit.name})`
      : `Selected: ${selUnit.name}`;
    title.style.color = selUnit.team === 'blue' ? '#00f0ff' : '#e67e22';
  }
  if (role) role.textContent = selUnit.roleTitle;
  if (hp) hp.textContent = `HP: ${Math.round(selUnit.hp)}/${selUnit.maxHp} | Shield: ${Math.round(selUnit.shield || 0)}/${selUnit.maxShield || 0}`;
}

function onArenaCanvasClick(event) {
  getAudioContext();
  const canvas = document.getElementById('arena-canvas');
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const mx = (event.clientX - rect.left) * scaleX;
  const my = (event.clientY - rect.top) * scaleY;

  let clicked = null;
  let minDist = 32;
  for (const u of arenaUnits) {
    if (!u.alive) continue;
    const d = Math.hypot(mx - u.x, my - u.y);
    if (d < minDist) {
      minDist = d;
      clicked = u;
    }
  }

  const cmdBar = document.getElementById('arena-unit-command-bar');
  if (clicked) {
    arenaSelectedUnitId = clicked.id;
    arenaSelectedUnitIds = [clicked.id];
    showCommandBarForSelection();
    const teamColor = clicked.team === 'blue' ? '#00f0ff' : '#e67e22';
    logArena(`[INSPECT] Selected: ${clicked.name} (${clicked.roleTitle}) | HP: ${Math.round(clicked.hp)}/${clicked.maxHp} | Shield: ${Math.round(clicked.shield || 0)}/${clicked.maxShield || 0} | Weapon: ${clicked.weaponType}`, teamColor);
  } else {
    arenaSelectedUnitId = null;
    arenaSelectedUnitIds = [];
    if (cmdBar) cmdBar.style.display = 'none';
  }
}

function onArenaCanvasContextMenu(event) {
  event.preventDefault();
  getAudioContext();
  const canvas = document.getElementById('arena-canvas');
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const mx = (event.clientX - rect.left) * scaleX;
  const my = (event.clientY - rect.top) * scaleY;

  const squad = arenaUnits.filter(u => (arenaSelectedUnitIds.includes(u.id) || u.id === arenaSelectedUnitId) && u.alive);
  if (squad.length === 0) return;

  let clickedEnemy = null;
  let minDist = 30;
  for (const other of arenaUnits) {
    if (other.team !== squad[0].team && other.alive) {
      const d = Math.hypot(mx - other.x, my - other.y);
      if (d < minDist) {
        minDist = d;
        clickedEnemy = other;
      }
    }
  }

  if (clickedEnemy) {
    squad.forEach(u => {
      u.targetEnemyId = clickedEnemy.id;
      u.cooldown = 0;
    });
    logArena(`[FOCUS TARGET] ${squad.length > 1 ? squad.length + ' Units' : squad[0].name} targeting ${clickedEnemy.name}!`, "#ff007f");
    playSfxSpecialMove();
    arenaWaypoints.push({ x: clickedEnemy.x, y: clickedEnemy.y, radius: 26, alpha: 1.0, color: '#ff007f' });
  } else {
    const cols = Math.ceil(Math.sqrt(squad.length));
    const spacing = 32;
    squad.forEach((u, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      const offX = (col - cols * 0.5) * spacing;
      const offY = (row - cols * 0.5) * spacing;
      u.moveTargetX = Math.max(25, Math.min(canvas.width - 25, mx + offX));
      u.moveTargetY = Math.max(30, Math.min(canvas.height - 30, my + offY));
      u.state = 'march';
    });
    logArena(`[FORMATION ORDER] Directed ${squad.length} units to (${Math.round(mx)}, ${Math.round(my)})`, "#00f0ff");
    playSfxWaypoint();
    arenaWaypoints.push({ x: mx, y: my, radius: 24, alpha: 1.0, color: '#00f0ff' });
  }
}

function triggerManualSpecialMove(moveIndex) {
  getAudioContext();
  const selUnit = arenaUnits.find(u => u.id === arenaSelectedUnitId && u.alive);
  if (!selUnit) {
    logArena("[ORDER] Select an active unit first to unleash signature moves!", "#f1c40f");
    return;
  }

  let nearest = null;
  let minDist = 99999;
  for (const other of arenaUnits) {
    if (other.team !== selUnit.team && other.alive) {
      const d = Math.hypot(other.x - selUnit.x, other.y - selUnit.y);
      if (d < minDist) {
        minDist = d;
        nearest = other;
      }
    }
  }

  if (!nearest) {
    logArena("[ORDER] No opposing units remaining in range.", "var(--text-muted)");
    return;
  }

  const sp = ARENA_SPECIAL_MOVES[moveIndex % ARENA_SPECIAL_MOVES.length];
  selUnit.cooldown = 0;
  selUnit.facing = nearest.x >= selUnit.x ? 1 : -1;

  if (sp.type === 'orbital') {
    arenaAbilityFX.push({
      type: 'orbital',
      x: nearest.x,
      y: nearest.y,
      radius: 80,
      maxTimer: 25,
      timer: 25
    });
    for (const other of arenaUnits) {
      if (other.team !== selUnit.team && other.alive) {
        if (Math.hypot(other.x - nearest.x, other.y - nearest.y) <= 80) {
          applyDirectDamage(other, 65, true, "🛰️ ORBITAL");
        }
      }
    }
    playSfxOrbitalBeam();
  } else if (sp.type === 'emp') {
    arenaAbilityFX.push({
      type: 'emp',
      x: selUnit.x,
      y: selUnit.y,
      maxRadius: 180,
      maxTimer: 24,
      timer: 24
    });
    for (const other of arenaUnits) {
      if (other.team !== selUnit.team && other.alive) {
        if (Math.hypot(other.x - selUnit.x, other.y - selUnit.y) <= 180) {
          other.isStunned = 40;
          applyDirectDamage(other, 30, false, "⚡ EMP");
        }
      }
    }
    playSfxEmpShock();
  } else if (sp.type === 'nanite') {
    arenaAbilityFX.push({
      type: 'nanite',
      x: nearest.x,
      y: nearest.y,
      radius: 70,
      maxTimer: 90,
      timer: 90,
      tickDelay: 0
    });
    playSfxPlasma();
  } else {
    unitAttackTarget(selUnit, nearest, sp);
  }

  logArena(`[SIGNATURE UNLEASHED] ${selUnit.name} activated ${sp.name}!`, sp.color);
}

function applyDirectDamage(target, rawDamage, isSpecial = false, prefix = "") {
  if (!target || !target.alive) return;
  target.shieldRegenDelay = 60;
  let dmgRem = rawDamage;
  let absorbed = false;

  if (target.shield > 0) {
    absorbed = true;
    if (target.shield >= dmgRem) {
      target.shield -= dmgRem;
      dmgRem = 0;
      playSfxShieldDeflect();
    } else {
      dmgRem -= target.shield;
      target.shield = 0;
      arenaDamageTexts.push({
        text: "⚡ SHIELD BREAK!",
        x: target.x,
        y: target.y - 32,
        color: '#d8b4fe',
        vy: -0.9,
        alpha: 1.0,
        size: 12,
        bold: true
      });
    }
  }

  target.hp = Math.max(0, target.hp - dmgRem);

  arenaDamageTexts.push({
    text: (prefix ? prefix + " " : "") + (isSpecial ? "💥 " : (absorbed && dmgRem === 0 ? "🛡️ " : "-")) + Math.round(rawDamage) + (isSpecial ? " CRIT!" : (absorbed && dmgRem === 0 ? " ABSORB" : "")),
    x: target.x + (Math.random() - 0.5) * 16,
    y: target.y - 20,
    color: isSpecial ? '#ff0055' : (absorbed && dmgRem === 0 ? '#c084fc' : (target.team === 'blue' ? '#ff7849' : '#00f0ff')),
    vy: -0.8,
    alpha: 1.0,
    size: isSpecial ? 13 : 11,
    bold: isSpecial || absorbed
  });

  if (target.hp <= 0) {
    target.hp = 0;
    target.alive = false;
    playSfxExplosion(true);
    logArena(`[KILL] ${target.name} was eliminated!`, target.team === 'blue' ? '#ff4d4d' : '#2ecc71');
    for (let d = 0; d < 20; d++) {
      const a = Math.random() * Math.PI * 2;
      const spd = 1 + Math.random() * 4.5;
      arenaParticles.push({
        x: target.x,
        y: target.y,
        vx: Math.cos(a) * spd,
        vy: Math.sin(a) * spd,
        color: target.team === 'blue' ? '#00f0ff' : '#e67e22',
        size: 3.5,
        alpha: 1.0,
        decay: 0.03
      });
    }
    updateArenaBadges();
    checkArenaVictory();
  }
}

function updateArenaBadges() {
  const blueAlive = arenaUnits.filter(u => u.team === 'blue' && u.alive).length;
  const redAlive = arenaUnits.filter(u => u.team === 'red' && u.alive).length;

  const t1Badge = document.getElementById('arena-t1-alive-badge');
  if (t1Badge) t1Badge.textContent = `${blueAlive} Unit${blueAlive === 1 ? '' : 's'}`;

  const t2Badge = document.getElementById('arena-t2-alive-badge');
  if (t2Badge) t2Badge.textContent = `${redAlive} Unit${redAlive === 1 ? '' : 's'}`;

  const scoreDisplay = document.getElementById('arena-score-display');
  if (scoreDisplay) scoreDisplay.textContent = `Blue: ${arenaScore.blue} (${blueAlive} alive)  |  Red: ${arenaScore.red} (${redAlive} alive)`;

  // Update command bar HP text if selected unit is living
  if (arenaSelectedUnitId) {
    const selUnit = arenaUnits.find(u => u.id === arenaSelectedUnitId);
    const hpText = document.getElementById('cmd-unit-hp-text');
    if (selUnit && hpText) {
      hpText.textContent = `HP: ${Math.round(selUnit.hp)}/${selUnit.maxHp} | Weapon: ${selUnit.weaponType}`;
    }
  }
}

function updateArenaStatusBadge(text, color) {
  const badge = document.getElementById('arena-status-badge');
  if (badge) {
    badge.textContent = text;
    if (color) badge.style.color = color;
  }
}

function showArenaBanner(title, subtitle, color) {
  const banner = document.getElementById('arena-banner');
  const bTitle = document.getElementById('arena-banner-title');
  const bSub = document.getElementById('arena-banner-subtitle');
  if (banner) banner.style.display = 'block';
  if (bTitle) {
    bTitle.textContent = title;
    bTitle.style.color = color || '#00f0ff';
  }
  if (bSub) bSub.textContent = subtitle;
}

function hideArenaBanner() {
  const banner = document.getElementById('arena-banner');
  if (banner) banner.style.display = 'none';
}

function logArena(msg, color = 'var(--text-muted)') {
  const feed = document.getElementById('arena-combat-feed');
  if (!feed) return;
  const line = document.createElement('div');
  line.style.color = color;
  line.textContent = msg;
  feed.appendChild(line);
  while (feed.children.length > 80) {
    feed.removeChild(feed.firstChild);
  }
  feed.scrollTop = feed.scrollHeight;
}

function clearArenaLog() {
  const feed = document.getElementById('arena-combat-feed');
  if (feed) feed.innerHTML = '<div style="color:var(--text-muted);">[FEED CLEARED]</div>';
}

function checkArenaVictory() {
  const blueAlive = arenaUnits.filter(u => u.team === 'blue' && u.alive).length;
  const redAlive = arenaUnits.filter(u => u.team === 'red' && u.alive).length;

  if (arenaRunning) {
    if (blueAlive === 0 && redAlive > 0) {
      arenaRunning = false;
      arenaScore.red++;
      showArenaBanner("RED SYNDICATE VICTORY", "All opposing alliance forces eliminated", "#e67e22");
      updateArenaStatusBadge("(Red Syndicate Won)", "#e67e22");
      logArena("[VICTORY] Red Syndicate has dominated the arena battlefield!", "#e67e22");
      playSfxVictory();
    } else if (redAlive === 0 && blueAlive > 0) {
      arenaRunning = false;
      arenaScore.blue++;
      showArenaBanner("BLUE ALLIANCE VICTORY", "All opposing syndicate forces eliminated", "#00f0ff");
      updateArenaStatusBadge("(Blue Alliance Won)", "#00f0ff");
      logArena("[VICTORY] Blue Alliance has secured total battlefield victory!", "#00f0ff");
      playSfxVictory();
    } else if (blueAlive === 0 && redAlive === 0) {
      arenaRunning = false;
      showArenaBanner("MUTUAL ANNIHILATION", "Both squads were neutralized in combat", "#ffc300");
      updateArenaStatusBadge("(Stalemate)", "#ffc300");
      logArena("[STALEMATE] Mutual destruction across both factions.", "#ffc300");
      playSfxExplosion(true);
    }
  }
}

function arenaRenderLoop() {
  const canvas = document.getElementById('arena-canvas');
  const arenaTab = document.getElementById('tab-arena');

  if (canvas && arenaTab && arenaTab.classList.contains('active')) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;

    // 1. Draw Battlefield Grid & Dividing Perimeter
    drawArenaBattlefieldGrid(ctx, w, h);

    // 2. Draw Defensive Obstacle Barriers
    drawArenaBarriers(ctx);

    // 3. Render Waypoints
    for (let i = arenaWaypoints.length - 1; i >= 0; i--) {
      const wp = arenaWaypoints[i];
      wp.radius -= 0.3 * arenaSimSpeed;
      wp.alpha -= 0.02 * arenaSimSpeed;
      if (wp.alpha <= 0 || wp.radius <= 3) {
        arenaWaypoints.splice(i, 1);
        continue;
      }
      ctx.save();
      ctx.beginPath();
      ctx.arc(wp.x, wp.y, wp.radius, 0, Math.PI * 2);
      ctx.strokeStyle = wp.color;
      ctx.lineWidth = 2;
      ctx.globalAlpha = Math.max(0, wp.alpha);
      ctx.stroke();
      ctx.restore();
    }

    // 3.5. Update & Render Active Ability FX
    for (let i = arenaAbilityFX.length - 1; i >= 0; i--) {
      const fx = arenaAbilityFX[i];
      fx.timer -= arenaSimSpeed;

      if (fx.type === 'orbital') {
        const p = fx.timer / fx.maxTimer;
        ctx.save();
        const bGrad = ctx.createLinearGradient(fx.x - 20, 0, fx.x + 20, 0);
        bGrad.addColorStop(0, 'rgba(0, 240, 255, 0)');
        bGrad.addColorStop(0.5, `rgba(220, 250, 255, ${p * 0.95})`);
        bGrad.addColorStop(1, 'rgba(0, 240, 255, 0)');
        ctx.fillStyle = bGrad;
        ctx.fillRect(fx.x - 16, 0, 32, fx.y);

        ctx.strokeStyle = `rgba(255, 255, 255, ${p})`;
        ctx.lineWidth = 6;
        ctx.beginPath();
        ctx.moveTo(fx.x, 0);
        ctx.lineTo(fx.x, fx.y);
        ctx.stroke();

        const curR = fx.radius * (1 - p * 0.3);
        ctx.strokeStyle = `rgba(0, 240, 255, ${p})`;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, curR, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      } else if (fx.type === 'emp') {
        const t = 1 - (fx.timer / fx.maxTimer);
        const curR = fx.maxRadius * t;
        const a = (1 - t) * 0.85;
        ctx.save();
        ctx.strokeStyle = `rgba(168, 85, 247, ${a})`;
        ctx.lineWidth = 3.5;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, curR, 0, Math.PI * 2);
        ctx.stroke();

        ctx.strokeStyle = `rgba(0, 240, 255, ${a * 0.6})`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, curR * 0.85, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      } else if (fx.type === 'nanite') {
        const a = (fx.timer / fx.maxTimer) * 0.45;
        ctx.save();
        ctx.fillStyle = `rgba(140, 255, 40, ${a})`;
        ctx.beginPath();
        ctx.arc(fx.x, fx.y, fx.radius, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = `rgba(140, 255, 40, ${a * 1.5})`;
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.restore();

        fx.tickDelay = (fx.tickDelay || 0) + arenaSimSpeed;
        if (fx.tickDelay >= 15) {
          fx.tickDelay = 0;
          for (const u of arenaUnits) {
            if (u.alive && u.team === 'red' && Math.hypot(u.x - fx.x, u.y - fx.y) <= fx.radius) {
              applyDirectDamage(u, 7, false, "☣️");
            }
          }
        }
      }

      if (fx.timer <= 0) {
        arenaAbilityFX.splice(i, 1);
      }
    }

    // 4. Update Combat Simulation
    if (arenaRunning && !arenaPaused) {
      // Update Units
      for (const u of arenaUnits) {
        if (!u.alive) continue;

        if (u.recoil > 0) u.recoil = Math.max(0, u.recoil - 0.8 * arenaSimSpeed);
        if (u.cooldown > 0) u.cooldown = Math.max(0, u.cooldown - arenaSimSpeed);

        // Shield regeneration & EMP Stun
        if (u.shieldRegenDelay > 0) u.shieldRegenDelay -= arenaSimSpeed;
        else if (u.shield < u.maxShield) u.shield = Math.min(u.maxShield, u.shield + 0.3 * arenaSimSpeed);

        if (u.isStunned > 0) {
          u.isStunned = Math.max(0, u.isStunned - 0.05 * arenaSimSpeed);
          continue; // Stunned units cannot march or attack
        }

        // Tactical Stance Orders
        if (u.team === 'blue' && u.moveTargetX == null) {
          if (arenaStance === 'retreat') {
            const rdx = 60 - u.x;
            if (Math.abs(rdx) > 15) {
              u.state = 'march';
              u.walkFrame += 0.25 * arenaSimSpeed;
              u.facing = rdx >= 0 ? 1 : -1;
              u.x += Math.sign(rdx) * u.speed * 1.3 * arenaSimSpeed;
            }
            continue;
          }
        }

        // Check if unit has manual destination waypoint
        if (u.moveTargetX != null && u.moveTargetY != null) {
          const tdx = u.moveTargetX - u.x;
          const tdy = u.moveTargetY - u.y;
          const tdist = Math.hypot(tdx, tdy);
          if (tdist < 10) {
            u.moveTargetX = null;
            u.moveTargetY = null;
            u.state = 'idle';
          } else {
            u.state = 'march';
            u.walkFrame += 0.25 * arenaSimSpeed;
            u.facing = tdx >= 0 ? 1 : -1;
            u.x += (tdx / tdist) * u.speed * 1.3 * arenaSimSpeed;
            u.y += (tdy / tdist) * u.speed * 1.3 * arenaSimSpeed;
          }
        }

        // Find nearest living enemy
        let nearestEnemy = null;
        if (u.targetEnemyId) {
          nearestEnemy = arenaUnits.find(other => other.id === u.targetEnemyId && other.alive);
          if (!nearestEnemy) u.targetEnemyId = null;
        }
        if (!nearestEnemy) {
          let minDist = 99999;
          for (const other of arenaUnits) {
            if (other.team !== u.team && other.alive) {
              const d = Math.hypot(other.x - u.x, other.y - u.y);
              if (d < minDist) {
                minDist = d;
                nearestEnemy = other;
              }
            }
          }
        }

        if (nearestEnemy) {
          u.facing = nearestEnemy.x >= u.x ? 1 : -1;
          const edist = Math.hypot(nearestEnemy.x - u.x, nearestEnemy.y - u.y);

          if (edist <= u.attackRange) {
            u.state = 'attack';
            if (u.cooldown <= 0) {
              unitAttackTarget(u, nearestEnemy);
            }
          } else if (u.moveTargetX == null) {
            if (u.team === 'blue' && arenaStance === 'hold') {
              u.state = 'idle';
              continue;
            }

            // March towards enemy with obstacle avoidance
            u.state = 'march';
            u.walkFrame += 0.2 * arenaSimSpeed;

            let dx = nearestEnemy.x - u.x;
            let dy = nearestEnemy.y - u.y;
            const dist = Math.hypot(dx, dy) || 1;

            let moveVx = (dx / dist) * u.speed * arenaSimSpeed;
            let moveVy = (dy / dist) * u.speed * arenaSimSpeed;

            for (const b of ARENA_BARRIERS) {
              if (u.x + moveVx >= b.x - 18 && u.x + moveVx <= b.x + b.w + 18 &&
                  u.y + moveVy >= b.y - 18 && u.y + moveVy <= b.y + b.h + 18) {
                moveVx *= 0.1;
                moveVy = (u.y < b.y + b.h / 2 ? -1 : 1) * u.speed * 1.2 * arenaSimSpeed;
              }
            }

            u.x = Math.max(25, Math.min(w - 25, u.x + moveVx));
            u.y = Math.max(30, Math.min(h - 40, u.y + moveVy));
          }
        } else if (u.moveTargetX == null) {
          u.state = 'idle';
        }
      }

      // Update Projectiles
      for (let i = arenaProjectiles.length - 1; i >= 0; i--) {
        const p = arenaProjectiles[i];
        p.x += p.vx * arenaSimSpeed;
        p.y += p.vy * arenaSimSpeed;
        p.life -= arenaSimSpeed;

        if (Math.random() < 0.6) {
          arenaParticles.push({
            x: p.x,
            y: p.y,
            vx: -p.vx * 0.15 + (Math.random() - 0.5),
            vy: -p.vy * 0.15 + (Math.random() - 0.5),
            color: p.color,
            size: p.radius * 0.7,
            alpha: 0.8,
            decay: 0.06
          });
        }

        let hit = false;
        const target = arenaUnits.find(u => u.id === p.targetUnitId && u.alive);
        if (target) {
          const d = Math.hypot(p.x - target.x, p.y - target.y);
          if (d <= target.radius + p.radius + 6) {
            hit = true;
            playSfxLaser();

            target.shieldRegenDelay = 60;
            let dmgRem = p.damage;
            let absorbed = false;
            if (target.shield > 0) {
              absorbed = true;
              if (target.shield >= dmgRem) {
                target.shield -= dmgRem;
                dmgRem = 0;
                playSfxShieldDeflect();
              } else {
                dmgRem -= target.shield;
                target.shield = 0;
                arenaDamageTexts.push({
                  text: "⚡ SHIELD BREAK!",
                  x: target.x,
                  y: target.y - 32,
                  color: '#d8b4fe',
                  vy: -0.9,
                  alpha: 1.0,
                  size: 12,
                  bold: true
                });
              }
            }
            target.hp = Math.max(0, target.hp - dmgRem);

            arenaDamageTexts.push({
              text: (p.isSpecial ? "💥 " : (absorbed && dmgRem === 0 ? "🛡️ " : "-")) + p.damage + (p.isSpecial ? " CRIT!" : (absorbed && dmgRem === 0 ? " ABSORB" : "")),
              x: target.x + (Math.random() - 0.5) * 16,
              y: target.y - 18,
              color: p.isSpecial ? '#ff0055' : (absorbed && dmgRem === 0 ? '#c084fc' : (p.team === 'blue' ? '#79c0ff' : '#ffa657')),
              vy: -0.8,
              alpha: 1.0,
              size: p.isSpecial ? 14 : 11,
              bold: p.isSpecial || absorbed
            });

            const sparkCount = p.isSpecial ? 16 : 8;
            for (let s = 0; s < sparkCount; s++) {
              const spd = 1.5 + Math.random() * 3.5;
              const a = Math.random() * Math.PI * 2;
              arenaParticles.push({
                x: target.x,
                y: target.y,
                vx: Math.cos(a) * spd,
                vy: Math.sin(a) * spd,
                color: p.color,
                size: 2.5,
                alpha: 1.0,
                decay: 0.05
              });
            }

            if (target.hp <= 0) {
              target.hp = 0;
              target.alive = false;
              playSfxExplosion(true);
              logArena(`[KILL] ${target.name} (${target.team === 'blue' ? 'Blue' : 'Red'}) was eliminated!`, target.team === 'blue' ? '#ff4d4d' : '#2ecc71');

              for (let d = 0; d < 22; d++) {
                const a = Math.random() * Math.PI * 2;
                const spd = 1 + Math.random() * 4.5;
                arenaParticles.push({
                  x: target.x,
                  y: target.y,
                  vx: Math.cos(a) * spd,
                  vy: Math.sin(a) * spd,
                  color: target.team === 'blue' ? '#00f0ff' : '#e67e22',
                  size: 3.5,
                  alpha: 1.0,
                  decay: 0.03
                });
              }
              updateArenaBadges();
              checkArenaVictory();
            }
          }
        }

        if (hit || p.life <= 0 || p.x < 0 || p.x > w || p.y < 0 || p.y > h) {
          arenaProjectiles.splice(i, 1);
        }
      }

      // Update Particles
      for (let i = arenaParticles.length - 1; i >= 0; i--) {
        const p = arenaParticles[i];
        p.x += p.vx * arenaSimSpeed;
        p.y += p.vy * arenaSimSpeed;
        p.alpha -= p.decay * arenaSimSpeed;
        if (p.alpha <= 0) arenaParticles.splice(i, 1);
      }

      // Update Floating Damage Texts
      for (let i = arenaDamageTexts.length - 1; i >= 0; i--) {
        const dt = arenaDamageTexts[i];
        dt.y += dt.vy * arenaSimSpeed;
        dt.alpha -= 0.02 * arenaSimSpeed;
        if (dt.alpha <= 0) arenaDamageTexts.splice(i, 1);
      }
    }

    // 4.5. Render Tactical Fog of War Shroud
    if (arenaFogOfWar) {
      ctx.save();
      ctx.fillStyle = 'rgba(5, 8, 14, 0.88)';
      ctx.fillRect(0, 0, w, h);

      // Reveal circles around living Blue Alliance units
      ctx.globalCompositeOperation = 'destination-out';
      for (const u of arenaUnits) {
        if (u.team === 'blue' && u.alive) {
          const vRad = u.visionRadius || 240;
          const grad = ctx.createRadialGradient(u.x, u.y, vRad * 0.35, u.x, u.y, vRad);
          grad.addColorStop(0, 'rgba(0, 0, 0, 1.0)');
          grad.addColorStop(0.75, 'rgba(0, 0, 0, 0.85)');
          grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
          ctx.fillStyle = grad;
          ctx.beginPath();
          ctx.arc(u.x, u.y, vRad, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.globalCompositeOperation = 'source-over';
      ctx.restore();
    }

    // 5. Render Living Units
    for (const u of arenaUnits) {
      if (!u.alive) continue;
      let isVisibleInFog = true;
      if (arenaFogOfWar && u.team === 'red') {
        isVisibleInFog = false;
        for (const b of arenaUnits) {
          if (b.team === 'blue' && b.alive) {
            const vRad = b.visionRadius || 240;
            if (Math.hypot(b.x - u.x, b.y - u.y) <= vRad) {
              isVisibleInFog = true;
              break;
            }
          }
        }
      }

      if (isVisibleInFog) {
        drawArenaUnit(ctx, u);
      } else {
        // Shrouded radar contact
        ctx.save();
        ctx.translate(u.x, u.y);
        ctx.strokeStyle = 'rgba(255, 75, 75, 0.55)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(0, -9);
        ctx.lineTo(7, 0);
        ctx.lineTo(0, 9);
        ctx.lineTo(-7, 0);
        ctx.closePath();
        ctx.stroke();
        ctx.fillStyle = 'rgba(255, 75, 75, 0.7)';
        ctx.font = '8px monospace';
        ctx.textAlign = 'center';
        ctx.fillText('RADAR', 0, -12);
        ctx.restore();
      }
    }

    // 6. Render Projectiles
    for (const p of arenaProjectiles) {
      ctx.save();
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
      ctx.fillStyle = p.color;
      ctx.shadowColor = p.color;
      ctx.shadowBlur = 8;
      ctx.fill();
      ctx.restore();
    }

    // 7. Render Particles
    for (const p of arenaParticles) {
      ctx.save();
      ctx.globalAlpha = Math.max(0, p.alpha);
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    // 8. Render Damage Texts
    for (const dt of arenaDamageTexts) {
      ctx.save();
      ctx.globalAlpha = Math.max(0, dt.alpha);
      ctx.fillStyle = dt.color;
      ctx.font = `${dt.bold ? 'bold ' : ''}${dt.size || 11}px -apple-system, sans-serif`;
      ctx.shadowColor = 'rgba(0,0,0,0.9)';
      ctx.shadowBlur = 4;
      ctx.textAlign = 'center';
      ctx.fillText(dt.text, dt.x, dt.y);
      ctx.restore();
    }

    // 9. Render Drag-Box Marquee
    if (arenaIsBoxDragging) {
      const minX = Math.min(arenaDragBoxStart.x, arenaDragBoxCurrent.x);
      const maxX = Math.max(arenaDragBoxStart.x, arenaDragBoxCurrent.x);
      const minY = Math.min(arenaDragBoxStart.y, arenaDragBoxCurrent.y);
      const maxY = Math.max(arenaDragBoxStart.y, arenaDragBoxCurrent.y);

      ctx.save();
      ctx.fillStyle = 'rgba(0, 240, 255, 0.18)';
      ctx.fillRect(minX, minY, maxX - minX, maxY - minY);
      ctx.strokeStyle = '#00f0ff';
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.strokeRect(minX, minY, maxX - minX, maxY - minY);
      ctx.setLineDash([]);
      ctx.restore();
    }
  }

  requestAnimationFrame(arenaRenderLoop);
}

function unitAttackTarget(attacker, target, manualSpecial = null) {
  attacker.cooldown = attacker.cooldownMax;
  attacker.recoil = 8;
  attacker.state = 'attack';
  attacker.facing = target.x >= attacker.x ? 1 : -1;

  const isSpecial = manualSpecial != null || Math.random() < 0.18;
  let dmg = attacker.damage + (Math.random() * 6 - 3);

  if (isSpecial) {
    const sp = manualSpecial || ARENA_SPECIAL_MOVES[Math.floor(Math.random() * ARENA_SPECIAL_MOVES.length)];
    dmg *= sp.multiplier;
    arenaDamageTexts.push({
      text: sp.name,
      x: attacker.x,
      y: attacker.y - 28,
      color: sp.color,
      vy: -0.6,
      alpha: 1.0,
      size: 12,
      bold: true
    });
    for (let i = 0; i < 10; i++) {
      const ang = Math.random() * Math.PI * 2;
      const spd = 2 + Math.random() * 3.5;
      arenaParticles.push({
        x: attacker.x + attacker.facing * 16,
        y: attacker.y - 4,
        vx: Math.cos(ang) * spd,
        vy: Math.sin(ang) * spd,
        color: sp.color,
        size: 3,
        alpha: 1.0,
        decay: 0.04
      });
    }
    playSfxSpecialMove();
  } else {
    // Standard weapon sound based on archetype
    if (attacker.roleKey === 'sniper') playSfxRailgun();
    else if (attacker.roleKey === 'rocket') playSfxExplosion(false);
    else if (attacker.roleKey === 'flame') playSfxPlasma();
    else playSfxLaser(false);
  }

  const dx = target.x - attacker.x;
  const dy = target.y - attacker.y;
  const dist = Math.hypot(dx, dy) || 1;
  const pSpeed = attacker.roleKey === 'sniper' ? 14 : attacker.roleKey === 'rocket' ? 6.5 : 9;

  arenaProjectiles.push({
    x: attacker.x + attacker.facing * 14,
    y: attacker.y - 4,
    vx: (dx / dist) * pSpeed,
    vy: (dy / dist) * pSpeed,
    targetUnitId: target.id,
    team: attacker.team,
    damage: Math.round(dmg),
    isSpecial: isSpecial,
    projType: attacker.projType,
    color: attacker.team === 'blue' ? (isSpecial ? '#00ffff' : '#38bdf8') : (isSpecial ? '#ff3b30' : '#fb923c'),
    life: 180,
    radius: attacker.roleKey === 'rocket' ? 5 : 3
  });

  for (let i = 0; i < 4; i++) {
    arenaParticles.push({
      x: attacker.x + attacker.facing * 14,
      y: attacker.y - 4,
      vx: attacker.facing * (1 + Math.random() * 3),
      vy: (Math.random() - 0.5) * 2,
      color: attacker.team === 'blue' ? '#00f0ff' : '#ff922b',
      size: 2.5,
      alpha: 1.0,
      decay: 0.08
    });
  }
}

function drawArenaUnit(ctx, u) {
  ctx.save();
  ctx.translate(u.x, u.y);

  const isSelected = (u.id === arenaSelectedUnitId) || arenaSelectedUnitIds.includes(u.id);
  if (isSelected) {
    ctx.beginPath();
    ctx.arc(0, 12, 22, 0, Math.PI * 2);
    ctx.strokeStyle = u.team === 'blue' ? '#00f0ff' : '#ff7849';
    ctx.lineWidth = 2;
    ctx.setLineDash([4, 4]);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  ctx.beginPath();
  ctx.ellipse(0, 16, 16, 6, 0, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(0, 0, 0, 0.45)';
  ctx.fill();

  const bounceY = u.state === 'march' ? Math.sin(u.walkFrame) * 2.5 : 0;

  ctx.save();
  ctx.translate(0, bounceY);
  if (u.facing < 0) {
    ctx.scale(-1, 1);
  }

  const img = u.spriteImg;
  if (img && img.complete && img.naturalWidth > 0) {
    const targetH = 48;
    const aspect = img.naturalWidth / img.naturalHeight;
    const targetW = targetH * aspect;
    ctx.drawImage(img, -targetW / 2, -targetH + 16, targetW, targetH);
  } else {
    ctx.beginPath();
    ctx.arc(0, -10, 14, 0, Math.PI * 2);
    ctx.fillStyle = u.team === 'blue' ? '#003b5c' : '#5c2200';
    ctx.strokeStyle = u.team === 'blue' ? '#00f0ff' : '#e67e22';
    ctx.lineWidth = 2;
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 10px monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(u.roleTitle.charAt(0), 0, -10);
  }

  const wImg = u.weaponImg;
  ctx.save();
  ctx.translate(6 - (u.recoil || 0), -6);
  if (wImg && wImg.complete && wImg.naturalWidth > 0) {
    const wH = 14;
    const wAspect = wImg.naturalWidth / wImg.naturalHeight;
    const wW = wH * wAspect;
    ctx.drawImage(wImg, 0, -wH / 2, wW, wH);
  }
  if (u.recoil > 4) {
    ctx.beginPath();
    ctx.arc(16, 0, 5, 0, Math.PI * 2);
    ctx.fillStyle = u.team === 'blue' ? '#00ffff' : '#ffaa00';
    ctx.shadowColor = u.team === 'blue' ? '#00ffff' : '#ff8800';
    ctx.shadowBlur = 8;
    ctx.fill();
  }
  ctx.restore();

  ctx.restore();

  const barW = 36;
  const barH = 4;
  const barY = -38;
  const pct = Math.max(0, Math.min(1, u.hp / u.maxHp));

  // Shield Bar (above health bar)
  if (u.maxShield > 0) {
    const sBarY = barY - 4;
    const sBarH = 2.5;
    const sPct = Math.max(0, Math.min(1, (u.shield || 0) / u.maxShield));
    ctx.fillStyle = 'rgba(10, 14, 22, 0.85)';
    ctx.fillRect(-barW / 2 - 1, sBarY - 1, barW + 2, sBarH + 2);
    ctx.fillStyle = '#a855f7';
    ctx.fillRect(-barW / 2, sBarY, barW * sPct, sBarH);
  }

  // Health Bar Background
  ctx.fillStyle = 'rgba(10, 14, 22, 0.85)';
  ctx.fillRect(-barW / 2 - 1, barY - 1, barW + 2, barH + 2);
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
  ctx.lineWidth = 1;
  ctx.strokeRect(-barW / 2 - 1, barY - 1, barW + 2, barH + 2);

  // Health Bar Fill
  ctx.fillStyle = u.team === 'blue' ? '#00f0ff' : '#e67e22';
  if (pct < 0.25) ctx.fillStyle = '#ff4d4d';
  ctx.fillRect(-barW / 2, barY, barW * pct, barH);

  // Segment Notches
  ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
  for (const s of [0.25, 0.5, 0.75]) {
    ctx.fillRect(-barW / 2 + barW * s, barY, 1, barH);
  }

  // Role and Unit Name
  ctx.fillStyle = '#cbd5e1';
  ctx.font = '9px -apple-system, BlinkMacSystemFont, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(u.name.length > 14 ? u.name.substr(0, 12) + '..' : u.name, 0, barY - (u.maxShield > 0 ? 8 : 4));

  // EMP Stun indicator
  if (u.isStunned > 0) {
    ctx.fillStyle = '#facc15';
    ctx.font = 'bold 9px sans-serif';
    ctx.fillText('⚡ STUNNED', 0, barY - 18);
  }

  ctx.restore();
}

function drawArenaBarriers(ctx) {
  ARENA_BARRIERS.forEach(b => {
    ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
    ctx.fillRect(b.x + 4, b.y + 4, b.w, b.h);

    const grad = ctx.createLinearGradient(b.x, b.y, b.x + b.w, b.y + b.h);
    grad.addColorStop(0, '#1a2333');
    grad.addColorStop(1, '#0e1522');
    ctx.fillStyle = grad;
    ctx.fillRect(b.x, b.y, b.w, b.h);

    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(b.x, b.y, b.w, b.h);

    ctx.strokeStyle = 'rgba(230, 126, 34, 0.4)';
    ctx.lineWidth = 2;
    for (let ly = b.y + 10; ly < b.y + b.h; ly += 16) {
      ctx.beginPath();
      ctx.moveTo(b.x + 4, ly);
      ctx.lineTo(b.x + b.w - 4, ly + 8);
      ctx.stroke();
    }
  });
}

function drawArenaBattlefieldGrid(ctx, w, h) {
  ctx.fillStyle = '#070a10';
  ctx.fillRect(0, 0, w, h);

  const blueGlow = ctx.createRadialGradient(80, h / 2, 20, 80, h / 2, 280);
  blueGlow.addColorStop(0, 'rgba(0, 240, 255, 0.08)');
  blueGlow.addColorStop(1, 'transparent');
  ctx.fillStyle = blueGlow;
  ctx.fillRect(0, 0, w / 2, h);

  const redGlow = ctx.createRadialGradient(w - 80, h / 2, 20, w - 80, h / 2, 280);
  redGlow.addColorStop(0, 'rgba(230, 126, 34, 0.08)');
  redGlow.addColorStop(1, 'transparent');
  ctx.fillStyle = redGlow;
  ctx.fillRect(w / 2, 0, w / 2, h);

  ctx.strokeStyle = 'rgba(255, 255, 255, 0.035)';
  ctx.lineWidth = 1;
  const step = 40;
  for (let x = 0; x <= w; x += step) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let y = 0; y <= h; y += step) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  ctx.strokeStyle = 'rgba(0, 240, 255, 0.2)';
  ctx.lineWidth = 2;
  ctx.setLineDash([8, 8]);
  ctx.beginPath();
  ctx.moveTo(w / 2, 0);
  ctx.lineTo(w / 2, h);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.strokeStyle = 'rgba(0, 240, 255, 0.5)';
  ctx.lineWidth = 2;
  ctx.strokeRect(1, 1, w - 2, h - 2);
}

// ---- Init ----
initAnimCatalog();
initSpecialCatalog();
setActivePill('pill-cyber_alien');
checkStatus();
checkModelStatus();
refreshGallery();
refreshArsenal();
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
