#!/usr/bin/env python3
"""
generate_pixel_anime_roster.py - 50 Mature Pixel/Anime Cyberpunk RTS Characters Generator

Generates 50 new, distinct, non-childish characters blending retro pixel art and gritty anime:
- Mature anime facial proportions: sharp angular jaws, narrow focused eyes, cybernetic oculars,
  gritty combat scars, spiky anime hair, tactical cowls, respirators, high-collared jackets.
- Pixel/Anime rendering pipeline: 32-color quantized palette with crisp pixel cluster alignment.
- 5 Elite Divisions (10 characters each):
  1. Ghost Protocol (Black-Ops Cyber-Ninjas & Netrunners)
  2. Iron Valkyrie (Heavy Exoskeleton & Heavy Ordinance)
  3. Neon Outcasts (Wasteland Cyber-Drifters & Chem-Raiders)
  4. Apex Transhumans (Cyborg Ascendants & Psi-Commanders)
  5. Section 9 Synth-Corp (Tactical Synthetic Androids & Droid Mechs)
- Sliced limbs, exploded sheets, full assembled previews, metadata.json, and Godot 4 scenes with 23 animations.
"""

import os
import sys
import json
import math
import random
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw
from typing import Dict, List, Any, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_sample_sprites import (
    create_character_assembled_preview,
    catmull_rom_spline,
    draw_curved_polygon,
    draw_curved_line
)
from scripts.generate_rig_animations import (
    SPECIAL_MOVES_CATALOG,
    build_character_animations,
    randomize_character_specials
)

# ==============================================================================
# PIXEL / ANIME RENDERING ENGINE
# ==============================================================================

def render_pixel_anime_sprite(size: Tuple[int, int], draw_func, num_colors: int = 36) -> Image.Image:
    """
    Renders sprite at 2x native resolution, downsamples with NEAREST for crisp pixel cluster alignment,
    and quantizes colors for an authentic 90s/2000s retro anime pixel art look.
    """
    scale = 2
    w, h = size[0] * scale, size[1] * scale
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw_func(draw, w, h, scale)

    pixel_img = canvas.resize(size, Image.Resampling.NEAREST)
    r, g, b, a = pixel_img.split()
    a = a.point(lambda p: 255 if p > 70 else 0)
    rgb = pixel_img.convert("RGB")
    try:
        quantized = rgb.quantize(colors=num_colors, method=Image.Quantize.MEDIANCUT).convert("RGBA")
        quantized.putalpha(a)
        return quantized
    except Exception:
        pixel_img.putalpha(a)
        return pixel_img


# ==============================================================================
# 5 ELITE DIVISIONS COLOR PALETTES
# ==============================================================================

DIVISION_PALETTES = {
    "ghost_protocol": {
        "skin": (220, 195, 180, 255),
        "skin_shadow": (170, 140, 125, 255),
        "hair": (35, 40, 50, 255),
        "hair_hi": (65, 80, 105, 255),
        "armor_dark": (18, 22, 28, 255),
        "armor_mid": (34, 42, 54, 255),
        "armor_light": (58, 72, 92, 255),
        "trim": (120, 140, 165, 255),
        "glow": (0, 230, 255, 255),          # Neon Cyan
        "glow_core": (200, 250, 255, 255),
        "eye": (0, 240, 255, 255),
        "outline": (10, 12, 16, 255)
    },
    "iron_valkyrie": {
        "skin": (210, 180, 165, 255),
        "skin_shadow": (160, 130, 115, 255),
        "hair": (180, 160, 140, 255),
        "hair_hi": (225, 210, 190, 255),
        "armor_dark": (35, 38, 44, 255),
        "armor_mid": (62, 68, 78, 255),
        "armor_light": (95, 105, 120, 255),
        "trim": (240, 180, 20, 255),         # Hazard Gold / Yellow
        "glow": (255, 150, 0, 255),          # Industrial Amber
        "glow_core": (255, 225, 120, 255),
        "eye": (255, 180, 30, 255),
        "outline": (14, 15, 18, 255)
    },
    "neon_outcasts": {
        "skin": (195, 160, 135, 255),
        "skin_shadow": (145, 110, 85, 255),
        "hair": (255, 60, 120, 255),         # Neon Magenta / Punk
        "hair_hi": (255, 140, 185, 255),
        "armor_dark": (45, 28, 20, 255),     # Grimy Leather
        "armor_mid": (95, 55, 32, 255),      # Weathered Rust
        "armor_light": (145, 88, 52, 255),
        "trim": (210, 175, 75, 255),
        "glow": (57, 255, 20, 255),          # Toxic Chem Lime
        "glow_core": (180, 255, 80, 255),
        "eye": (255, 40, 100, 255),
        "outline": (16, 10, 8, 255)
    },
    "apex_transhumans": {
        "skin": (230, 215, 210, 255),        # Pale Synthetic Porcelain
        "skin_shadow": (175, 160, 165, 255),
        "hair": (220, 225, 240, 255),        # Platinum White
        "hair_hi": (255, 255, 255, 255),
        "armor_dark": (26, 14, 42, 255),     # Abyssal Obsidian
        "armor_mid": (52, 26, 80, 255),      # Void Purple
        "armor_light": (88, 45, 132, 255),
        "trim": (215, 175, 85, 255),         # Royal Astral Gold
        "glow": (225, 30, 255, 255),         # Psionic Violet
        "glow_core": (255, 170, 255, 255),
        "eye": (220, 40, 255, 255),
        "outline": (10, 6, 16, 255)
    },
    "synth_corp": {
        "skin": (150, 160, 175, 255),        # Synthetic Steel Mesh
        "skin_shadow": (105, 115, 130, 255),
        "hair": (30, 32, 36, 255),           # Matte Black Fiber
        "hair_hi": (70, 75, 85, 255),
        "armor_dark": (20, 24, 30, 255),     # Carbon Tungsten
        "armor_mid": (42, 48, 60, 255),
        "armor_light": (72, 82, 100, 255),
        "trim": (180, 190, 205, 255),        # Polished Chrome
        "glow": (255, 18, 45, 255),          # Laser Red Optical
        "glow_core": (255, 150, 170, 255),
        "eye": (255, 20, 50, 255),
        "outline": (8, 10, 12, 255)
    }
}

# ==============================================================================
# PROCEDURAL DRAWING: MATURE PIXEL / ANIME ANATOMY
# ==============================================================================

def draw_mature_anime_head(draw, w, h, s, p: dict, char_data: dict, seed: int = 42):
    """
    Draws a serious, mature anime face with sharp jawline, high cheekbones, narrow focused eyes,
    spiky anime hair / undercut / cyber cowls, and cybernetic implants.
    """
    cx, cy = w // 2, h // 2
    role = char_data["role"].lower()
    head_type = char_data.get("head_type", "humanoid")
    rng = random.Random(seed)

    # 1. Back Hair / Cowl / Neck Base
    if head_type in ["hooded", "ninja"]:
        # Dark tactical ninja hood / assassin cowl
        draw_curved_polygon(draw, [
            (cx - 18*s, cy + 18*s), (cx - 22*s, cy + 2*s), (cx - 18*s, cy - 20*s),
            (cx, cy - 26*s), (cx + 18*s, cy - 20*s), (cx + 22*s, cy + 2*s), (cx + 18*s, cy + 18*s), (cx, cy + 22*s)
        ], fill=p["armor_dark"], outline=p["outline"], width=2*s)
    elif head_type in ["helmet", "droid"]:
        # Angular military combat helmet or droid frame
        draw_curved_polygon(draw, [
            (cx - 17*s, cy + 18*s), (cx - 20*s, cy + 2*s), (cx - 17*s, cy - 20*s),
            (cx, cy - 24*s), (cx + 17*s, cy - 20*s), (cx + 20*s, cy + 2*s), (cx + 17*s, cy + 18*s), (cx, cy + 22*s)
        ], fill=p["armor_mid"], outline=p["outline"], width=2*s)
    else:
        # Spiky mature anime hair (silhouette behind head)
        hair_pts = [
            (cx - 16*s, cy - 10*s), (cx - 24*s, cy - 4*s), (cx - 26*s, cy - 22*s), (cx - 16*s, cy - 26*s),
            (cx - 8*s, cy - 34*s), (cx, cy - 28*s), (cx + 8*s, cy - 34*s), (cx + 16*s, cy - 26*s),
            (cx + 26*s, cy - 22*s), (cx + 24*s, cy - 4*s), (cx + 16*s, cy - 10*s)
        ]
        draw_curved_polygon(draw, hair_pts, fill=p["hair"], outline=p["outline"], width=2*s)

    # 2. Mature Chiseled Anime Face (Sharp V-line jaw, high cheekbones)
    face_pts = [
        (cx - 14*s, cy - 10*s), # Temple L
        (cx - 15*s, cy + 2*s),  # Cheekbone L
        (cx - 8*s, cy + 14*s),  # Sharp jawline L
        (cx, cy + 20*s),        # Sharp athletic chin
        (cx + 8*s, cy + 14*s),  # Sharp jawline R
        (cx + 15*s, cy + 2*s),  # Cheekbone R
        (cx + 14*s, cy - 10*s), # Temple R
        (cx, cy - 16*s)         # Forehead
    ]
    draw_curved_polygon(draw, face_pts, fill=p["skin"], outline=p["outline"], width=2*s)

    # Shadow under chin & jaw contour
    chin_shadow = [(cx - 7*s, cy + 15*s), (cx, cy + 13*s), (cx + 7*s, cy + 15*s), (cx, cy + 20*s)]
    draw_curved_polygon(draw, chin_shadow, fill=p["skin_shadow"])

    # 3. Mature Focused Anime Eyes & Cybernetic Optics
    if head_type == "droid":
        # Sweeping horizontal tactical eye bar
        draw.rectangle([cx - 14*s, cy - 2*s, cx + 14*s, cy + 4*s], fill=p["armor_dark"], outline=p["outline"], width=s)
        draw.line([(cx - 11*s, cy + 1*s), (cx + 11*s, cy + 1*s)], fill=p["glow"], width=2*s)
        draw.ellipse([cx - 2*s, cy, cx + 2*s, cy + 2*s], fill=p["glow_core"])
    elif head_type in ["sniper", "targeter"]:
        # Left eye: Sharp anime eye with battle scar | Right eye: Glowing high-tech monocle lens
        # Left eye
        draw.polygon([(cx - 11*s, cy - 1*s), (cx - 4*s, cy - 3*s), (cx - 3*s, cy + 2*s), (cx - 10*s, cy + 2*s)], fill=p["eye"], outline=p["outline"], width=s)
        draw.line([(cx - 12*s, cy - 2*s), (cx - 3*s, cy - 4*s)], fill=p["outline"], width=2*s)
        # Right bionic targeting lens
        draw.ellipse([cx + 3*s, cy - 5*s, cx + 13*s, cy + 5*s], fill=p["armor_dark"], outline=p["glow"], width=2*s)
        draw.ellipse([cx + 5*s, cy - 3*s, cx + 11*s, cy + 3*s], fill=p["glow"])
        draw.ellipse([cx + 7*s, cy - 1*s, cx + 9*s, cy + 1*s], fill=p["glow_core"])
    else:
        # Dual sharp, narrow anime eyes (focused warrior glare, NO child blush!)
        for side in [-1, 1]:
            ex = cx + 8*s*side
            ey = cy
            # Upper angled eyelid lash
            draw.line([(ex - 5*s, ey - 2*s), (ex + 5*s, ey - 4*s if side == 1 else ey - 1*s)], fill=p["outline"], width=2*s)
            # Sclera & Iris
            draw.polygon([(ex - 4*s, ey), (ex + 4*s, ey - 1*s), (ex + 3*s, ey + 3*s), (ex - 3*s, ey + 3*s)], fill=(245, 245, 250, 255))
            draw.rectangle([ex - 2*s, ey, ex + 2*s, ey + 3*s], fill=p["eye"])
            # Lower eyelid line
            draw.line([(ex - 3*s, ey + 4*s), (ex + 3*s, ey + 4*s)], fill=p["outline"], width=s)
            # Intense eyebrow
            draw.line([(ex - 6*s, ey - 7*s), (ex + 5*s, ey - 5*s if side == 1 else ey - 8*s)], fill=p["hair"], width=2*s)

    # 4. Grim determined mouth / Cybernetic faceplate
    if head_type in ["respirator", "flamethrower"]:
        # Tactical gas rebreather mask covering nose & mouth
        draw.polygon([(cx - 8*s, cy + 6*s), (cx + 8*s, cy + 6*s), (cx + 6*s, cy + 18*s), (cx - 6*s, cy + 18*s)], fill=p["armor_dark"], outline=p["outline"], width=2*s)
        draw.ellipse([cx - 4*s, cy + 10*s, cx + 4*s, cy + 16*s], fill=p["glow"], outline=p["outline"], width=s)
    elif head_type in ["cyborg_jaw"]:
        # Chrome cybernetic jaw implant with bolted seam
        draw.polygon([(cx - 10*s, cy + 8*s), (cx + 10*s, cy + 8*s), (cx + 7*s, cy + 19*s), (cx - 7*s, cy + 19*s)], fill=p["trim"], outline=p["outline"], width=s)
        draw.line([(cx - 4*s, cy + 13*s), (cx + 4*s, cy + 13*s)], fill=p["glow"], width=s)
    else:
        # Grim determined warrior mouth line
        draw.line([(cx - 4*s, cy + 12*s), (cx + 4*s, cy + 12*s)], fill=p["outline"], width=2*s)
        draw.line([(cx - 2*s, cy + 14*s), (cx + 2*s, cy + 14*s)], fill=p["skin_shadow"], width=s)

    # 5. Front Hair Bangs & Cyber-Implants
    if head_type not in ["helmet", "droid", "hooded"]:
        # Sharp anime bangs framing forehead
        draw.polygon([(cx - 14*s, cy - 14*s), (cx - 8*s, cy - 2*s), (cx - 4*s, cy - 10*s)], fill=p["hair"])
        draw.polygon([(cx - 5*s, cy - 12*s), (cx, cy + 2*s), (cx + 5*s, cy - 10*s)], fill=p["hair"])
        draw.polygon([(cx + 4*s, cy - 12*s), (cx + 10*s, cy), (cx + 15*s, cy - 12*s)], fill=p["hair"])
        draw.line([(cx - 12*s, cy - 10*s), (cx - 6*s, cy)], fill=p["hair_hi"], width=s)
        draw.line([(cx + 2*s, cy - 8*s), (cx + 8*s, cy - 2*s)], fill=p["hair_hi"], width=s)

    # Cybernetic Temple Jack / Neural Antenna
    draw.rectangle([cx - 16*s, cy - 4*s, cx - 14*s, cy + 4*s], fill=p["trim"], outline=p["outline"], width=s)
    draw.line([(cx - 15*s, cy - 2*s), (cx - 15*s, cy + 2*s)], fill=p["glow"], width=s)


def draw_mature_anime_torso(draw, w, h, s, p: dict, char_data: dict, seed: int = 42):
    """
    Draws an athletic, broad-shouldered cyberpunk V-taper torso with high-collar jacket,
    ballistic chestplate, tactical pouches, and glowing cyber-circuits.
    """
    cx, cy = w // 2, h // 2
    role = char_data["role"].lower()
    torso_style = char_data.get("torso_style", "tactical_jacket")

    # Athletic V-Taper Torso Contour (Broad shoulders, tapered waist)
    torso_contour = [
        (cx - 26*s, cy - 22*s),  # Shoulder L
        (cx + 26*s, cy - 22*s),  # Shoulder R
        (cx + 22*s, cy + 4*s),   # Ribs R
        (cx + 15*s, cy + 24*s),  # Waist R
        (cx, cy + 28*s),         # Groin attach
        (cx - 15*s, cy + 24*s),  # Waist L
        (cx - 22*s, cy + 4*s)    # Ribs L
    ]
    draw_curved_polygon(draw, torso_contour, fill=p["armor_dark"], outline=p["outline"], width=2*s)

    # High-Collar Cyberpunk Jacket / Chestplate
    draw.polygon([(cx - 18*s, cy - 22*s), (cx + 18*s, cy - 22*s), (cx + 14*s, cy + 12*s), (cx - 14*s, cy + 12*s)], fill=p["armor_mid"], outline=p["outline"], width=2*s)

    # High Standing Collar framing the neck
    draw.polygon([(cx - 14*s, cy - 24*s), (cx - 10*s, cy - 14*s), (cx + 10*s, cy - 14*s), (cx + 14*s, cy - 24*s)], fill=p["armor_dark"], outline=p["outline"], width=s)
    draw.line([(cx - 12*s, cy - 22*s), (cx - 8*s, cy - 14*s)], fill=p["glow"], width=s)
    draw.line([(cx + 12*s, cy - 22*s), (cx + 8*s, cy - 14*s)], fill=p["glow"], width=s)

    # Role-specific chest gear
    if "medic" in role:
        # White/cyan medical cross
        draw.rectangle([cx - 12*s, cy - 14*s, cx + 12*s, cy + 4*s], fill=(235, 245, 250, 255), outline=p["outline"], width=s)
        draw.rectangle([cx - 2*s, cy - 11*s, cx + 2*s, cy + 1*s], fill=p["glow"])
        draw.rectangle([cx - 6*s, cy - 7*s, cx + 6*s, cy - 3*s], fill=p["glow"])
    elif "rocket" in role or "heavy" in role:
        # Heavy hazard blast plating
        draw.rectangle([cx - 16*s, cy - 14*s, cx + 16*s, cy + 8*s], fill=p["armor_dark"], outline=p["outline"], width=2*s)
        for hx in range(-12, 14, 7):
            draw.line([(cx + hx*s, cy - 10*s), (cx + (hx+3)*s, cy + 2*s)], fill=p["trim"], width=2*s)
    elif "grenadier" in role:
        # Grenade bandolier
        draw.line([(cx - 18*s, cy - 18*s), (cx + 16*s, cy + 16*s)], fill=p["armor_dark"], width=5*s)
        for gy in [-8, 0, 8]:
            draw.rectangle([cx + (gy-2)*s, cy + gy*s, cx + (gy+2)*s, cy + (gy+3)*s], fill=p["glow"], outline=p["outline"], width=s)
    else:
        # Glowing Arc Reactor / Power Conduit Lines
        draw.ellipse([cx - 6*s, cy - 8*s, cx + 6*s, cy + 4*s], fill=p["armor_dark"], outline=p["glow"], width=2*s)
        draw.ellipse([cx - 3*s, cy - 5*s, cx + 3*s, cy + 1*s], fill=p["glow"])
        draw.ellipse([cx - 1*s, cy - 3*s, cx + 1*s, cy - 1*s], fill=p["glow_core"])
        # Circuit traces
        draw.line([(cx - 14*s, cy - 6*s), (cx - 7*s, cy - 2*s)], fill=p["glow"], width=s)
        draw.line([(cx + 14*s, cy - 6*s), (cx + 7*s, cy - 2*s)], fill=p["glow"], width=s)


def draw_mature_anime_pelvis(draw, w, h, s, p: dict, char_data: dict, seed: int = 42):
    cx, cy = w // 2, h // 2
    # Tactical Utility Belt & Groin Ballistic Plate
    draw_curved_polygon(draw, [
        (cx - 20*s, cy - 16*s), (cx + 20*s, cy - 16*s), (cx + 16*s, cy + 4*s),
        (cx + 8*s, cy + 18*s), (cx - 8*s, cy + 18*s), (cx - 16*s, cy + 4*s)
    ], fill=p["armor_mid"], outline=p["outline"], width=2*s)
    # Belt with ammo pouches
    draw.rectangle([cx - 20*s, cy - 18*s, cx + 20*s, cy - 10*s], fill=p["armor_dark"], outline=p["outline"], width=s)
    draw.rectangle([cx - 16*s, cy - 16*s, cx - 10*s, cy - 10*s], fill=p["trim"])
    draw.rectangle([cx + 10*s, cy - 16*s, cx + 16*s, cy - 10*s], fill=p["trim"])
    # Buckle
    draw.rectangle([cx - 4*s, cy - 17*s, cx + 4*s, cy - 11*s], fill=p["glow"], outline=p["outline"], width=s)


def draw_mature_anime_arm_upper(draw, w, h, s, p: dict, char_data: dict, is_left: bool):
    cx, cy = w // 2, h // 2
    # Angular Pauldron / Jacket Sleeve
    draw_curved_polygon(draw, [
        (cx - 16*s, cy - 18*s), (cx + 16*s, cy - 18*s), (cx + 14*s, cy + 2*s),
        (cx + 10*s, cy + 20*s), (cx - 10*s, cy + 20*s), (cx - 14*s, cy + 2*s)
    ], fill=p["armor_mid"], outline=p["outline"], width=2*s)
    draw.rectangle([cx - 14*s, cy - 16*s, cx + 14*s, cy - 6*s], fill=p["armor_dark"])
    draw.line([(cx - 12*s, cy - 2*s), (cx + 12*s, cy - 2*s)], fill=p["glow"], width=s)


def draw_mature_anime_arm_lower(draw, w, h, s, p: dict, char_data: dict, is_left: bool):
    cx, cy = w // 2, h // 2
    # Cybernetic Forearm / Armored Bracer
    draw_curved_polygon(draw, [
        (cx - 12*s, cy - 20*s), (cx + 12*s, cy - 20*s), (cx + 14*s, cy + 12*s),
        (cx + 8*s, cy + 20*s), (cx - 8*s, cy + 20*s), (cx - 14*s, cy + 12*s)
    ], fill=p["armor_dark"], outline=p["outline"], width=2*s)
    draw.rectangle([cx - 8*s, cy - 14*s, cx + 8*s, cy + 8*s], fill=p["armor_mid"], outline=p["outline"], width=s)
    draw.line([(cx, cy - 10*s), (cx, cy + 6*s)], fill=p["glow"], width=s)


def draw_mature_anime_hand(draw, w, h, s, p: dict, char_data: dict, is_left: bool):
    cx, cy = w // 2, h // 2
    # Armored Knuckle Combat Glove
    draw_curved_polygon(draw, [
        (cx - 8*s, cy - 10*s), (cx + 8*s, cy - 10*s), (cx + 10*s, cy + 2*s),
        (cx + 6*s, cy + 10*s), (cx - 6*s, cy + 10*s), (cx - 10*s, cy + 2*s)
    ], fill=p["armor_dark"], outline=p["outline"], width=s)
    draw.line([(cx - 6*s, cy - 3*s), (cx + 6*s, cy - 3*s)], fill=p["trim"], width=2*s)


def draw_mature_anime_leg_upper(draw, w, h, s, p: dict, char_data: dict, is_left: bool):
    cx, cy = w // 2, h // 2
    # Tactical Cargo Thigh with Holster Strap
    draw_curved_polygon(draw, [
        (cx - 14*s, cy - 22*s), (cx + 14*s, cy - 22*s), (cx + 12*s, cy + 12*s),
        (cx + 8*s, cy + 22*s), (cx - 8*s, cy + 22*s), (cx - 12*s, cy + 12*s)
    ], fill=p["armor_dark"], outline=p["outline"], width=2*s)
    draw.rectangle([cx - 10*s, cy - 14*s, cx + 10*s, cy + 4*s], fill=p["armor_mid"], outline=p["outline"], width=s)
    draw.line([(cx - 12*s, cy - 4*s), (cx + 12*s, cy - 4*s)], fill=p["trim"], width=2*s)


def draw_mature_anime_leg_lower(draw, w, h, s, p: dict, char_data: dict, is_left: bool):
    cx, cy = w // 2, h // 2
    # Tactical Shin Guard & Knee Protector
    draw_curved_polygon(draw, [
        (cx - 12*s, cy - 22*s), (cx + 12*s, cy - 22*s), (cx + 14*s, cy + 12*s),
        (cx + 10*s, cy + 22*s), (cx - 10*s, cy + 22*s), (cx - 14*s, cy + 12*s)
    ], fill=p["armor_mid"], outline=p["outline"], width=2*s)
    draw.ellipse([cx - 8*s, cy - 20*s, cx + 8*s, cy - 8*s], fill=p["armor_dark"], outline=p["outline"], width=s)
    draw.line([(cx - 4*s, cy - 14*s), (cx + 4*s, cy - 14*s)], fill=p["glow"], width=s)


def draw_mature_anime_foot(draw, w, h, s, p: dict, char_data: dict, is_left: bool):
    cx, cy = w // 2, h // 2
    dir_mul = 1 if is_left else -1
    draw_curved_polygon(draw, [
        (cx - 12*s*dir_mul, cy - 8*s), (cx + 8*s*dir_mul, cy - 8*s),
        (cx + 18*s*dir_mul, cy + 8*s), (cx - 14*s*dir_mul, cy + 8*s)
    ], fill=p["armor_dark"], outline=p["outline"], width=2*s)
    x0 = min(cx - 14*s*dir_mul, cx + 18*s*dir_mul)
    x1 = max(cx - 14*s*dir_mul, cx + 18*s*dir_mul)
    draw.rectangle([x0, cy + 6*s, x1, cy + 10*s], fill=p["armor_mid"])


# ==============================================================================
# 50 CYBERPUNK ANIME ROSTER DEFINITIONS
# ==============================================================================

ROSTER_50_DEFINITIONS = [
    # DIVISION 1: GHOST PROTOCOL (Black-Ops Cyber-Ninjas & Netrunners)
    {"id": "ghost_operative", "display": "Ghost Operative", "div": "ghost_protocol", "role": "Special Agent", "weapon": "directorate_submachine_gun", "head_type": "ninja"},
    {"id": "shadow_netrunner", "display": "Shadow Netrunner", "div": "ghost_protocol", "role": "Mind Controller", "weapon": "covenant_psi_emitter", "head_type": "humanoid"},
    {"id": "phase_infiltrator", "display": "Phase Infiltrator", "div": "ghost_protocol", "role": "Spy / Saboteur", "weapon": "directorate_submachine_gun", "head_type": "hooded"},
    {"id": "cybersamurai_kage", "display": "Cyber-Samurai Kage", "div": "ghost_protocol", "role": "Soldier", "weapon": "covenant_assault_rifle", "head_type": "cyborg_jaw"},
    {"id": "dataspike_assassin", "display": "Dataspike Assassin", "div": "ghost_protocol", "role": "Special Agent", "weapon": "silicon_submachine_gun", "head_type": "sniper"},
    {"id": "void_stalker", "display": "Void Stalker", "div": "ghost_protocol", "role": "Sniper", "weapon": "covenant_sniper_rifle", "head_type": "hooded"},
    {"id": "optical_wraith", "display": "Optical Wraith", "div": "ghost_protocol", "role": "Spy / Saboteur", "weapon": "directorate_submachine_gun", "head_type": "ninja"},
    {"id": "monoblade_ronin", "display": "Monoblade Ronin", "div": "ghost_protocol", "role": "Soldier", "weapon": "syndicate_assault_rifle", "head_type": "humanoid"},
    {"id": "nanowire_trapper", "display": "Nanowire Trapper", "div": "ghost_protocol", "role": "Engineer", "weapon": "directorate_shotgun", "head_type": "targeter"},
    {"id": "phantom_courier", "display": "Phantom Courier", "div": "ghost_protocol", "role": "Special Agent", "weapon": "directorate_submachine_gun", "head_type": "ninja"},

    # DIVISION 2: IRON VALKYRIE (Heavy Exoskeleton & Heavy Ordinance)
    {"id": "titan_juggernaut", "display": "Titan Juggernaut", "div": "iron_valkyrie", "role": "Rocket Trooper", "weapon": "directorate_rocket_launcher", "head_type": "helmet"},
    {"id": "valkyrie_breacher", "display": "Valkyrie Breacher", "div": "iron_valkyrie", "role": "Soldier", "weapon": "directorate_assault_rifle", "head_type": "helmet"},
    {"id": "rail_artillerist", "display": "Rail Artillerist", "div": "iron_valkyrie", "role": "Sniper", "weapon": "directorate_sniper_rifle", "head_type": "targeter"},
    {"id": "siege_sentinel", "display": "Siege Sentinel", "div": "iron_valkyrie", "role": "Flak Trooper", "weapon": "directorate_flak_cannon", "head_type": "helmet"},
    {"id": "colossus_gunner", "display": "Colossus Gunner", "div": "iron_valkyrie", "role": "Soldier", "weapon": "directorate_assault_rifle", "head_type": "respirator"},
    {"id": "demolition_vanguard", "display": "Demolition Vanguard", "div": "iron_valkyrie", "role": "Grenadier", "weapon": "directorate_grenade_launcher", "head_type": "helmet"},
    {"id": "vulcan_dreadnought", "display": "Vulcan Dreadnought", "div": "iron_valkyrie", "role": "Flame Trooper", "weapon": "directorate_flamethrower", "head_type": "flamethrower"},
    {"id": "mortar_bastion", "display": "Mortar Bastion", "div": "iron_valkyrie", "role": "Rocket Trooper", "weapon": "directorate_rocket_launcher", "head_type": "helmet"},
    {"id": "ironclad_shock", "display": "Ironclad Shock", "div": "iron_valkyrie", "role": "Soldier", "weapon": "directorate_shotgun", "head_type": "helmet"},
    {"id": "thunder_centurion", "display": "Thunder Centurion", "div": "iron_valkyrie", "role": "Drone Operator", "weapon": "directorate_drone_pad", "head_type": "helmet"},

    # DIVISION 3: NEON OUTCASTS (Wasteland Cyber-Drifters & Chem-Raiders)
    {"id": "neon_scavenger", "display": "Neon Scavenger", "div": "neon_outcasts", "role": "Soldier", "weapon": "syndicate_assault_rifle", "head_type": "humanoid"},
    {"id": "chem_wastelander", "display": "Chem Wastelander", "div": "neon_outcasts", "role": "Flame Trooper", "weapon": "syndicate_flamethrower", "head_type": "respirator"},
    {"id": "plasma_biker", "display": "Plasma Biker", "div": "neon_outcasts", "role": "Soldier", "weapon": "syndicate_shotgun", "head_type": "humanoid"},
    {"id": "sandstorm_sniper", "display": "Sandstorm Sniper", "div": "neon_outcasts", "role": "Sniper", "weapon": "syndicate_sniper_rifle", "head_type": "hooded"},
    {"id": "scrap_sawbones", "display": "Scrap Sawbones", "div": "neon_outcasts", "role": "Medic", "weapon": "syndicate_submachine_gun", "head_type": "respirator"},
    {"id": "rebar_gladiator", "display": "Rebar Gladiator", "div": "neon_outcasts", "role": "Soldier", "weapon": "syndicate_shotgun", "head_type": "cyborg_jaw"},
    {"id": "rad_stalker", "display": "Rad Stalker", "div": "neon_outcasts", "role": "Spy / Saboteur", "weapon": "syndicate_submachine_gun", "head_type": "hooded"},
    {"id": "junk_demolitionist", "display": "Junk Demolitionist", "div": "neon_outcasts", "role": "Grenadier", "weapon": "syndicate_grenade_launcher", "head_type": "humanoid"},
    {"id": "toxic_nomad", "display": "Toxic Nomad", "div": "neon_outcasts", "role": "Engineer", "weapon": "syndicate_shotgun", "head_type": "respirator"},
    {"id": "dune_tracker", "display": "Dune Tracker", "div": "neon_outcasts", "role": "Drone Operator", "weapon": "syndicate_drone_pad", "head_type": "targeter"},

    # DIVISION 4: APEX TRANSHUMANS (Cyborg Ascendants & Psi-Commanders)
    {"id": "apex_overseer", "display": "Apex Overseer", "div": "apex_transhumans", "role": "Mind Controller", "weapon": "covenant_psi_emitter", "head_type": "humanoid"},
    {"id": "synapse_weaver", "display": "Synapse Weaver", "div": "apex_transhumans", "role": "Mind Controller", "weapon": "covenant_psi_emitter", "head_type": "humanoid"},
    {"id": "chrono_operative", "display": "Chrono Operative", "div": "apex_transhumans", "role": "Special Agent", "weapon": "covenant_submachine_gun", "head_type": "ninja"},
    {"id": "cyber_archon", "display": "Cyber Archon", "div": "apex_transhumans", "role": "Soldier", "weapon": "covenant_assault_rifle", "head_type": "cyborg_jaw"},
    {"id": "psionic_crusader", "display": "Psionic Crusader", "div": "apex_transhumans", "role": "Soldier", "weapon": "covenant_assault_rifle", "head_type": "hooded"},
    {"id": "neural_phantom", "display": "Neural Phantom", "div": "apex_transhumans", "role": "Spy / Saboteur", "weapon": "covenant_submachine_gun", "head_type": "ninja"},
    {"id": "singularity_vanguard", "display": "Singularity Vanguard", "div": "apex_transhumans", "role": "Rocket Trooper", "weapon": "covenant_rocket_launcher", "head_type": "helmet"},
    {"id": "void_oracle", "display": "Void Oracle", "div": "apex_transhumans", "role": "Sniper", "weapon": "covenant_sniper_rifle", "head_type": "hooded"},
    {"id": "graviton_marshal", "display": "Graviton Marshal", "div": "apex_transhumans", "role": "Flak Trooper", "weapon": "covenant_flak_cannon", "head_type": "helmet"},
    {"id": "psi_reaper", "display": "Psi Reaper", "div": "apex_transhumans", "role": "Special Agent", "weapon": "covenant_submachine_gun", "head_type": "hooded"},

    # DIVISION 5: SECTION 9 SYNTH-CORP (Tactical Synthetic Androids & Droids)
    {"id": "synth_recon", "display": "Synth Recon", "div": "synth_corp", "role": "Spy / Saboteur", "weapon": "silicon_submachine_gun", "head_type": "droid"},
    {"id": "tactical_android", "display": "Tactical Android", "div": "synth_corp", "role": "Soldier", "weapon": "silicon_assault_rifle", "head_type": "droid"},
    {"id": "ballistic_cyborg", "display": "Ballistic Cyborg", "div": "synth_corp", "role": "Soldier", "weapon": "silicon_assault_rifle", "head_type": "cyborg_jaw"},
    {"id": "field_technomancer", "display": "Field Technomancer", "div": "synth_corp", "role": "Engineer", "weapon": "silicon_shotgun", "head_type": "droid"},
    {"id": "combat_medic_core", "display": "Combat Medic Core", "div": "synth_corp", "role": "Medic", "weapon": "silicon_submachine_gun", "head_type": "droid"},
    {"id": "heavy_flak_droid", "display": "Heavy Flak Droid", "div": "synth_corp", "role": "Flak Trooper", "weapon": "silicon_flak_cannon", "head_type": "droid"},
    {"id": "laser_sharpshooter", "display": "Laser Sharpshooter", "div": "synth_corp", "role": "Sniper", "weapon": "silicon_sniper_rifle", "head_type": "targeter"},
    {"id": "specops_automaton", "display": "SpecOps Automaton", "div": "synth_corp", "role": "Special Agent", "weapon": "silicon_submachine_gun", "head_type": "droid"},
    {"id": "hazard_incinerator", "display": "Hazard Incinerator", "div": "synth_corp", "role": "Flame Trooper", "weapon": "silicon_flamethrower", "head_type": "droid"},
    {"id": "assault_frame", "display": "Assault Frame", "div": "synth_corp", "role": "Rocket Trooper", "weapon": "silicon_rocket_launcher", "head_type": "droid"}
]


# ==============================================================================
# CHARACTER GENERATION ROUTINE
# ==============================================================================

def generate_pixel_anime_character(char: dict, godot_bin: str = None) -> Dict[str, Any]:
    char_id = char["id"]
    char_dir = PROJECT_ROOT / "sprites" / char_id
    char_dir.mkdir(parents=True, exist_ok=True)

    div = char["div"]
    p = DIVISION_PALETTES.get(div, DIVISION_PALETTES["ghost_protocol"])
    seed = abs(hash(char_id)) % 2147483647

    parts = {
        "head": ((64, 64), lambda d, w, h, s: draw_mature_anime_head(d, w, h, s, p, char, seed)),
        "torso": ((72, 64), lambda d, w, h, s: draw_mature_anime_torso(d, w, h, s, p, char, seed)),
        "pelvis": ((64, 48), lambda d, w, h, s: draw_mature_anime_pelvis(d, w, h, s, p, char, seed)),
        "arm_upper_L": ((44, 56), lambda d, w, h, s: draw_mature_anime_arm_upper(d, w, h, s, p, char, True)),
        "arm_lower_L": ((36, 52), lambda d, w, h, s: draw_mature_anime_arm_lower(d, w, h, s, p, char, True)),
        "hand_L": ((32, 32), lambda d, w, h, s: draw_mature_anime_hand(d, w, h, s, p, char, True)),
        "arm_upper_R": ((44, 56), lambda d, w, h, s: draw_mature_anime_arm_upper(d, w, h, s, p, char, False)),
        "arm_lower_R": ((36, 52), lambda d, w, h, s: draw_mature_anime_arm_lower(d, w, h, s, p, char, False)),
        "hand_R": ((32, 32), lambda d, w, h, s: draw_mature_anime_hand(d, w, h, s, p, char, False)),
        "leg_upper_L": ((40, 56), lambda d, w, h, s: draw_mature_anime_leg_upper(d, w, h, s, p, char, True)),
        "leg_lower_L": ((36, 56), lambda d, w, h, s: draw_mature_anime_leg_lower(d, w, h, s, p, char, True)),
        "foot_L": ((48, 32), lambda d, w, h, s: draw_mature_anime_foot(d, w, h, s, p, char, True)),
        "leg_upper_R": ((40, 56), lambda d, w, h, s: draw_mature_anime_leg_upper(d, w, h, s, p, char, False)),
        "leg_lower_R": ((36, 56), lambda d, w, h, s: draw_mature_anime_leg_lower(d, w, h, s, p, char, False)),
        "foot_R": ((48, 32), lambda d, w, h, s: draw_mature_anime_foot(d, w, h, s, p, char, False)),
    }

    limb_images = {}
    for name, (size, fn) in parts.items():
        img = render_pixel_anime_sprite(size, fn, num_colors=36)
        out_path = char_dir / f"{char_id}_{name}.png"
        img.save(out_path, "PNG")
        limb_images[name] = img

    # Master Exploded Sheet ({char_id}_exploded.png)
    sheet_w, sheet_h = 512, 512
    exploded = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
    grid = [
        ("head", (20, 20)), ("torso", (110, 20)), ("pelvis", (210, 20)),
        ("arm_upper_L", (20, 110)), ("arm_lower_L", (90, 110)), ("hand_L", (150, 110)),
        ("arm_upper_R", (210, 110)), ("arm_lower_R", (280, 110)), ("hand_R", (340, 110)),
        ("leg_upper_L", (20, 200)), ("leg_lower_L", (90, 200)), ("foot_L", (150, 210)),
        ("leg_upper_R", (210, 200)), ("leg_lower_R", (280, 200)), ("foot_R", (340, 210))
    ]
    for part_name, (gx, gy) in grid:
        if part_name in limb_images:
            exploded.alpha_composite(limb_images[part_name], (gx, gy))
    exploded.save(char_dir / f"{char_id}_exploded.png", "PNG")

    # Assembled Full Model Preview ({char_id}_full.png)
    create_character_assembled_preview(char_dir, prefix=char_id, rig_type="biped")

    # 4 Signature Special Moves
    specials = randomize_character_specials()
    char_anims = build_character_animations(specials)

    # Rig Godot 4 Scene (scenes/{char_id}_character.tscn)
    target_scene = f"res://scenes/{char_id}_character.tscn"
    if godot_bin:
        cmd = [
            godot_bin,
            "--headless",
            "--path", str(PROJECT_ROOT),
            "--script", "res://scripts/headless_rig_builder.gd",
            "--",
            "--character-name", char_id,
            "--assets-dir", f"res://sprites/{char_id}",
            "--target-scene", target_scene,
            "--rig-type", "biped"
        ]
        try:
            subprocess.run(cmd, cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=25)
        except Exception:
            pass

    # Save metadata.json
    div_names = {
        "ghost_protocol": "Ghost Protocol (Black-Ops)",
        "iron_valkyrie": "Iron Valkyrie (Heavy Armor)",
        "neon_outcasts": "Neon Outcasts (Wasteland)",
        "apex_transhumans": "Apex Transhumans (Psionic)",
        "synth_corp": "Section 9 Synth-Corp (Androids)"
    }
    meta = {
        "character_name": char_id,
        "display_name": char["display"],
        "faction_id": div,
        "faction_name": div_names.get(div, div.replace("_", " ").title()),
        "role": char["role"],
        "description": f"Cyberpunk post-apocalyptic pixel/anime warrior: {char['display']} specializing as {char['role']}.",
        "weapon_id": char["weapon"],
        "equipped_weapon": char["weapon"],
        "art_style": "pixel_anime",
        "specials": specials,
        "special_details": [
            {
                "slot": f"special_{idx+1:02d}",
                "key": sp_key,
                "name": SPECIAL_MOVES_CATALOG.get(sp_key, {}).get("name", sp_key),
                "desc": SPECIAL_MOVES_CATALOG.get(sp_key, {}).get("desc", ""),
                "category": SPECIAL_MOVES_CATALOG.get(sp_key, {}).get("category", "combat")
            }
            for idx, sp_key in enumerate(specials)
        ]
    }
    with open(char_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    return meta


def generate_all_50_pixel_anime_roster():
    from scripts.generate_faction_roster import find_godot
    godot_bin = find_godot()
    print("\n========================================================")
    print("Generating 50 Mature Pixel/Anime Cyberpunk RTS Characters")
    print(f"5 Elite Divisions x 10 Operatives | Godot Engine: {godot_bin}")
    print("========================================================\n")

    roster = []
    total = len(ROSTER_50_DEFINITIONS)
    for i, char in enumerate(ROSTER_50_DEFINITIONS):
        print(f"[{i+1:02d}/{total:02d}] Generating '{char['id']}' ({char['display']}) [{char['div']}]...")
        meta = generate_pixel_anime_character(char, godot_bin)
        roster.append(meta)

    # Save to index
    index_path = PROJECT_ROOT / "sprites" / "pixel_anime_roster.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(roster, f, indent=2)

    print(f"\n[OK] Successfully generated {len(roster)} mature pixel/anime cyberpunk characters!")
    print(f"Index saved to: {index_path}\n")
    return roster


if __name__ == "__main__":
    generate_all_50_pixel_anime_roster()
