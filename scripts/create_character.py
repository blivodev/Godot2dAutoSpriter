#!/usr/bin/env python3
"""
create_character.py - Standalone CLI tool to create and rig any character archetype
without needing an AI agent or MCP host.

Usage examples:
  python scripts/create_character.py --name sorceress --archetype mage
  python scripts/create_character.py --name shinobi --archetype assassin
  python scripts/create_character.py --name goliath --archetype mech
  python scripts/create_character.py --name sylvana --archetype ranger
  python scripts/create_character.py --name paladin --archetype warrior
"""

import os
import sys
import argparse
import json
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def find_godot() -> str:
    env_bin = os.environ.get("GODOT_BIN")
    if env_bin and os.path.isfile(env_bin):
        return env_bin
    for name in ["Godot_v4.7.2-stable_win64_console.exe", "godot4", "godot", "godot.exe"]:
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
    return "godot"


def main():
    parser = argparse.ArgumentParser(description="Create and auto-rig any 2D character for Godot 4.")
    parser.add_argument("--name", "-n", required=True, help="Character identifier (e.g. sorceress, shinobi, titan)")
    parser.add_argument("--archetype", "-a", default="warrior", choices=["warrior", "mage", "assassin", "ranger", "mech", "beast"],
                        help="Visual archetype preset (controls colors, glow, theme)")
    parser.add_argument("--rig-type", "-r", default="", choices=["", "biped", "quadruped"],
                        help="Rig hierarchy type: biped (humanoid) or quadruped (beast/mount)")
    parser.add_argument("--template", "-t", default="", help="Optional custom template scene path")
    parser.add_argument("--prompt", "-p", default="", help="Optional prompt description when using ComfyUI")
    parser.add_argument("--comfy", action="store_true", help="Attempt generating via local ComfyUI API first")
    parser.add_argument("--no-godot", action="store_true", help="Generate sprites only, skip Godot rig assembly")
    parser.add_argument("--target-scene", "-o", default="", help="Custom output .tscn path")

    args = parser.parse_args()

    char_name = args.name.strip().lower().replace(" ", "_")
    archetype = args.archetype.lower()
    rig_type = args.rig_type.lower()
    if not rig_type:
        rig_type = "quadruped" if archetype == "beast" else "biped"

    sprites_dir = PROJECT_ROOT / "sprites" / char_name
    sprites_dir.mkdir(parents=True, exist_ok=True)

    print("\n========================================================")
    print(f"Creating Character: '{char_name}' (Archetype: {archetype.upper()}, Rig: {rig_type.upper()})")
    print("========================================================")

    # 1. Sprite Generation
    generated_via_comfy = False
    if args.comfy:
        try:
            import server
            prompt_text = args.prompt if args.prompt else f"anime {archetype} character"
            res = json.loads(server.generate_character_sprites(char_name, prompt_text))
            if res.get("source") == "comfyui_api":
                print("✓ Successfully generated via ComfyUI API.")
                generated_via_comfy = True
        except Exception as e:
            print(f"ComfyUI API unavailable ({e}), using built-in generator.")

    if not generated_via_comfy:
        prompt_text = args.prompt if args.prompt else f"{archetype} character"
        if rig_type == "quadruped":
            from scripts.generate_sample_sprites import generate_quadruped
            generate_quadruped(str(sprites_dir), prefix=char_name, archetype="assassin" if archetype == "beast" else archetype, prompt=prompt_text)
        else:
            from scripts.generate_sample_sprites import generate_all
            generate_all(str(sprites_dir), prefix=char_name, archetype=archetype, prompt=prompt_text)

    # 2. Godot Rig Assembly
    if args.no_godot:
        print("\nSkipping Godot rig assembly (--no-godot specified).")
        print(f"Limb sprites ready at: {sprites_dir}")
        return 0

    godot_exe = find_godot()
    target_scene = args.target_scene if args.target_scene else f"res://scenes/{char_name}_character.tscn"
    res_dir = f"res://sprites/{char_name}"

    print(f"\nAssembling Godot 4 Skeleton2D rig into '{target_scene}'...")
    cmd = [
        godot_exe,
        "--headless",
        "--path",
        str(PROJECT_ROOT),
        "--script",
        "res://scripts/headless_rig_builder.gd",
        "--",
        "--character-name", char_name,
        "--assets-dir", res_dir,
        "--target-scene", target_scene,
        "--rig-type", rig_type
    ]
    if args.template:
        cmd.extend(["--template", args.template])

    try:
        proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        if proc.returncode == 0:
            print("\n--------------------------------------------------------")
            print(f"[OK] SUCCESS! Character '{char_name}' is fully rigged and saved:")
            print(f"  Scene:  {target_scene}")
            print(f"  Assets: {res_dir}")
            print("--------------------------------------------------------")
            print(f"Open Godot 4 and load '{target_scene}' to see your rigged {archetype.upper()} character!\n")
            return 0
        else:
            print(f"\n[ERROR] in Godot rig assembly (code {proc.returncode}):")
            print(proc.stdout)
            print(proc.stderr)
            return 1
    except Exception as e:
        print(f"\n[ERROR] Execution failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
