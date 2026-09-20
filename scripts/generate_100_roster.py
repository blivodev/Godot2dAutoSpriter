#!/usr/bin/env python3
"""
generate_100_roster.py - Generates 100 Additional Cyberpunk RTS Characters across 5 Generative Models

Models & Sectors:
1. Neo-Tokyo Cyber-Corps (20 units) - Animagine XL Model Profile
2. Abyssal Sector Outcasts (20 units) - Counterfeit V3 Model Profile
3. Orbital Black-Ops Legion (20 units) - DreamShaper 8 Model Profile
4. Aetherium Psionic Syndicate (20 units) - RPG Remix Model Profile
5. Neon Glitch Underground (20 units) - Pixel/Anime Hybrid Model Profile

Creates:
- 1,500 transparent sliced limb sprites (15 per character)
- 100 master exploded sprite sheets (_exploded.png)
- 100 full assembled character previews (_full.png)
- 100 metadata.json files with 4 tailored signature moves
- 100 Godot 4 .tscn scenes with 23 skeletal animations
- sprites/mega_roster_100.json
"""

import os
import sys
import json
import math
import random
import shutil
import numpy as np
from pathlib import Path
from PIL import Image, ImageEnhance, ImageOps, ImageDraw, ImageFilter
from typing import Dict, List, Any, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRAIN_DIR = Path("C:/Users/USER/.gemini/antigravity-ide/brain/7f7019a6-43a1-40f1-b616-f0eb9c79d69d")

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.generate_rig_animations import (
    SPECIAL_MOVES_CATALOG,
    build_tscn_animation_text,
    randomize_character_specials
)

# 5 Base Generative Model Archetypes
MODEL_ARCHETYPES = {
    "neotokyo": {
        "image": BRAIN_DIR / "neotokyo_vanguard_1789902041893.jpg",
        "sector_id": "neotokyo",
        "sector_name": "Neo-Tokyo Cyber-Corps",
        "model_engine": "Animagine XL 3.1 (SDXL Premier Anime)",
        "model_key": "animagine_xl",
        "theme_color": "#00f0ff",
        "default_tint": (0, 240, 255)
    },
    "abyssal": {
        "image": BRAIN_DIR / "abyssal_scrapper_1789902058339.jpg",
        "sector_id": "abyssal",
        "sector_name": "Abyssal Sector Outcasts",
        "model_engine": "Counterfeit V3.0 (Painterly Grimdark)",
        "model_key": "counterfeit_v3",
        "theme_color": "#e67e22",
        "default_tint": (230, 126, 34)
    },
    "orbital": {
        "image": BRAIN_DIR / "orbital_blackops_1789902074116.jpg",
        "sector_id": "orbital",
        "sector_name": "Orbital Black-Ops Legion",
        "model_engine": "DreamShaper 8 (Military Spec-Ops Sci-Fi)",
        "model_key": "dreamshaper_8",
        "theme_color": "#2ecc71",
        "default_tint": (46, 204, 113)
    },
    "aetherium": {
        "image": BRAIN_DIR / "aetherium_archon_1789902092730.jpg",
        "sector_id": "aetherium",
        "sector_name": "Aetherium Psionic Syndicate",
        "model_engine": "RPG Remix (Ornate Psionic Occult)",
        "model_key": "rpg_remix",
        "theme_color": "#9b59b6",
        "default_tint": (155, 89, 182)
    },
    "neonglitch": {
        "image": BRAIN_DIR / "neonglitch_rebel_1789902111381.jpg",
        "sector_id": "neonglitch",
        "sector_name": "Neon Glitch Underground",
        "model_engine": "Pixel/Anime Hybrid Multi-Diffusion",
        "model_key": "pixel_anime_hybrid",
        "theme_color": "#ff007f",
        "default_tint": (255, 0, 127)
    }
}

# 100 Characters Definition across 5 Sectors (20 units each)
ROSTER_DEFS = [
    # 1. NEO-TOKYO CYBER-CORPS (20 units) - Animagine XL 3.1
    {"id": "tachyon_striker", "display": "Tachyon Striker", "sector": "neotokyo", "role": "Soldier", "weapon": "plasma_rifle", "tint": (0, 230, 255)},
    {"id": "railgun_phantom", "display": "Railgun Phantom", "sector": "neotokyo", "role": "Sniper", "weapon": "sniper_railgun", "tint": (100, 200, 255)},
    {"id": "orbital_lance", "display": "Orbital Lance", "sector": "neotokyo", "role": "Special Agent", "weapon": "pulse_pistol", "tint": (0, 255, 200)},
    {"id": "pulse_dragoon", "display": "Pulse Dragoon", "sector": "neotokyo", "role": "Juggernaut", "weapon": "heavy_repeater", "tint": (50, 150, 255)},
    {"id": "nanite_ronin", "display": "Nanite Ronin", "sector": "neotokyo", "role": "Assassin", "weapon": "plasma_blade", "tint": (0, 240, 255)},
    {"id": "graviton_blade", "display": "Graviton Blade", "sector": "neotokyo", "role": "Special Agent", "weapon": "graviton_saber", "tint": (120, 180, 255)},
    {"id": "hyper_scythe", "display": "Hyper-Scythe", "sector": "neotokyo", "role": "Saboteur", "weapon": "hyper_scythe", "tint": (0, 210, 240)},
    {"id": "void_shinobi", "display": "Void Shinobi", "sector": "neotokyo", "role": "Infiltrator", "weapon": "void_daggers", "tint": (30, 120, 220)},
    {"id": "cyber_kunoichi", "display": "Cyber Kunoichi", "sector": "neotokyo", "role": "Infiltrator", "weapon": "needle_darts", "tint": (80, 220, 255)},
    {"id": "plasma_buster", "display": "Plasma Buster", "sector": "neotokyo", "role": "Rocket Trooper", "weapon": "plasma_cannon", "tint": (0, 190, 255)},
    {"id": "aegis_sentinel", "display": "Aegis Sentinel", "sector": "neotokyo", "role": "Engineer", "weapon": "barrier_shield", "tint": (140, 220, 255)},
    {"id": "tachyon_breaker", "display": "Tachyon Breaker", "sector": "neotokyo", "role": "Flak Trooper", "weapon": "flak_cannon", "tint": (20, 200, 250)},
    {"id": "beam_valkyrie", "display": "Beam Valkyrie", "sector": "neotokyo", "role": "Medic", "weapon": "beam_injector", "tint": (120, 240, 255)},
    {"id": "emp_commando", "display": "EMP Commando", "sector": "neotokyo", "role": "Saboteur", "weapon": "emp_disrupter", "tint": (40, 160, 240)},
    {"id": "dynamo_mech", "display": "Dynamo Mech", "sector": "neotokyo", "role": "Juggernaut", "weapon": "dynamo_fist", "tint": (60, 180, 255)},
    {"id": "kinetic_hunter", "display": "Kinetic Hunter", "sector": "neotokyo", "role": "Soldier", "weapon": "kinetic_carbine", "tint": (0, 220, 240)},
    {"id": "solar_flare_trooper", "display": "Solar Flare Trooper", "sector": "neotokyo", "role": "Flamethrower", "weapon": "solar_caster", "tint": (0, 240, 255)},
    {"id": "warp_vanguard", "display": "Warp Vanguard", "sector": "neotokyo", "role": "Special Agent", "weapon": "warp_rifle", "tint": (90, 170, 255)},
    {"id": "glitch_operator", "display": "Glitch Operator", "sector": "neotokyo", "role": "Drone Operator", "weapon": "drone_pad", "tint": (0, 255, 230)},
    {"id": "zero_point_warden", "display": "Zero-Point Warden", "sector": "neotokyo", "role": "Mind Controller", "weapon": "zero_staff", "tint": (150, 210, 255)},

    # 2. ABYSSAL SECTOR OUTCASTS (20 units) - Counterfeit V3.0
    {"id": "rust_marauder", "display": "Rust Marauder", "sector": "abyssal", "role": "Soldier", "weapon": "scrap_autogun", "tint": (210, 120, 40)},
    {"id": "scrap_reaver", "display": "Scrap Reaver", "sector": "abyssal", "role": "Juggernaut", "weapon": "rebar_hammer", "tint": (180, 90, 30)},
    {"id": "ash_valkyrie", "display": "Ash Valkyrie", "sector": "abyssal", "role": "Sniper", "weapon": "junk_rifle", "tint": (230, 140, 50)},
    {"id": "toxic_desperado", "display": "Toxic Desperado", "sector": "abyssal", "role": "Special Agent", "weapon": "dual_sluggers", "tint": (200, 110, 40)},
    {"id": "grim_revenant", "display": "Grim Revenant", "sector": "abyssal", "role": "Saboteur", "weapon": "corrosive_blade", "tint": (160, 80, 20)},
    {"id": "rad_waste_hunter", "display": "Rad-Waste Hunter", "sector": "abyssal", "role": "Infiltrator", "weapon": "rad_crossbow", "tint": (220, 130, 45)},
    {"id": "bone_stalker", "display": "Bone Stalker", "sector": "abyssal", "role": "Assassin", "weapon": "serrated_scythe", "tint": (190, 100, 35)},
    {"id": "slag_berserker", "display": "Slag Berserker", "sector": "abyssal", "role": "Juggernaut", "weapon": "molten_flail", "tint": (240, 100, 20)},
    {"id": "diesel_titan", "display": "Diesel Titan", "sector": "abyssal", "role": "Heavy Ordinance", "weapon": "diesel_cannon", "tint": (170, 95, 40)},
    {"id": "scrap_gunner", "display": "Scrap Gunner", "sector": "abyssal", "role": "Soldier", "weapon": "pipe_minigun", "tint": (210, 125, 55)},
    {"id": "dust_shaman", "display": "Dust Shaman", "sector": "abyssal", "role": "Mind Controller", "weapon": "totem_staff", "tint": (230, 150, 60)},
    {"id": "sewer_stalker", "display": "Sewer Stalker", "sector": "abyssal", "role": "Saboteur", "weapon": "toxin_dart_gun", "tint": (180, 110, 30)},
    {"id": "iron_nomad", "display": "Iron Nomad", "sector": "abyssal", "role": "Soldier", "weapon": "lever_carbine", "tint": (205, 120, 50)},
    {"id": "hazard_raider", "display": "Hazard Raider", "sector": "abyssal", "role": "Rocket Trooper", "weapon": "junk_rpg", "tint": (225, 135, 45)},
    {"id": "smog_alchemist", "display": "Smog Alchemist", "sector": "abyssal", "role": "Medic", "weapon": "chem_injector", "tint": (240, 160, 70)},
    {"id": "lead_spitter", "display": "Lead-Spitter", "sector": "abyssal", "role": "Flak Trooper", "weapon": "quad_shredder", "tint": (195, 105, 35)},
    {"id": "chain_ripper", "display": "Chain Ripper", "sector": "abyssal", "role": "Engineer", "weapon": "chainsaw_cutter", "tint": (215, 115, 40)},
    {"id": "rust_zealot", "display": "Rust Zealot", "sector": "abyssal", "role": "Flamethrower", "weapon": "napalm_spewer", "tint": (250, 110, 30)},
    {"id": "acid_vulture", "display": "Acid Vulture", "sector": "abyssal", "role": "Drone Operator", "weapon": "drone_controller", "tint": (210, 140, 50)},
    {"id": "ruin_crawler", "display": "Ruin Crawler", "sector": "abyssal", "role": "Infiltrator", "weapon": "suppressed_smg", "tint": (175, 90, 30)},

    # 3. ORBITAL BLACK-OPS LEGION (20 units) - DreamShaper 8
    {"id": "orbital_ranger", "display": "Orbital Ranger", "sector": "orbital", "role": "Soldier", "weapon": "carbine_mk4", "tint": (50, 180, 100)},
    {"id": "apex_infiltrator", "display": "Apex Infiltrator", "sector": "orbital", "role": "Infiltrator", "weapon": "silenced_pdw", "tint": (40, 160, 90)},
    {"id": "stealth_recon_alpha", "display": "Stealth Recon Alpha", "sector": "orbital", "role": "Sniper", "weapon": "dmr_50cal", "tint": (60, 200, 120)},
    {"id": "ghost_recon_delta", "display": "Ghost Recon Delta", "sector": "orbital", "role": "Special Agent", "weapon": "holo_carbine", "tint": (70, 210, 130)},
    {"id": "heavy_exo_breacher", "display": "Heavy Exo-Breacher", "sector": "orbital", "role": "Juggernaut", "weapon": "breaching_shotgun", "tint": (35, 150, 80)},
    {"id": "tactical_juggernaut", "display": "Tactical Juggernaut", "sector": "orbital", "role": "Heavy Ordinance", "weapon": "rotary_cannon", "tint": (45, 170, 95)},
    {"id": "null_g_marine", "display": "Null-G Marine", "sector": "orbital", "role": "Soldier", "weapon": "magnetic_rifle", "tint": (55, 190, 110)},
    {"id": "drop_pod_commando", "display": "Drop-Pod Commando", "sector": "orbital", "role": "Rocket Trooper", "weapon": "missile_launcher", "tint": (65, 180, 105)},
    {"id": "sub_orbital_spotter", "display": "Sub-Orbital Spotter", "sector": "orbital", "role": "Sniper", "weapon": "target_designator", "tint": (80, 220, 140)},
    {"id": "thermal_predator", "display": "Thermal Predator", "sector": "orbital", "role": "Assassin", "weapon": "thermal_blade", "tint": (30, 140, 75)},
    {"id": "shock_trooper_prime", "display": "Shock Trooper Prime", "sector": "orbital", "role": "Soldier", "weapon": "shock_carbine", "tint": (50, 195, 115)},
    {"id": "cryo_infiltrator", "display": "Cryo-Infiltrator", "sector": "orbital", "role": "Saboteur", "weapon": "cryo_pistol", "tint": (90, 230, 160)},
    {"id": "magneto_gunner", "display": "Magneto-Gunner", "sector": "orbital", "role": "Flak Trooper", "weapon": "mag_flak", "tint": (40, 165, 90)},
    {"id": "void_commando", "display": "Void Commando", "sector": "orbital", "role": "Special Agent", "weapon": "assault_rifle_ex", "tint": (60, 185, 105)},
    {"id": "bastion_frame", "display": "Bastion Frame", "sector": "orbital", "role": "Engineer", "weapon": "deployable_shield", "tint": (45, 155, 85)},
    {"id": "cerberus_operative", "display": "Cerberus Operative", "sector": "orbital", "role": "Saboteur", "weapon": "combat_shotgun", "tint": (70, 200, 120)},
    {"id": "nightfall_sentry", "display": "Nightfall Sentry", "sector": "orbital", "role": "Flamethrower", "weapon": "pyro_cannon", "tint": (55, 175, 100)},
    {"id": "horizon_vanguard", "display": "Horizon Vanguard", "sector": "orbital", "role": "Medic", "weapon": "med_applicator", "tint": (80, 215, 135)},
    {"id": "quantum_scout", "display": "Quantum Scout", "sector": "orbital", "role": "Drone Operator", "weapon": "drone_terminal", "tint": (65, 205, 125)},
    {"id": "zenith_enforcer", "display": "Zenith Enforcer", "sector": "orbital", "role": "Mind Controller", "weapon": "neural_disrupter", "tint": (50, 170, 95)},

    # 4. AETHERIUM PSIONIC SYNDICATE (20 units) - RPG Remix
    {"id": "astral_psion", "display": "Astral Psion", "sector": "aetherium", "role": "Mind Controller", "weapon": "psi_staff", "tint": (170, 70, 220)},
    {"id": "chrono_mystic", "display": "Chrono Mystic", "sector": "aetherium", "role": "Special Agent", "weapon": "time_scepter", "tint": (190, 90, 240)},
    {"id": "warp_weaver", "display": "Warp Weaver", "sector": "aetherium", "role": "Saboteur", "weapon": "dimensional_dagger", "tint": (150, 50, 200)},
    {"id": "soul_core_adept", "display": "Soul-Core Adept", "sector": "aetherium", "role": "Medic", "weapon": "aether_orb", "tint": (210, 110, 255)},
    {"id": "mind_flare_archon", "display": "Mind-Flare Archon", "sector": "aetherium", "role": "Mind Controller", "weapon": "telepathic_rod", "tint": (160, 60, 210)},
    {"id": "void_templar", "display": "Void Templar", "sector": "aetherium", "role": "Juggernaut", "weapon": "crystal_greatsword", "tint": (130, 40, 180)},
    {"id": "ether_sovereign", "display": "Ether Sovereign", "sector": "aetherium", "role": "Special Agent", "weapon": "psionic_crown", "tint": (180, 80, 230)},
    {"id": "graviton_oracle", "display": "Graviton Oracle", "sector": "aetherium", "role": "Sniper", "weapon": "singularity_bow", "tint": (140, 50, 195)},
    {"id": "prism_mage", "display": "Prism Mage", "sector": "aetherium", "role": "Soldier", "weapon": "prism_wand", "tint": (200, 100, 245)},
    {"id": "rift_stalker", "display": "Rift Stalker", "sector": "aetherium", "role": "Infiltrator", "weapon": "phase_claws", "tint": (155, 65, 215)},
    {"id": "telekinesis_master", "display": "Telekinesis Master", "sector": "aetherium", "role": "Mind Controller", "weapon": "kinetic_focus", "tint": (175, 75, 225)},
    {"id": "crystalline_golem", "display": "Crystalline Golem", "sector": "aetherium", "role": "Juggernaut", "weapon": "crystal_fists", "tint": (120, 30, 170)},
    {"id": "spectral_assassin", "display": "Spectral Assassin", "sector": "aetherium", "role": "Assassin", "weapon": "astral_blade", "tint": (165, 70, 220)},
    {"id": "nullifier_monk", "display": "Nullifier Monk", "sector": "aetherium", "role": "Engineer", "weapon": "null_ward", "tint": (185, 85, 235)},
    {"id": "astral_ward", "display": "Astral Ward", "sector": "aetherium", "role": "Flak Trooper", "weapon": "shard_burst", "tint": (145, 55, 205)},
    {"id": "psionic_inquisitor", "display": "Psionic Inquisitor", "sector": "aetherium", "role": "Soldier", "weapon": "psi_revolver", "tint": (195, 95, 245)},
    {"id": "warp_sorcerer", "display": "Warp Sorcerer", "sector": "aetherium", "role": "Flamethrower", "weapon": "soul_fire_caster", "tint": (215, 80, 230)},
    {"id": "reality_bender", "display": "Reality Bender", "sector": "aetherium", "role": "Rocket Trooper", "weapon": "spatial_mortar", "tint": (135, 45, 190)},
    {"id": "cosmic_harbinger", "display": "Cosmic Harbinger", "sector": "aetherium", "role": "Drone Operator", "weapon": "familiar_beacon", "tint": (160, 60, 210)},
    {"id": "eclipse_zealot", "display": "Eclipse Zealot", "sector": "aetherium", "role": "Soldier", "weapon": "dark_matter_rifle", "tint": (170, 70, 225)},

    # 5. NEON GLITCH UNDERGROUND (20 units) - Pixel/Anime Hybrid
    {"id": "neon_hacker", "display": "Neon Hacker", "sector": "neonglitch", "role": "Saboteur", "weapon": "cyberdeck", "tint": (255, 0, 140)},
    {"id": "holo_vandal", "display": "Holo-Vandal", "sector": "neonglitch", "role": "Special Agent", "weapon": "spray_laser", "tint": (240, 20, 160)},
    {"id": "synth_blade_rebel", "display": "Synth-Blade Rebel", "sector": "neonglitch", "role": "Assassin", "weapon": "neon_katana", "tint": (255, 40, 120)},
    {"id": "cyber_punkette", "display": "Cyber Punkette", "sector": "neonglitch", "role": "Infiltrator", "weapon": "twin_subguns", "tint": (230, 0, 170)},
    {"id": "street_ronin", "display": "Street Ronin", "sector": "neonglitch", "role": "Soldier", "weapon": "high_freq_blade", "tint": (250, 30, 130)},
    {"id": "wire_tap_infiltrator", "display": "Wire-Tap Infiltrator", "sector": "neonglitch", "role": "Infiltrator", "weapon": "data_tether", "tint": (220, 10, 150)},
    {"id": "glitch_witch", "display": "Glitch Witch", "sector": "neonglitch", "role": "Mind Controller", "weapon": "signal_jammer", "tint": (255, 50, 180)},
    {"id": "bass_cannon_heavy", "display": "Bass-Cannon Heavy", "sector": "neonglitch", "role": "Heavy Ordinance", "weapon": "sonic_subwoofer", "tint": (210, 0, 130)},
    {"id": "data_courier", "display": "Data-Courier", "sector": "neonglitch", "role": "Special Agent", "weapon": "flash_pistol", "tint": (245, 25, 145)},
    {"id": "sub_zero_rioter", "display": "Sub-Zero Rioter", "sector": "neonglitch", "role": "Juggernaut", "weapon": "cryo_bat", "tint": (235, 15, 155)},
    {"id": "laser_skater", "display": "Laser Skater", "sector": "neonglitch", "role": "Soldier", "weapon": "light_smg", "tint": (255, 35, 165)},
    {"id": "arc_disrupter", "display": "Arc-Disrupter", "sector": "neonglitch", "role": "Rocket Trooper", "weapon": "emp_rpg", "tint": (225, 5, 135)},
    {"id": "turbo_juggler", "display": "Turbo Juggler", "sector": "neonglitch", "role": "Sniper", "weapon": "photon_rifle", "tint": (250, 45, 175)},
    {"id": "monomolecular_whip", "display": "Monomolecular Whip", "sector": "neonglitch", "role": "Assassin", "weapon": "mono_whip", "tint": (240, 20, 140)},
    {"id": "spark_duelist", "display": "Spark Duelist", "sector": "neonglitch", "role": "Soldier", "weapon": "plasma_rapier", "tint": (255, 60, 150)},
    {"id": "grid_runner", "display": "Grid Runner", "sector": "neonglitch", "role": "Medic", "weapon": "stim_dispenser", "tint": (230, 30, 160)},
    {"id": "overclocked_punk", "display": "Overclocked Punk", "sector": "neonglitch", "role": "Flamethrower", "weapon": "neon_flamethrower", "tint": (255, 10, 120)},
    {"id": "sonic_disruptor", "display": "Sonic Disruptor", "sector": "neonglitch", "role": "Flak Trooper", "weapon": "soundwave_mortar", "tint": (215, 0, 145)},
    {"id": "neon_brawler", "display": "Neon Brawler", "sector": "neonglitch", "role": "Juggernaut", "weapon": "power_knuckles", "tint": (245, 40, 135)},
    {"id": "matrix_phantom", "display": "Matrix Phantom", "sector": "neonglitch", "role": "Drone Operator", "weapon": "holo_drone", "tint": (255, 50, 170)},
]


def make_transparent(img: Image.Image) -> Image.Image:
    """Removes solid white studio background with anti-aliased edge alpha."""
    rgba = img.convert("RGBA")
    arr = np.array(rgba)
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)

    is_bg = (r > 235) & (g > 235) & (b > 235)
    arr[is_bg, 3] = 0

    edge_bg = (r > 215) & (g > 215) & (b > 215) & ~is_bg
    arr[edge_bg, 3] = 120

    return Image.fromarray(arr)


def slice_anatomical_limbs(src: Image.Image, out_dir: Path, prefix: str, tint_color: Tuple[int, int, int] = None):
    """Slices 15 anatomical limbs matching Godot Skeleton2D bone layout."""
    bbox = src.getbbox()
    if not bbox:
        bbox = (0, 0, src.width, src.height)

    min_x, min_y, max_x, max_y = bbox
    w = max_x - min_x
    h = max_y - min_y
    cx = (min_x + max_x) // 2

    regions = {
        "head": (cx - int(w*0.25), min_y, cx + int(w*0.25), min_y + int(h*0.22)),
        "torso": (cx - int(w*0.32), min_y + int(h*0.18), cx + int(w*0.32), min_y + int(h*0.46)),
        "pelvis": (cx - int(w*0.25), min_y + int(h*0.42), cx + int(w*0.25), min_y + int(h*0.58)),
        "arm_upper_L": (cx - int(w*0.50), min_y + int(h*0.18), cx - int(w*0.12), min_y + int(h*0.40)),
        "arm_lower_L": (cx - int(w*0.50), min_y + int(h*0.35), cx - int(w*0.15), min_y + int(h*0.55)),
        "hand_L": (cx - int(w*0.45), min_y + int(h*0.50), cx - int(w*0.18), min_y + int(h*0.65)),
        "arm_upper_R": (cx + int(w*0.12), min_y + int(h*0.18), cx + int(w*0.50), min_y + int(h*0.40)),
        "arm_lower_R": (cx + int(w*0.15), min_y + int(h*0.35), cx + int(w*0.50), min_y + int(h*0.55)),
        "hand_R": (cx + int(w*0.18), min_y + int(h*0.50), cx + int(w*0.45), min_y + int(h*0.65)),
        "leg_upper_L": (cx - int(w*0.30), min_y + int(h*0.52), cx - int(w*0.02), min_y + int(h*0.75)),
        "leg_lower_L": (cx - int(w*0.32), min_y + int(h*0.72), cx - int(w*0.05), min_y + int(h*0.92)),
        "foot_L": (cx - int(w*0.38), min_y + int(h*0.88), cx - int(w*0.05), max_y),
        "leg_upper_R": (cx + int(w*0.02), min_y + int(h*0.52), cx + int(w*0.30), min_y + int(h*0.75)),
        "leg_lower_R": (cx + int(w*0.05), min_y + int(h*0.72), cx + int(w*0.32), min_y + int(h*0.92)),
        "foot_R": (cx + int(w*0.05), min_y + int(h*0.88), cx + int(w*0.38), max_y),
    }

    target_sizes = {
        "head": (64, 64), "torso": (72, 64), "pelvis": (64, 48),
        "arm_upper_L": (44, 56), "arm_lower_L": (36, 52), "hand_L": (32, 32),
        "arm_upper_R": (44, 56), "arm_lower_R": (36, 52), "hand_R": (32, 32),
        "leg_upper_L": (40, 56), "leg_lower_L": (36, 56), "foot_L": (48, 32),
        "leg_upper_R": (40, 56), "leg_lower_R": (36, 56), "foot_R": (48, 32)
    }

    limb_images = {}
    for part, box in regions.items():
        bx0 = max(0, min(src.width - 1, box[0]))
        by0 = max(0, min(src.height - 1, box[1]))
        bx1 = max(bx0 + 1, min(src.width, box[2]))
        by1 = max(by0 + 1, min(src.height, box[3]))
        cropped = src.crop((bx0, by0, bx1, by1))
        resized = cropped.resize(target_sizes[part], Image.Resampling.LANCZOS)

        # Subtle tint variation
        if tint_color:
            r, g, b, a = resized.split()
            gray = ImageOps.grayscale(resized)
            tinted_rgb = ImageOps.colorize(gray, black=(10, 10, 15), white=tint_color)
            blended = Image.blend(resized.convert("RGB"), tinted_rgb, 0.20).convert("RGBA")
            blended.putalpha(a)
            resized = blended

        dest = out_dir / f"{prefix}_{part}.png"
        resized.save(dest, "PNG")
        limb_images[part] = resized

    # Full Assembled Preview
    preview_full = src.resize((256, 380), Image.Resampling.LANCZOS)
    if tint_color:
        r, g, b, a = preview_full.split()
        gray = ImageOps.grayscale(preview_full)
        tinted_rgb = ImageOps.colorize(gray, black=(10, 10, 15), white=tint_color)
        blended = Image.blend(preview_full.convert("RGB"), tinted_rgb, 0.16).convert("RGBA")
        blended.putalpha(a)
        preview_full = blended
    preview_full.save(out_dir / f"{prefix}_full.png", "PNG")

    # Master Exploded Sheet
    sheet = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    grid = [
        ("head", (20, 20)), ("torso", (110, 20)), ("pelvis", (210, 20)),
        ("arm_upper_L", (20, 110)), ("arm_lower_L", (90, 110)), ("hand_L", (150, 110)),
        ("arm_upper_R", (210, 110)), ("arm_lower_R", (280, 110)), ("hand_R", (340, 110)),
        ("leg_upper_L", (20, 200)), ("leg_lower_L", (90, 200)), ("foot_L", (150, 210)),
        ("leg_upper_R", (210, 200)), ("leg_lower_R", (280, 200)), ("foot_R", (340, 210))
    ]
    for part_name, (gx, gy) in grid:
        if part_name in limb_images:
            sheet.alpha_composite(limb_images[part_name], (gx, gy))
    sheet.save(out_dir / f"{prefix}_exploded.png", "PNG")


def generate_godot_scene(char_name: str, scene_path: Path, specials: List[str]):
    """Constructs Godot 4 .tscn scene rigged with all 23 animations."""
    bones = [
        ("pelvis", (0, 0), "res://sprites/{c}/{c}_pelvis.png", []),
        ("torso", (0, -40), "res://sprites/{c}/{c}_torso.png", ["pelvis"]),
        ("head", (0, -42), "res://sprites/{c}/{c}_head.png", ["torso"]),
        ("arm_upper_L", (-22, -32), "res://sprites/{c}/{c}_arm_upper_L.png", ["torso"]),
        ("arm_lower_L", (-10, 26), "res://sprites/{c}/{c}_arm_lower_L.png", ["arm_upper_L"]),
        ("hand_L", (-4, 22), "res://sprites/{c}/{c}_hand_L.png", ["arm_lower_L"]),
        ("arm_upper_R", (22, -32), "res://sprites/{c}/{c}_arm_upper_R.png", ["torso"]),
        ("arm_lower_R", (10, 26), "res://sprites/{c}/{c}_arm_lower_R.png", ["arm_upper_R"]),
        ("hand_R", (4, 22), "res://sprites/{c}/{c}_hand_R.png", ["arm_lower_R"]),
        ("leg_upper_L", (-14, 4), "res://sprites/{c}/{c}_leg_upper_L.png", ["pelvis"]),
        ("leg_lower_L", (0, 30), "res://sprites/{c}/{c}_leg_lower_L.png", ["leg_upper_L"]),
        ("foot_L", (-2, 28), "res://sprites/{c}/{c}_foot_L.png", ["leg_lower_L"]),
        ("leg_upper_R", (14, 4), "res://sprites/{c}/{c}_leg_upper_R.png", ["pelvis"]),
        ("leg_lower_R", (0, 30), "res://sprites/{c}/{c}_leg_lower_R.png", ["leg_upper_R"]),
        ("foot_R", (2, 28), "res://sprites/{c}/{c}_foot_R.png", ["leg_lower_R"]),
    ]

    ext_res = []
    res_id = 1
    limb_to_res = {}
    for bone_name, _, path_tmpl, _ in bones:
        p = path_tmpl.format(c=char_name)
        ext_res.append(f'[ext_resource type="Texture2D" uid="uid://char_{char_name}_{bone_name}" path="{p}" id="{res_id}"]')
        limb_to_res[bone_name] = res_id
        res_id += 1

    # Animation Library with all 23 animations (including 4 specials)
    from scripts.generate_rig_animations import build_character_animations
    char_anims = build_character_animations(specials)
    anim_blocks = []
    lib_dict_entries = []
    for name, data in char_anims.items():
        anim_blocks.append(build_tscn_animation_text(name, data))
        lib_dict_entries.append(f'&"{name}": SubResource("Animation_{name}")')

    anims_combined = "\n\n".join(anim_blocks)
    lib_dict_str = ",\n".join(lib_dict_entries)
    library_block = f"""[sub_resource type="AnimationLibrary" id="AnimationLibrary_auto"]
_data = {{
{lib_dict_str}
}}"""

    content = f"""[gd_scene load_steps={len(ext_res)+2} format=3]

{"\n".join(ext_res)}

{anims_combined}

{library_block}

[node name="{char_name}" type="Node2D"]

[node name="Skeleton2D" type="Skeleton2D" parent="."]

[node name="pelvis" type="Bone2D" parent="Skeleton2D"]
rest = Transform2D(1, 0, 0, 1, 0, 0)

[node name="Sprite_pelvis" type="Sprite2D" parent="Skeleton2D/pelvis"]
texture = ExtResource("{limb_to_res['pelvis']}")

[node name="torso" type="Bone2D" parent="Skeleton2D/pelvis"]
position = Vector2(0, -40)
rest = Transform2D(1, 0, 0, 1, 0, -40)

[node name="Sprite_torso" type="Sprite2D" parent="Skeleton2D/pelvis/torso"]
texture = ExtResource("{limb_to_res['torso']}")

[node name="head" type="Bone2D" parent="Skeleton2D/pelvis/torso"]
position = Vector2(0, -42)
rest = Transform2D(1, 0, 0, 1, 0, -42)

[node name="Sprite_head" type="Sprite2D" parent="Skeleton2D/pelvis/torso/head"]
texture = ExtResource("{limb_to_res['head']}")

[node name="arm_upper_L" type="Bone2D" parent="Skeleton2D/pelvis/torso"]
position = Vector2(-22, -32)
rest = Transform2D(1, 0, 0, 1, -22, -32)

[node name="Sprite_arm_upper_L" type="Sprite2D" parent="Skeleton2D/pelvis/torso/arm_upper_L"]
texture = ExtResource("{limb_to_res['arm_upper_L']}")

[node name="arm_lower_L" type="Bone2D" parent="Skeleton2D/pelvis/torso/arm_upper_L"]
position = Vector2(-10, 26)
rest = Transform2D(1, 0, 0, 1, -10, 26)

[node name="Sprite_arm_lower_L" type="Sprite2D" parent="Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L"]
texture = ExtResource("{limb_to_res['arm_lower_L']}")

[node name="hand_L" type="Bone2D" parent="Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L"]
position = Vector2(-4, 22)
rest = Transform2D(1, 0, 0, 1, -4, 22)

[node name="Sprite_hand_L" type="Sprite2D" parent="Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L/hand_L"]
texture = ExtResource("{limb_to_res['hand_L']}")

[node name="WeaponSlot_L" type="Marker2D" parent="Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L/hand_L"]
position = Vector2(-6, 8)

[node name="arm_upper_R" type="Bone2D" parent="Skeleton2D/pelvis/torso"]
position = Vector2(22, -32)
rest = Transform2D(1, 0, 0, 1, 22, -32)

[node name="Sprite_arm_upper_R" type="Sprite2D" parent="Skeleton2D/pelvis/torso/arm_upper_R"]
texture = ExtResource("{limb_to_res['arm_upper_R']}")

[node name="arm_lower_R" type="Bone2D" parent="Skeleton2D/pelvis/torso/arm_upper_R"]
position = Vector2(10, 26)
rest = Transform2D(1, 0, 0, 1, 10, 26)

[node name="Sprite_arm_lower_R" type="Sprite2D" parent="Skeleton2D/pelvis/torso/arm_upper_R/arm_lower_R"]
texture = ExtResource("{limb_to_res['arm_lower_R']}")

[node name="hand_R" type="Bone2D" parent="Skeleton2D/pelvis/torso/arm_upper_R/arm_lower_R"]
position = Vector2(4, 22)
rest = Transform2D(1, 0, 0, 1, 4, 22)

[node name="Sprite_hand_R" type="Sprite2D" parent="Skeleton2D/pelvis/torso/arm_upper_R/arm_lower_R/hand_R"]
texture = ExtResource("{limb_to_res['hand_R']}")

[node name="WeaponSlot_R" type="Marker2D" parent="Skeleton2D/pelvis/torso/arm_upper_R/arm_lower_R/hand_R"]
position = Vector2(6, 8)

[node name="leg_upper_L" type="Bone2D" parent="Skeleton2D/pelvis"]
position = Vector2(-14, 4)
rest = Transform2D(1, 0, 0, 1, -14, 4)

[node name="Sprite_leg_upper_L" type="Sprite2D" parent="Skeleton2D/pelvis/leg_upper_L"]
texture = ExtResource("{limb_to_res['leg_upper_L']}")

[node name="leg_lower_L" type="Bone2D" parent="Skeleton2D/pelvis/leg_upper_L"]
position = Vector2(0, 30)
rest = Transform2D(1, 0, 0, 1, 0, 30)

[node name="Sprite_leg_lower_L" type="Sprite2D" parent="Skeleton2D/pelvis/leg_upper_L/leg_lower_L"]
texture = ExtResource("{limb_to_res['leg_lower_L']}")

[node name="foot_L" type="Bone2D" parent="Skeleton2D/pelvis/leg_upper_L/leg_lower_L"]
position = Vector2(-2, 28)
rest = Transform2D(1, 0, 0, 1, -2, 28)

[node name="Sprite_foot_L" type="Sprite2D" parent="Skeleton2D/pelvis/leg_upper_L/leg_lower_L/foot_L"]
texture = ExtResource("{limb_to_res['foot_L']}")

[node name="leg_upper_R" type="Bone2D" parent="Skeleton2D/pelvis"]
position = Vector2(14, 4)
rest = Transform2D(1, 0, 0, 1, 14, 4)

[node name="Sprite_leg_upper_R" type="Sprite2D" parent="Skeleton2D/pelvis/leg_upper_R"]
texture = ExtResource("{limb_to_res['leg_upper_R']}")

[node name="leg_lower_R" type="Bone2D" parent="Skeleton2D/pelvis/leg_upper_R"]
position = Vector2(0, 30)
rest = Transform2D(1, 0, 0, 1, 0, 30)

[node name="Sprite_leg_lower_R" type="Sprite2D" parent="Skeleton2D/pelvis/leg_upper_R/leg_lower_R"]
texture = ExtResource("{limb_to_res['leg_lower_R']}")

[node name="foot_R" type="Bone2D" parent="Skeleton2D/pelvis/leg_upper_R/leg_lower_R"]
position = Vector2(2, 28)
rest = Transform2D(1, 0, 0, 1, 2, 28)

[node name="Sprite_foot_R" type="Sprite2D" parent="Skeleton2D/pelvis/leg_upper_R/leg_lower_R/foot_R"]
texture = ExtResource("{limb_to_res['foot_R']}")

[node name="AnimationPlayer" type="AnimationPlayer" parent="."]
libraries = {{
"": SubResource("AnimationLibrary_auto")
}}
autoplay = "idle"
"""
    with open(scene_path, "w", encoding="utf-8") as f:
        f.write(content)


def run_generate_100_roster():
    print("\n========================================================")
    print("Generating 100 Cyberpunk Characters Across 5 Generative Models")
    print("========================================================\n")

    preloaded_models = {}
    for key, info in MODEL_ARCHETYPES.items():
        p = info["image"]
        if p.is_file():
            print(f"Loading Base Model [{info['sector_name']}] from {p.name}...")
            raw = Image.open(p)
            preloaded_models[key] = make_transparent(raw)
        else:
            print(f"ERROR: {p} not found!")

    sprites_root = PROJECT_ROOT / "sprites"
    scenes_root = PROJECT_ROOT / "scenes"
    sprites_root.mkdir(parents=True, exist_ok=True)
    scenes_root.mkdir(parents=True, exist_ok=True)

    catalog = []
    total = len(ROSTER_DEFS)

    for i, c in enumerate(ROSTER_DEFS, start=1):
        cid = c["id"]
        display = c["display"]
        sec_key = c["sector"]
        role = c["role"]
        weapon = c["weapon"]
        tint = c.get("tint")
        sec_info = MODEL_ARCHETYPES[sec_key]

        char_dir = sprites_root / cid
        char_dir.mkdir(parents=True, exist_ok=True)

        base_img = preloaded_models.get(sec_key)
        if not base_img:
            continue

        # Slice 15 limbs, save previews
        slice_anatomical_limbs(base_img, char_dir, cid, tint_color=tint)

        # 4 Signature Moves
        specials = randomize_character_specials(hash(cid) & 0x7FFFFFFF)
        special_details = [
            {
                "slot": f"special_{s_idx+1:02d}",
                "key": sp_key,
                "name": SPECIAL_MOVES_CATALOG.get(sp_key, {}).get("name", sp_key),
                "desc": SPECIAL_MOVES_CATALOG.get(sp_key, {}).get("desc", ""),
                "category": SPECIAL_MOVES_CATALOG.get(sp_key, {}).get("category", "combat")
            }
            for s_idx, sp_key in enumerate(specials)
        ]

        # Metadata
        meta = {
            "character_name": cid,
            "display_name": display,
            "faction_id": sec_info["sector_id"],
            "faction_name": sec_info["sector_name"],
            "sector": sec_info["sector_name"],
            "model_engine": sec_info["model_engine"],
            "model_key": sec_info["model_key"],
            "theme_color": sec_info["theme_color"],
            "role": role,
            "weapon_id": weapon,
            "art_style": "anime",
            "specials": specials,
            "special_details": special_details
        }

        with open(char_dir / "metadata.json", "w", encoding="utf-8") as mf:
            json.dump(meta, mf, indent=2)

        # Godot 4 scene
        scene_file = scenes_root / f"{cid}_character.tscn"
        generate_godot_scene(cid, scene_file, specials)

        catalog.append(meta)
        if i % 10 == 0 or i == total:
            print(f"[{i:03d}/{total}] Generated '{display}' ({sec_info['sector_name']}) -> Sliced 15 limbs & Rigged 23 Anims")

    # Write full mega-roster catalog
    with open(sprites_root / "mega_roster_100.json", "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)

    print(f"\n[SUCCESS] Completed generation of all {len(catalog)} characters across 5 generative models!")
    print(f"Roster catalog written to: {sprites_root / 'mega_roster_100.json'}\n")


if __name__ == "__main__":
    run_generate_100_roster()
