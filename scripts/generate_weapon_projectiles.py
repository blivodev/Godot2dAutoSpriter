#!/usr/bin/env python3
"""
generate_weapon_projectiles.py - Procedural Weapons & (Animated / Static) Projectiles Generator

Generates high-quality 2D sci-fi cyberpunk weapons and projectiles for Godot 4:
- 12 Weapon Types (Assault Rifle, Sniper Railgun, Rocket Launcher, Grenade Lobber, Flamethrower,
  Psionic Emitter, Flak Cannon, SMG, Scatter Shotgun, Drone Deployer, Bio-Spitter, Rotary Gatling)
- 9 Projectile Types (Static tracers, rail beams, missiles, animated plasma bolts, flame jets,
  psionic singularity orbs, flak bursts, acid globules, spinning grenades)
- Automatic Godot 4 scene generation:
  - res://scenes/weapons/<name>.tscn (Sprite2D, Muzzle Marker2D, Ejector Marker2D, metadata)
  - res://scenes/projectiles/<name>.tscn (Area2D, CollisionShape2D, AnimatedSprite2D / Sprite2D)
"""

import os
import sys
import math
import random
from pathlib import Path
from typing import Dict, List, Tuple, Any
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WEAPONS_DIR = PROJECT_ROOT / "sprites" / "weapons"
PROJECTILES_DIR = PROJECT_ROOT / "sprites" / "projectiles"
SCENES_WEAPONS_DIR = PROJECT_ROOT / "scenes" / "weapons"
SCENES_PROJECTILES_DIR = PROJECT_ROOT / "scenes" / "projectiles"

for d in [WEAPONS_DIR, PROJECTILES_DIR, SCENES_WEAPONS_DIR, SCENES_PROJECTILES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# FACTION COLOR THEMES (ALL 15 FACTIONS & MODEL SECTORS)
# ==============================================================================
FACTION_PALETTES = {
    # Original 5 RTS Factions
    "directorate": {
        "primary": (52, 64, 82, 255),       # Tactical gunmetal
        "primary_dark": (30, 38, 50, 255),
        "accent": (78, 96, 122, 255),
        "glow": (0, 215, 255, 255),         # Neon Cyan
        "metal": (160, 175, 195, 255),
        "outline": (16, 22, 32, 255)
    },
    "syndicate": {
        "primary": (145, 90, 45, 255),       # Welded rust-iron
        "primary_dark": (85, 48, 22, 255),
        "accent": (230, 140, 20, 255),      # Hazard Orange
        "glow": (255, 195, 0, 255),         # Amber spark
        "metal": (130, 120, 110, 255),
        "outline": (35, 20, 10, 255)
    },
    "covenant": {
        "primary": (38, 32, 54, 255),       # Matte Carbon
        "primary_dark": (20, 16, 30, 255),
        "accent": (140, 70, 210, 255),      # Psionic Violet
        "glow": (220, 100, 255, 255),       # Ethereal Magenta
        "metal": (175, 160, 205, 255),
        "outline": (14, 10, 22, 255)
    },
    "bioforge": {
        "primary": (45, 65, 38, 255),       # Bio-chitin olive
        "primary_dark": (26, 40, 22, 255),
        "accent": (80, 170, 50, 255),       # Acid green
        "glow": (140, 255, 40, 255),        # Radioactive slime
        "metal": (120, 110, 95, 255),
        "outline": (18, 28, 14, 255)
    },
    "silicon": {
        "primary": (32, 34, 38, 255),       # Matte black chassis
        "primary_dark": (18, 20, 24, 255),
        "accent": (90, 95, 105, 255),
        "glow": (255, 45, 60, 255),         # Optical Laser Red
        "metal": (180, 185, 195, 255),
        "outline": (10, 12, 14, 255)
    },
    # 5 High-Detail Generative Model Sectors
    "neotokyo": {
        "primary": (230, 240, 255, 255),     # Titanium white ceramic
        "primary_dark": (175, 195, 220, 255),
        "accent": (0, 180, 230, 255),        # Electric cyan
        "glow": (0, 240, 255, 255),          # Tachyon energy neon
        "metal": (210, 225, 245, 255),
        "outline": (15, 25, 40, 255)
    },
    "abyssal": {
        "primary": (95, 65, 45, 255),        # Heavily rusted scrap metal
        "primary_dark": (55, 35, 24, 255),
        "accent": (195, 95, 32, 255),        # Corroded iron orange
        "glow": (230, 126, 34, 255),         # Toxic furnace amber
        "metal": (118, 108, 98, 255),
        "outline": (28, 18, 12, 255)
    },
    "orbital": {
        "primary": (30, 36, 32, 255),        # Spec-ops matte carbon
        "primary_dark": (16, 20, 18, 255),
        "accent": (48, 96, 64, 255),         # Tactical dark olive
        "glow": (46, 204, 113, 255),         # Night-vision green
        "metal": (135, 150, 140, 255),
        "outline": (10, 14, 12, 255)
    },
    "aetherium": {
        "primary": (42, 28, 58, 255),        # Astral obsidian
        "primary_dark": (24, 15, 34, 255),
        "accent": (135, 70, 200, 255),       # Deep amethyst crystal
        "glow": (195, 120, 255, 255),        # Psionic starlight violet
        "metal": (190, 165, 215, 255),
        "outline": (16, 10, 24, 255)
    },
    "neonglitch": {
        "primary": (26, 20, 38, 255),        # Midnight synth chassis
        "primary_dark": (15, 11, 22, 255),
        "accent": (255, 0, 127, 255),        # Hot neon magenta
        "glow": (0, 255, 204, 255),          # Glitch electric cyan
        "metal": (165, 145, 195, 255),
        "outline": (12, 8, 18, 255)
    },
    # 5 Pixel/Anime Cyberpunk Factions
    "ghost_protocol": {
        "primary": (32, 48, 54, 255),
        "primary_dark": (18, 26, 30, 255),
        "accent": (57, 197, 187, 255),
        "glow": (0, 255, 230, 255),
        "metal": (155, 185, 190, 255),
        "outline": (12, 18, 22, 255)
    },
    "iron_valkyrie": {
        "primary": (58, 48, 32, 255),
        "primary_dark": (34, 26, 18, 255),
        "accent": (210, 153, 34, 255),
        "glow": (255, 215, 0, 255),
        "metal": (200, 180, 145, 255),
        "outline": (22, 18, 12, 255)
    },
    "neon_outcasts": {
        "primary": (42, 22, 38, 255),
        "primary_dark": (24, 12, 20, 255),
        "accent": (247, 120, 186, 255),
        "glow": (255, 105, 180, 255),
        "metal": (175, 135, 165, 255),
        "outline": (18, 10, 16, 255)
    },
    "apex_transhumans": {
        "primary": (36, 26, 52, 255),
        "primary_dark": (20, 14, 30, 255),
        "accent": (163, 113, 247, 255),
        "glow": (180, 130, 255, 255),
        "metal": (170, 155, 195, 255),
        "outline": (14, 10, 22, 255)
    },
    "synth_corp": {
        "primary": (48, 26, 26, 255),
        "primary_dark": (26, 14, 14, 255),
        "accent": (255, 123, 114, 255),
        "glow": (255, 60, 60, 255),
        "metal": (185, 155, 155, 255),
        "outline": (22, 12, 12, 255)
    }
}

# ==============================================================================
# WEAPON DEFINITIONS & PROCEDURAL RENDERING
# ==============================================================================
WEAPON_ARCHETYPES = [
    "assault_rifle", "sniper_rifle", "rocket_launcher", "grenade_launcher",
    "flamethrower", "psi_emitter", "flak_cannon", "submachine_gun",
    "shotgun", "drone_pad", "bio_spitter", "rotary_gatling",
    "melee_blade", "pistol"
]

def render_weapon_sprite(weapon_type: str, faction: str = "directorate", size: Tuple[int, int] = (96, 48)) -> Image.Image:
    """Renders a detailed 2D sci-fi cyberpunk weapon sprite."""
    w, h = size[0] * 2, size[1] * 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    theme = FACTION_PALETTES.get(faction, FACTION_PALETTES["directorate"])

    cx, cy = w // 2, h // 2

    if weapon_type in ["assault_rifle", "submachine_gun"]:
        length = 130 if weapon_type == "assault_rifle" else 95
        barrel_y = cy - 4
        # Receiver / Main Body
        draw.rounded_rectangle([cx - length//3, cy - 14, cx + length//4, cy + 10], radius=4, fill=theme["primary"], outline=theme["outline"], width=3)
        # Top tactical rail / optic
        draw.rectangle([cx - length//4, cy - 20, cx + 15, cy - 14], fill=theme["accent"], outline=theme["outline"], width=2)
        draw.ellipse([cx - 5, cy - 24, cx + 5, cy - 14], fill=theme["glow"])
        # Barrel & Shroud
        draw.rectangle([cx + length//4, cy - 10, cx + length//2, cy + 2], fill=theme["primary_dark"], outline=theme["outline"], width=2)
        draw.rectangle([cx + length//2, cy - 8, cx + length//2 + 16, cy], fill=theme["metal"], outline=theme["outline"], width=2)
        # Muzzle break
        draw.polygon([(cx + length//2 + 16, cy - 10), (cx + length//2 + 22, cy - 7), (cx + length//2 + 22, cy + 3), (cx + length//2 + 16, cy + 6)], fill=theme["primary_dark"])
        # Grip
        draw.polygon([(cx - length//5, cy + 8), (cx - length//5 - 12, cy + 36), (cx - length//5 + 2, cy + 36), (cx - length//5 + 4, cy + 8)], fill=theme["primary_dark"], outline=theme["outline"], width=2)
        # Curved Magazine
        draw.polygon([(cx + 4, cy + 8), (cx + 12, cy + 40), (cx + 26, cy + 38), (cx + 18, cy + 8)], fill=theme["metal"], outline=theme["outline"], width=2)
        # Stock
        draw.polygon([(cx - length//3, cy - 10), (cx - length//2 - 12, cy - 12), (cx - length//2 - 12, cy + 18), (cx - length//3, cy + 6)], fill=theme["accent"], outline=theme["outline"], width=2)
        # Glowing faction conduit
        draw.line([(cx - 15, cy - 2), (cx + 35, cy - 2)], fill=theme["glow"], width=3)

    elif weapon_type == "sniper_rifle":
        # Ultra long sniper railgun
        # Slim receiver
        draw.rounded_rectangle([cx - 45, cy - 10, cx + 25, cy + 8], radius=3, fill=theme["primary"], outline=theme["outline"], width=3)
        # Long heavy rail barrel
        draw.rectangle([cx + 25, cy - 8, cx + 80, cy + 4], fill=theme["primary_dark"], outline=theme["outline"], width=2)
        draw.rectangle([cx + 80, cy - 6, cx + 115, cy + 2], fill=theme["metal"], outline=theme["outline"], width=2)
        # Railgun capacitor coils
        for x_coil in [cx + 35, cx + 55, cx + 75, cx + 95]:
            draw.rectangle([x_coil, cy - 10, x_coil + 8, cy + 6], fill=theme["glow"], outline=theme["outline"], width=1)
        # Heavy Muzzle crown
        draw.polygon([(cx + 115, cy - 10), (cx + 126, cy - 6), (cx + 126, cy + 4), (cx + 115, cy + 8)], fill=theme["primary_dark"])
        # High-tech Scope
        draw.rounded_rectangle([cx - 20, cy - 26, cx + 35, cy - 12], radius=4, fill=theme["metal"], outline=theme["outline"], width=2)
        draw.ellipse([cx + 28, cy - 24, cx + 38, cy - 14], fill=theme["glow"])
        # Bipod folded
        draw.line([(cx + 60, cy + 6), (cx + 85, cy + 14)], fill=theme["outline"], width=3)
        # Skeleton stock & grip
        draw.polygon([(cx - 45, cy - 6), (cx - 85, cy - 8), (cx - 85, cy + 14), (cx - 45, cy + 6)], fill=theme["accent"], outline=theme["outline"], width=2)
        draw.polygon([(cx - 25, cy + 6), (cx - 35, cy + 34), (cx - 20, cy + 34), (cx - 10, cy + 6)], fill=theme["primary_dark"], outline=theme["outline"], width=2)

    elif weapon_type == "rocket_launcher":
        # Massive shoulder-mounted cylinder launcher
        draw.rounded_rectangle([cx - 75, cy - 22, cx + 60, cy + 16], radius=6, fill=theme["primary"], outline=theme["outline"], width=4)
        # Reinforced banding
        for bx in [cx - 60, cx - 15, cx + 30]:
            draw.rectangle([bx, cy - 24, bx + 12, cy + 18], fill=theme["accent"], outline=theme["outline"], width=2)
        # Front exhaust shroud
        draw.polygon([(cx + 60, cy - 26), (cx + 74, cy - 20), (cx + 74, cy + 14), (cx + 60, cy + 20)], fill=theme["metal"], outline=theme["outline"], width=3)
        # Rocket warhead tip peeking out
        draw.polygon([(cx + 65, cy - 10), (cx + 84, cy - 3), (cx + 65, cy + 4)], fill=theme["glow"])
        # Shoulder rest notch & front grip
        draw.rectangle([cx - 50, cy + 16, cx - 20, cy + 26], fill=theme["primary_dark"], outline=theme["outline"], width=2)
        draw.rectangle([cx + 10, cy + 16, cx + 24, cy + 40], fill=theme["primary_dark"], outline=theme["outline"], width=3)
        # Holographic target HUD
        draw.rectangle([cx - 10, cy - 36, cx + 20, cy - 24], fill=(0, 0, 0, 160), outline=theme["glow"], width=2)
        draw.line([(cx + 5, cy - 36), (cx + 5, cy - 24)], fill=theme["glow"], width=2)

    elif weapon_type == "flamethrower":
        # Dual fuel canister with nozzle
        # Upper barrel & ignition coil
        draw.rectangle([cx - 20, cy - 14, cx + 65, cy - 2], fill=theme["metal"], outline=theme["outline"], width=2)
        # Nozzle & pilot light
        draw.polygon([(cx + 65, cy - 18), (cx + 78, cy - 14), (cx + 78, cy), (cx + 65, cy + 4)], fill=theme["primary_dark"], outline=theme["outline"], width=2)
        draw.ellipse([cx + 72, cy - 12, cx + 84, cy - 2], fill=(255, 140, 20, 255))
        # Fuel pressure canister (round bottom)
        draw.rounded_rectangle([cx - 55, cy - 6, cx + 5, cy + 28], radius=8, fill=theme["accent"], outline=theme["outline"], width=3)
        # Pressure gauge
        draw.ellipse([cx - 35, cy + 4, cx - 15, cy + 24], fill=(255, 255, 255, 230), outline=theme["outline"], width=2)
        draw.line([(cx - 25, cy + 14), (cx - 20, cy + 8)], fill=(220, 30, 30, 255), width=2)
        # Pressure hoses
        draw.arc([cx - 40, cy + 18, cx + 45, cy + 38], 0, 180, fill=theme["glow"], width=3)
        # Dual handles
        draw.rectangle([cx - 65, cy - 16, cx - 52, cy + 12], fill=theme["primary_dark"], outline=theme["outline"], width=2)
        draw.rectangle([cx + 15, cy - 2, cx + 27, cy + 22], fill=theme["primary_dark"], outline=theme["outline"], width=2)

    elif weapon_type == "flak_cannon":
        # Dual heavy anti-air barrels with ventilated heat vents
        draw.rectangle([cx - 50, cy - 18, cx + 15, cy + 18], fill=theme["primary"], outline=theme["outline"], width=4)
        # Twin heavy flak barrels
        draw.rectangle([cx + 15, cy - 16, cx + 80, cy - 2], fill=theme["primary_dark"], outline=theme["outline"], width=2)
        draw.rectangle([cx + 15, cy + 2, cx + 80, cy + 16], fill=theme["primary_dark"], outline=theme["outline"], width=2)
        # Flak recoil baffles
        for fx in [cx + 35, cx + 55, cx + 75]:
            draw.rectangle([fx, cy - 20, fx + 6, cy + 20], fill=theme["metal"], outline=theme["outline"], width=2)
        # Large drum magazine
        draw.ellipse([cx - 35, cy + 12, cx + 5, cy + 44], fill=theme["metal"], outline=theme["outline"], width=3)
        draw.line([(cx - 15, cy + 12), (cx - 15, cy + 44)], fill=theme["glow"], width=3)

    elif weapon_type == "psi_emitter":
        # Floating crystalline focus staff / gauntlet
        draw.line([(cx - 70, cy + 2), (cx + 40, cy + 2)], fill=theme["primary"], width=6)
        # Crystal focus head
        draw.polygon([(cx + 40, cy - 14), (cx + 70, cy), (cx + 40, cy + 14), (cx + 25, cy)], fill=theme["glow"], outline=theme["outline"], width=2)
        # Levitating orbital rings
        draw.ellipse([cx + 48, cy - 22, cx + 62, cy + 22], outline=theme["accent"], width=3)
        draw.ellipse([cx + 38, cy - 16, cx + 72, cy + 16], outline=theme["glow"], width=2)
        # Energy conduits wrapping shaft
        for sp in [-50, -20, 10]:
            draw.arc([cx + sp, cy - 8, cx + sp + 18, cy + 10], 0, 180, fill=theme["glow"], width=3)

    elif weapon_type == "rotary_gatling":
        # Tri-barrel rotary minigun
        draw.rounded_rectangle([cx - 60, cy - 16, cx + 5, cy + 16], radius=5, fill=theme["primary"], outline=theme["outline"], width=3)
        # 3 spinning barrels
        draw.rectangle([cx + 5, cy - 14, cx + 75, cy - 6], fill=theme["metal"], outline=theme["outline"], width=2)
        draw.rectangle([cx + 5, cy - 4, cx + 75, cy + 4], fill=theme["primary_dark"], outline=theme["outline"], width=2)
        draw.rectangle([cx + 5, cy + 6, cx + 75, cy + 14], fill=theme["metal"], outline=theme["outline"], width=2)
        # Rotary support rings
        draw.ellipse([cx + 30, cy - 16, cx + 42, cy + 16], fill=theme["accent"], outline=theme["outline"], width=2)
        draw.ellipse([cx + 70, cy - 16, cx + 82, cy + 16], fill=theme["primary_dark"], outline=theme["outline"], width=2)
        # Ammo chute
        draw.rectangle([cx - 45, cy + 16, cx - 15, cy + 38], fill=theme["metal"], outline=theme["outline"], width=2)
        # Dual spade grips
        draw.rectangle([cx - 75, cy - 10, cx - 60, cy + 10], fill=theme["primary_dark"], outline=theme["outline"], width=2)

    elif weapon_type == "melee_blade":
        # Cyberpunk Vibro-Katana / Monomolecular Energy Blade
        # Tsuka (hilt) & Pommel
        draw.rounded_rectangle([cx - 75, cy - 5, cx - 35, cy + 5], radius=2, fill=theme["primary_dark"], outline=theme["outline"], width=2)
        # Hilt wrap diamond diamonds
        for hx in [cx - 68, cx - 56, cx - 44]:
            draw.polygon([(hx, cy - 4), (hx + 5, cy), (hx, cy + 4), (hx - 5, cy)], fill=theme["accent"])
        # Tsuba (handguard)
        draw.ellipse([cx - 37, cy - 14, cx - 31, cy + 14], fill=theme["metal"], outline=theme["outline"], width=2)
        # Blade base / Habaki
        draw.rectangle([cx - 31, cy - 4, cx - 22, cy + 4], fill=theme["accent"])
        # Main Blade Spine (Dark steel)
        draw.polygon([(cx - 22, cy - 5), (cx + 65, cy - 3), (cx + 85, cy + 2), (cx - 22, cy + 3)], fill=theme["primary"], outline=theme["outline"], width=2)
        # Glowing Monomolecular Plasma Edge
        draw.polygon([(cx - 22, cy + 1), (cx + 70, cy + 3), (cx + 86, cy + 2), (cx + 74, cy + 6), (cx - 22, cy + 4)], fill=theme["glow"])
        draw.line([(cx - 20, cy + 2), (cx + 80, cy + 3)], fill=(255, 255, 255, 240), width=1)

    elif weapon_type == "pistol":
        # Compact Cyberpunk Blaster / Tactical Sidearm
        # Slide & Upper Barrel
        draw.rounded_rectangle([cx - 25, cy - 12, cx + 38, cy + 2], radius=3, fill=theme["primary"], outline=theme["outline"], width=2)
        # Laser Sight / Underbarrel Mount
        draw.rectangle([cx + 5, cy + 2, cx + 32, cy + 8], fill=theme["primary_dark"], outline=theme["outline"], width=1)
        draw.ellipse([cx + 30, cy + 3, cx + 36, cy + 7], fill=theme["glow"])
        # Ejection port & optic
        draw.rectangle([cx - 10, cy - 10, cx + 2, cy - 5], fill=theme["metal"])
        draw.rectangle([cx - 20, cy - 16, cx - 6, cy - 12], fill=theme["accent"], outline=theme["outline"], width=1)
        draw.ellipse([cx - 16, cy - 15, cx - 10, cy - 13], fill=theme["glow"])
        # Grip
        draw.polygon([(cx - 20, cy + 2), (cx - 30, cy + 28), (cx - 16, cy + 28), (cx - 8, cy + 2)], fill=theme["primary_dark"], outline=theme["outline"], width=2)
        draw.rectangle([cx - 26, cy + 8, cx - 18, cy + 22], fill=theme["accent"])
        # Muzzle tip
        draw.rectangle([cx + 38, cy - 10, cx + 43, cy], fill=theme["metal"])

    elif weapon_type == "shotgun":
        # Tactical Combat Scattergun with Pump
        # Heavy Receiver
        draw.rounded_rectangle([cx - 45, cy - 12, cx + 15, cy + 10], radius=4, fill=theme["primary"], outline=theme["outline"], width=3)
        # Twin heavy barrels with ventilated rib
        draw.rectangle([cx + 15, cy - 10, cx + 75, cy + 2], fill=theme["primary_dark"], outline=theme["outline"], width=2)
        draw.rectangle([cx + 15, cy + 2, cx + 70, cy + 8], fill=theme["metal"], outline=theme["outline"], width=2)
        # Underbarrel sliding pump grip
        draw.rounded_rectangle([cx + 25, cy + 6, cx + 55, cy + 18], radius=3, fill=theme["accent"], outline=theme["outline"], width=2)
        # Stock & Pistol grip
        draw.polygon([(cx - 45, cy - 8), (cx - 78, cy - 6), (cx - 78, cy + 16), (cx - 45, cy + 6)], fill=theme["primary_dark"], outline=theme["outline"], width=2)
        draw.polygon([(cx - 25, cy + 8), (cx - 32, cy + 32), (cx - 18, cy + 32), (cx - 12, cy + 8)], fill=theme["primary_dark"], outline=theme["outline"], width=2)
        # Shell ejection port glowing
        draw.rectangle([cx - 8, cy - 8, cx + 6, cy - 2], fill=theme["glow"])

    elif weapon_type == "grenade_launcher":
        # 6-Round Revolving Cylinder Grenade Launcher
        # Receiver & Stock
        draw.rounded_rectangle([cx - 55, cy - 14, cx - 15, cy + 10], radius=4, fill=theme["primary"], outline=theme["outline"], width=3)
        draw.polygon([(cx - 55, cy - 10), (cx - 80, cy - 8), (cx - 80, cy + 16), (cx - 55, cy + 8)], fill=theme["accent"], outline=theme["outline"], width=2)
        # Massive Revolving Cylinder Drum
        draw.ellipse([cx - 16, cy - 18, cx + 24, cy + 18], fill=theme["metal"], outline=theme["outline"], width=3)
        # 6 Chambers
        for c_idx in range(6):
            c_ang = c_idx * (math.pi / 3)
            chx = cx + 4 + int(math.cos(c_ang) * 11)
            chy = cy + int(math.sin(c_ang) * 11)
            draw.ellipse([chx - 3, chy - 3, chx + 3, chy + 3], fill=theme["glow"])
        # Wide-Bore Short Barrel
        draw.rectangle([cx + 24, cy - 12, cx + 75, cy + 8], fill=theme["primary_dark"], outline=theme["outline"], width=3)
        draw.polygon([(cx + 75, cy - 14), (cx + 84, cy - 10), (cx + 84, cy + 10), (cx + 75, cy + 14)], fill=theme["metal"])
        # Foregrip & Grip
        draw.rectangle([cx - 35, cy + 8, cx - 22, cy + 34], fill=theme["primary_dark"], outline=theme["outline"], width=2)
        draw.rectangle([cx + 42, cy + 8, cx + 52, cy + 32], fill=theme["primary_dark"], outline=theme["outline"], width=2)

    elif weapon_type == "drone_pad":
        # Cybernetic Wrist-Mounted UAV Uplink Console
        draw.rounded_rectangle([cx - 45, cy - 16, cx + 40, cy + 14], radius=6, fill=theme["primary"], outline=theme["outline"], width=3)
        # Holographic Projected Screen
        draw.rounded_rectangle([cx - 35, cy - 12, cx + 15, cy + 8], radius=3, fill=(10, 20, 35, 230), outline=theme["glow"], width=2)
        # Radar circles on screen
        draw.ellipse([cx - 18, cy - 8, cx - 2, cy + 4], outline=theme["glow"], width=1)
        draw.line([(cx - 10, cy - 8), (cx - 10, cy + 4)], fill=theme["glow"], width=1)
        # Mini Docked Quad-Rotor Drone
        draw.polygon([(cx + 22, cy - 10), (cx + 36, cy - 10), (cx + 29, cy + 2)], fill=theme["metal"])
        draw.line([(cx + 16, cy - 12), (cx + 42, cy - 12)], fill=theme["accent"], width=2)
        draw.ellipse([cx + 27, cy - 8, cx + 31, cy - 4], fill=theme["glow"])
        # Wrist mounting bracers
        draw.rectangle([cx - 50, cy - 12, cx - 44, cy + 10], fill=theme["primary_dark"])
        draw.rectangle([cx + 40, cy - 12, cx + 46, cy + 10], fill=theme["primary_dark"])

    elif weapon_type == "bio_spitter":
        # Biomechanical Chitin Acid Projector
        draw.polygon([(cx - 55, cy - 10), (cx - 15, cy - 16), (cx + 35, cy - 10), (cx + 70, cy), (cx + 40, cy + 14), (cx - 20, cy + 18), (cx - 55, cy + 8)], fill=theme["primary"], outline=theme["outline"], width=3)
        # Organic ribbed sac / gland
        draw.ellipse([cx - 35, cy - 8, cx + 5, cy + 18], fill=theme["accent"], outline=theme["outline"], width=2)
        draw.ellipse([cx - 25, cy - 2, cx - 5, cy + 12], fill=theme["glow"])
        # Toxic dripping nozzle jaws
        draw.polygon([(cx + 60, cy - 14), (cx + 82, cy - 6), (cx + 65, cy)], fill=theme["primary_dark"])
        draw.polygon([(cx + 60, cy + 14), (cx + 82, cy + 6), (cx + 65, cy)], fill=theme["primary_dark"])
        draw.ellipse([cx + 78, cy - 3, cx + 86, cy + 3], fill=theme["glow"])

    else: # fallback default
        draw.rounded_rectangle([cx - 50, cy - 12, cx + 20, cy + 10], radius=4, fill=theme["primary"], outline=theme["outline"], width=3)
        draw.rectangle([cx + 20, cy - 8, cx + 70, cy + 6], fill=theme["metal"], outline=theme["outline"], width=2)
        draw.polygon([(cx + 70, cy - 12), (cx + 80, cy - 8), (cx + 80, cy + 6), (cx + 70, cy + 10)], fill=theme["primary_dark"])
        draw.ellipse([cx - 5, cy - 2, cx + 15, cy + 18], fill=theme["accent"], outline=theme["outline"], width=2)
        draw.rectangle([cx - 30, cy + 8, cx - 16, cy + 34], fill=theme["primary_dark"], outline=theme["outline"], width=3)
        draw.line([(cx - 20, cy - 2), (cx + 30, cy - 2)], fill=theme["glow"], width=3)

    return img.resize(size, Image.Resampling.LANCZOS)


# ==============================================================================
# PROJECTILE DEFINITIONS & PROCEDURAL RENDERING (STATIC & ANIMATED)
# ==============================================================================
PROJECTILE_TYPES = [
    "kinetic_bullet", "sniper_beam", "rocket_missile", "grenade_canister",
    "plasma_bolt", "flame_jet", "psionic_orb", "flak_burst", "acid_globule"
]

def render_projectile_frames(proj_type: str, faction: str = "directorate", frame_size: Tuple[int, int] = (48, 48)) -> List[Image.Image]:
    """
    Renders projectile frame(s):
    - Static projectiles return [1 frame]
    - Animated projectiles return [4 or 6 sequential frames]
    """
    theme = FACTION_PALETTES.get(faction, FACTION_PALETTES["directorate"])
    glow = theme["glow"]
    w, h = frame_size[0] * 2, frame_size[1] * 2
    cx, cy = w // 2, h // 2

    # STATIC PROJECTILES
    if proj_type == "kinetic_bullet":
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Bullet streak with trailing motion fade
        draw.line([(cx - 28, cy), (cx + 20, cy)], fill=(255, 200, 50, 200), width=6)
        draw.line([(cx - 10, cy), (cx + 25, cy)], fill=(255, 255, 220, 255), width=3)
        draw.ellipse([cx + 20, cy - 4, cx + 28, cy + 4], fill=(255, 255, 255, 255))
        return [img.resize(frame_size, Image.Resampling.LANCZOS)]

    elif proj_type == "sniper_beam":
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Glowing rail beam
        draw.line([(cx - 40, cy), (cx + 40, cy)], fill=(glow[0], glow[1], glow[2], 120), width=10)
        draw.line([(cx - 36, cy), (cx + 36, cy)], fill=glow, width=5)
        draw.line([(cx - 30, cy), (cx + 30, cy)], fill=(255, 255, 255, 255), width=2)
        return [img.resize(frame_size, Image.Resampling.LANCZOS)]

    # ANIMATED PROJECTILES (4–6 Frames)
    frames = []

    if proj_type == "plasma_bolt":
        # 4-frame pulsating energy sphere
        for i in range(4):
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            phase = i * (math.pi / 2)
            r_outer = 22 + int(math.sin(phase) * 5)
            r_inner = 14 + int(math.cos(phase) * 3)
            # Outer aura
            draw.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], fill=(glow[0], glow[1], glow[2], 130))
            # Mid core
            draw.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner], fill=glow)
            # Center hot white
            draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=(255, 255, 255, 255))
            # Arc flare
            flare_ang = phase * 2
            fx = cx + int(math.cos(flare_ang) * (r_outer - 4))
            fy = cy + int(math.sin(flare_ang) * (r_outer - 4))
            draw.ellipse([fx - 4, fy - 4, fx + 4, fy + 4], fill=(255, 255, 255, 220))
            frames.append(img.resize(frame_size, Image.Resampling.LANCZOS))

    elif proj_type == "rocket_missile":
        # 4-frame missile with flickering exhaust jet
        flame_colors = [(255, 100, 20), (255, 200, 40), (255, 60, 10), (255, 240, 80)]
        for i in range(4):
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            # Missile body
            draw.polygon([(cx + 26, cy), (cx + 10, cy - 7), (cx - 16, cy - 7), (cx - 16, cy + 7), (cx + 10, cy + 7)], fill=theme["primary"], outline=theme["outline"], width=2)
            # Fins
            draw.polygon([(cx - 16, cy - 7), (cx - 24, cy - 14), (cx - 18, cy - 7)], fill=theme["metal"])
            draw.polygon([(cx - 16, cy + 7), (cx - 24, cy + 14), (cx - 18, cy + 7)], fill=theme["metal"])
            # Warhead tip
            draw.polygon([(cx + 26, cy), (cx + 18, cy - 5), (cx + 18, cy + 5)], fill=glow)
            # Animated exhaust flame flicker
            flame_len = 16 + (i % 2) * 8
            fcol = flame_colors[i % len(flame_colors)]
            draw.polygon([(cx - 16, cy - 4), (cx - 16 - flame_len, cy), (cx - 16, cy + 4)], fill=fcol)
            draw.polygon([(cx - 16, cy - 2), (cx - 16 - (flame_len // 2), cy), (cx - 16, cy + 2)], fill=(255, 255, 255, 240))
            frames.append(img.resize(frame_size, Image.Resampling.LANCZOS))

    elif proj_type == "flame_jet":
        # 6-frame swirling fire ball jet
        for i in range(6):
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            ang = i * (math.pi / 3)
            # 3 overlapping flame lobes
            for l_idx in range(3):
                l_ang = ang + l_idx * (2 * math.pi / 3)
                lx = cx + int(math.cos(l_ang) * 10)
                ly = cy + int(math.sin(l_ang) * 10)
                draw.ellipse([lx - 16, ly - 16, lx + 16, ly + 16], fill=(255, 90 + l_idx * 40, 20, 180))
            draw.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=(255, 220, 60, 240))
            draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(255, 255, 255, 255))
            frames.append(img.resize(frame_size, Image.Resampling.LANCZOS))

    elif proj_type == "psionic_orb":
        # 6-frame swirling ethereal void singularity
        for i in range(6):
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            ang = i * (math.pi / 3)
            # Outer violet distortion
            draw.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], fill=(160, 40, 240, 100))
            # Swirling spiral tentacles
            for t_idx in range(4):
                tang = ang + t_idx * (math.pi / 2)
                tx1 = cx + int(math.cos(tang) * 6)
                ty1 = cy + int(math.sin(tang) * 6)
                tx2 = cx + int(math.cos(tang + 0.8) * 20)
                ty2 = cy + int(math.sin(tang + 0.8) * 20)
                draw.line([(tx1, ty1), (tx2, ty2)], fill=(220, 90, 255, 220), width=4)
            # Black singularity core with glowing rim
            draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=(20, 10, 30, 255), outline=(255, 140, 255, 255), width=2)
            frames.append(img.resize(frame_size, Image.Resampling.LANCZOS))

    elif proj_type == "flak_burst":
        # 6-frame airburst detonation with expanding shrapnel
        for i in range(6):
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            progress = (i + 1) / 6.0
            r_burst = int(28 * progress)
            alpha = int(255 * (1.0 - progress * 0.7))
            draw.ellipse([cx - r_burst, cy - r_burst, cx + r_burst, cy + r_burst], fill=(255, 160, 40, alpha // 2), outline=(255, 230, 100, alpha), width=2)
            # Flying shrapnel fragments
            num_frags = 8
            for f in range(num_frags):
                fang = f * (2 * math.pi / num_frags) + i * 0.1
                dist = int(32 * progress)
                fx = cx + int(math.cos(fang) * dist)
                fy = cy + int(math.sin(fang) * dist)
                draw.rectangle([fx - 2, fy - 2, fx + 2, fy + 2], fill=(255, 255, 220, alpha))
            frames.append(img.resize(frame_size, Image.Resampling.LANCZOS))

    elif proj_type == "grenade_canister":
        # 4-frame spinning grenade
        for i in range(4):
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            rot = i * (math.pi / 2)
            cos_r, sin_r = math.cos(rot), math.sin(rot)
            # Draw rotated oval canister
            pts = []
            for px, py in [(-12, -7), (12, -7), (12, 7), (-12, 7)]:
                rx = cx + int(px * cos_r - py * sin_r)
                ry = cy + int(px * sin_r + py * cos_r)
                pts.append((rx, ry))
            draw.polygon(pts, fill=theme["primary"], outline=theme["outline"], width=2)
            # Blinking LED
            led_x = cx + int(6 * cos_r)
            led_y = cy + int(6 * sin_r)
            draw.ellipse([led_x - 3, led_y - 3, led_x + 3, led_y + 3], fill=glow)
            frames.append(img.resize(frame_size, Image.Resampling.LANCZOS))

    else: # acid_globule default
        # 4-frame bubbling caustic slime
        for i in range(4):
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            phase = i * (math.pi / 2)
            draw.ellipse([cx - 18, cy - 14, cx + 18, cy + 14], fill=(60, 180, 40, 220), outline=(20, 60, 15, 255), width=2)
            # Bubbles
            bx1 = cx - 6 + int(math.sin(phase) * 4)
            by1 = cy - 4
            draw.ellipse([bx1 - 4, by1 - 4, bx1 + 4, by1 + 4], fill=(160, 255, 60, 255))
            draw.ellipse([cx + 6, cy + 2, cx + 10, cy + 6], fill=(160, 255, 60, 255))
            frames.append(img.resize(frame_size, Image.Resampling.LANCZOS))

    return frames


# ==============================================================================
# GODOT 4 SCENE GENERATOR FOR WEAPONS & PROJECTILES
# ==============================================================================

def generate_weapon_scene(weapon_name: str, weapon_type: str, faction: str) -> str:
    """Generates a complete Godot 4 .tscn scene for a weapon."""
    tex_path = f"res://sprites/weapons/{weapon_name}.png"
    scene_file = SCENES_WEAPONS_DIR / f"{weapon_name}.tscn"

    content = f"""[gd_scene load_steps=2 format=3 uid="uid://wpn_{weapon_name}"]

[ext_resource type="Texture2D" path="{tex_path}" id="1_tex"]

[node name="{weapon_name.capitalize()}" type="Node2D"]
metadata/weapon_type = "{weapon_type}"
metadata/faction = "{faction}"

[node name="Sprite2D" type="Sprite2D" parent="."]
texture = ExtResource("1_tex")
offset = Vector2(16, 0)

[node name="Muzzle" type="Marker2D" parent="."]
position = Vector2(48, -2)

[node name="Ejector" type="Marker2D" parent="."]
position = Vector2(-4, -6)
"""
    with open(scene_file, "w", encoding="utf-8") as f:
        f.write(content)
    return str(scene_file)


def generate_projectile_scene(proj_name: str, proj_type: str, is_animated: bool, num_frames: int = 1) -> str:
    """Generates a complete Godot 4 .tscn scene for a projectile."""
    scene_file = SCENES_PROJECTILES_DIR / f"{proj_name}.tscn"

    if is_animated:
        # Load steps for each frame
        ext_resources = []
        anim_frames_lines = []
        for f_idx in range(num_frames):
            rid = f_idx + 1
            f_path = f"res://sprites/projectiles/{proj_name}_f{f_idx}.png"
            ext_resources.append(f'[ext_resource type="Texture2D" path="{f_path}" id="{rid}_tex"]')
            anim_frames_lines.append(f'{{"duration": 1.0, "texture": ExtResource("{rid}_tex")}}')

        ext_str = "\n".join(ext_resources)
        frames_array = ", ".join(anim_frames_lines)

        content = f"""[gd_scene load_steps={num_frames + 3} format=3 uid="uid://prj_{proj_name}"]

{ext_str}

[sub_resource type="SpriteFrames" id="SpriteFrames_proj"]
animations = [{{
"frames": [{frames_array}],
"loop": true,
"name": &"default",
"speed": 10.0
}}]

[sub_resource type="CircleShape2D" id="CircleShape2D_col"]
radius = 12.0

[node name="{proj_name.capitalize()}" type="Area2D"]
metadata/projectile_type = "{proj_type}"
metadata/speed = 550.0

[node name="AnimatedSprite2D" type="AnimatedSprite2D" parent="."]
sprite_frames = SubResource("SpriteFrames_proj")
autoplay = "default"

[node name="CollisionShape2D" type="CollisionShape2D" parent="."]
shape = SubResource("CircleShape2D_col")
"""
    else:
        tex_path = f"res://sprites/projectiles/{proj_name}.png"
        content = f"""[gd_scene load_steps=3 format=3 uid="uid://prj_{proj_name}"]

[ext_resource type="Texture2D" path="{tex_path}" id="1_tex"]

[sub_resource type="CircleShape2D" id="CircleShape2D_col"]
radius = 8.0

[node name="{proj_name.capitalize()}" type="Area2D"]
metadata/projectile_type = "{proj_type}"
metadata/speed = 700.0

[node name="Sprite2D" type="Sprite2D" parent="."]
texture = ExtResource("1_tex")

[node name="CollisionShape2D" type="CollisionShape2D" parent="."]
shape = SubResource("CircleShape2D_col")
"""
    with open(scene_file, "w", encoding="utf-8") as f:
        f.write(content)
    return str(scene_file)


# ==============================================================================
# BATCH CREATION & PIPELINE API
# ==============================================================================

def create_weapon(weapon_name: str, weapon_type: str = "assault_rifle", faction: str = "directorate") -> Dict[str, Any]:
    """Generates weapon sprite and Godot 4 scene."""
    img = render_weapon_sprite(weapon_type, faction)
    out_png = WEAPONS_DIR / f"{weapon_name}.png"
    img.save(out_png)

    scene_path = generate_weapon_scene(weapon_name, weapon_type, faction)
    return {
        "status": "success",
        "name": weapon_name,
        "type": weapon_type,
        "faction": faction,
        "sprite_path": str(out_png),
        "scene_path": scene_path
    }


def create_projectile(proj_name: str, proj_type: str = "plasma_bolt", faction: str = "directorate") -> Dict[str, Any]:
    """Generates projectile sprite(s), animated horizontal strip, and Godot 4 scene."""
    frames = render_projectile_frames(proj_type, faction)
    is_anim = len(frames) > 1

    if is_anim:
        # Save individual frames and combined strip
        fw, fh = frames[0].size
        strip = Image.new("RGBA", (fw * len(frames), fh), (0, 0, 0, 0))
        for idx, f in enumerate(frames):
            f.save(PROJECTILES_DIR / f"{proj_name}_f{idx}.png")
            strip.paste(f, (idx * fw, 0))
        out_png = PROJECTILES_DIR / f"{proj_name}_strip.png"
        strip.save(out_png)
        # Also save f0 as preview
        frames[0].save(PROJECTILES_DIR / f"{proj_name}.png")
    else:
        out_png = PROJECTILES_DIR / f"{proj_name}.png"
        frames[0].save(out_png)

    scene_path = generate_projectile_scene(proj_name, proj_type, is_anim, len(frames))
    return {
        "status": "success",
        "name": proj_name,
        "type": proj_type,
        "faction": faction,
        "animated": is_anim,
        "frame_count": len(frames),
        "sprite_path": str(out_png),
        "scene_path": scene_path
    }


def generate_all_default_weapons_and_projectiles() -> Dict[str, Any]:
    """Generates standard weapon and projectile suite across all 15 factions and model sectors."""
    weapons_created = []
    projectiles_created = []

    # All 15 factions and model sectors
    factions = [
        "directorate", "syndicate", "covenant", "bioforge", "silicon",
        "neotokyo", "abyssal", "orbital", "aetherium", "neonglitch",
        "ghost_protocol", "iron_valkyrie", "neon_outcasts", "apex_transhumans", "synth_corp"
    ]

    for faction in factions:
        for w_type in WEAPON_ARCHETYPES:
            w_name = f"{faction}_{w_type}"
            res = create_weapon(w_name, w_type, faction)
            weapons_created.append(res)

    for faction in factions:
        for p_type in PROJECTILE_TYPES:
            p_name = f"{faction}_{p_type}"
            res = create_projectile(p_name, p_type, faction)
            projectiles_created.append(res)

    print(f"✓ Generated {len(weapons_created)} weapons and {len(projectiles_created)} projectiles across {len(factions)} factions.")
    return {
        "weapons_count": len(weapons_created),
        "projectiles_count": len(projectiles_created),
        "weapons": weapons_created,
        "projectiles": projectiles_created
    }


if __name__ == "__main__":
    generate_all_default_weapons_and_projectiles()
