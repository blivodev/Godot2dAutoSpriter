#!/usr/bin/env python3
"""
generate_cyberpunk_sprites.py - Procedural High-Detail Sprite Generator for Cyberpunk RTS Roster

Generates 100% distinct, tailored sprites for:
- 5 Cyberpunk Factions (Directorate, Syndicate, Covenant, Bio-Forge, Silicon Hive)
- 12 RTS Archetypes (Soldier, Sniper, Grenadier, Rocket, SpecAgent, Medic, Engineer,
  Saboteur, Flamethrower, MindController, DroneOp, Flak)

Every faction has unique silhouettes, materials, armor styles, and lighting.
Every role within each faction has unmistakable gear (visors, heavy blast suites, medical crosses,
gas masks, brain cores, sniper mono-optics, hazard markings, drone bays).
"""

import os
import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from typing import Dict, Any, Tuple, List

from scripts.generate_sample_sprites import (
    create_sprite,
    catmull_rom_spline,
    draw_curved_polygon,
    draw_curved_line,
    hex_to_rgba,
    create_character_assembled_preview
)

# ==============================================================================
# FACTION PALETTES & COLOR PROFILES
# ==============================================================================

FACTION_PALETTES = {
    "directorate": {
        "primary_dark": (26, 34, 46, 255),       # Deep Gunmetal Navy
        "primary_mid": (42, 56, 75, 255),        # Ballistic Slate
        "primary_light": (68, 88, 115, 255),     # Composite Armor Highlight
        "accent_dark": (18, 23, 31, 255),        # Under-suit Carbon Weave
        "accent_mid": (100, 125, 155, 255),      # Brushed Titanium Trim
        "accent_light": (155, 185, 215, 255),    # Chrome Edging
        "glow": (0, 225, 255, 255),              # Neon Cyan HUD
        "glow_core": (180, 248, 255, 255),       # Core Laser White-Cyan
        "outline": (10, 14, 20, 255),            # Clean Navy Outline
        "hazard": (255, 210, 0, 255)
    },
    "syndicate": {
        "primary_dark": (70, 36, 18, 255),       # Heavy Rust
        "primary_mid": (115, 58, 26, 255),       # Oxidized Iron
        "primary_light": (160, 85, 38, 255),     # Scrap Orange Highlight
        "accent_dark": (35, 22, 14, 255),        # Oily Greasy Leather
        "accent_mid": (105, 98, 92, 255),        # Scavenged Steel
        "accent_light": (150, 142, 134, 255),    # Welded Tin Highlight
        "glow": (255, 155, 0, 255),              # Dirty Amber / Sodium Lamp
        "glow_core": (255, 220, 100, 255),       # Sparking Yellow Core
        "outline": (16, 10, 6, 255),             # Grimy Soot Outline
        "hazard": (255, 195, 0, 255)             # Caution Yellow
    },
    "covenant": {
        "primary_dark": (30, 16, 48, 255),       # Deep Cosmic Void
        "primary_mid": (58, 28, 88, 255),        # Royal Amethyst
        "primary_light": (95, 48, 140, 255),     # Psychokinetic Purple
        "accent_dark": (14, 8, 24, 255),         # Abyssal Obsidian
        "accent_mid": (195, 152, 68, 255),       # Ceremonial Astral Gold
        "accent_light": (235, 205, 125, 255),    # Radiant Gold Filigree
        "glow": (225, 32, 255, 255),             # Psychokinetic Magenta
        "glow_core": (255, 160, 255, 255),       # Violet Transcendence Core
        "outline": (10, 5, 16, 255),             # Dark Void Outline
        "hazard": (240, 60, 255, 255)
    },
    "bioforge": {
        "primary_dark": (28, 44, 20, 255),       # Deep Chitin Olive
        "primary_mid": (48, 72, 32, 255),        # Bio-Carapace Moss
        "primary_light": (76, 110, 52, 255),     # Living Carapace Green
        "accent_dark": (16, 25, 12, 255),        # Dark Necrotic Chitin
        "accent_mid": (165, 152, 122, 255),      # Hardened Bone White
        "accent_light": (215, 204, 172, 255),    # Ivory Spine Tip
        "glow": (57, 255, 20, 255),              # Radioactive Bile Green
        "glow_core": (175, 255, 80, 255),        # Acid Glow Core
        "outline": (8, 14, 6, 255),              # Toxic Black Outline
        "hazard": (80, 255, 0, 255)
    },
    "silicon": {
        "primary_dark": (28, 32, 40, 255),       # Combat Tungsten
        "primary_mid": (48, 55, 68, 255),        # Cold Titanium Alloy
        "primary_light": (78, 88, 105, 255),     # Machine Plate Bevel
        "accent_dark": (15, 18, 22, 255),        # Internal Chassis Carbon
        "accent_mid": (130, 140, 155, 255),      # Industrial Hydraulic Steel
        "accent_light": (195, 205, 220, 255),    # Polished Chrome Glint
        "glow": (255, 15, 45, 255),              # Menacing Laser Crimson
        "glow_core": (255, 140, 160, 255),       # White-Red Optical Core
        "outline": (8, 10, 14, 255),             # Cold Machine Outline
        "hazard": (255, 140, 0, 255)             # Industrial Warning Orange
    }
}

# ==============================================================================
# PROCEDURAL DRAWING: HEADS (100% DISTINCT PER FACTION & ROLE)
# ==============================================================================

def draw_cyberpunk_head(draw, w, h, s, p: dict, faction: str, role: str, seed: int = 42):
    cx, cy = w // 2, h // 2
    rng = random.Random(seed)

    # 1. NEO-TERRA DIRECTORATE HEADS (High-Tech Corporate Military)
    if faction == "directorate":
        if role in ["sniper"]:
            # Sleek helmet with asymmetrical mono-eye targeting rangefinder lens
            draw_curved_polygon(draw, [
                (cx - 15*s, cy + 16*s), (cx - 18*s, cy + 2*s), (cx - 16*s, cy - 18*s),
                (cx, cy - 22*s), (cx + 16*s, cy - 18*s), (cx + 18*s, cy + 2*s), (cx + 15*s, cy + 16*s), (cx, cy + 20*s)
            ], fill=p["primary_mid"], outline=p["outline"], width=2*s)
            draw.rectangle([cx - 12*s, cy - 16*s, cx + 12*s, cy - 10*s], fill=p["primary_dark"])
            draw.ellipse([cx + 2*s, cy - 4*s, cx + 14*s, cy + 8*s], fill=p["primary_dark"], outline=p["glow"], width=2*s)
            draw.ellipse([cx + 5*s, cy - 1*s, cx + 11*s, cy + 5*s], fill=p["glow"])
            draw.ellipse([cx + 7*s, cy + 1*s, cx + 9*s, cy + 3*s], fill=p["glow_core"])
            draw.line([(cx - 12*s, cy + 2*s), (cx - 3*s, cy + 2*s)], fill=p["glow"], width=2*s)
            draw.line([(cx - 16*s, cy - 12*s), (cx - 22*s, cy - 26*s)], fill=p["accent_mid"], width=2*s)

        elif role in ["medic"]:
            # Clean medical helmet with diagnostic visor & illuminated medical cross
            draw_curved_polygon(draw, [
                (cx - 16*s, cy + 16*s), (cx - 19*s, cy), (cx - 17*s, cy - 18*s),
                (cx, cy - 22*s), (cx + 17*s, cy - 18*s), (cx + 19*s, cy), (cx + 16*s, cy + 16*s), (cx, cy + 20*s)
            ], fill=(230, 240, 245, 255), outline=p["outline"], width=2*s)
            draw.rectangle([cx - 2*s, cy - 18*s, cx + 2*s, cy - 10*s], fill=(0, 220, 240, 255))
            draw.rectangle([cx - 6*s, cy - 15*s, cx + 6*s, cy - 13*s], fill=(0, 220, 240, 255))
            draw.polygon([(cx - 14*s, cy - 2*s), (cx + 14*s, cy - 2*s), (cx + 11*s, cy + 6*s), (cx - 11*s, cy + 6*s)], fill=p["glow"])
            draw.line([(cx - 9*s, cy + 2*s), (cx + 9*s, cy + 2*s)], fill=p["glow_core"], width=s)

        elif role in ["flamethrower"]:
            # Dual-canister airtight gas mask with heavy heat-shield collar
            draw_curved_polygon(draw, [
                (cx - 18*s, cy + 16*s), (cx - 20*s, cy), (cx - 17*s, cy - 18*s),
                (cx, cy - 22*s), (cx + 17*s, cy - 18*s), (cx + 20*s, cy), (cx + 18*s, cy + 16*s), (cx, cy + 22*s)
            ], fill=p["primary_dark"], outline=p["outline"], width=2*s)
            draw.rectangle([cx - 14*s, cy - 5*s, cx - 2*s, cy + 3*s], fill=(255, 140, 0, 255), outline=p["outline"], width=s)
            draw.rectangle([cx + 2*s, cy - 5*s, cx + 14*s, cy + 3*s], fill=(255, 140, 0, 255), outline=p["outline"], width=s)
            draw.ellipse([cx - 18*s, cy + 6*s, cx - 6*s, cy + 18*s], fill=p["accent_mid"], outline=p["outline"], width=2*s)
            draw.ellipse([cx + 6*s, cy + 6*s, cx + 18*s, cy + 18*s], fill=p["accent_mid"], outline=p["outline"], width=2*s)
            draw.line([(cx - 15*s, cy + 12*s), (cx - 9*s, cy + 12*s)], fill=p["primary_dark"], width=s)
            draw.line([(cx + 9*s, cy + 12*s), (cx + 15*s, cy + 12*s)], fill=p["primary_dark"], width=s)

        elif role in ["mindcontroller"]:
            # Open cranial neuro-amplifier crown with pulsing cyan synapse nodes
            draw_curved_polygon(draw, [
                (cx - 14*s, cy + 16*s), (cx - 16*s, cy + 2*s), (cx - 14*s, cy - 12*s),
                (cx, cy - 16*s), (cx + 14*s, cy - 12*s), (cx + 16*s, cy + 2*s), (cx + 14*s, cy + 16*s), (cx, cy + 20*s)
            ], fill=(210, 195, 185, 255), outline=p["outline"], width=2*s)
            draw.ellipse([cx - 10*s, cy - 2*s, cx - 3*s, cy + 4*s], fill=p["glow"])
            draw.ellipse([cx + 3*s, cy - 2*s, cx + 10*s, cy + 4*s], fill=p["glow"])
            circlet = [(cx - 18*s, cy - 6*s), (cx, cy - 18*s), (cx + 18*s, cy - 6*s)]
            draw_curved_line(draw, circlet, fill=p["accent_light"], width=3*s)
            for nx in [-14, 0, 14]:
                draw.ellipse([cx + (nx-3)*s, cy - 22*s, cx + (nx+3)*s, cy - 16*s], fill=p["glow"], outline=p["outline"], width=s)
                draw.ellipse([cx + (nx-1)*s, cy - 20*s, cx + (nx+1)*s, cy - 18*s], fill=p["glow_core"])
                draw.line([(cx + nx*s, cy - 16*s), (cx + nx*s, cy - 10*s)], fill=p["glow"], width=s)

        elif role in ["drone_op"]:
            # High-tech officer cap / headset with folding HUD monocle and comm-radar
            draw_curved_polygon(draw, [
                (cx - 15*s, cy + 16*s), (cx - 17*s, cy + 2*s), (cx - 15*s, cy - 14*s),
                (cx, cy - 18*s), (cx + 15*s, cy - 14*s), (cx + 17*s, cy + 2*s), (cx + 15*s, cy + 16*s), (cx, cy + 20*s)
            ], fill=p["primary_mid"], outline=p["outline"], width=2*s)
            draw.polygon([(cx - 18*s, cy - 10*s), (cx + 18*s, cy - 10*s), (cx + 14*s, cy - 3*s), (cx - 14*s, cy - 3*s)], fill=p["primary_dark"])
            draw.rectangle([cx - 12*s, cy - 1*s, cx - 2*s, cy + 7*s], fill=(0, 240, 255, 160), outline=p["glow"], width=s)
            draw.line([(cx + 16*s, cy - 6*s), (cx + 24*s, cy - 22*s)], fill=p["accent_mid"], width=2*s)
            draw.ellipse([cx + 20*s, cy - 26*s, cx + 28*s, cy - 18*s], fill=p["glow"], outline=p["outline"], width=s)

        elif role in ["rocket", "flak"]:
            # Heavy juggernaut blast helmet with armored visor slit and brow
            draw_curved_polygon(draw, [
                (cx - 18*s, cy + 18*s), (cx - 21*s, cy + 2*s), (cx - 18*s, cy - 20*s),
                (cx, cy - 24*s), (cx + 18*s, cy - 20*s), (cx + 21*s, cy + 2*s), (cx + 18*s, cy + 18*s), (cx, cy + 22*s)
            ], fill=p["primary_dark"], outline=p["outline"], width=2*s)
            draw.rectangle([cx - 19*s, cy - 12*s, cx + 19*s, cy - 4*s], fill=p["primary_mid"], outline=p["outline"], width=s)
            draw.rectangle([cx - 14*s, cy - 2*s, cx + 14*s, cy + 3*s], fill=p["glow"])
            draw.line([(cx - 10*s, cy), (cx + 10*s, cy)], fill=p["glow_core"], width=s)

        elif role in ["specagent", "saboteur"]:
            # Sleek ninja balaclava with Quad-NVG
            draw_curved_polygon(draw, [
                (cx - 14*s, cy + 16*s), (cx - 16*s, cy + 2*s), (cx - 14*s, cy - 16*s),
                (cx, cy - 20*s), (cx + 14*s, cy - 16*s), (cx + 16*s, cy + 2*s), (cx + 14*s, cy + 16*s), (cx, cy + 20*s)
            ], fill=p["accent_dark"], outline=p["outline"], width=2*s)
            draw.rectangle([cx - 16*s, cy - 6*s, cx + 16*s, cy + 2*s], fill=p["primary_dark"], outline=p["outline"], width=s)
            for gx in [-11, -4, 4, 11]:
                draw.ellipse([cx + (gx-2)*s, cy - 4*s, cx + (gx+2)*s, cy], fill=p["glow"], outline=p["outline"], width=s)

        else:
            # Standard Directorate Enforcer Full Tactical Helmet with Cyan Visor
            draw_curved_polygon(draw, [
                (cx - 16*s, cy + 16*s), (cx - 19*s, cy + 2*s), (cx - 17*s, cy - 18*s),
                (cx, cy - 22*s), (cx + 17*s, cy - 18*s), (cx + 19*s, cy + 2*s), (cx + 16*s, cy + 16*s), (cx, cy + 20*s)
            ], fill=p["primary_mid"], outline=p["outline"], width=2*s)
            draw.polygon([(cx - 14*s, cy - 16*s), (cx + 14*s, cy - 16*s), (cx + 11*s, cy - 6*s), (cx - 11*s, cy - 6*s)], fill=p["primary_dark"])
            draw.polygon([(cx - 15*s, cy - 3*s), (cx + 15*s, cy - 3*s), (cx + 12*s, cy + 5*s), (cx - 12*s, cy + 5*s)], fill=p["glow"])
            draw.line([(cx - 10*s, cy + 1*s), (cx + 10*s, cy + 1*s)], fill=p["glow_core"], width=s)
            draw.line([(cx + 17*s, cy - 8*s), (cx + 22*s, cy - 22*s)], fill=p["accent_mid"], width=2*s)

    # 2. RUST SYNDICATE HEADS (Scrap Raiders & Wasteland Outlaws)
    elif faction == "syndicate":
        if role in ["sniper"]:
            draw_curved_polygon(draw, [
                (cx - 15*s, cy + 16*s), (cx - 17*s, cy), (cx - 15*s, cy - 16*s),
                (cx, cy - 20*s), (cx + 15*s, cy - 16*s), (cx + 17*s, cy), (cx + 15*s, cy + 16*s), (cx, cy + 20*s)
            ], fill=p["accent_dark"], outline=p["outline"], width=2*s)
            draw.polygon([(cx - 12*s, cy + 4*s), (cx + 12*s, cy + 4*s), (cx + 8*s, cy + 18*s), (cx - 8*s, cy + 18*s)], fill=(210, 200, 185, 255), outline=p["outline"])
            draw.polygon([(cx - 3*s, cy + 10*s), (cx + 3*s, cy + 10*s), (cx, cy + 14*s)], fill=p["outline"])
            draw.ellipse([cx - 16*s, cy - 8*s, cx - 2*s, cy + 6*s], fill=(185, 140, 50, 255), outline=p["outline"], width=2*s)
            draw.ellipse([cx - 13*s, cy - 5*s, cx - 5*s, cy + 3*s], fill=p["glow"])
            draw_curved_line(draw, [(cx - 17*s, cy - 10*s), (cx, cy - 22*s), (cx + 17*s, cy - 10*s)], fill=p["primary_dark"], width=3*s)

        elif role in ["specagent"]:
            draw_curved_polygon(draw, [
                (cx - 14*s, cy + 16*s), (cx - 16*s, cy + 2*s), (cx - 14*s, cy - 14*s),
                (cx, cy - 18*s), (cx + 14*s, cy - 14*s), (cx + 16*s, cy + 2*s), (cx + 14*s, cy + 16*s), (cx, cy + 20*s)
            ], fill=(200, 160, 130, 255), outline=p["outline"], width=2*s)
            draw.polygon([(cx - 13*s, cy + 6*s), (cx + 13*s, cy + 6*s), (cx + 9*s, cy + 20*s), (cx - 9*s, cy + 20*s)], fill=p["accent_mid"], outline=p["outline"], width=s)
            draw.ellipse([cx + 3*s, cy - 2*s, cx + 9*s, cy + 4*s], fill=p["glow"], outline=p["outline"], width=s)
            mohawk_pts = [(cx - 4*s, cy - 16*s), (cx - 8*s, cy - 28*s), (cx - 2*s, cy - 36*s), (cx + 4*s, cy - 28*s), (cx + 2*s, cy - 16*s)]
            draw_curved_polygon(draw, mohawk_pts, fill=(255, 80, 0, 255), outline=p["outline"], width=2*s)

        elif role in ["medic"]:
            draw_curved_polygon(draw, [
                (cx - 15*s, cy + 14*s), (cx - 17*s, cy), (cx - 15*s, cy - 16*s),
                (cx, cy - 20*s), (cx + 15*s, cy - 16*s), (cx + 17*s, cy), (cx + 15*s, cy + 14*s), (cx, cy + 18*s)
            ], fill=p["accent_dark"], outline=p["outline"], width=2*s)
            draw.ellipse([cx - 14*s, cy - 6*s, cx - 2*s, cy + 4*s], fill=(210, 160, 60, 255), outline=p["outline"], width=2*s)
            draw.ellipse([cx + 2*s, cy - 6*s, cx + 14*s, cy + 4*s], fill=(210, 160, 60, 255), outline=p["outline"], width=2*s)
            draw.ellipse([cx - 11*s, cy - 3*s, cx - 5*s, cy + 1*s], fill=p["glow"])
            draw.ellipse([cx + 5*s, cy - 3*s, cx + 11*s, cy + 1*s], fill=p["glow"])
            snout = [(cx - 6*s, cy + 4*s), (cx + 6*s, cy + 4*s), (cx, cy + 24*s)]
            draw.polygon(snout, fill=p["primary_dark"], outline=p["outline"], width=2*s)

        elif role in ["mindcontroller"]:
            draw_curved_polygon(draw, [
                (cx - 14*s, cy + 16*s), (cx - 16*s, cy + 2*s), (cx - 14*s, cy - 14*s),
                (cx, cy - 18*s), (cx + 14*s, cy - 14*s), (cx + 16*s, cy + 2*s), (cx + 14*s, cy + 16*s), (cx, cy + 20*s)
            ], fill=(195, 170, 145, 255), outline=p["outline"], width=2*s)
            draw.polygon([(cx - 12*s, cy - 16*s), (cx + 12*s, cy - 16*s), (cx + 8*s, cy - 6*s), (cx - 8*s, cy - 6*s)], fill=p["accent_mid"], outline=p["outline"], width=s)
            draw.ellipse([cx - 16*s, cy - 8*s, cx - 10*s, cy - 2*s], fill=p["glow"], outline=p["outline"], width=s)
            draw.ellipse([cx + 10*s, cy - 8*s, cx + 16*s, cy - 2*s], fill=p["glow"], outline=p["outline"], width=s)
            draw.ellipse([cx - 9*s, cy + 2*s, cx - 3*s, cy + 8*s], fill=p["glow_core"])
            draw.ellipse([cx + 3*s, cy + 2*s, cx + 9*s, cy + 8*s], fill=p["glow_core"])

        elif role in ["engineer"]:
            draw_curved_polygon(draw, [
                (cx - 15*s, cy + 16*s), (cx - 17*s, cy + 2*s), (cx - 15*s, cy - 14*s),
                (cx, cy - 18*s), (cx + 15*s, cy - 14*s), (cx + 17*s, cy + 2*s), (cx + 15*s, cy + 16*s), (cx, cy + 20*s)
            ], fill=(190, 160, 135, 255), outline=p["outline"], width=2*s)
            draw.rectangle([cx - 16*s, cy - 8*s, cx - 2*s, cy + 2*s], fill=(60, 60, 60, 255), outline=p["outline"], width=2*s)
            draw.rectangle([cx + 2*s, cy - 8*s, cx + 16*s, cy + 2*s], fill=(60, 60, 60, 255), outline=p["outline"], width=2*s)
            draw.rectangle([cx - 13*s, cy - 6*s, cx - 5*s, cy], fill=p["glow"])
            draw.rectangle([cx + 5*s, cy - 6*s, cx + 13*s, cy], fill=p["glow"])
            draw.line([(cx - 8*s, cy + 8*s), (cx - 2*s, cy + 11*s)], fill=(30, 25, 20, 200), width=2*s)

        elif role in ["rocket", "flak"]:
            draw_curved_polygon(draw, [
                (cx - 17*s, cy + 18*s), (cx - 19*s, cy), (cx - 17*s, cy - 18*s),
                (cx, cy - 22*s), (cx + 17*s, cy - 18*s), (cx + 19*s, cy), (cx + 17*s, cy + 18*s), (cx, cy + 20*s)
            ], fill=p["primary_mid"], outline=p["outline"], width=2*s)
            draw.rectangle([cx - 18*s, cy - 14*s, cx + 18*s, cy - 8*s], fill=p["primary_dark"], outline=p["outline"], width=s)
            draw.rectangle([cx - 14*s, cy - 4*s, cx + 14*s, cy + 4*s], fill=p["outline"])
            for bx in [-10, -5, 0, 5, 10]:
                draw.line([(cx + bx*s, cy - 4*s), (cx + bx*s, cy + 4*s)], fill=p["accent_mid"], width=s)
            draw.ellipse([cx - 8*s, cy - 2*s, cx - 4*s, cy + 2*s], fill=p["glow"])
            draw.ellipse([cx + 4*s, cy - 2*s, cx + 8*s, cy + 2*s], fill=p["glow"])

        else:
            # Welded Rust Raider Plate Mask
            draw_curved_polygon(draw, [
                (cx - 16*s, cy + 16*s), (cx - 18*s, cy), (cx - 16*s, cy - 18*s),
                (cx, cy - 22*s), (cx + 16*s, cy - 18*s), (cx + 18*s, cy), (cx + 16*s, cy + 16*s), (cx, cy + 20*s)
            ], fill=p["primary_mid"], outline=p["outline"], width=2*s)
            draw.polygon([(cx - 14*s, cy + 4*s), (cx + 14*s, cy + 4*s), (cx + 10*s, cy + 18*s), (cx - 10*s, cy + 18*s)], fill=p["primary_dark"], outline=p["outline"], width=s)
            draw.polygon([(cx - 13*s, cy - 4*s), (cx - 3*s, cy - 2*s), (cx - 4*s, cy + 2*s), (cx - 12*s, cy)], fill=p["glow"])
            draw.polygon([(cx + 3*s, cy - 2*s), (cx + 13*s, cy - 4*s), (cx + 12*s, cy), (cx + 4*s, cy + 2*s)], fill=p["glow"])
            draw.polygon([(cx - 3*s, cy - 22*s), (cx + 3*s, cy - 22*s), (cx, cy - 32*s)], fill=p["accent_mid"], outline=p["outline"], width=s)

    # 3. NEURO-COVENANT HEADS (Psionic Void Cult)
    elif faction == "covenant":
        if role in ["mindcontroller"]:
            draw_curved_polygon(draw, [
                (cx - 14*s, cy + 16*s), (cx - 16*s, cy + 2*s), (cx - 14*s, cy - 14*s),
                (cx, cy - 18*s), (cx + 14*s, cy - 14*s), (cx + 16*s, cy + 2*s), (cx + 14*s, cy + 16*s), (cx, cy + 20*s)
            ], fill=p["accent_dark"], outline=p["outline"], width=2*s)
            draw.polygon([(cx, cy - 16*s), (cx + 6*s, cy - 10*s), (cx, cy - 4*s), (cx - 6*s, cy - 10*s)], fill=p["glow"], outline=p["accent_mid"], width=s)
            draw.ellipse([cx - 2*s, cy - 12*s, cx + 2*s, cy - 8*s], fill=p["glow_core"])
            draw.arc([cx - 22*s, cy - 34*s, cx + 22*s, cy - 14*s], 0, 360, fill=p["glow"], width=3*s)
            draw.ellipse([cx - 4*s, cy - 36*s, cx + 4*s, cy - 28*s], fill=p["glow_core"])
            draw.rectangle([cx - 14*s, cy - 1*s, cx + 14*s, cy + 5*s], fill=p["primary_mid"], outline=p["outline"], width=s)
            draw.line([(cx - 10*s, cy + 2*s), (cx + 10*s, cy + 2*s)], fill=p["accent_mid"], width=s)

        elif role in ["medic"]:
            draw_curved_polygon(draw, [
                (cx - 16*s, cy + 16*s), (cx - 19*s, cy), (cx - 16*s, cy - 18*s),
                (cx, cy - 24*s), (cx + 16*s, cy - 18*s), (cx + 19*s, cy), (cx + 16*s, cy + 16*s), (cx, cy + 20*s)
            ], fill=(235, 230, 245, 255), outline=p["outline"], width=2*s)
            draw.arc([cx - 18*s, cy - 28*s, cx + 18*s, cy - 8*s], 180, 360, fill=p["glow"], width=2*s)
            draw.ellipse([cx - 8*s, cy - 2*s, cx - 2*s, cy + 4*s], fill=p["glow"])
            draw.ellipse([cx + 2*s, cy - 2*s, cx + 8*s, cy + 4*s], fill=p["glow"])

        elif role in ["sniper", "saboteur"]:
            draw_curved_polygon(draw, [
                (cx - 18*s, cy + 16*s), (cx - 22*s, cy), (cx - 18*s, cy - 20*s),
                (cx, cy - 26*s), (cx + 18*s, cy - 20*s), (cx + 22*s, cy), (cx + 18*s, cy + 16*s), (cx, cy + 22*s)
            ], fill=p["primary_dark"], outline=p["outline"], width=2*s)
            draw.ellipse([cx - 13*s, cy - 8*s, cx + 13*s, cy + 14*s], fill=(5, 2, 8, 255))
            draw.ellipse([cx - 7*s, cy, cx - 3*s, cy + 4*s], fill=p["glow"])
            draw.ellipse([cx + 3*s, cy, cx + 7*s, cy + 4*s], fill=p["glow"])
            draw.ellipse([cx - 2*s, cy - 5*s, cx + 2*s, cy - 1*s], fill=p["glow_core"])

        else:
            # Polished chrome mask with vertical psychic slit
            draw_curved_polygon(draw, [
                (cx - 15*s, cy + 16*s), (cx - 18*s, cy), (cx - 15*s, cy - 18*s),
                (cx, cy - 22*s), (cx + 15*s, cy - 18*s), (cx + 18*s, cy), (cx + 15*s, cy + 16*s), (cx, cy + 20*s)
            ], fill=p["primary_mid"], outline=p["outline"], width=2*s)
            draw_curved_line(draw, [(cx - 16*s, cy - 12*s), (cx, cy - 20*s), (cx + 16*s, cy - 12*s)], fill=p["accent_mid"], width=2*s)
            draw.polygon([(cx - 2*s, cy - 12*s), (cx + 2*s, cy - 12*s), (cx + 4*s, cy + 6*s), (cx - 4*s, cy + 6*s)], fill=p["glow"])
            draw.line([(cx, cy - 10*s), (cx, cy + 4*s)], fill=p["glow_core"], width=s)

    # 4. BIO-FORGE LEGION HEADS (Mutant Chem-Warriors & Chitinous Horrors)
    elif faction == "bioforge":
        if role in ["mindcontroller"]:
            draw_curved_polygon(draw, [
                (cx - 14*s, cy + 6*s), (cx - 10*s, cy + 18*s), (cx, cy + 22*s), (cx + 10*s, cy + 18*s), (cx + 14*s, cy + 6*s)
            ], fill=p["primary_dark"], outline=p["outline"], width=2*s)
            for fx in [-6, 0, 6]:
                draw.polygon([(cx + (fx-1)*s, cy + 12*s), (cx + (fx+1)*s, cy + 12*s), (cx + fx*s, cy + 18*s)], fill=p["accent_light"])
            draw.ellipse([cx - 20*s, cy - 26*s, cx + 20*s, cy + 6*s], fill=(70, 110, 50, 255), outline=p["outline"], width=2*s)
            draw.ellipse([cx - 16*s, cy - 24*s, cx - 2*s, cy - 4*s], fill=p["glow"])
            draw.ellipse([cx + 2*s, cy - 24*s, cx + 16*s, cy - 4*s], fill=p["glow"])
            draw.line([(cx - 10*s, cy - 18*s), (cx + 10*s, cy - 12*s)], fill=p["glow_core"], width=2*s)

        elif role in ["flamethrower"]:
            draw_curved_polygon(draw, [
                (cx - 16*s, cy + 8*s), (cx - 20*s, cy + 18*s), (cx, cy + 24*s), (cx + 20*s, cy + 18*s), (cx + 16*s, cy + 8*s),
                (cx + 16*s, cy - 16*s), (cx, cy - 20*s), (cx - 16*s, cy - 16*s)
            ], fill=p["primary_mid"], outline=p["outline"], width=2*s)
            draw.ellipse([cx - 16*s, cy + 8*s, cx - 2*s, cy + 20*s], fill=p["glow"], outline=p["outline"], width=s)
            draw.ellipse([cx + 2*s, cy + 8*s, cx + 16*s, cy + 20*s], fill=p["glow"], outline=p["outline"], width=s)
            draw.polygon([(cx - 13*s, cy - 4*s), (cx - 4*s, cy - 2*s), (cx - 6*s, cy + 2*s), (cx - 12*s, cy)], fill=p["glow_core"])
            draw.polygon([(cx + 4*s, cy - 2*s), (cx + 13*s, cy - 4*s), (cx + 12*s, cy), (cx + 6*s, cy + 2*s)], fill=p["glow_core"])

        elif role in ["sniper"]:
            draw_curved_polygon(draw, [
                (cx - 14*s, cy + 16*s), (cx - 18*s, cy + 2*s), (cx - 16*s, cy - 14*s),
                (cx, cy - 32*s),
                (cx + 16*s, cy - 14*s), (cx + 18*s, cy + 2*s), (cx + 14*s, cy + 16*s), (cx, cy + 22*s)
            ], fill=p["primary_mid"], outline=p["outline"], width=2*s)
            draw.line([(cx, cy - 30*s), (cx, cy - 4*s)], fill=p["accent_light"], width=2*s)
            draw.ellipse([cx - 12*s, cy - 2*s, cx - 4*s, cy + 4*s], fill=p["glow"])
            draw.ellipse([cx + 4*s, cy - 2*s, cx + 12*s, cy + 4*s], fill=p["glow"])

        else:
            # Segmented insectoid chitin helmet with mandibles & compound eyes
            draw_curved_polygon(draw, [
                (cx - 16*s, cy + 12*s), (cx - 19*s, cy), (cx - 16*s, cy - 18*s),
                (cx, cy - 24*s), (cx + 16*s, cy - 18*s), (cx + 19*s, cy), (cx + 16*s, cy + 12*s), (cx, cy + 18*s)
            ], fill=p["primary_mid"], outline=p["outline"], width=2*s)
            draw.polygon([(cx - 14*s, cy + 10*s), (cx - 18*s, cy + 22*s), (cx - 8*s, cy + 16*s)], fill=p["accent_mid"], outline=p["outline"], width=s)
            draw.polygon([(cx + 14*s, cy + 10*s), (cx + 18*s, cy + 22*s), (cx + 8*s, cy + 16*s)], fill=p["accent_mid"], outline=p["outline"], width=s)
            for ex in [-12, -5, 5, 12]:
                draw.ellipse([cx + (ex-2)*s, cy - 2*s, cx + (ex+2)*s, cy + 3*s], fill=p["glow"], outline=p["outline"], width=s)
                draw.ellipse([cx + ex*s, cy, cx + ex*s, cy + 1*s], fill=p["glow_core"])

    # 5. SILICON HIVE HEADS (Autonomous Machine Empire / Glitch AI Droids)
    elif faction == "silicon":
        if role in ["sniper"]:
            draw_curved_polygon(draw, [
                (cx - 16*s, cy + 16*s), (cx - 18*s, cy), (cx - 16*s, cy - 18*s),
                (cx, cy - 20*s), (cx + 16*s, cy - 18*s), (cx + 18*s, cy), (cx + 16*s, cy + 16*s), (cx, cy + 18*s)
            ], fill=p["primary_mid"], outline=p["outline"], width=2*s)
            draw.ellipse([cx - 15*s, cy - 8*s, cx - 1*s, cy + 6*s], fill=p["primary_dark"], outline=p["outline"], width=2*s)
            draw.ellipse([cx - 12*s, cy - 5*s, cx - 4*s, cy + 3*s], fill=p["glow"])
            draw.ellipse([cx - 9*s, cy - 2*s, cx - 7*s, cy], fill=p["glow_core"])
            for ty in [-8, 0, 8]:
                draw.ellipse([cx + 4*s, cy + (ty-2)*s, cx + 10*s, cy + (ty+4)*s], fill=p["glow"], outline=p["outline"], width=s)

        elif role in ["specagent"]:
            draw.polygon([
                (cx, cy - 24*s), (cx + 16*s, cy - 8*s), (cx + 14*s, cy + 16*s), (cx, cy + 22*s), (cx - 14*s, cy + 16*s), (cx - 16*s, cy - 8*s)
            ], fill=p["accent_dark"], outline=p["outline"], width=2*s)
            draw.line([(cx - 12*s, cy + 2*s), (cx + 12*s, cy + 2*s)], fill=p["glow"], width=2*s)
            draw.line([(cx - 6*s, cy + 2*s), (cx + 6*s, cy + 2*s)], fill=p["glow_core"], width=s)

        elif role in ["mindcontroller"]:
            draw_curved_polygon(draw, [
                (cx - 16*s, cy + 16*s), (cx - 18*s, cy + 2*s), (cx - 16*s, cy - 14*s),
                (cx, cy - 18*s), (cx + 16*s, cy - 14*s), (cx + 18*s, cy + 2*s), (cx + 16*s, cy + 16*s), (cx, cy + 20*s)
            ], fill=p["primary_dark"], outline=p["outline"], width=2*s)
            draw.rectangle([cx - 10*s, cy - 10*s, cx + 10*s, cy + 4*s], fill=p["glow"], outline=p["accent_mid"], width=2*s)
            draw.rectangle([cx - 6*s, cy - 7*s, cx + 6*s, cy + 1*s], fill=p["glow_core"])
            draw.arc([cx - 20*s, cy - 28*s, cx + 20*s, cy - 8*s], 0, 360, fill=p["glow"], width=2*s)

        elif role in ["flamethrower"]:
            draw.rectangle([cx - 16*s, cy - 18*s, cx + 16*s, cy + 16*s], fill=p["primary_dark"], outline=p["outline"], width=2*s)
            for fy in range(-14, 0, 5):
                draw.line([(cx - 14*s, cy + fy*s), (cx + 14*s, cy + fy*s)], fill=p["primary_light"], width=2*s)
            draw.rectangle([cx - 12*s, cy + 4*s, cx - 2*s, cy + 10*s], fill=p["glow"])
            draw.rectangle([cx + 2*s, cy + 4*s, cx + 12*s, cy + 10*s], fill=p["glow"])

        else:
            # Autonomous Battle Droid Head (Cylon/Terminator)
            draw_curved_polygon(draw, [
                (cx - 16*s, cy + 16*s), (cx - 19*s, cy + 2*s), (cx - 16*s, cy - 18*s),
                (cx, cy - 22*s), (cx + 16*s, cy - 18*s), (cx + 19*s, cy + 2*s), (cx + 16*s, cy + 16*s), (cx, cy + 20*s)
            ], fill=p["primary_mid"], outline=p["outline"], width=2*s)
            draw.polygon([(cx - 14*s, cy - 16*s), (cx + 14*s, cy - 16*s), (cx + 11*s, cy - 6*s), (cx - 11*s, cy - 6*s)], fill=p["primary_dark"])
            draw.rectangle([cx - 15*s, cy - 3*s, cx + 15*s, cy + 5*s], fill=p["accent_dark"], outline=p["outline"], width=s)
            draw.line([(cx - 12*s, cy + 1*s), (cx + 12*s, cy + 1*s)], fill=p["glow"], width=3*s)
            draw.ellipse([cx - 2*s, cy, cx + 2*s, cy + 2*s], fill=p["glow_core"])


# ==============================================================================
# PROCEDURAL DRAWING: TORSOS (100% DISTINCT PER FACTION & ROLE)
# ==============================================================================

def draw_cyberpunk_torso(draw, w, h, s, p: dict, faction: str, role: str, seed: int = 42):
    cx, cy = w // 2, h // 2

    # 1. NEO-TERRA DIRECTORATE (Composite Angular Body Armor)
    if faction == "directorate":
        draw_curved_polygon(draw, [
            (cx - 24*s, cy - 22*s), (cx + 24*s, cy - 22*s), (cx + 20*s, cy + 6*s),
            (cx + 14*s, cy + 24*s), (cx, cy + 28*s), (cx - 14*s, cy + 24*s), (cx - 20*s, cy + 6*s)
        ], fill=p["primary_mid"], outline=p["outline"], width=2*s)
        draw.rectangle([cx - 12*s, cy - 24*s, cx + 12*s, cy - 18*s], fill=p["primary_dark"], outline=p["outline"], width=s)

        if role in ["medic"]:
            draw.rectangle([cx - 16*s, cy - 16*s, cx + 16*s, cy + 8*s], fill=(235, 245, 250, 255), outline=p["outline"], width=s)
            draw.rectangle([cx - 3*s, cy - 12*s, cx + 3*s, cy + 4*s], fill=p["glow"])
            draw.rectangle([cx - 8*s, cy - 6*s, cx + 8*s, cy - 2*s], fill=p["glow"])
            draw.ellipse([cx - 2*s, cy - 5*s, cx + 2*s, cy - 3*s], fill=p["glow_core"])
        elif role in ["grenadier"]:
            draw.line([(cx - 20*s, cy - 18*s), (cx + 16*s, cy + 18*s)], fill=p["accent_dark"], width=6*s)
            for by in [-10, 0, 10]:
                draw.rectangle([cx + (by-3)*s, cy + by*s, cx + (by+3)*s, cy + (by+4)*s], fill=p["glow"], outline=p["outline"], width=s)
        elif role in ["rocket", "flak"]:
            draw.rectangle([cx - 18*s, cy - 14*s, cx + 18*s, cy + 12*s], fill=p["primary_dark"], outline=p["outline"], width=2*s)
            for hx in range(-12, 14, 8):
                draw.line([(cx + hx*s, cy - 10*s), (cx + (hx+4)*s, cy - 2*s)], fill=p["hazard"], width=2*s)
        elif role in ["flamethrower"]:
            draw.rectangle([cx - 18*s, cy - 12*s, cx + 18*s, cy + 12*s], fill=p["primary_dark"], outline=p["outline"], width=2*s)
            draw.line([(cx - 16*s, cy + 6*s), (cx + 16*s, cy + 6*s)], fill=(255, 140, 0, 255), width=3*s)
        else:
            draw.polygon([(cx - 16*s, cy - 14*s), (cx + 16*s, cy - 14*s), (cx + 12*s, cy), (cx - 12*s, cy)], fill=p["primary_dark"])
            draw.ellipse([cx - 6*s, cy - 10*s, cx + 6*s, cy + 2*s], fill=p["primary_dark"], outline=p["glow"], width=2*s)
            draw.ellipse([cx - 3*s, cy - 7*s, cx + 3*s, cy - 1*s], fill=p["glow"])
            draw.ellipse([cx - 1*s, cy - 5*s, cx + 1*s, cy - 3*s], fill=p["glow_core"])

    # 2. RUST SYNDICATE (Bolted Scrap Metal, Leather Jackets & Chains)
    elif faction == "syndicate":
        draw_curved_polygon(draw, [
            (cx - 24*s, cy - 22*s), (cx + 24*s, cy - 22*s), (cx + 21*s, cy + 6*s),
            (cx + 14*s, cy + 24*s), (cx, cy + 28*s), (cx - 14*s, cy + 24*s), (cx - 21*s, cy + 6*s)
        ], fill=p["accent_dark"], outline=p["outline"], width=2*s)
        draw.polygon([(cx - 18*s, cy - 16*s), (cx + 18*s, cy - 16*s), (cx + 14*s, cy + 14*s), (cx - 14*s, cy + 14*s)], fill=p["primary_mid"], outline=p["outline"], width=2*s)
        for bx, by in [(-14, -12), (14, -12), (-10, 10), (10, 10), (0, -2)]:
            draw.ellipse([cx + (bx-1)*s, cy + (by-1)*s, cx + (bx+1)*s, cy + (by+1)*s], fill=p["accent_light"])

        if role in ["medic"]:
            draw.rectangle([cx - 12*s, cy - 10*s, cx + 12*s, cy + 22*s], fill=(210, 190, 170, 255), outline=p["outline"], width=s)
            draw.line([(cx - 6*s, cy), (cx + 6*s, cy)], fill=(160, 30, 30, 255), width=2*s)
            draw.line([(cx, cy - 6*s), (cx, cy + 6*s)], fill=(160, 30, 30, 255), width=2*s)
        elif role in ["grenadier"]:
            for dy in [-8, 2, 12]:
                draw.rectangle([cx - 14*s, cy + dy*s, cx + 14*s, cy + (dy+4)*s], fill=(180, 40, 20, 255), outline=p["outline"], width=s)
        elif role in ["engineer"]:
            for hx in range(-12, 14, 8):
                draw.line([(cx + hx*s, cy - 8*s), (cx + (hx+4)*s, cy + 4*s)], fill=p["hazard"], width=3*s)
        elif role in ["flamethrower"]:
            draw.rectangle([cx - 16*s, cy - 10*s, cx + 16*s, cy + 12*s], fill=(45, 30, 25, 255), outline=p["outline"], width=2*s)
            draw_curved_line(draw, [(cx - 20*s, cy - 14*s), (cx, cy + 16*s), (cx + 20*s, cy - 14*s)], fill=p["glow"], width=3*s)
        else:
            draw.line([(cx - 18*s, cy - 14*s), (cx + 18*s, cy + 14*s)], fill=p["accent_mid"], width=4*s)

    # 3. NEURO-COVENANT (Flowing Ceremonial Robes & Amethyst Singularity)
    elif faction == "covenant":
        draw_curved_polygon(draw, [
            (cx - 24*s, cy - 22*s), (cx + 24*s, cy - 22*s), (cx + 22*s, cy + 8*s),
            (cx + 16*s, cy + 26*s), (cx, cy + 30*s), (cx - 16*s, cy + 26*s), (cx - 22*s, cy + 8*s)
        ], fill=p["primary_dark"], outline=p["outline"], width=2*s)
        draw.polygon([(cx - 10*s, cy - 22*s), (cx + 10*s, cy - 22*s), (cx + 8*s, cy + 28*s), (cx - 8*s, cy + 28*s)], fill=p["primary_mid"])
        draw.line([(cx - 10*s, cy - 22*s), (cx - 8*s, cy + 28*s)], fill=p["accent_mid"], width=2*s)
        draw.line([(cx + 10*s, cy - 22*s), (cx + 8*s, cy + 28*s)], fill=p["accent_mid"], width=2*s)
        draw.polygon([(cx, cy - 12*s), (cx + 8*s, cy - 4*s), (cx, cy + 4*s), (cx - 8*s, cy - 4*s)], fill=p["glow"], outline=p["accent_light"], width=s)
        draw.ellipse([cx - 2*s, cy - 6*s, cx + 2*s, cy - 2*s], fill=p["glow_core"])

        if role in ["rocket"]:
            draw.ellipse([cx - 10*s, cy - 8*s, cx + 10*s, cy + 12*s], fill=(10, 5, 20, 255), outline=p["glow"], width=2*s)
            draw.ellipse([cx - 5*s, cy - 3*s, cx + 5*s, cy + 7*s], fill=p["glow"])
            draw.ellipse([cx - 2*s, cy, cx + 2*s, cy + 4*s], fill=p["glow_core"])

    # 4. BIO-FORGE LEGION (Living Chitin Carapace & Pulsating Chem Sacs)
    elif faction == "bioforge":
        draw_curved_polygon(draw, [
            (cx - 25*s, cy - 22*s), (cx + 25*s, cy - 22*s), (cx + 22*s, cy + 6*s),
            (cx + 14*s, cy + 24*s), (cx, cy + 28*s), (cx - 14*s, cy + 24*s), (cx - 22*s, cy + 6*s)
        ], fill=p["primary_mid"], outline=p["outline"], width=2*s)
        for ry in [-12, -2, 8]:
            draw.line([(cx - 18*s, cy + ry*s), (cx - 6*s, cy + ry*s)], fill=p["accent_mid"], width=2*s)
            draw.line([(cx + 6*s, cy + ry*s), (cx + 18*s, cy + ry*s)], fill=p["accent_mid"], width=2*s)

        if role in ["flamethrower", "grenadier"]:
            draw.ellipse([cx - 14*s, cy - 10*s, cx + 14*s, cy + 14*s], fill=p["glow"], outline=p["outline"], width=2*s)
            draw.ellipse([cx - 7*s, cy - 5*s, cx + 7*s, cy + 9*s], fill=p["glow_core"])
        else:
            draw.ellipse([cx - 7*s, cy - 6*s, cx + 7*s, cy + 8*s], fill=p["primary_dark"], outline=p["glow"], width=2*s)
            draw.ellipse([cx - 4*s, cy - 3*s, cx + 4*s, cy + 5*s], fill=p["glow"])

    # 5. SILICON HIVE (Segmented Robotic Chassis, Reactor & Cooling Fins)
    elif faction == "silicon":
        draw_curved_polygon(draw, [
            (cx - 25*s, cy - 22*s), (cx + 25*s, cy - 22*s), (cx + 22*s, cy + 8*s),
            (cx + 14*s, cy + 24*s), (cx, cy + 26*s), (cx - 14*s, cy + 24*s), (cx - 22*s, cy + 8*s)
        ], fill=p["primary_dark"], outline=p["outline"], width=2*s)
        draw.rectangle([cx - 20*s, cy - 18*s, cx + 20*s, cy - 4*s], fill=p["primary_mid"], outline=p["outline"], width=s)
        for hx in range(-16, 16, 6):
            draw.line([(cx + hx*s, cy - 16*s), (cx + (hx+3)*s, cy - 6*s)], fill=p["accent_mid"], width=2*s)

        draw.rectangle([cx - 8*s, cy + 2*s, cx + 8*s, cy + 16*s], fill=p["primary_dark"], outline=p["glow"], width=2*s)
        draw.rectangle([cx - 5*s, cy + 5*s, cx + 5*s, cy + 13*s], fill=p["glow"])
        draw.rectangle([cx - 2*s, cy + 7*s, cx + 2*s, cy + 11*s], fill=p["glow_core"])

        if role in ["engineer"]:
            for hx in range(-14, 16, 8):
                draw.line([(cx + hx*s, cy + 4*s), (cx + (hx+4)*s, cy + 14*s)], fill=p["hazard"], width=2*s)


# ==============================================================================
# PROCEDURAL DRAWING: PELVIS, ARMS, LEGS
# ==============================================================================

def draw_cyberpunk_pelvis(draw, w, h, s, p: dict, faction: str, role: str, seed: int = 42):
    cx, cy = w // 2, h // 2
    draw_curved_polygon(draw, [
        (cx - 20*s, cy - 16*s), (cx + 20*s, cy - 16*s), (cx + 16*s, cy + 4*s),
        (cx + 8*s, cy + 18*s), (cx - 8*s, cy + 18*s), (cx - 16*s, cy + 4*s)
    ], fill=p["primary_mid"], outline=p["outline"], width=2*s)
    draw.rectangle([cx - 20*s, cy - 18*s, cx + 20*s, cy - 10*s], fill=p["accent_dark"], outline=p["outline"], width=s)
    draw.rectangle([cx - 5*s, cy - 17*s, cx + 5*s, cy - 11*s], fill=p["glow"], outline=p["outline"], width=s)


def draw_cyberpunk_arm_upper(draw, w, h, s, p: dict, faction: str, role: str, is_left: bool):
    cx, cy = w // 2, h // 2
    draw_curved_polygon(draw, [
        (cx - 16*s, cy - 18*s), (cx + 16*s, cy - 18*s), (cx + 14*s, cy),
        (cx + 10*s, cy + 20*s), (cx - 10*s, cy + 20*s), (cx - 14*s, cy)
    ], fill=p["primary_mid"], outline=p["outline"], width=2*s)
    draw_curved_polygon(draw, [
        (cx - 18*s, cy - 20*s), (cx + 18*s, cy - 20*s), (cx + 14*s, cy - 6*s), (cx - 14*s, cy - 6*s)
    ], fill=p["primary_dark"], outline=p["outline"], width=s)
    draw.line([(cx - 12*s, cy - 4*s), (cx + 12*s, cy - 4*s)], fill=p["glow"], width=s)


def draw_cyberpunk_arm_lower(draw, w, h, s, p: dict, faction: str, role: str, is_left: bool):
    cx, cy = w // 2, h // 2
    draw_curved_polygon(draw, [
        (cx - 12*s, cy - 20*s), (cx + 12*s, cy - 20*s), (cx + 14*s, cy + 12*s),
        (cx + 8*s, cy + 20*s), (cx - 8*s, cy + 20*s), (cx - 14*s, cy + 12*s)
    ], fill=p["primary_dark"], outline=p["outline"], width=2*s)
    draw.rectangle([cx - 8*s, cy - 14*s, cx + 8*s, cy + 8*s], fill=p["primary_mid"], outline=p["outline"], width=s)
    draw.line([(cx, cy - 12*s), (cx, cy + 6*s)], fill=p["glow"], width=s)


def draw_cyberpunk_hand(draw, w, h, s, p: dict, faction: str, role: str, is_left: bool):
    cx, cy = w // 2, h // 2
    draw_curved_polygon(draw, [
        (cx - 8*s, cy - 10*s), (cx + 8*s, cy - 10*s), (cx + 10*s, cy + 2*s),
        (cx + 6*s, cy + 10*s), (cx - 6*s, cy + 10*s), (cx - 10*s, cy + 2*s)
    ], fill=p["accent_dark"], outline=p["outline"], width=s)
    draw.line([(cx - 6*s, cy - 4*s), (cx + 6*s, cy - 4*s)], fill=p["accent_mid"], width=2*s)


def draw_cyberpunk_leg_upper(draw, w, h, s, p: dict, faction: str, role: str, is_left: bool):
    cx, cy = w // 2, h // 2
    draw_curved_polygon(draw, [
        (cx - 14*s, cy - 22*s), (cx + 14*s, cy - 22*s), (cx + 12*s, cy + 12*s),
        (cx + 8*s, cy + 22*s), (cx - 8*s, cy + 22*s), (cx - 12*s, cy + 12*s)
    ], fill=p["primary_dark"], outline=p["outline"], width=2*s)
    draw.rectangle([cx - 10*s, cy - 16*s, cx + 10*s, cy + 6*s], fill=p["primary_mid"], outline=p["outline"], width=s)


def draw_cyberpunk_leg_lower(draw, w, h, s, p: dict, faction: str, role: str, is_left: bool):
    cx, cy = w // 2, h // 2
    draw_curved_polygon(draw, [
        (cx - 12*s, cy - 22*s), (cx + 12*s, cy - 22*s), (cx + 14*s, cy + 12*s),
        (cx + 10*s, cy + 22*s), (cx - 10*s, cy + 22*s), (cx - 14*s, cy + 12*s)
    ], fill=p["primary_mid"], outline=p["outline"], width=2*s)
    draw.ellipse([cx - 8*s, cy - 20*s, cx + 8*s, cy - 8*s], fill=p["primary_dark"], outline=p["outline"], width=s)
    draw.line([(cx - 4*s, cy - 14*s), (cx + 4*s, cy - 14*s)], fill=p["glow"], width=s)


def draw_cyberpunk_foot(draw, w, h, s, p: dict, faction: str, role: str, is_left: bool):
    cx, cy = w // 2, h // 2
    dir_mul = 1 if is_left else -1
    draw_curved_polygon(draw, [
        (cx - 12*s*dir_mul, cy - 8*s), (cx + 8*s*dir_mul, cy - 8*s),
        (cx + 18*s*dir_mul, cy + 8*s), (cx - 14*s*dir_mul, cy + 8*s)
    ], fill=p["primary_dark"], outline=p["outline"], width=2*s)
    x0 = min(cx - 14*s*dir_mul, cx + 18*s*dir_mul)
    x1 = max(cx - 14*s*dir_mul, cx + 18*s*dir_mul)
    draw.rectangle([x0, cy + 6*s, x1, cy + 10*s], fill=p["accent_dark"])


# ==============================================================================
# MASTER GENERATOR FOR CYBERPUNK CHARACTERS
# ==============================================================================

def generate_cyberpunk_character_sprites(out_dir: str, prefix: str, faction: str, role: str, seed: int = 42) -> List[str]:
    """
    Generates all 15 limb sprites, master exploded sheet, and assembled full preview.
    Uses faction-tailored silhouettes, materials, and gear.
    """
    os.makedirs(out_dir, exist_ok=True)
    p = FACTION_PALETTES.get(faction, FACTION_PALETTES["directorate"])

    parts = {
        "head": ((64, 64), lambda d, w, h, s: draw_cyberpunk_head(d, w, h, s, p, faction, role, seed)),
        "torso": ((72, 64), lambda d, w, h, s: draw_cyberpunk_torso(d, w, h, s, p, faction, role, seed)),
        "pelvis": ((64, 48), lambda d, w, h, s: draw_cyberpunk_pelvis(d, w, h, s, p, faction, role, seed)),
        "arm_upper_L": ((44, 56), lambda d, w, h, s: draw_cyberpunk_arm_upper(d, w, h, s, p, faction, role, True)),
        "arm_lower_L": ((36, 52), lambda d, w, h, s: draw_cyberpunk_arm_lower(d, w, h, s, p, faction, role, True)),
        "hand_L": ((32, 32), lambda d, w, h, s: draw_cyberpunk_hand(d, w, h, s, p, faction, role, True)),
        "arm_upper_R": ((44, 56), lambda d, w, h, s: draw_cyberpunk_arm_upper(d, w, h, s, p, faction, role, False)),
        "arm_lower_R": ((36, 52), lambda d, w, h, s: draw_cyberpunk_arm_lower(d, w, h, s, p, faction, role, False)),
        "hand_R": ((32, 32), lambda d, w, h, s: draw_cyberpunk_hand(d, w, h, s, p, faction, role, False)),
        "leg_upper_L": ((40, 56), lambda d, w, h, s: draw_cyberpunk_leg_upper(d, w, h, s, p, faction, role, True)),
        "leg_lower_L": ((36, 56), lambda d, w, h, s: draw_cyberpunk_leg_lower(d, w, h, s, p, faction, role, True)),
        "foot_L": ((48, 32), lambda d, w, h, s: draw_cyberpunk_foot(d, w, h, s, p, faction, role, True)),
        "leg_upper_R": ((40, 56), lambda d, w, h, s: draw_cyberpunk_leg_upper(d, w, h, s, p, faction, role, False)),
        "leg_lower_R": ((36, 56), lambda d, w, h, s: draw_cyberpunk_leg_lower(d, w, h, s, p, faction, role, False)),
        "foot_R": ((48, 32), lambda d, w, h, s: draw_cyberpunk_foot(d, w, h, s, p, faction, role, False)),
    }

    generated_paths = []
    limb_images = {}
    for name, (size, fn) in parts.items():
        img = create_sprite(size, fn, art_style="anime", detail_level=3)
        out_path = os.path.join(out_dir, f"{prefix}_{name}.png")
        img.save(out_path, "PNG")
        generated_paths.append(out_path)
        limb_images[name] = img

    # Create Master Exploded Sheet ({prefix}_exploded.png)
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

    exploded_path = os.path.join(out_dir, f"{prefix}_exploded.png")
    exploded.save(exploded_path, "PNG")
    generated_paths.append(exploded_path)

    # Create Assembled Full Model Preview ({prefix}_full.png)
    preview_path = create_character_assembled_preview(out_dir, prefix=prefix, rig_type="biped")
    if preview_path and os.path.isfile(preview_path):
        generated_paths.append(str(preview_path))

    return generated_paths
