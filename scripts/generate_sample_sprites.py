import os
import sys
import math
import random
import re
from PIL import Image, ImageDraw

def create_sprite(size, draw_func):
    """Render at 4x resolution for smooth anti-aliased edges, then downsample with LANCZOS."""
    scale = 4
    w, h = size[0] * scale, size[1] * scale
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw_func(draw, w, h, scale)
    return img.resize(size, Image.Resampling.LANCZOS)


# ==============================================================================
# Dynamic Prompt & Species Analyzer
# ==============================================================================
def detect_species(prompt: str, archetype: str = "") -> str:
    """Extracts the biological / thematic species from the user's prompt text."""
    p = (prompt + " " + archetype).lower()
    if any(k in p for k in ["alien", "xenomorph", "extraterrestrial", "martian", "biomechanic"]):
        return "alien"
    if any(k in p for k in ["demon", "fiend", "devil", "tiefling", "succubus", "oni", "hell"]):
        return "demon"
    if any(k in p for k in ["undead", "skeleton", "lich", "ghoul", "zombie", "skull", "bone", "necromancer"]):
        return "undead"
    if any(k in p for k in ["reptil", "lizard", "dragon", "drake", "serpent", "snake", "scale", "croc"]):
        return "reptilian"
    if any(k in p for k in ["insect", "mantis", "bug", "arachnid", "spider", "beetle", "chitin", "wasp", "ant"]):
        return "insectoid"
    if any(k in p for k in ["aquatic", "merfolk", "merman", "mermaid", "fish", "siren", "shark", "coral"]):
        return "aquatic"
    if any(k in p for k in ["plant", "dryad", "treant", "tree", "wood", "floral", "vine", "bark", "moss"]):
        return "plant"
    if any(k in p for k in ["slime", "ooze", "gelatin", "elemental", "blob"]):
        return "slime"
    if any(k in p for k in ["mech", "robot", "cyborg", "automaton", "android", "dieselpunk", "steampunk", "golem"]):
        return "mech"
    if any(k in p for k in ["beast", "wolf", "chimera", "hound", "tiger", "lion", "bear", "cat", "fox", "werewolf", "fenrir", "mount"]):
        return "beast"
    # Default to organic humanoid (human, elf, anime, caster, rogue, warrior)
    return "humanoid"


def build_palette(prompt: str, archetype: str = "", seed: int = 42) -> dict:
    """
    Extracts explicit colors from prompt or deterministically synthesizes
    a rich, harmonious 8-color palette tailored to the creature/humanoid type.
    """
    p = (prompt + " " + archetype).lower()
    rng = random.Random(seed if seed >= 0 else hash(prompt + archetype) & 0x7fffffff)
    species = detect_species(prompt, archetype)

    # Color keyword mapping
    has_cyan = any(k in p for k in ["cyan", "neon", "plasma", "blue", "azure", "electric", "ice", "frost", "sapphire", "crystal"])
    has_red = any(k in p for k in ["red", "crimson", "blood", "scarlet", "ruby", "flame", "fire", "lava"])
    has_green = any(k in p for k in ["green", "emerald", "jade", "toxic", "acid", "poison", "forest", "nature", "leaf"])
    has_purple = any(k in p for k in ["purple", "violet", "magenta", "arcane", "amethyst", "pink", "rose"])
    has_gold = any(k in p for k in ["gold", "golden", "amber", "yellow", "sun", "holy", "solar", "brass"])
    has_dark = any(k in p for k in ["black", "obsidian", "shadow", "dark", "void", "night", "stealth"])
    has_white = any(k in p for k in ["white", "silver", "pale", "bone", "snow", "pearl", "ghost"])

    # Base species skin/body defaults
    if species == "alien":
        # Sleek extraterrestrial slate-cyan / iridescent violet with neon crest
        skin_dark = (25, 38, 52, 255)
        skin_mid = (45, 75, 95, 255)
        skin_light = (75, 125, 150, 255)
        glow = (0, 255, 230, 255) if not has_purple else (230, 60, 255, 255)
        accent_mid = (130, 60, 190, 255) if not has_gold else (220, 170, 50, 255)
        accent_light = (190, 110, 255, 255)
        outline = (12, 18, 26, 255)
    elif species == "demon":
        skin_dark = (48, 16, 24, 255) if not has_dark else (24, 14, 20, 255)
        skin_mid = (95, 28, 42, 255)
        skin_light = (150, 48, 65, 255)
        glow = (255, 45, 30, 255) if not has_purple else (255, 30, 190, 255)
        accent_mid = (20, 18, 24, 255) # Obsidian horn color
        accent_light = (85, 80, 95, 255)
        outline = (14, 8, 12, 255)
    elif species == "undead":
        skin_dark = (45, 42, 40, 255)
        skin_mid = (160, 155, 145, 255) # Bone ivory
        skin_light = (225, 220, 205, 255)
        glow = (0, 240, 255, 255) if not has_green else (60, 255, 100, 255) # Soul flame
        accent_mid = (70, 55, 75, 255) # Tattered shroud
        accent_light = (115, 90, 125, 255)
        outline = (20, 18, 16, 255)
    elif species == "reptilian":
        skin_dark = (22, 45, 32, 255) if not has_red else (55, 25, 18, 255)
        skin_mid = (45, 92, 60, 255) if not has_red else (115, 52, 36, 255)
        skin_light = (85, 155, 105, 255) if not has_red else (185, 95, 65, 255)
        glow = (255, 210, 30, 255) # Slit yellow eyes
        accent_mid = (140, 100, 40, 255) # Horns/spikes
        accent_light = (210, 160, 75, 255)
        outline = (12, 24, 18, 255)
    elif species == "insectoid":
        skin_dark = (30, 25, 40, 255)
        skin_mid = (58, 48, 80, 255)
        skin_light = (98, 85, 135, 255)
        glow = (80, 255, 90, 255) # Phosphor eyes
        accent_mid = (175, 95, 30, 255)
        accent_light = (240, 155, 60, 255)
        outline = (15, 12, 20, 255)
    elif species == "beast":
        skin_dark = (35, 28, 24, 255) if not has_white else (70, 75, 85, 255)
        skin_mid = (75, 60, 52, 255) if not has_white else (160, 168, 180, 255)
        skin_light = (130, 108, 92, 255) if not has_white else (230, 235, 245, 255)
        glow = (255, 165, 20, 255) if not has_cyan else (0, 230, 255, 255)
        accent_mid = (165, 115, 65, 255)
        accent_light = (225, 175, 110, 255)
        outline = (16, 12, 10, 255)
    elif species == "plant":
        skin_dark = (35, 28, 18, 255) # Bark
        skin_mid = (85, 65, 42, 255)
        skin_light = (135, 105, 70, 255)
        glow = (255, 80, 180, 255) # Flower bloom
        accent_mid = (45, 125, 55, 255) # Foliage
        accent_light = (95, 195, 105, 255)
        outline = (18, 14, 8, 255)
    elif species == "slime":
        skin_dark = (15, 45, 55, 200)
        skin_mid = (35, 110, 130, 220)
        skin_light = (85, 195, 220, 240)
        glow = (120, 255, 255, 255)
        accent_mid = (200, 60, 180, 255)
        accent_light = (255, 130, 240, 255)
        outline = (10, 30, 38, 255)
    elif species == "mech":
        skin_dark = (38, 40, 45, 255)
        skin_mid = (70, 75, 85, 255)
        skin_light = (120, 128, 145, 255)
        glow = (255, 140, 0, 255) if not has_cyan else (0, 240, 255, 255)
        accent_mid = (220, 145, 25, 255)
        accent_light = (255, 200, 60, 255)
        outline = (18, 18, 22, 255)
    else:
        # Organic Human / Elf: Natural skin tone with anime hair and stylish clothing
        skin_tones = [
            # Porcelain / fair
            ((175, 145, 135, 255), (235, 205, 190, 255), (255, 235, 225, 255)),
            # Warm peach / anime standard
            ((185, 135, 115, 255), (245, 195, 165, 255), (255, 225, 205, 255)),
            # Golden tan
            ((150, 105, 75, 255), (210, 155, 115, 255), (240, 190, 150, 255)),
            # Rich bronze / deep
            ((95, 60, 42, 255), (145, 95, 68, 255), (185, 130, 98, 255)),
        ]
        chosen_tone = skin_tones[rng.randint(0, len(skin_tones) - 1)]
        skin_dark, skin_mid, skin_light = chosen_tone

        # Hair & clothing color
        if has_cyan or archetype == "mage":
            accent_mid = (65, 45, 125, 255)
            accent_light = (130, 95, 215, 255)
            glow = (0, 230, 255, 255)
        elif has_red or archetype == "assassin":
            accent_mid = (135, 25, 40, 255)
            accent_light = (210, 50, 70, 255)
            glow = (255, 40, 50, 255)
        elif has_green or archetype == "ranger":
            accent_mid = (45, 95, 60, 255)
            accent_light = (90, 165, 110, 255)
            glow = (45, 245, 130, 255)
        else:
            # Regal blue / gold warrior or custom
            accent_mid = (45, 65, 115, 255)
            accent_light = (215, 165, 45, 255)
            glow = (255, 215, 60, 255)

        outline = (22, 16, 18, 255)

    # Prompt overrides for glow
    if has_red and glow[0] < 180:
        glow = (255, 40, 50, 255)
    elif has_cyan and glow[1] < 180:
        glow = (0, 240, 255, 255)
    elif has_green and glow[1] < 180:
        glow = (40, 245, 110, 255)
    elif has_purple and glow[0] < 180:
        glow = (245, 50, 230, 255)
    elif has_gold and glow[0] < 180:
        glow = (255, 205, 40, 255)

    glow_core = (
        min(255, glow[0] + 70),
        min(255, glow[1] + 70),
        min(255, glow[2] + 70),
        255
    )

    return {
        "species": species,
        "primary_dark": skin_dark,
        "primary_mid": skin_mid,
        "primary_light": skin_light,
        "accent_dark": (max(0, accent_mid[0]-40), max(0, accent_mid[1]-40), max(0, accent_mid[2]-40), 255),
        "accent_mid": accent_mid,
        "accent_light": accent_light,
        "glow": glow,
        "glow_core": glow_core,
        "outline": outline,
    }


# ==============================================================================
# Procedural Anatomical Drawing Routines
# ==============================================================================

def draw_head(draw, w, h, s, theme, seed=42):
    cx, cy = w // 2, h // 2
    sp = theme["species"]
    rng = random.Random(seed)

    if sp == "alien":
        # 👾 Elongated bulbous cranium sloping back
        draw.polygon([
            (cx - 14*s, cy + 18*s), # Chin
            (cx - 18*s, cy + 4*s),  # Cheek
            (cx - 22*s, cy - 8*s),  # Temple
            (cx - 18*s, cy - 24*s), # Forehead base
            (cx, cy - 30*s),        # Elongated cranial crest tip
            (cx + 18*s, cy - 24*s),
            (cx + 22*s, cy - 8*s),
            (cx + 18*s, cy + 4*s),
            (cx + 14*s, cy + 18*s),
            (cx, cy + 24*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

        # Cranium biomechanical highlight
        draw.polygon([
            (cx - 12*s, cy - 10*s),
            (cx - 8*s, cy - 24*s),
            (cx, cy - 27*s),
            (cx + 8*s, cy - 24*s),
            (cx + 12*s, cy - 10*s),
            (cx, cy - 6*s)
        ], fill=theme["primary_light"])

        # Bioluminescent forehead crest & veins
        draw.line([(cx, cy - 26*s), (cx, cy - 8*s)], fill=theme["glow"], width=2*s)
        draw.line([(cx - 7*s, cy - 18*s), (cx + 7*s, cy - 18*s)], fill=theme["glow"], width=s)

        # Alien glowing triple-ocular sensory cluster
        # Center eye
        draw.ellipse([cx - 4*s, cy - 4*s, cx + 4*s, cy + 4*s], fill=theme["glow"], outline=theme["outline"], width=s)
        draw.ellipse([cx - 2*s, cy - 2*s, cx + 2*s, cy + 2*s], fill=theme["glow_core"])
        # Left & right peripheral sensory eyes
        draw.ellipse([cx - 14*s, cy - 2*s, cx - 8*s, cy + 3*s], fill=theme["glow"])
        draw.ellipse([cx + 8*s, cy - 2*s, cx + 14*s, cy + 3*s], fill=theme["glow"])

        # Alien bio-vent slits on jaw
        draw.line([(cx - 8*s, cy + 12*s), (cx - 3*s, cy + 12*s)], fill=theme["outline"], width=s)
        draw.line([(cx + 3*s, cy + 12*s), (cx + 8*s, cy + 12*s)], fill=theme["outline"], width=s)
        draw.line([(cx - 6*s, cy + 16*s), (cx + 6*s, cy + 16*s)], fill=theme["outline"], width=s)

    elif sp == "demon":
        # 😈 Menacing horned demon
        # Sweeping curved demonic horns
        # Left Horn
        draw.polygon([
            (cx - 12*s, cy - 12*s),
            (cx - 24*s, cy - 22*s),
            (cx - 28*s, cy - 36*s), # Horn tip
            (cx - 18*s, cy - 28*s),
            (cx - 6*s, cy - 14*s)
        ], fill=theme["accent_mid"], outline=theme["outline"], width=2*s)
        draw.polygon([(cx - 26*s, cy - 34*s), (cx - 21*s, cy - 28*s), (cx - 16*s, cy - 24*s)], fill=theme["accent_light"])

        # Right Horn
        draw.polygon([
            (cx + 12*s, cy - 12*s),
            (cx + 24*s, cy - 22*s),
            (cx + 28*s, cy - 36*s), # Horn tip
            (cx + 18*s, cy - 28*s),
            (cx + 6*s, cy - 14*s)
        ], fill=theme["accent_mid"], outline=theme["outline"], width=2*s)
        draw.polygon([(cx + 26*s, cy - 34*s), (cx + 21*s, cy - 28*s), (cx + 16*s, cy - 24*s)], fill=theme["accent_light"])

        # Demon face
        draw.polygon([
            (cx - 16*s, cy - 12*s),
            (cx + 16*s, cy - 12*s),
            (cx + 14*s, cy + 6*s),
            (cx + 8*s, cy + 18*s),
            (cx, cy + 24*s), # Sharp chin
            (cx - 8*s, cy + 18*s),
            (cx - 14*s, cy + 6*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

        # Forehead demonic runic mark
        draw.polygon([
            (cx, cy - 10*s),
            (cx + 4*s, cy - 4*s),
            (cx, cy + 1*s),
            (cx - 4*s, cy - 4*s)
        ], fill=theme["glow"])

        # Piercing glowing eyes
        draw.polygon([(cx - 11*s, cy), (cx - 4*s, cy - 2*s), (cx - 3*s, cy + 3*s), (cx - 10*s, cy + 3*s)], fill=theme["glow"])
        draw.polygon([(cx + 11*s, cy), (cx + 4*s, cy - 2*s), (cx + 3*s, cy + 3*s), (cx + 10*s, cy + 3*s)], fill=theme["glow"])
        draw.ellipse([cx - 7*s, cy, cx - 5*s, cy + 2*s], fill=theme["glow_core"])
        draw.ellipse([cx + 5*s, cy, cx + 7*s, cy + 2*s], fill=theme["glow_core"])

        # Mouth with fangs
        draw.line([(cx - 6*s, cy + 12*s), (cx + 6*s, cy + 12*s)], fill=theme["outline"], width=2*s)
        draw.polygon([(cx - 4*s, cy + 12*s), (cx - 3*s, cy + 16*s), (cx - 2*s, cy + 12*s)], fill=(255, 255, 255, 255))
        draw.polygon([(cx + 2*s, cy + 12*s), (cx + 3*s, cy + 16*s), (cx + 4*s, cy + 12*s)], fill=(255, 255, 255, 255))

    elif sp == "undead":
        # 💀 Bony skull with glowing soul sockets
        draw.polygon([
            (cx - 14*s, cy - 18*s),
            (cx + 14*s, cy - 18*s),
            (cx + 16*s, cy - 4*s),
            (cx + 12*s, cy + 6*s),  # Cheekbone
            (cx + 8*s, cy + 18*s),  # Upper teeth
            (cx - 8*s, cy + 18*s),
            (cx - 12*s, cy + 6*s),
            (cx - 16*s, cy - 4*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

        # Temple hollows
        draw.polygon([(cx - 14*s, cy), (cx - 10*s, cy), (cx - 12*s, cy + 6*s)], fill=theme["primary_dark"])
        draw.polygon([(cx + 14*s, cy), (cx + 10*s, cy), (cx + 12*s, cy + 6*s)], fill=theme["primary_dark"])

        # Hollow eye sockets with floating soul fire
        draw.ellipse([cx - 10*s, cy - 4*s, cx - 3*s, cy + 4*s], fill=theme["outline"])
        draw.ellipse([cx + 3*s, cy - 4*s, cx + 10*s, cy + 4*s], fill=theme["outline"])
        draw.ellipse([cx - 8*s, cy - 2*s, cx - 5*s, cy + 2*s], fill=theme["glow"])
        draw.ellipse([cx + 5*s, cy - 2*s, cx + 8*s, cy + 2*s], fill=theme["glow"])
        draw.ellipse([cx - 7*s, cy - 1*s, cx - 6*s, cy + 1*s], fill=theme["glow_core"])
        draw.ellipse([cx + 6*s, cy - 1*s, cx + 7*s, cy + 1*s], fill=theme["glow_core"])

        # Inverted heart nasal cavity
        draw.polygon([(cx - 2*s, cy + 7*s), (cx, cy + 4*s), (cx + 2*s, cy + 7*s)], fill=theme["outline"])

        # Articulated teeth row
        for tx in range(-6, 7, 3):
            draw.line([(cx + tx*s, cy + 12*s), (cx + tx*s, cy + 17*s)], fill=theme["outline"], width=s)

    elif sp == "reptilian":
        # 🦎 Dragon / Reptilian snout with horns and scales
        # Dragon brow horns
        draw.polygon([(cx - 10*s, cy - 10*s), (cx - 24*s, cy - 24*s), (cx - 14*s, cy - 18*s)], fill=theme["accent_mid"], outline=theme["outline"], width=s)
        draw.polygon([(cx + 10*s, cy - 10*s), (cx + 24*s, cy - 24*s), (cx + 14*s, cy - 18*s)], fill=theme["accent_mid"], outline=theme["outline"], width=s)

        # Scaled head
        draw.polygon([
            (cx - 16*s, cy - 12*s),
            (cx + 16*s, cy - 12*s),
            (cx + 18*s, cy + 2*s),
            (cx + 12*s, cy + 18*s),
            (cx + 4*s, cy + 24*s),  # Snout
            (cx - 4*s, cy + 24*s),
            (cx - 12*s, cy + 18*s),
            (cx - 18*s, cy + 2*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

        # Reptilian vertical slit eyes
        draw.ellipse([cx - 12*s, cy - 2*s, cx - 5*s, cy + 5*s], fill=theme["glow"], outline=theme["outline"], width=s)
        draw.ellipse([cx + 5*s, cy - 2*s, cx + 12*s, cy + 5*s], fill=theme["glow"], outline=theme["outline"], width=s)
        draw.line([(cx - 8*s, cy - 1*s), (cx - 8*s, cy + 4*s)], fill=theme["outline"], width=2*s)
        draw.line([(cx + 8*s, cy - 1*s), (cx + 8*s, cy + 4*s)], fill=theme["outline"], width=2*s)

        # Nostrils and serrated jaw
        draw.ellipse([cx - 3*s, cy + 16*s, cx - 1*s, cy + 18*s], fill=theme["outline"])
        draw.ellipse([cx + 1*s, cy + 16*s, cx + 3*s, cy + 18*s], fill=theme["outline"])
        draw.line([(cx - 8*s, cy + 20*s), (cx + 8*s, cy + 20*s)], fill=theme["outline"], width=s)

    elif sp == "insectoid":
        # 🦗 Insectoid triangular carapace head with antennae & compound eyes
        # Long curved antennae
        draw.line([(cx - 6*s, cy - 12*s), (cx - 22*s, cy - 32*s)], fill=theme["accent_light"], width=2*s)
        draw.line([(cx + 6*s, cy - 12*s), (cx + 22*s, cy - 32*s)], fill=theme["accent_light"], width=2*s)

        # Carapace head
        draw.polygon([
            (cx - 16*s, cy - 16*s),
            (cx + 16*s, cy - 16*s),
            (cx + 20*s, cy),
            (cx + 6*s, cy + 22*s),
            (cx - 6*s, cy + 22*s),
            (cx - 20*s, cy)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

        # Large multifaceted compound eyes
        draw.ellipse([cx - 18*s, cy - 8*s, cx - 7*s, cy + 8*s], fill=theme["glow"], outline=theme["outline"], width=s)
        draw.ellipse([cx + 7*s, cy - 8*s, cx + 18*s, cy + 8*s], fill=theme["glow"], outline=theme["outline"], width=s)

        # Clicking mandibles
        draw.polygon([(cx - 8*s, cy + 14*s), (cx - 3*s, cy + 26*s), (cx - 1*s, cy + 18*s)], fill=theme["accent_mid"], outline=theme["outline"])
        draw.polygon([(cx + 8*s, cy + 14*s), (cx + 3*s, cy + 26*s), (cx + 1*s, cy + 18*s)], fill=theme["accent_mid"], outline=theme["outline"])

    elif sp == "mech":
        # 🤖 Robotic helmet with visor
        draw.polygon([
            (cx - 18*s, cy - 20*s),
            (cx + 18*s, cy - 20*s),
            (cx + 20*s, cy + 4*s),
            (cx + 14*s, cy + 18*s),
            (cx, cy + 22*s),
            (cx - 14*s, cy + 18*s),
            (cx - 20*s, cy + 4*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
        # Antenna / ear bolt
        draw.rectangle([cx - 22*s, cy - 4*s, cx - 18*s, cy + 4*s], fill=theme["accent_mid"])
        draw.rectangle([cx + 18*s, cy - 4*s, cx + 22*s, cy + 4*s], fill=theme["accent_mid"])
        # Glowing visor slit
        draw.rectangle([cx - 14*s, cy - 2*s, cx + 14*s, cy + 4*s], fill=theme["glow"], outline=theme["outline"], width=s)
        draw.rectangle([cx - 10*s, cy - 1*s, cx + 10*s, cy + 3*s], fill=theme["glow_core"])

    else:
        # 🧝 Humanoid / Elf with organic skin, expressive anime eyes, and styled hair
        # Base skin face
        draw.polygon([
            (cx - 13*s, cy - 10*s),
            (cx + 13*s, cy - 10*s),
            (cx + 14*s, cy + 4*s),
            (cx + 8*s, cy + 16*s),
            (cx, cy + 21*s), # Chin
            (cx - 8*s, cy + 16*s),
            (cx - 14*s, cy + 4*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

        # Elven pointed ears or earrings
        draw.polygon([(cx - 14*s, cy - 4*s), (cx - 22*s, cy - 10*s), (cx - 13*s, cy + 4*s)], fill=theme["primary_mid"], outline=theme["outline"], width=s)
        draw.polygon([(cx + 14*s, cy - 4*s), (cx + 22*s, cy - 10*s), (cx + 13*s, cy + 4*s)], fill=theme["primary_mid"], outline=theme["outline"], width=s)

        # Expressive anime eyes (colored iris, pupil, highlight sparkle)
        # Left eye
        draw.ellipse([cx - 11*s, cy - 1*s, cx - 4*s, cy + 7*s], fill=(255, 255, 255, 255), outline=theme["outline"], width=s)
        draw.ellipse([cx - 9*s, cy, cx - 5*s, cy + 6*s], fill=theme["glow"])
        draw.ellipse([cx - 8*s, cy + 1*s, cx - 6*s, cy + 4*s], fill=theme["outline"])
        draw.ellipse([cx - 8*s, cy, cx - 7*s, cy + 2*s], fill=(255, 255, 255, 255)) # Sparkle

        # Right eye
        draw.ellipse([cx + 4*s, cy - 1*s, cx + 11*s, cy + 7*s], fill=(255, 255, 255, 255), outline=theme["outline"], width=s)
        draw.ellipse([cx + 5*s, cy, cx + 9*s, cy + 6*s], fill=theme["glow"])
        draw.ellipse([cx + 6*s, cy + 1*s, cx + 8*s, cy + 4*s], fill=theme["outline"])
        draw.ellipse([cx + 6*s, cy, cx + 7*s, cy + 2*s], fill=(255, 255, 255, 255)) # Sparkle

        # Delicate mouth & eyebrows
        draw.line([(cx - 10*s, cy - 4*s), (cx - 4*s, cy - 5*s)], fill=theme["accent_mid"], width=s)
        draw.line([(cx + 4*s, cy - 5*s), (cx + 10*s, cy - 4*s)], fill=theme["accent_mid"], width=s)
        draw.line([(cx - 3*s, cy + 13*s), (cx + 3*s, cy + 13*s)], fill=theme["primary_dark"], width=s)

        # Stylized anime hair / bangs / crown
        draw.polygon([
            (cx - 17*s, cy + 6*s),
            (cx - 16*s, cy - 14*s),
            (cx - 8*s, cy - 26*s),
            (cx, cy - 28*s),
            (cx + 8*s, cy - 26*s),
            (cx + 16*s, cy - 14*s),
            (cx + 17*s, cy + 6*s),
            (cx + 13*s, cy - 2*s),
            (cx + 7*s, cy - 6*s),
            (cx + 2*s, cy - 2*s),  # Center bang tuft
            (cx - 3*s, cy - 5*s),
            (cx - 8*s, cy - 1*s),
            (cx - 13*s, cy - 2*s)
        ], fill=theme["accent_mid"], outline=theme["outline"], width=2*s)
        draw.polygon([(cx - 12*s, cy - 20*s), (cx, cy - 24*s), (cx + 6*s, cy - 18*s)], fill=theme["accent_light"])


def draw_torso(draw, w, h, s, theme, seed=42):
    cx, cy = w // 2, h // 2
    sp = theme["species"]

    if sp == "alien":
        # 👾 Biomechanical carapace with glowing bio-core
        draw.polygon([
            (cx - 24*s, cy - 22*s),
            (cx + 24*s, cy - 22*s),
            (cx + 20*s, cy + 6*s),
            (cx + 14*s, cy + 24*s),
            (cx, cy + 28*s),
            (cx - 14*s, cy + 24*s),
            (cx - 20*s, cy + 6*s)
        ], fill=theme["primary_dark"], outline=theme["outline"], width=2*s)

        # Side biomechanical ribs
        for ry in [-12, -2, 8]:
            draw.line([(cx - 20*s, cy + ry*s), (cx - 8*s, cy + ry*s)], fill=theme["primary_light"], width=2*s)
            draw.line([(cx + 8*s, cy + ry*s), (cx + 20*s, cy + ry*s)], fill=theme["primary_light"], width=2*s)

        # Central glowing pulsating alien core
        draw.ellipse([cx - 8*s, cy - 8*s, cx + 8*s, cy + 8*s], fill=theme["primary_dark"], outline=theme["glow"], width=2*s)
        draw.ellipse([cx - 5*s, cy - 5*s, cx + 5*s, cy + 5*s], fill=theme["glow"])
        draw.ellipse([cx - 2*s, cy - 2*s, cx + 2*s, cy + 2*s], fill=theme["glow_core"])

    elif sp == "demon":
        # 😈 Muscular demonic torso with fiery runic scar/brand
        draw.polygon([
            (cx - 26*s, cy - 22*s),
            (cx + 26*s, cy - 22*s),
            (cx + 22*s, cy + 4*s),
            (cx + 14*s, cy + 24*s),
            (cx, cy + 28*s),
            (cx - 14*s, cy + 24*s),
            (cx - 22*s, cy + 4*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

        # Pectoral & ab shading
        draw.line([(cx, cy - 18*s), (cx, cy + 18*s)], fill=theme["primary_dark"], width=2*s)
        draw.arc([cx - 18*s, cy - 14*s, cx - 2*s, cy - 2*s], 0, 180, fill=theme["primary_dark"], width=2*s)
        draw.arc([cx + 2*s, cy - 14*s, cx + 18*s, cy - 2*s], 0, 180, fill=theme["primary_dark"], width=2*s)

        # Glowing fiery runic scar
        draw.polygon([
            (cx, cy - 6*s),
            (cx + 7*s, cy),
            (cx, cy + 6*s),
            (cx - 7*s, cy)
        ], fill=theme["glow"], outline=theme["outline"], width=s)
        draw.ellipse([cx - 2*s, cy - 2*s, cx + 2*s, cy + 2*s], fill=theme["glow_core"])

    elif sp == "undead":
        # 💀 Exposed skeletal ribcage with floating soul orb
        draw.rectangle([cx - 20*s, cy - 20*s, cx + 20*s, cy + 24*s], fill=theme["outline"])
        # Central spine column
        draw.rectangle([cx - 4*s, cy - 22*s, cx + 4*s, cy + 26*s], fill=theme["primary_mid"], outline=theme["primary_dark"], width=s)

        # Rib pairs curving around
        for ry in [-14, -6, 2, 10]:
            draw.arc([cx - 20*s, cy + (ry-4)*s, cx - 2*s, cy + (ry+6)*s], 180, 360, fill=theme["primary_light"], width=3*s)
            draw.arc([cx + 2*s, cy + (ry-4)*s, cx + 20*s, cy + (ry+6)*s], 180, 360, fill=theme["primary_light"], width=3*s)

        # Floating soul orb inside chest
        draw.ellipse([cx - 6*s, cy - 4*s, cx + 6*s, cy + 8*s], fill=theme["glow"])
        draw.ellipse([cx - 2*s, cy - 1*s, cx + 2*s, cy + 4*s], fill=theme["glow_core"])

    else:
        # 🧝 Humanoid / Adventurer cloth tunic / robe / leather doublet
        draw.polygon([
            (cx - 24*s, cy - 22*s),
            (cx + 24*s, cy - 22*s),
            (cx + 20*s, cy + 6*s),
            (cx + 14*s, cy + 24*s),
            (cx, cy + 26*s),
            (cx - 14*s, cy + 24*s),
            (cx - 20*s, cy + 6*s)
        ], fill=theme["accent_mid"], outline=theme["outline"], width=2*s)

        # V-neck / collar / open vest showing skin or shirt
        draw.polygon([
            (cx - 10*s, cy - 22*s),
            (cx + 10*s, cy - 22*s),
            (cx, cy - 4*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=s)

        # Trim lapels and center buttons / buckle
        draw.line([(cx - 10*s, cy - 22*s), (cx, cy + 20*s)], fill=theme["accent_light"], width=2*s)
        draw.line([(cx + 10*s, cy - 22*s), (cx, cy + 20*s)], fill=theme["accent_light"], width=2*s)
        # Gem / Brooch / Core
        draw.ellipse([cx - 4*s, cy - 6*s, cx + 4*s, cy + 2*s], fill=theme["glow"], outline=theme["outline"], width=s)
        draw.ellipse([cx - 1*s, cy - 4*s, cx + 1*s, cy - 1*s], fill=theme["glow_core"])


def draw_pelvis(draw, w, h, s, theme, seed=42):
    cx, cy = w // 2, h // 2
    sp = theme["species"]

    if sp in ["alien", "insectoid"]:
        # Chitinous abdominal girdle
        draw.polygon([
            (cx - 20*s, cy - 12*s),
            (cx + 20*s, cy - 12*s),
            (cx + 16*s, cy + 14*s),
            (cx, cy + 18*s),
            (cx - 16*s, cy + 14*s)
        ], fill=theme["primary_dark"], outline=theme["outline"], width=2*s)
        draw.line([(cx - 12*s, cy), (cx + 12*s, cy)], fill=theme["glow"], width=s)
    elif sp == "undead":
        # Skeletal pelvic bone
        draw.polygon([
            (cx - 22*s, cy - 10*s),
            (cx + 22*s, cy - 10*s),
            (cx + 18*s, cy + 6*s),
            (cx, cy + 14*s),
            (cx - 18*s, cy + 6*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
        draw.ellipse([cx - 14*s, cy - 4*s, cx - 6*s, cy + 4*s], fill=theme["outline"])
        draw.ellipse([cx + 6*s, cy - 4*s, cx + 14*s, cy + 4*s], fill=theme["outline"])
    else:
        # Adventurer belt / sash / waist
        draw.rectangle([cx - 22*s, cy - 12*s, cx + 22*s, cy - 2*s], fill=theme["accent_dark"], outline=theme["outline"], width=s)
        # Folded sash / loincloth
        draw.polygon([
            (cx - 18*s, cy - 2*s),
            (cx + 18*s, cy - 2*s),
            (cx + 12*s, cy + 16*s),
            (cx, cy + 18*s),
            (cx - 12*s, cy + 16*s)
        ], fill=theme["accent_mid"], outline=theme["outline"], width=2*s)
        # Ornate buckle
        draw.rectangle([cx - 6*s, cy - 10*s, cx + 6*s, cy - 4*s], fill=theme["accent_light"], outline=theme["outline"], width=s)


def draw_arm_upper(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    sp = theme["species"]

    if sp == "alien":
        # Slender organic limb with glowing elbow node
        draw.polygon([
            (cx - 10*s, cy - 18*s),
            (cx + 10*s, cy - 18*s),
            (cx + 12*s, cy),
            (cx + 8*s, cy + 18*s),
            (cx - 8*s, cy + 18*s),
            (cx - 12*s, cy)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
        draw.ellipse([cx - 4*s, cy + 12*s, cx + 4*s, cy + 20*s], fill=theme["glow"])
    elif sp == "undead":
        # Bone shaft (humerus)
        draw.ellipse([cx - 8*s, cy - 18*s, cx + 8*s, cy - 10*s], fill=theme["primary_mid"], outline=theme["outline"], width=s)
        draw.rectangle([cx - 4*s, cy - 12*s, cx + 4*s, cy + 14*s], fill=theme["primary_light"], outline=theme["outline"], width=s)
        draw.ellipse([cx - 7*s, cy + 12*s, cx + 7*s, cy + 20*s], fill=theme["primary_mid"], outline=theme["outline"], width=s)
    else:
        # Organic muscular arm / cloth sleeve
        draw.polygon([
            (cx - 12*s, cy - 18*s),
            (cx + 12*s, cy - 18*s),
            (cx + 14*s, cy - 2*s),
            (cx + 9*s, cy + 18*s),
            (cx - 9*s, cy + 18*s),
            (cx - 14*s, cy - 2*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
        # Cuff / bracelet
        draw.rectangle([cx - 11*s, cy + 12*s, cx + 11*s, cy + 18*s], fill=theme["accent_mid"], outline=theme["outline"], width=s)


def draw_arm_lower(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    sp = theme["species"]

    if sp == "alien":
        draw.polygon([
            (cx - 8*s, cy - 16*s),
            (cx + 8*s, cy - 16*s),
            (cx + 10*s, cy + 4*s),
            (cx + 7*s, cy + 18*s),
            (cx - 7*s, cy + 18*s),
            (cx - 10*s, cy + 4*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
        draw.line([(cx, cy - 12*s), (cx, cy + 14*s)], fill=theme["glow"], width=s)
    elif sp == "undead":
        # Dual forearm bones (radius & ulna)
        draw.line([(cx - 3*s, cy - 14*s), (cx - 3*s, cy + 16*s)], fill=theme["primary_light"], width=2*s)
        draw.line([(cx + 3*s, cy - 14*s), (cx + 3*s, cy + 16*s)], fill=theme["primary_light"], width=2*s)
    else:
        draw.polygon([
            (cx - 10*s, cy - 16*s),
            (cx + 10*s, cy - 16*s),
            (cx + 11*s, cy + 4*s),
            (cx + 7*s, cy + 18*s),
            (cx - 7*s, cy + 18*s),
            (cx - 11*s, cy + 4*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
        # Vambrace / glove cuff
        draw.rectangle([cx - 9*s, cy + 8*s, cx + 9*s, cy + 16*s], fill=theme["accent_mid"], outline=theme["outline"], width=s)


def draw_hand(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    sp = theme["species"]

    if sp in ["alien", "demon", "reptilian"]:
        # 👾 Sharp clawed hand with distinct talons
        draw.polygon([
            (cx - 8*s, cy - 8*s),
            (cx + 8*s, cy - 8*s),
            (cx + 9*s, cy + 2*s),
            (cx - 9*s, cy + 2*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=s)
        # 4 elongated claw talons
        for ox in [-6, -2, 2, 6]:
            draw.polygon([
                (cx + (ox-1)*s, cy + 2*s),
                (cx + ox*s, cy + 12*s), # Claw tip
                (cx + (ox+1)*s, cy + 2*s)
            ], fill=theme["accent_light"], outline=theme["outline"], width=s)
    elif sp == "undead":
        # Bony fingers
        for ox in [-6, -2, 2, 6]:
            draw.line([(cx + ox*s, cy - 4*s), (cx + ox*s, cy + 10*s)], fill=theme["primary_light"], width=2*s)
            draw.ellipse([cx + (ox-1)*s, cy + 8*s, cx + (ox+1)*s, cy + 11*s], fill=theme["outline"])
    else:
        # 🧝 Organic humanoid hand with fingers and thumb
        thumb_mul = -1 if is_left else 1
        # Palm
        draw.polygon([
            (cx - 8*s, cy - 8*s),
            (cx + 8*s, cy - 8*s),
            (cx + 8*s, cy + 4*s),
            (cx - 8*s, cy + 4*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=s)
        # Thumb
        draw.polygon([
            (cx + 6*s * thumb_mul, cy - 4*s),
            (cx + 12*s * thumb_mul, cy + 2*s),
            (cx + 6*s * thumb_mul, cy + 4*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=s)
        # Fingers
        for fx in [-6, -2, 2]:
            draw.rectangle([cx + fx*s, cy + 4*s, cx + (fx+3)*s, cy + 10*s], fill=theme["primary_light"], outline=theme["outline"], width=s)


def draw_leg_upper(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    sp = theme["species"]

    if sp == "undead":
        # Femur bone
        draw.ellipse([cx - 8*s, cy - 20*s, cx + 8*s, cy - 12*s], fill=theme["primary_mid"], outline=theme["outline"], width=s)
        draw.rectangle([cx - 5*s, cy - 14*s, cx + 5*s, cy + 14*s], fill=theme["primary_light"], outline=theme["outline"], width=s)
        draw.ellipse([cx - 8*s, cy + 12*s, cx + 8*s, cy + 20*s], fill=theme["primary_mid"], outline=theme["outline"], width=s)
    else:
        # Muscular thigh
        draw.polygon([
            (cx - 13*s, cy - 20*s),
            (cx + 13*s, cy - 20*s),
            (cx + 14*s, cy),
            (cx + 9*s, cy + 20*s),
            (cx - 9*s, cy + 20*s),
            (cx - 14*s, cy)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
        # Thigh guard / pants crease
        draw.line([(cx, cy - 14*s), (cx, cy + 12*s)], fill=theme["primary_light"], width=s)


def draw_leg_lower(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    sp = theme["species"]

    if sp == "undead":
        # Tibia & fibula
        draw.line([(cx - 3*s, cy - 16*s), (cx - 3*s, cy + 16*s)], fill=theme["primary_light"], width=2*s)
        draw.line([(cx + 3*s, cy - 16*s), (cx + 3*s, cy + 16*s)], fill=theme["primary_light"], width=2*s)
    else:
        draw.polygon([
            (cx - 11*s, cy - 18*s),
            (cx + 11*s, cy - 18*s),
            (cx + 12*s, cy),
            (cx + 8*s, cy + 20*s),
            (cx - 8*s, cy + 20*s),
            (cx - 12*s, cy)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
        # Greave / boot fold
        draw.polygon([
            (cx - 8*s, cy - 8*s),
            (cx + 8*s, cy - 8*s),
            (cx + 6*s, cy + 16*s),
            (cx - 6*s, cy + 16*s)
        ], fill=theme["accent_mid"], outline=theme["outline"], width=s)


def draw_foot(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    sp = theme["species"]
    dir_mul = 1 if is_left else -1

    if sp in ["alien", "demon", "reptilian"]:
        # Digitigrade clawed foot with 3 sharp talons
        draw.polygon([
            (cx - 12*s * dir_mul, cy - 8*s),
            (cx + 10*s * dir_mul, cy - 8*s),
            (cx + 16*s * dir_mul, cy + 2*s),
            (cx + 20*s * dir_mul, cy + 8*s), # Front claw
            (cx - 14*s * dir_mul, cy + 8*s)  # Heel claw
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
        # Talons
        for tox in [6, 12, 18]:
            draw.polygon([
                (cx + tox*s * dir_mul, cy + 4*s),
                (cx + (tox+4)*s * dir_mul, cy + 10*s),
                (cx + tox*s * dir_mul, cy + 9*s)
            ], fill=theme["accent_light"], outline=theme["outline"], width=s)
    elif sp == "undead":
        # Skeletal foot bones
        draw.line([(cx - 10*s * dir_mul, cy - 4*s), (cx + 16*s * dir_mul, cy + 4*s)], fill=theme["primary_light"], width=3*s)
        for tx in [4, 10, 16]:
            draw.line([(cx + tx*s * dir_mul, cy + 2*s), (cx + (tx+3)*s * dir_mul, cy + 8*s)], fill=theme["primary_light"], width=2*s)
    else:
        # 🧝 Adventurer boot / sandal
        draw.polygon([
            (cx - 14*s * dir_mul, cy - 8*s),
            (cx + 8*s * dir_mul, cy - 8*s),
            (cx + 18*s * dir_mul, cy + 4*s),
            (cx + 22*s * dir_mul, cy + 8*s), # Toe
            (cx - 14*s * dir_mul, cy + 8*s)  # Heel
        ], fill=theme["accent_dark"], outline=theme["outline"], width=2*s)
        # Sole & cuff
        rx0 = min(cx - 14*s * dir_mul, cx + 22*s * dir_mul)
        rx1 = max(cx - 14*s * dir_mul, cx + 22*s * dir_mul)
        draw.rectangle([rx0, cy + 6*s, rx1, cy + 9*s], fill=theme["outline"])
        draw.line([(cx - 12*s * dir_mul, cy - 4*s), (cx + 6*s * dir_mul, cy - 4*s)], fill=theme["accent_light"], width=2*s)


# ==============================================================================
# Quadruped / Beast Specific Drawers
# ==============================================================================

def draw_beast_head(draw, w, h, s, theme, seed=42):
    cx, cy = w // 2, h // 2
    # Canine / Feline predatory snout with ears and glowing eyes
    draw.polygon([
        (cx - 20*s, cy + 10*s),
        (cx - 16*s, cy - 10*s),
        (cx - 14*s, cy - 26*s), # Left ear tip
        (cx - 6*s, cy - 14*s),
        (cx + 6*s, cy - 14*s),
        (cx + 14*s, cy - 26*s), # Right ear tip
        (cx + 16*s, cy - 10*s),
        (cx + 26*s, cy + 4*s),  # Snout
        (cx + 24*s, cy + 16*s), # Jaw
        (cx + 4*s, cy + 20*s),
        (cx - 16*s, cy + 18*s)
    ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

    # Snout bridge highlight
    draw.polygon([(cx, cy - 8*s), (cx + 20*s, cy + 4*s), (cx + 6*s, cy + 12*s)], fill=theme["primary_light"])
    # Glowing predatory eye
    draw.ellipse([cx - 4*s, cy - 4*s, cx + 6*s, cy + 4*s], fill=theme["glow"])
    draw.ellipse([cx - 1*s, cy - 2*s, cx + 3*s, cy + 2*s], fill=theme["glow_core"])
    # Dark nose
    draw.ellipse([cx + 20*s, cy + 2*s, cx + 25*s, cy + 7*s], fill=theme["outline"])


def draw_beast_paw(draw, w, h, s, theme):
    cx, cy = w // 2, h // 2
    draw.ellipse([cx - 14*s, cy - 8*s, cx + 14*s, cy + 12*s], fill=theme["primary_dark"], outline=theme["outline"], width=2*s)
    # 4 soft toe beans with sharp claws
    for ox in [-8, -2, 4, 10]:
        draw.polygon([(cx + ox*s, cy + 4*s), (cx + (ox+3)*s, cy + 14*s), (cx + (ox-1)*s, cy + 12*s)], fill=theme["accent_light"])


def draw_beast_tail(draw, w, h, s, theme, seg_idx=1):
    cx, cy = w // 2, h // 2
    r = 14 - seg_idx * 2
    draw.ellipse([cx - r*s, cy - r*s, cx + r*s, cy + r*s], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
    draw.line([(cx - (r-4)*s, cy), (cx + (r-4)*s, cy)], fill=theme["primary_light"], width=2*s)


# ==============================================================================
# Public Generation APIs
# ==============================================================================

def generate_all(out_dir, prefix="warrior", archetype="warrior", prompt="", seed=-1):
    """
    Generates all 15 limb sprites for any creature or humanoid.
    Dynamically responds to prompt concepts, seeds, and archetypes.
    """
    os.makedirs(out_dir, exist_ok=True)
    theme = build_palette(prompt, archetype, seed)
    s_int = seed if seed >= 0 else 42

    parts = {
        "head": ((64, 64), lambda d, w, h, s: draw_head(d, w, h, s, theme, s_int)),
        "torso": ((72, 64), lambda d, w, h, s: draw_torso(d, w, h, s, theme, s_int)),
        "pelvis": ((64, 48), lambda d, w, h, s: draw_pelvis(d, w, h, s, theme, s_int)),
        "arm_upper_L": ((44, 56), lambda d, w, h, s: draw_arm_upper(d, w, h, s, theme, True)),
        "arm_lower_L": ((36, 52), lambda d, w, h, s: draw_arm_lower(d, w, h, s, theme, True)),
        "hand_L": ((32, 32), lambda d, w, h, s: draw_hand(d, w, h, s, theme, True)),
        "arm_upper_R": ((44, 56), lambda d, w, h, s: draw_arm_upper(d, w, h, s, theme, False)),
        "arm_lower_R": ((36, 52), lambda d, w, h, s: draw_arm_lower(d, w, h, s, theme, False)),
        "hand_R": ((32, 32), lambda d, w, h, s: draw_hand(d, w, h, s, theme, False)),
        "leg_upper_L": ((40, 56), lambda d, w, h, s: draw_leg_upper(d, w, h, s, theme, True)),
        "leg_lower_L": ((36, 56), lambda d, w, h, s: draw_leg_lower(d, w, h, s, theme, True)),
        "foot_L": ((48, 32), lambda d, w, h, s: draw_foot(d, w, h, s, theme, True)),
        "leg_upper_R": ((40, 56), lambda d, w, h, s: draw_leg_upper(d, w, h, s, theme, False)),
        "leg_lower_R": ((36, 56), lambda d, w, h, s: draw_leg_lower(d, w, h, s, theme, False)),
        "foot_R": ((48, 32), lambda d, w, h, s: draw_foot(d, w, h, s, theme, False)),
    }

    generated_paths = []
    for name, (size, fn) in parts.items():
        img = create_sprite(size, fn)
        out_path = os.path.join(out_dir, f"{prefix}_{name}.png")
        img.save(out_path, "PNG")
        generated_paths.append(out_path)

    print(f"[Generator] Created {len(generated_paths)} {theme['species'].upper()} sprites for '{prefix}' in: {out_dir}")
    return generated_paths


def generate_quadruped(out_dir, prefix="fenrir", archetype="beast", prompt="", seed=-1):
    """Generates all 20 quadruped body part sprites."""
    os.makedirs(out_dir, exist_ok=True)
    theme = build_palette(prompt, archetype, seed)
    s_int = seed if seed >= 0 else 42

    parts = {
        "head": ((64, 64), lambda d, w, h, s: draw_beast_head(d, w, h, s, theme, s_int)),
        "neck": ((48, 56), lambda d, w, h, s: draw_torso(d, w, h, s, theme, s_int)),
        "torso": ((80, 64), lambda d, w, h, s: draw_torso(d, w, h, s, theme, s_int)),
        "spine": ((64, 56), lambda d, w, h, s: draw_pelvis(d, w, h, s, theme, s_int)),
        "pelvis": ((64, 56), lambda d, w, h, s: draw_pelvis(d, w, h, s, theme, s_int)),
        "tail_01": ((36, 36), lambda d, w, h, s: draw_beast_tail(d, w, h, s, theme, 1)),
        "tail_02": ((32, 32), lambda d, w, h, s: draw_beast_tail(d, w, h, s, theme, 2)),
        "tail_03": ((28, 28), lambda d, w, h, s: draw_beast_tail(d, w, h, s, theme, 3)),
        "leg_front_upper_L": ((40, 56), lambda d, w, h, s: draw_leg_upper(d, w, h, s, theme, True)),
        "leg_front_lower_L": ((36, 56), lambda d, w, h, s: draw_leg_lower(d, w, h, s, theme, True)),
        "paw_front_L": ((36, 32), lambda d, w, h, s: draw_beast_paw(d, w, h, s, theme)),
        "leg_front_upper_R": ((40, 56), lambda d, w, h, s: draw_leg_upper(d, w, h, s, theme, False)),
        "leg_front_lower_R": ((36, 56), lambda d, w, h, s: draw_leg_lower(d, w, h, s, theme, False)),
        "paw_front_R": ((36, 32), lambda d, w, h, s: draw_beast_paw(d, w, h, s, theme)),
        "leg_back_upper_L": ((44, 60), lambda d, w, h, s: draw_leg_upper(d, w, h, s, theme, True)),
        "leg_back_lower_L": ((38, 56), lambda d, w, h, s: draw_leg_lower(d, w, h, s, theme, True)),
        "paw_back_L": ((36, 32), lambda d, w, h, s: draw_beast_paw(d, w, h, s, theme)),
        "leg_back_upper_R": ((44, 60), lambda d, w, h, s: draw_leg_upper(d, w, h, s, theme, False)),
        "leg_back_lower_R": ((38, 56), lambda d, w, h, s: draw_leg_lower(d, w, h, s, theme, False)),
        "paw_back_R": ((36, 32), lambda d, w, h, s: draw_beast_paw(d, w, h, s, theme)),
    }

    generated_paths = []
    for name, (size, fn) in parts.items():
        img = create_sprite(size, fn)
        out_path = os.path.join(out_dir, f"{prefix}_{name}.png")
        img.save(out_path, "PNG")
        generated_paths.append(out_path)

    print(f"[Generator] Created {len(generated_paths)} QUADRUPED sprites for '{prefix}' in: {out_dir}")
    return generated_paths


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "sprites/test_char"
    char_name = sys.argv[2] if len(sys.argv) > 2 else "alien"
    concept = sys.argv[3] if len(sys.argv) > 3 else "cyberpunk warrior alien with glowing neon crest"
    generate_all(target, prefix=char_name, prompt=concept)
