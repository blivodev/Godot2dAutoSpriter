import os
import sys
import math
import random
import re
from PIL import Image, ImageDraw

def create_sprite(size, draw_func, art_style="anime", detail_level=3):
    """
    Renders sprite according to chosen art style and detail level.
    - anime / dark_fantasy / cyberpunk: 4x resolution downsampled with LANCZOS
    - pixel_8bit: Render at 2x, downsample with NEAREST, quantize to 16-color palette
    - pixel_16bit: Render at 2x, downsample with NEAREST, quantize to 32-color palette
    """
    is_pixel = art_style in ("pixel_8bit", "pixel_16bit")
    scale = 2 if is_pixel else 4
    w, h = size[0] * scale, size[1] * scale
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw_func(draw, w, h, scale)

    if is_pixel:
        small = img.resize(size, Image.Resampling.NEAREST)
        r, g, b, a = small.split()
        a = a.point(lambda p: 255 if p > 80 else 0)
        num_colors = 16 if art_style == "pixel_8bit" else 32
        try:
            rgb = small.convert("RGB")
            quantized = rgb.quantize(colors=num_colors, method=Image.Quantize.MEDIANCUT).convert("RGBA")
            quantized.putalpha(a)
            return quantized
        except Exception:
            small.putalpha(a)
            return small

    return img.resize(size, Image.Resampling.LANCZOS)


# ==============================================================================
# Organic Curved Anime Silhouette & Shading Engine
# ==============================================================================

def catmull_rom_spline(pts, num_subdivs=6, closed=True):
    """Generates smooth, continuous organic curves through control points using Catmull-Rom interpolation."""
    if len(pts) < 3:
        return [(round(x), round(y)) for x, y in pts]
    result = []
    n = len(pts)
    for i in range(n):
        if not closed and (i == 0 or i >= n - 2):
            result.append((round(pts[i][0]), round(pts[i][1])))
            continue
        p0 = pts[(i - 1 + n) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]
        for t_step in range(num_subdivs):
            t = t_step / float(num_subdivs)
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * ((2*p1[0]) + (-p0[0] + p2[0])*t + (2*p0[0] - 5*p1[0] + 4*p2[0] - p3[0])*t2 + (-p0[0] + 3*p1[0] - 3*p2[0] + p3[0])*t3)
            y = 0.5 * ((2*p1[1]) + (-p0[1] + p2[1])*t + (2*p0[1] - 5*p1[1] + 4*p2[1] - p3[1])*t2 + (-p0[1] + 3*p1[1] - 3*p2[1] + p3[1])*t3)
            result.append((round(x), round(y)))
    return result


def draw_curved_polygon(draw, pts, fill=None, outline=None, width=1, num_subdivs=6):
    """Draws an organically curved polygon without hard polygonal corners."""
    curved = catmull_rom_spline(pts, num_subdivs=num_subdivs, closed=True)
    draw.polygon(curved, fill=fill, outline=outline, width=width)


def draw_curved_line(draw, pts, fill=None, width=1, num_subdivs=6):
    """Draws a smooth flowing curved line (e.g. hair strands, clothing folds, eyelash curves)."""
    curved = catmull_rom_spline(pts, num_subdivs=num_subdivs, closed=False)
    if len(curved) >= 2:
        draw.line(curved, fill=fill, width=width)


def draw_expressive_anime_eye(draw, ex, ey, s, theme, is_left=True):
    """Renders a sparkling, multi-layered expressive anime eye with gradient iris, double catchlights, and blush."""
    dir_mul = 1 if is_left else -1
    
    # Sclera (eye white)
    sclera_pts = [
        (ex - 7*s*dir_mul, ey + 1*s),
        (ex - 4*s*dir_mul, ey - 3*s),
        (ex + 4*s*dir_mul, ey - 3*s),
        (ex + 7*s*dir_mul, ey + 2*s),
        (ex + 3*s*dir_mul, ey + 7*s),
        (ex - 4*s*dir_mul, ey + 7*s)
    ]
    draw_curved_polygon(draw, sclera_pts, fill=(255, 255, 255, 255), outline=theme["outline"], width=s)

    # Large Gradient Iris
    iris_glow = theme.get("glow", (120, 200, 255, 255))
    iris_dark = theme.get("primary_dark", (40, 50, 70, 255))
    draw.ellipse([ex - 4*s, ey - 2*s, ex + 4*s, ey + 6*s], fill=iris_glow)
    # Upper iris shadow (cast by upper eyelid)
    draw.chord([ex - 4*s, ey - 2*s, ex + 4*s, ey + 6*s], start=180, end=360, fill=iris_dark)

    # Deep Pupil
    draw.ellipse([ex - 2*s, ey, ex + 2*s, ey + 5*s], fill=theme["outline"])
    draw.ellipse([ex - 1*s, ey + 1*s, ex + 1*s, ey + 4*s], fill=(0, 0, 0, 255))

    # Dual Specular Catchlights (The unmistakable anime gleam!)
    # Primary star/circle highlight (top-left)
    draw.ellipse([ex - 3*s, ey - 1*s, ex - 1*s, ey + 2*s], fill=(255, 255, 255, 255))
    # Secondary soft reflection highlight (bottom-right)
    draw.ellipse([ex + 1*s, ey + 3*s, ex + 2*s, ey + 5*s], fill=(240, 245, 255, 220))

    # Bold winged upper eyelash curve
    lash_pts = [
        (ex - 8*s*dir_mul, ey + 2*s),
        (ex - 4*s*dir_mul, ey - 4*s),
        (ex + 2*s*dir_mul, ey - 4*s),
        (ex + 8*s*dir_mul, ey - 1*s),
        (ex + 10*s*dir_mul, ey - 3*s) # Wing flick
    ]
    draw_curved_line(draw, lash_pts, fill=theme["outline"], width=2*s)

    # Delicate lower eyelash accent
    lower_lash_pts = [
        (ex - 4*s*dir_mul, ey + 7*s),
        (ex + 3*s*dir_mul, ey + 7*s),
        (ex + 6*s*dir_mul, ey + 6*s)
    ]
    draw_curved_line(draw, lower_lash_pts, fill=theme["outline"], width=s)

    # Eyelid crease line above the eye
    draw_curved_line(draw, [(ex - 5*s*dir_mul, ey - 7*s), (ex, ey - 7*s), (ex + 4*s*dir_mul, ey - 6*s)], fill=theme["outline"], width=s)

    # Anime blush lines on cheek below eye
    blush_col = (255, 140, 160, 180)
    for bx in [-3, 0, 3]:
        draw.line([(ex + (bx-1)*s, ey + 10*s), (ex + (bx+1)*s, ey + 13*s)], fill=blush_col, width=s)



# ==============================================================================
# Dynamic Prompt & Species Analyzer
# ==============================================================================
def detect_species(prompt: str, archetype: str = "") -> str:
    """Extracts the biological / thematic species from the user's prompt text using word-boundary matching."""
    p = (prompt + " " + archetype).lower()
    def has_any(*words):
        pattern = r'\b(' + '|'.join(re.escape(w) for w in words) + r')\b'
        return bool(re.search(pattern, p))

    if has_any("wolfman", "wolf man", "werewolf", "lycan", "beastman", "beast", "wolf", "chimera", "hound", "tiger", "lion", "bear", "cat", "fox", "fenrir", "mount"):
        return "beast"
    if has_any("alien", "xenomorph", "extraterrestrial", "martian", "biomechanic"):
        return "alien"
    if has_any("demon", "fiend", "devil", "tiefling", "succubus", "oni", "hell", "infernal"):
        return "demon"
    if has_any("undead", "skeleton", "lich", "ghoul", "zombie", "skull", "bone", "necromancer"):
        return "undead"
    if has_any("reptile", "reptilian", "lizard", "dragon", "drake", "serpent", "snake", "scale", "scales", "croc", "crocodile", "dragonkin"):
        return "reptilian"
    if has_any("insect", "insectoid", "mantis", "bug", "arachnid", "spider", "beetle", "chitin", "wasp", "ant", "ants"):
        return "insectoid"
    if has_any("mech", "robot", "cyborg", "automaton", "android", "dieselpunk", "steampunk", "golem", "titan", "juggernaut"):
        return "mech"
    if has_any("aquatic", "merfolk", "merman", "mermaid", "fish", "siren", "shark", "coral"):
        return "aquatic"
    if has_any("plant", "dryad", "treant", "tree", "wood", "floral", "vine", "vines", "bark", "moss"):
        return "plant"
    if has_any("slime", "ooze", "gelatin", "elemental", "blob"):
        return "slime"
    # Default to organic humanoid (human, elf, anime, caster, rogue, warrior, paladin, sorceress)
    return "humanoid"


def hex_to_rgba(h_str: str, default=(128, 128, 128, 255)):
    if not h_str or not isinstance(h_str, str):
        return default
    h = h_str.strip().lstrip("#")
    if len(h) == 6:
        try:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
        except Exception:
            return default
    return default


def build_palette(prompt: str, archetype: str = "", seed: int = 42, custom_colors: dict = None, art_style: str = "anime") -> dict:
    """
    Extracts explicit colors from prompt or deterministically synthesizes
    a rich, harmonious 8-color palette tailored to the creature/humanoid type and selected art_style.
    Accepts optional custom_colors dict with 'primary', 'accent', 'glow', 'outline' hex values.
    """
    p = (prompt + " " + archetype).lower()
    rng = random.Random(seed if seed >= 0 else hash(prompt + archetype) & 0x7fffffff)
    species = custom_colors.get("species") if (custom_colors and custom_colors.get("species")) else detect_species(prompt, archetype)

    if custom_colors and any(k in custom_colors for k in ["primary", "accent", "glow", "outline"]):
        p_col = hex_to_rgba(custom_colors.get("primary"), (60, 75, 100, 255))
        a_col = hex_to_rgba(custom_colors.get("accent"), (215, 165, 45, 255))
        g_col = hex_to_rgba(custom_colors.get("glow"), (0, 240, 255, 255))
        out_col = hex_to_rgba(custom_colors.get("outline"), (16, 18, 22, 255))

        skin_dark = (max(0, p_col[0] - 35), max(0, p_col[1] - 35), max(0, p_col[2] - 35), 255)
        skin_mid = p_col
        skin_light = (min(255, p_col[0] + 45), min(255, p_col[1] + 45), min(255, p_col[2] + 45), 255)

        accent_dark = (max(0, a_col[0] - 40), max(0, a_col[1] - 40), max(0, a_col[2] - 40), 255)
        accent_mid = a_col
        accent_light = (min(255, a_col[0] + 45), min(255, a_col[1] + 45), min(255, a_col[2] + 45), 255)

        glow = g_col
        glow_core = (min(255, g_col[0] + 70), min(255, g_col[1] + 70), min(255, g_col[2] + 70), 255)
        outline = out_col

        return {
            "species": species,
            "art_style": art_style,
            "primary_dark": skin_dark,
            "primary_mid": skin_mid,
            "primary_light": skin_light,
            "accent_dark": accent_dark,
            "accent_mid": accent_mid,
            "accent_light": accent_light,
            "glow": glow,
            "glow_core": glow_core,
            "outline": outline,
        }

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

    # Art style color adjustments
    if art_style == "dark_fantasy":
        skin_dark = (max(0, skin_dark[0]-25), max(0, skin_dark[1]-25), max(0, skin_dark[2]-25), 255)
        skin_mid = (max(0, skin_mid[0]-20), max(0, skin_mid[1]-20), max(0, skin_mid[2]-20), 255)
        accent_mid = (max(0, accent_mid[0]-20), max(0, accent_mid[1]-20), max(0, accent_mid[2]-20), 255)
        outline = (8, 9, 12, 255)
    elif art_style == "cyberpunk":
        skin_dark = (16, 20, 26, 255)
        skin_mid = (32, 40, 52, 255)
        skin_light = (64, 82, 106, 255)
        outline = (10, 12, 18, 255)
    elif art_style == "pixel_arcade":
        def q(c): return ((c[0]//32)*32, (c[1]//32)*32, (c[2]//32)*32, 255)
        skin_dark = q(skin_dark)
        skin_mid = q(skin_mid)
        skin_light = q(skin_light)
        accent_mid = q(accent_mid)
        outline = (12, 14, 20, 255)
    elif art_style == "comic_ink":
        outline = (0, 0, 0, 255)
    elif art_style == "moba_chibi":
        skin_light = (min(255, skin_light[0]+25), min(255, skin_light[1]+25), min(255, skin_light[2]+25), 255)

    return {
        "species": species,
        "art_style": art_style,
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
        draw_curved_polygon(draw, [
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
        draw_curved_polygon(draw, [
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
        draw_curved_polygon(draw, [
            (cx - 12*s, cy - 12*s),
            (cx - 24*s, cy - 22*s),
            (cx - 28*s, cy - 36*s), # Horn tip
            (cx - 18*s, cy - 28*s),
            (cx - 6*s, cy - 14*s)
        ], fill=theme["accent_mid"], outline=theme["outline"], width=2*s)
        draw_curved_polygon(draw, [(cx - 26*s, cy - 34*s), (cx - 21*s, cy - 28*s), (cx - 16*s, cy - 24*s)], fill=theme["accent_light"])

        # Right Horn
        draw_curved_polygon(draw, [
            (cx + 12*s, cy - 12*s),
            (cx + 24*s, cy - 22*s),
            (cx + 28*s, cy - 36*s), # Horn tip
            (cx + 18*s, cy - 28*s),
            (cx + 6*s, cy - 14*s)
        ], fill=theme["accent_mid"], outline=theme["outline"], width=2*s)
        draw_curved_polygon(draw, [(cx + 26*s, cy - 34*s), (cx + 21*s, cy - 28*s), (cx + 16*s, cy - 24*s)], fill=theme["accent_light"])

        # Demon face
        draw_curved_polygon(draw, [
            (cx - 16*s, cy - 12*s),
            (cx + 16*s, cy - 12*s),
            (cx + 14*s, cy + 6*s),
            (cx + 8*s, cy + 18*s),
            (cx, cy + 24*s), # Sharp chin
            (cx - 8*s, cy + 18*s),
            (cx - 14*s, cy + 6*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

        # Forehead demonic runic mark
        draw_curved_polygon(draw, [
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
        draw_curved_polygon(draw, [
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
        draw_curved_polygon(draw, [(cx - 14*s, cy), (cx - 10*s, cy), (cx - 12*s, cy + 6*s)], fill=theme["primary_dark"])
        draw_curved_polygon(draw, [(cx + 14*s, cy), (cx + 10*s, cy), (cx + 12*s, cy + 6*s)], fill=theme["primary_dark"])

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
        draw_curved_polygon(draw, [(cx - 10*s, cy - 10*s), (cx - 24*s, cy - 24*s), (cx - 14*s, cy - 18*s)], fill=theme["accent_mid"], outline=theme["outline"], width=s)
        draw_curved_polygon(draw, [(cx + 10*s, cy - 10*s), (cx + 24*s, cy - 24*s), (cx + 14*s, cy - 18*s)], fill=theme["accent_mid"], outline=theme["outline"], width=s)

        # Scaled head
        draw_curved_polygon(draw, [
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
        draw.line([(cx - 6*s, cy - 12*s), (cx - 22*s, cy - 32*s)], fill=theme["accent_light"], width=2*s)
        draw.line([(cx + 6*s, cy - 12*s), (cx + 22*s, cy - 32*s)], fill=theme["accent_light"], width=2*s)

        # Carapace head
        draw_curved_polygon(draw, [
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
        draw_curved_polygon(draw, [(cx - 8*s, cy + 14*s), (cx - 3*s, cy + 26*s), (cx - 1*s, cy + 18*s)], fill=theme["accent_mid"], outline=theme["outline"])
        draw_curved_polygon(draw, [(cx + 8*s, cy + 14*s), (cx + 3*s, cy + 26*s), (cx + 1*s, cy + 18*s)], fill=theme["accent_mid"], outline=theme["outline"])

    elif sp == "mech":
        # 🤖 Robotic helmet with visor
        draw_curved_polygon(draw, [
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

    elif sp == "beast":
        # 🐺 Werewolf / Beast Head with alert ears, furry cheeks, predatory muzzle and sharp fangs
        draw_curved_polygon(draw, [(cx - 16*s, cy - 8*s), (cx - 22*s, cy - 30*s), (cx - 8*s, cy - 16*s)], fill=theme["primary_dark"], outline=theme["outline"], width=2*s)
        draw_curved_polygon(draw, [(cx - 17*s, cy - 12*s), (cx - 20*s, cy - 26*s), (cx - 10*s, cy - 16*s)], fill=theme["accent_light"])

        draw_curved_polygon(draw, [(cx + 16*s, cy - 8*s), (cx + 22*s, cy - 30*s), (cx + 8*s, cy - 16*s)], fill=theme["primary_dark"], outline=theme["outline"], width=2*s)
        draw_curved_polygon(draw, [(cx + 17*s, cy - 12*s), (cx + 20*s, cy - 26*s), (cx + 10*s, cy - 16*s)], fill=theme["accent_light"])

        # Skull and furry cheek tufts
        draw_curved_polygon(draw, [
            (cx - 15*s, cy - 16*s),
            (cx + 15*s, cy - 16*s),
            (cx + 22*s, cy - 4*s),
            (cx + 16*s, cy + 8*s),
            (cx + 9*s, cy + 22*s),
            (cx - 9*s, cy + 22*s),
            (cx - 16*s, cy + 8*s),
            (cx - 22*s, cy - 4*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

        # Muzzle bridge
        draw.polygon([(cx - 6*s, cy - 4*s), (cx + 6*s, cy - 4*s), (cx + 7*s, cy + 16*s), (cx - 7*s, cy + 16*s)], fill=theme["primary_light"], outline=theme["outline"], width=s)
        # Dark nose
        draw.polygon([(cx - 4*s, cy + 8*s), (cx + 4*s, cy + 8*s), (cx, cy + 13*s)], fill=theme["outline"])
        # Sharp bared white fangs
        draw.polygon([(cx - 6*s, cy + 15*s), (cx - 3*s, cy + 22*s), (cx - 1*s, cy + 15*s)], fill=(250, 250, 245, 255), outline=theme["outline"])
        draw.polygon([(cx + 1*s, cy + 15*s), (cx + 3*s, cy + 22*s), (cx + 6*s, cy + 15*s)], fill=(250, 250, 245, 255), outline=theme["outline"])

        # Predatory beast eyes
        draw.polygon([(cx - 13*s, cy - 4*s), (cx - 5*s, cy - 2*s), (cx - 6*s, cy + 3*s), (cx - 12*s, cy + 1*s)], fill=theme["glow"], outline=theme["outline"], width=s)
        draw.polygon([(cx + 13*s, cy - 4*s), (cx + 5*s, cy - 2*s), (cx + 6*s, cy + 3*s), (cx + 12*s, cy + 1*s)], fill=theme["glow"], outline=theme["outline"], width=s)
        draw.ellipse([cx - 9*s, cy - 2*s, cx - 7*s, cy + 1*s], fill=theme["glow_core"])
        draw.ellipse([cx + 7*s, cy - 2*s, cx + 9*s, cy + 1*s], fill=theme["glow_core"])

    else:
        # 🧝 Humanoid / Anime Character (e.g. Elf Sorceress, Paladin, Cyber Ninja, Rogue)
        # 1. Back Hair Layer (flowing silhouette behind head & neck)
        back_hair_pts = [
            (cx - 16*s, cy - 14*s),
            (cx - 24*s, cy + 2*s),
            (cx - 22*s, cy + 26*s),
            (cx - 15*s, cy + 24*s),
            (cx - 12*s, cy + 16*s),
            (cx + 12*s, cy + 16*s),
            (cx + 15*s, cy + 24*s),
            (cx + 22*s, cy + 26*s),
            (cx + 24*s, cy + 2*s),
            (cx + 16*s, cy - 14*s),
            (cx, cy - 28*s)
        ]
        draw_curved_polygon(draw, back_hair_pts, fill=theme["accent_dark"], outline=theme["outline"], width=2*s)

        # 2. Smooth, organic anime jaw and cranium
        face_pts = [
            (cx - 14*s, cy - 12*s), # Temple L
            (cx - 15*s, cy + 2*s),  # Cheek L
            (cx - 9*s, cy + 14*s),  # Jaw L
            (cx, cy + 20*s),        # Cute anime chin
            (cx + 9*s, cy + 14*s),  # Jaw R
            (cx + 15*s, cy + 2*s),  # Cheek R
            (cx + 14*s, cy - 12*s), # Temple R
            (cx, cy - 22*s)         # Forehead
        ]
        draw_curved_polygon(draw, face_pts, fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

        # 3. Delicate anime ears (pointed for elf, or delicate curve for human)
        is_elf = "elf" in theme.get("archetype", "") or "sorceress" in theme.get("species", "") or "mage" in theme.get("archetype", "")
        if is_elf:
            # Swept back elven ears
            ear_l = [(cx - 14*s, cy - 2*s), (cx - 26*s, cy - 8*s), (cx - 13*s, cy + 6*s)]
            ear_r = [(cx + 14*s, cy - 2*s), (cx + 26*s, cy - 8*s), (cx + 13*s, cy + 6*s)]
            draw_curved_polygon(draw, ear_l, fill=theme["primary_mid"], outline=theme["outline"], width=s)
            draw_curved_polygon(draw, ear_r, fill=theme["primary_mid"], outline=theme["outline"], width=s)
            draw_curved_line(draw, [(cx - 14*s, cy), (cx - 22*s, cy - 5*s)], fill=theme["primary_dark"], width=s)
            draw_curved_line(draw, [(cx + 14*s, cy), (cx + 22*s, cy - 5*s)], fill=theme["primary_dark"], width=s)
        else:
            ear_l = [(cx - 14*s, cy - 3*s), (cx - 18*s, cy + 2*s), (cx - 13*s, cy + 7*s)]
            ear_r = [(cx + 14*s, cy - 3*s), (cx + 18*s, cy + 2*s), (cx + 13*s, cy + 7*s)]
            draw_curved_polygon(draw, ear_l, fill=theme["primary_mid"], outline=theme["outline"], width=s)
            draw_curved_polygon(draw, ear_r, fill=theme["primary_mid"], outline=theme["outline"], width=s)

        # 4. Soft cel-shading under chin & neck shadow
        chin_shadow = [(cx - 7*s, cy + 16*s), (cx, cy + 14*s), (cx + 7*s, cy + 16*s), (cx, cy + 20*s)]
        draw_curved_polygon(draw, chin_shadow, fill=theme["primary_dark"])

        # 5. Expressive, sparkling anime eyes (with gradient iris, dual catchlights, winged lashes, blush)
        draw_expressive_anime_eye(draw, cx - 8*s, cy + 2*s, s, theme, is_left=True)
        draw_expressive_anime_eye(draw, cx + 8*s, cy + 2*s, s, theme, is_left=False)

        # 6. Stylized anime eyebrows
        brow_l = [(cx - 12*s, cy - 6*s), (cx - 8*s, cy - 8*s), (cx - 4*s, cy - 7*s)]
        brow_r = [(cx + 4*s, cy - 7*s), (cx + 8*s, cy - 8*s), (cx + 12*s, cy - 6*s)]
        draw_curved_line(draw, brow_l, fill=theme["accent_dark"], width=s)
        draw_curved_line(draw, brow_r, fill=theme["accent_dark"], width=s)

        # 7. Subtle anime nose and mouth
        draw.polygon([(cx, cy + 8*s), (cx + 1*s, cy + 9*s), (cx, cy + 10*s)], fill=theme["primary_dark"])
        mouth_pts = [(cx - 4*s, cy + 13*s), (cx - 1*s, cy + 14*s), (cx + 1*s, cy + 14*s), (cx + 4*s, cy + 13*s)]
        draw_curved_line(draw, mouth_pts, fill=theme["outline"], width=s)
        draw.line([(cx - 1*s, cy + 15*s), (cx + 1*s, cy + 15*s)], fill=theme["primary_light"], width=s)

        # 8. Multi-layered front hair crown, stylish bangs, and sidelocks
        front_hair_pts = [
            (cx - 18*s, cy + 6*s),   # Sidelock left tip
            (cx - 17*s, cy - 14*s),
            (cx - 10*s, cy - 26*s),
            (cx, cy - 29*s),         # Crown top
            (cx + 10*s, cy - 26*s),
            (cx + 17*s, cy - 14*s),
            (cx + 18*s, cy + 6*s),   # Sidelock right tip
            (cx + 14*s, cy - 4*s),
            (cx + 9*s, cy - 2*s),    # Right fringe
            (cx + 5*s, cy - 6*s),
            (cx + 2*s, cy - 1*s),    # Center bang
            (cx - 3*s, cy - 6*s),
            (cx - 7*s, cy - 2*s),    # Left fringe
            (cx - 13*s, cy - 4*s)
        ]
        draw_curved_polygon(draw, front_hair_pts, fill=theme["accent_mid"], outline=theme["outline"], width=2*s)

        # 9. Luminous Anime Hair Sheen / Halo Highlight Band
        sheen_pts = [
            (cx - 12*s, cy - 18*s),
            (cx - 5*s, cy - 23*s),
            (cx + 5*s, cy - 23*s),
            (cx + 12*s, cy - 18*s)
        ]
        draw_curved_line(draw, sheen_pts, fill=theme["accent_light"], width=3*s)
        for hx in [-6, 0, 6]:
            draw.polygon([(cx + (hx-1)*s, cy - 22*s), (cx + hx*s, cy - 25*s), (cx + (hx+1)*s, cy - 22*s)], fill=(255, 255, 255, 200))

        # 10. Playful Ahoge / Cowlick strand flick at crown
        ahoge_pts = [(cx - 2*s, cy - 28*s), (cx + 3*s, cy - 35*s), (cx + 8*s, cy - 32*s), (cx + 2*s, cy - 27*s)]
        draw_curved_line(draw, ahoge_pts, fill=theme["accent_mid"], width=2*s)

        # 11. Head accessory: Jeweled circlet / diadem
        circlet_pts = [(cx - 15*s, cy - 10*s), (cx, cy - 13*s), (cx + 15*s, cy - 10*s)]
        draw_curved_line(draw, circlet_pts, fill=theme["accent_light"], width=2*s)
        draw.ellipse([cx - 3*s, cy - 15*s, cx + 3*s, cy - 9*s], fill=theme["glow"], outline=theme["outline"], width=s)
        draw.ellipse([cx - 1*s, cy - 14*s, cx + 1*s, cy - 11*s], fill=theme["glow_core"])


def draw_torso(draw, w, h, s, theme, seed=42):
    cx, cy = w // 2, h // 2
    sp = theme["species"]

    if sp == "alien":
        # 👾 Biomechanical carapace with glowing bio-core
        draw_curved_polygon(draw, [
            (cx - 24*s, cy - 22*s),
            (cx + 24*s, cy - 22*s),
            (cx + 20*s, cy + 6*s),
            (cx + 14*s, cy + 24*s),
            (cx, cy + 28*s),
            (cx - 14*s, cy + 24*s),
            (cx - 20*s, cy + 6*s)
        ], fill=theme["primary_dark"], outline=theme["outline"], width=2*s)

        for ry in [-12, -2, 8]:
            draw.line([(cx - 20*s, cy + ry*s), (cx - 8*s, cy + ry*s)], fill=theme["primary_light"], width=2*s)
            draw.line([(cx + 8*s, cy + ry*s), (cx + 20*s, cy + ry*s)], fill=theme["primary_light"], width=2*s)

        draw.ellipse([cx - 8*s, cy - 8*s, cx + 8*s, cy + 8*s], fill=theme["primary_dark"], outline=theme["glow"], width=2*s)
        draw.ellipse([cx - 5*s, cy - 5*s, cx + 5*s, cy + 5*s], fill=theme["glow"])
        draw.ellipse([cx - 2*s, cy - 2*s, cx + 2*s, cy + 2*s], fill=theme["glow_core"])

    elif sp == "demon":
        # 😈 Muscular demonic torso with fiery runic brand
        draw_curved_polygon(draw, [
            (cx - 26*s, cy - 22*s),
            (cx + 26*s, cy - 22*s),
            (cx + 22*s, cy + 4*s),
            (cx + 14*s, cy + 24*s),
            (cx, cy + 28*s),
            (cx - 14*s, cy + 24*s),
            (cx - 22*s, cy + 4*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

        draw.line([(cx, cy - 18*s), (cx, cy + 18*s)], fill=theme["primary_dark"], width=2*s)
        draw.arc([cx - 18*s, cy - 14*s, cx - 2*s, cy - 2*s], 0, 180, fill=theme["primary_dark"], width=2*s)
        draw.arc([cx + 2*s, cy - 14*s, cx + 18*s, cy - 2*s], 0, 180, fill=theme["primary_dark"], width=2*s)

        draw_curved_polygon(draw, [
            (cx, cy - 6*s),
            (cx + 7*s, cy),
            (cx, cy + 6*s),
            (cx - 7*s, cy)
        ], fill=theme["glow"], outline=theme["outline"], width=s)
        draw.ellipse([cx - 2*s, cy - 2*s, cx + 2*s, cy + 2*s], fill=theme["glow_core"])

    elif sp == "undead":
        # 💀 Exposed skeletal ribcage with floating soul orb
        draw.rectangle([cx - 20*s, cy - 20*s, cx + 20*s, cy + 24*s], fill=theme["outline"])
        draw.rectangle([cx - 4*s, cy - 22*s, cx + 4*s, cy + 26*s], fill=theme["primary_mid"], outline=theme["primary_dark"], width=s)

        for ry in [-14, -6, 2, 10]:
            draw.arc([cx - 20*s, cy + (ry-4)*s, cx - 2*s, cy + (ry+6)*s], 180, 360, fill=theme["primary_light"], width=3*s)
            draw.arc([cx + 2*s, cy + (ry-4)*s, cx + 20*s, cy + (ry+6)*s], 180, 360, fill=theme["primary_light"], width=3*s)

        draw.ellipse([cx - 6*s, cy - 4*s, cx + 6*s, cy + 8*s], fill=theme["glow"])
        draw.ellipse([cx - 2*s, cy - 1*s, cx + 2*s, cy + 4*s], fill=theme["glow_core"])

    elif sp == "beast":
        # 🐺 Muscular Beast Torso with Thick Fur Ruff
        draw_curved_polygon(draw, [
            (cx - 26*s, cy - 22*s),
            (cx + 26*s, cy - 22*s),
            (cx + 22*s, cy + 6*s),
            (cx + 14*s, cy + 24*s),
            (cx, cy + 28*s),
            (cx - 14*s, cy + 24*s),
            (cx - 22*s, cy + 6*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

        draw_curved_polygon(draw, [
            (cx - 24*s, cy - 22*s),
            (cx - 18*s, cy - 14*s),
            (cx - 26*s, cy - 8*s),
            (cx - 12*s, cy - 2*s),
            (cx, cy - 6*s),
            (cx + 12*s, cy - 2*s),
            (cx + 26*s, cy - 8*s),
            (cx + 18*s, cy - 14*s),
            (cx + 24*s, cy - 22*s)
        ], fill=theme["accent_mid"], outline=theme["outline"], width=2*s)

        draw.line([(cx - 16*s, cy - 12*s), (cx + 14*s, cy + 16*s)], fill=theme["accent_dark"], width=3*s)
        draw.line([(cx + 16*s, cy - 12*s), (cx - 14*s, cy + 16*s)], fill=theme["accent_dark"], width=3*s)

        draw.ellipse([cx - 6*s, cy - 2*s, cx + 6*s, cy + 10*s], fill=theme["glow"], outline=theme["outline"], width=s)
        draw.ellipse([cx - 2*s, cy + 1*s, cx + 2*s, cy + 6*s], fill=theme["glow_core"])

    elif sp == "mech":
        # 🤖 Heavy industrial mech torso with furnace core and hazard stripes
        draw_curved_polygon(draw, [
            (cx - 26*s, cy - 22*s),
            (cx + 26*s, cy - 22*s),
            (cx + 22*s, cy + 8*s),
            (cx + 14*s, cy + 24*s),
            (cx, cy + 26*s),
            (cx - 14*s, cy + 24*s),
            (cx - 22*s, cy + 8*s)
        ], fill=theme["primary_dark"], outline=theme["outline"], width=2*s)
        draw.rectangle([cx - 20*s, cy - 18*s, cx + 20*s, cy - 4*s], fill=theme["primary_mid"], outline=theme["outline"], width=s)
        for hx in range(-16, 16, 8):
            draw.line([(cx + hx*s, cy - 16*s), (cx + (hx+5)*s, cy - 6*s)], fill=theme["accent_mid"], width=2*s)
        draw.rectangle([cx - 8*s, cy, cx + 8*s, cy + 14*s], fill=theme["glow"], outline=theme["outline"], width=s)
        draw.rectangle([cx - 4*s, cy + 3*s, cx + 4*s, cy + 11*s], fill=theme["glow_core"])

    else:
        # 🧝 Humanoid / Anime Torso with organic contouring, tailored doublet/corset, and convex joint sockets
        torso_contour = [
            (cx - 8*s, cy - 24*s),   # Neck socket left
            (cx - 18*s, cy - 22*s),  # Clavicle left
            (cx - 24*s, cy - 14*s),  # Shoulder left
            (cx - 21*s, cy - 2*s),   # Chest / armpit left
            (cx - 14*s, cy + 12*s),  # Tapered anime waist left
            (cx - 17*s, cy + 24*s),  # Flare to pelvis left
            (cx, cy + 26*s),         # Center bottom convex cap (attaches to pelvis)
            (cx + 17*s, cy + 24*s),  # Flare to pelvis right
            (cx + 14*s, cy + 12*s),  # Tapered anime waist right
            (cx + 21*s, cy - 2*s),   # Chest / armpit right
            (cx + 24*s, cy - 14*s),  # Shoulder right
            (cx + 18*s, cy - 22*s),  # Clavicle right
            (cx + 8*s, cy - 24*s)    # Neck socket right
        ]
        draw_curved_polygon(draw, torso_contour, fill=theme["accent_mid"], outline=theme["outline"], width=2*s)

        # Ambient cel-shading along the flanks
        left_shade = [
            (cx - 18*s, cy - 20*s),
            (cx - 23*s, cy - 12*s),
            (cx - 20*s, cy),
            (cx - 14*s, cy + 12*s),
            (cx - 16*s, cy + 22*s),
            (cx - 10*s, cy + 20*s),
            (cx - 14*s, cy + 6*s),
            (cx - 16*s, cy - 10*s)
        ]
        draw_curved_polygon(draw, left_shade, fill=theme["accent_dark"])

        # Elegant V-neck / collar showing inner shirt or skin
        vneck_pts = [
            (cx - 9*s, cy - 24*s),
            (cx + 9*s, cy - 24*s),
            (cx + 7*s, cy - 14*s),
            (cx, cy - 4*s),
            (cx - 7*s, cy - 14*s)
        ]
        draw_curved_polygon(draw, vneck_pts, fill=theme["primary_mid"], outline=theme["outline"], width=s)
        draw_curved_polygon(draw, [(cx - 6*s, cy - 24*s), (cx + 6*s, cy - 24*s), (cx, cy - 18*s)], fill=theme["primary_dark"])

        # Decorative gold/accent piping / vest lapel curves
        lapel_l = [(cx - 9*s, cy - 24*s), (cx - 7*s, cy - 10*s), (cx - 2*s, cy + 18*s)]
        lapel_r = [(cx + 9*s, cy - 24*s), (cx + 7*s, cy - 10*s), (cx + 2*s, cy + 18*s)]
        draw_curved_line(draw, lapel_l, fill=theme["accent_light"], width=2*s)
        draw_curved_line(draw, lapel_r, fill=theme["accent_light"], width=2*s)

        # Center corset laces
        for by in range(-2, 16, 5):
            draw.line([(cx - 3*s, cy + by*s), (cx + 3*s, cy + (by+2)*s)], fill=theme["accent_light"], width=s)
            draw.line([(cx + 3*s, cy + by*s), (cx - 3*s, cy + (by+2)*s)], fill=theme["accent_light"], width=s)

        # Ornate Chest Brooch / Soul Gem (with glow, core gleam, and setting)
        draw.ellipse([cx - 5*s, cy - 7*s, cx + 5*s, cy + 3*s], fill=theme["accent_light"], outline=theme["outline"], width=s)
        draw.ellipse([cx - 4*s, cy - 6*s, cx + 4*s, cy + 2*s], fill=theme["glow"])
        draw.ellipse([cx - 2*s, cy - 4*s, cx + 1*s, cy - 1*s], fill=theme["glow_core"])
        draw.ellipse([cx - 1*s, cy - 3*s, cx, cy - 2*s], fill=(255, 255, 255, 255))


def draw_pelvis(draw, w, h, s, theme, seed=42):
    cx, cy = w // 2, h // 2
    sp = theme["species"]

    if sp in ["alien", "insectoid"]:
        draw_curved_polygon(draw, [
            (cx - 20*s, cy - 12*s),
            (cx + 20*s, cy - 12*s),
            (cx + 16*s, cy + 14*s),
            (cx, cy + 18*s),
            (cx - 16*s, cy + 14*s)
        ], fill=theme["primary_dark"], outline=theme["outline"], width=2*s)
        draw.line([(cx - 12*s, cy), (cx + 12*s, cy)], fill=theme["glow"], width=s)
    elif sp == "undead":
        draw_curved_polygon(draw, [
            (cx - 22*s, cy - 10*s),
            (cx + 22*s, cy - 10*s),
            (cx + 18*s, cy + 6*s),
            (cx, cy + 14*s),
            (cx - 18*s, cy + 6*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
        draw.ellipse([cx - 14*s, cy - 4*s, cx - 6*s, cy + 4*s], fill=theme["outline"])
        draw.ellipse([cx + 6*s, cy - 4*s, cx + 14*s, cy + 4*s], fill=theme["outline"])
    else:
        # 🧝 Humanoid / Anime Pelvis with curved waist sash, flowing tunic pleats, and convex hip joints
        belt_pts = [
            (cx - 21*s, cy - 14*s),
            (cx + 21*s, cy - 14*s),
            (cx + 19*s, cy - 2*s),
            (cx - 19*s, cy - 2*s)
        ]
        draw_curved_polygon(draw, belt_pts, fill=theme["accent_dark"], outline=theme["outline"], width=2*s)

        skirt_pts = [
            (cx - 19*s, cy - 2*s),
            (cx - 16*s, cy + 18*s),
            (cx - 7*s, cy + 16*s),
            (cx, cy + 20*s),         # Center front dip
            (cx + 7*s, cy + 16*s),
            (cx + 16*s, cy + 18*s),
            (cx + 19*s, cy - 2*s)
        ]
        draw_curved_polygon(draw, skirt_pts, fill=theme["accent_mid"], outline=theme["outline"], width=2*s)

        draw_curved_line(draw, [(cx - 12*s, cy - 2*s), (cx - 10*s, cy + 16*s)], fill=theme["accent_dark"], width=s)
        draw_curved_line(draw, [(cx + 12*s, cy - 2*s), (cx + 10*s, cy + 16*s)], fill=theme["accent_dark"], width=s)
        draw_curved_line(draw, [(cx, cy - 2*s), (cx, cy + 18*s)], fill=theme["accent_light"], width=s)

        draw.rectangle([cx - 7*s, cy - 12*s, cx + 7*s, cy - 4*s], fill=theme["accent_light"], outline=theme["outline"], width=s)
        draw.ellipse([cx - 3*s, cy - 10*s, cx + 3*s, cy - 6*s], fill=theme["glow"], outline=theme["outline"], width=s)


def draw_arm_upper(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    sp = theme["species"]

    if sp == "alien":
        draw_curved_polygon(draw, [
            (cx - 10*s, cy - 18*s),
            (cx + 10*s, cy - 18*s),
            (cx + 12*s, cy),
            (cx + 8*s, cy + 18*s),
            (cx - 8*s, cy + 18*s),
            (cx - 12*s, cy)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
        draw.ellipse([cx - 4*s, cy + 12*s, cx + 4*s, cy + 20*s], fill=theme["glow"])
    elif sp == "undead":
        draw.ellipse([cx - 8*s, cy - 18*s, cx + 8*s, cy - 10*s], fill=theme["primary_mid"], outline=theme["outline"], width=s)
        draw.rectangle([cx - 4*s, cy - 12*s, cx + 4*s, cy + 14*s], fill=theme["primary_light"], outline=theme["outline"], width=s)
        draw.ellipse([cx - 7*s, cy + 12*s, cx + 7*s, cy + 20*s], fill=theme["primary_mid"], outline=theme["outline"], width=s)
    else:
        # 🧝 Humanoid / Anime Upper Arm with Convex Shoulder Cap & Elbow Joint
        dir_mul = 1 if is_left else -1
        arm_pts = [
            (cx - 10*s, cy - 16*s),  # Inner shoulder
            (cx, cy - 22*s),         # Top convex shoulder cap (prevents rotation gaps!)
            (cx + 10*s, cy - 16*s),  # Outer shoulder
            (cx + 12*s, cy - 2*s),   # Outer bicep curve
            (cx + 8*s, cy + 14*s),   # Outer elbow
            (cx, cy + 20*s),         # Bottom convex elbow cap (perfect pivot overlap!)
            (cx - 7*s, cy + 14*s),   # Inner elbow
            (cx - 9*s, cy - 2*s)     # Inner arm curve
        ]
        draw_curved_polygon(draw, arm_pts, fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

        hl_pts = [
            (cx - 3*s * dir_mul, cy - 14*s),
            (cx - 2*s * dir_mul, cy),
            (cx - 1*s * dir_mul, cy + 12*s)
        ]
        draw_curved_line(draw, hl_pts, fill=theme["primary_light"], width=2*s)

        sh_pts = [
            (cx + 8*s * dir_mul, cy - 12*s),
            (cx + 9*s * dir_mul, cy),
            (cx + 6*s * dir_mul, cy + 12*s)
        ]
        draw_curved_line(draw, sh_pts, fill=theme["primary_dark"], width=2*s)

        draw_curved_polygon(draw, [
            (cx - 11*s, cy - 18*s),
            (cx + 11*s, cy - 18*s),
            (cx + 12*s, cy - 11*s),
            (cx - 12*s, cy - 11*s)
        ], fill=theme["accent_mid"], outline=theme["outline"], width=s)
        draw_curved_line(draw, [(cx - 11*s, cy - 15*s), (cx + 11*s, cy - 15*s)], fill=theme["accent_light"], width=s)


def draw_arm_lower(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    sp = theme["species"]

    if sp == "alien":
        draw_curved_polygon(draw, [
            (cx - 8*s, cy - 16*s),
            (cx + 8*s, cy - 16*s),
            (cx + 10*s, cy + 4*s),
            (cx + 7*s, cy + 18*s),
            (cx - 7*s, cy + 18*s),
            (cx - 10*s, cy + 4*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
        draw.line([(cx, cy - 12*s), (cx, cy + 14*s)], fill=theme["glow"], width=s)
    elif sp == "undead":
        draw.line([(cx - 3*s, cy - 14*s), (cx - 3*s, cy + 16*s)], fill=theme["primary_light"], width=2*s)
        draw.line([(cx + 3*s, cy - 14*s), (cx + 3*s, cy + 16*s)], fill=theme["primary_light"], width=2*s)
    else:
        # 🧝 Humanoid / Anime Forearm with Convex Elbow Pivot Cap & Sleek Vambrace
        dir_mul = 1 if is_left else -1
        forearm_pts = [
            (cx - 8*s, cy - 14*s),   # Inner elbow
            (cx, cy - 20*s),         # Top convex elbow socket (nests inside upper arm!)
            (cx + 8*s, cy - 14*s),   # Outer elbow
            (cx + 10*s, cy),         # Outer forearm muscle
            (cx + 7*s, cy + 16*s),   # Wrist outer
            (cx, cy + 19*s),         # Wrist bottom cap
            (cx - 7*s, cy + 16*s),   # Wrist inner
            (cx - 9*s, cy)           # Inner forearm
        ]
        draw_curved_polygon(draw, forearm_pts, fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

        vambrace_pts = [
            (cx - 9*s, cy - 4*s),
            (cx + 9*s, cy - 4*s),
            (cx + 8*s, cy + 16*s),
            (cx - 8*s, cy + 16*s)
        ]
        draw_curved_polygon(draw, vambrace_pts, fill=theme["accent_mid"], outline=theme["outline"], width=s)

        draw_curved_line(draw, [(cx - 8*s, cy + 2*s), (cx + 8*s, cy + 2*s)], fill=theme["accent_dark"], width=s)
        draw_curved_line(draw, [(cx - 7*s, cy + 10*s), (cx + 7*s, cy + 10*s)], fill=theme["accent_dark"], width=s)
        draw_curved_line(draw, [(cx - 2*s * dir_mul, cy - 3*s), (cx - 2*s * dir_mul, cy + 15*s)], fill=theme["accent_light"], width=2*s)


def draw_hand(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    sp = theme["species"]

    if sp in ["alien", "demon", "reptilian", "beast", "insectoid"]:
        draw_curved_polygon(draw, [
            (cx - 8*s, cy - 8*s),
            (cx + 8*s, cy - 8*s),
            (cx + 9*s, cy + 2*s),
            (cx - 9*s, cy + 2*s)
        ], fill=theme["primary_mid"], outline=theme["outline"], width=s)
        if sp == "beast":
            draw.polygon([(cx - 10*s, cy - 10*s), (cx - 5*s, cy - 6*s), (cx, cy - 10*s), (cx + 5*s, cy - 6*s), (cx + 10*s, cy - 10*s)], fill=theme["accent_mid"])
        for ox in [-6, -2, 2, 6]:
            draw.polygon([
                (cx + (ox-1)*s, cy + 2*s),
                (cx + ox*s, cy + 12*s),
                (cx + (ox+1)*s, cy + 2*s)
            ], fill=theme["outline"] if sp == "beast" else theme["accent_light"], outline=theme["outline"], width=s)
    elif sp == "mech":
        draw.rectangle([cx - 9*s, cy - 8*s, cx + 9*s, cy + 4*s], fill=theme["primary_dark"], outline=theme["outline"], width=s)
        draw.rectangle([cx - 7*s, cy + 4*s, cx + 7*s, cy + 12*s], fill=theme["primary_light"], outline=theme["outline"], width=s)
        draw.line([(cx - 5*s, cy + 4*s), (cx - 5*s, cy + 12*s)], fill=theme["outline"], width=s)
        draw.line([(cx, cy + 4*s), (cx, cy + 12*s)], fill=theme["outline"], width=s)
        draw.line([(cx + 5*s, cy + 4*s), (cx + 5*s, cy + 12*s)], fill=theme["outline"], width=s)
    elif sp == "undead":
        for ox in [-6, -2, 2, 6]:
            draw.line([(cx + ox*s, cy - 4*s), (cx + ox*s, cy + 10*s)], fill=theme["primary_light"], width=2*s)
            draw.ellipse([cx + (ox-1)*s, cy + 8*s, cx + (ox+1)*s, cy + 11*s], fill=theme["outline"])
    else:
        # 🧝 Organic Humanoid / Anime Hand with curved palm, opposable thumb, and slender fingers
        thumb_mul = -1 if is_left else 1
        palm_pts = [
            (cx - 7*s, cy - 10*s),
            (cx + 7*s, cy - 10*s),
            (cx + 8*s, cy + 2*s),
            (cx - 8*s, cy + 2*s)
        ]
        draw_curved_polygon(draw, palm_pts, fill=theme["primary_mid"], outline=theme["outline"], width=s)

        thumb_pts = [
            (cx + 5*s * thumb_mul, cy - 6*s),
            (cx + 12*s * thumb_mul, cy - 1*s),
            (cx + 14*s * thumb_mul, cy + 5*s),
            (cx + 9*s * thumb_mul, cy + 6*s),
            (cx + 5*s * thumb_mul, cy + 1*s)
        ]
        draw_curved_polygon(draw, thumb_pts, fill=theme["primary_light"], outline=theme["outline"], width=s)

        finger_widths = [(-6, -3, 9), (-3, 0, 11), (0, 3, 10), (3, 6, 8)]
        for f_left, f_right, f_len in finger_widths:
            f_pts = [
                (cx + f_left*s, cy + 2*s),
                (cx + (f_left+0.5)*s, cy + f_len*s),
                (cx + (f_right-0.5)*s, cy + f_len*s),
                (cx + f_right*s, cy + 2*s)
            ]
            draw_curved_polygon(draw, f_pts, fill=theme["primary_light"], outline=theme["outline"], width=s)
            draw.line([(cx + (f_left+1)*s, cy + (f_len//2)*s), (cx + (f_right-1)*s, cy + (f_len//2)*s)], fill=theme["primary_mid"], width=s)


def draw_leg_upper(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    sp = theme["species"]

    if sp == "undead":
        draw.ellipse([cx - 8*s, cy - 20*s, cx + 8*s, cy - 12*s], fill=theme["primary_mid"], outline=theme["outline"], width=s)
        draw.rectangle([cx - 5*s, cy - 14*s, cx + 5*s, cy + 14*s], fill=theme["primary_light"], outline=theme["outline"], width=s)
        draw.ellipse([cx - 8*s, cy + 12*s, cx + 8*s, cy + 20*s], fill=theme["primary_mid"], outline=theme["outline"], width=s)
    else:
        # 🧝 Humanoid / Anime Thigh with Convex Hip Ball & Convex Knee Cap
        dir_mul = 1 if is_left else -1
        thigh_pts = [
            (cx - 10*s, cy - 16*s),  # Hip inner
            (cx, cy - 22*s),         # Top convex hip ball cap (rotates seamlessly under pelvis!)
            (cx + 12*s, cy - 16*s),  # Hip outer
            (cx + 14*s, cy),         # Thigh lateral curve
            (cx + 9*s, cy + 16*s),   # Knee outer
            (cx, cy + 21*s),         # Bottom convex knee cap (pivot overlap!)
            (cx - 8*s, cy + 16*s),   # Knee inner
            (cx - 9*s, cy)           # Thigh medial curve
        ]
        draw_curved_polygon(draw, thigh_pts, fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

        draw_curved_line(draw, [
            (cx - 2*s * dir_mul, cy - 14*s),
            (cx - 1*s * dir_mul, cy),
            (cx, cy + 14*s)
        ], fill=theme["primary_light"], width=2*s)

        draw_curved_line(draw, [
            (cx + 10*s * dir_mul, cy - 12*s),
            (cx + 11*s * dir_mul, cy),
            (cx + 7*s * dir_mul, cy + 14*s)
        ], fill=theme["primary_dark"], width=2*s)

        draw_curved_line(draw, [(cx - 11*s, cy - 12*s), (cx + 13*s, cy - 12*s)], fill=theme["accent_dark"], width=2*s)


def draw_leg_lower(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    sp = theme["species"]

    if sp == "undead":
        draw.line([(cx - 3*s, cy - 16*s), (cx - 3*s, cy + 16*s)], fill=theme["primary_light"], width=2*s)
        draw.line([(cx + 3*s, cy - 16*s), (cx + 3*s, cy + 16*s)], fill=theme["primary_light"], width=2*s)
    else:
        # 🧝 Humanoid / Anime Shin/Calf with Convex Knee Cap & Detailed Boot
        dir_mul = 1 if is_left else -1
        shin_pts = [
            (cx - 9*s, cy - 15*s),   # Knee inner
            (cx, cy - 21*s),         # Top convex knee cap (nests into thigh knee!)
            (cx + 9*s, cy - 15*s),   # Knee outer
            (cx + 12*s, cy - 2*s),   # Calf bulge outer
            (cx + 8*s, cy + 16*s),   # Ankle outer
            (cx, cy + 20*s),         # Ankle bottom cap
            (cx - 7*s, cy + 16*s),   # Ankle inner
            (cx - 8*s, cy - 2*s)     # Calf inner
        ]
        draw_curved_polygon(draw, shin_pts, fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

        boot_pts = [
            (cx - 10*s, cy - 6*s),   # Boot cuff top inner
            (cx + 10*s, cy - 6*s),   # Boot cuff top outer
            (cx + 11*s, cy + 4*s),
            (cx + 8*s, cy + 18*s),   # Ankle
            (cx - 8*s, cy + 18*s),
            (cx - 10*s, cy + 4*s)
        ]
        draw_curved_polygon(draw, boot_pts, fill=theme["accent_mid"], outline=theme["outline"], width=s)

        cuff_pts = [(cx - 11*s, cy - 8*s), (cx, cy - 6*s), (cx + 11*s, cy - 8*s), (cx + 10*s, cy - 2*s), (cx - 10*s, cy - 2*s)]
        draw_curved_polygon(draw, cuff_pts, fill=theme["accent_light"], outline=theme["outline"], width=s)

        draw_curved_line(draw, [(cx, cy - 2*s), (cx, cy + 16*s)], fill=theme["accent_dark"], width=s)


def draw_foot(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    sp = theme["species"]
    dir_mul = 1 if is_left else -1

    if sp in ["alien", "demon", "reptilian", "beast", "insectoid"]:
        claw_pts = [
            (cx - 12*s * dir_mul, cy - 10*s),
            (cx + 8*s * dir_mul, cy - 10*s),
            (cx + 14*s * dir_mul, cy - 2*s),
            (cx + 22*s * dir_mul, cy + 4*s),
            (cx + 25*s * dir_mul, cy + 8*s),
            (cx + 14*s * dir_mul, cy + 10*s),
            (cx + 4*s * dir_mul, cy + 7*s),
            (cx - 10*s * dir_mul, cy + 10*s),
            (cx - 14*s * dir_mul, cy + 4*s),
            (cx - 13*s * dir_mul, cy - 2*s)
        ]
        draw_curved_polygon(draw, claw_pts, fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
        draw_curved_line(draw, [(cx - 10*s * dir_mul, cy + 9*s), (cx + 23*s * dir_mul, cy + 9*s)], fill=theme["outline"], width=2*s)
        for tox in [8, 14, 20]:
            draw.polygon([
                (cx + tox*s * dir_mul, cy + 4*s),
                (cx + (tox+4)*s * dir_mul, cy + 10*s),
                (cx + (tox+1)*s * dir_mul, cy + 9*s)
            ], fill=theme["outline"] if sp == "beast" else theme["accent_light"], outline=theme["outline"], width=s)
    elif sp == "mech":
        mech_boot = [
            (cx - 13*s * dir_mul, cy - 10*s),
            (cx + 9*s * dir_mul, cy - 10*s),
            (cx + 16*s * dir_mul, cy - 2*s),
            (cx + 23*s * dir_mul, cy + 5*s),
            (cx + 22*s * dir_mul, cy + 11*s),
            (cx - 13*s * dir_mul, cy + 11*s),
            (cx - 14*s * dir_mul, cy + 4*s)
        ]
        draw_curved_polygon(draw, mech_boot, fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
        draw.line([(cx - 13*s * dir_mul, cy + 9*s), (cx + 22*s * dir_mul, cy + 9*s)], fill=theme["accent_mid"], width=2*s)
        draw.rectangle([cx - 4*s, cy - 2*s, cx + 8*s, cy + 2*s], fill=theme["glow"], outline=theme["outline"], width=s)
    elif sp == "undead":
        draw.line([(cx - 10*s * dir_mul, cy - 4*s), (cx + 16*s * dir_mul, cy + 4*s)], fill=theme["primary_light"], width=3*s)
        for tx in [4, 10, 16]:
            draw.line([(cx + tx*s * dir_mul, cy + 2*s), (cx + (tx+3)*s * dir_mul, cy + 8*s)], fill=theme["primary_light"], width=2*s)
    else:
        # 🧝 Stylized Anime Boot / Shoe with curved instep, elevated heel, sole tread, and highlight
        boot_pts = [
            (cx - 11*s * dir_mul, cy - 10*s),  # Ankle collar back
            (cx + 7*s * dir_mul, cy - 10*s),   # Ankle collar front
            (cx + 14*s * dir_mul, cy - 2*s),   # Instep curve
            (cx + 22*s * dir_mul, cy + 5*s),   # Toe box top
            (cx + 24*s * dir_mul, cy + 10*s),  # Toe tip
            (cx + 12*s * dir_mul, cy + 11*s),  # Sole front
            (cx + 4*s * dir_mul, cy + 8*s),    # Foot arch indentation
            (cx - 10*s * dir_mul, cy + 11*s),  # Heel bottom
            (cx - 14*s * dir_mul, cy + 5*s),   # Heel back curve
            (cx - 13*s * dir_mul, cy - 2*s)    # Achilles curve
        ]
        draw_curved_polygon(draw, boot_pts, fill=theme["accent_mid"], outline=theme["outline"], width=2*s)

        sole_pts = [
            (cx - 14*s * dir_mul, cy + 8*s),
            (cx + 24*s * dir_mul, cy + 8*s),
            (cx + 24*s * dir_mul, cy + 11*s),
            (cx - 14*s * dir_mul, cy + 11*s)
        ]
        draw.polygon(sole_pts, fill=theme["outline"])

        toe_hl = [
            (cx + 16*s * dir_mul, cy + 3*s),
            (cx + 22*s * dir_mul, cy + 5*s),
            (cx + 20*s * dir_mul, cy + 7*s)
        ]
        draw_curved_polygon(draw, toe_hl, fill=theme["accent_light"])

        draw_curved_line(draw, [(cx - 10*s * dir_mul, cy - 4*s), (cx + 10*s * dir_mul, cy - 4*s)], fill=theme["accent_dark"], width=2*s)
        draw.rectangle([cx + 3*s * dir_mul - 2*s, cy - 6*s, cx + 3*s * dir_mul + 2*s, cy - 2*s], fill=theme["accent_light"], outline=theme["outline"], width=s)



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


def draw_wing_upper(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    dir_mul = 1 if is_left else -1
    draw.polygon([
        (cx - 14*s * dir_mul, cy + 20*s),
        (cx + 16*s * dir_mul, cy - 20*s),
        (cx + 20*s * dir_mul, cy - 14*s),
        (cx - 6*s * dir_mul, cy + 24*s)
    ], fill=theme["accent_mid"], outline=theme["outline"], width=2*s)
    draw.polygon([
        (cx - 10*s * dir_mul, cy + 18*s),
        (cx + 14*s * dir_mul, cy - 16*s),
        (cx + 2*s * dir_mul, cy + 16*s),
        (cx - 4*s * dir_mul, cy + 22*s)
    ], fill=theme["primary_light"])


def draw_wing_lower(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    dir_mul = 1 if is_left else -1
    draw.polygon([
        (cx - 16*s * dir_mul, cy - 18*s),
        (cx + 18*s * dir_mul, cy + 14*s),
        (cx + 6*s * dir_mul, cy + 22*s),
        (cx - 12*s * dir_mul, cy - 4*s)
    ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
    draw.line([(cx - 14*s * dir_mul, cy - 14*s), (cx + 16*s * dir_mul, cy + 12*s)], fill=theme["glow"], width=s)


# ==============================================================================
# Public Generation APIs
# ==============================================================================

def generate_all(out_dir, prefix="warrior", archetype="warrior", prompt="", seed=-1, custom_colors=None, custom_features=None, art_style="anime"):
    """
    Generates all limb sprites for any creature or humanoid.
    Dynamically responds to prompt concepts, seeds, custom colors, custom features, and art styles.
    """
    os.makedirs(out_dir, exist_ok=True)
    theme = build_palette(prompt, archetype, seed, custom_colors, art_style)
    s_int = seed if seed >= 0 else random.randint(1, 999999999)
    feat = custom_features or {}

    head_sp = feat.get("head_style") or theme["species"]
    torso_sp = feat.get("torso_style") or theme["species"]
    hand_sp = feat.get("hand_style") or theme["species"]
    foot_sp = feat.get("foot_style") or theme["species"]

    theme_head = dict(theme, species=head_sp)
    theme_torso = dict(theme, species=torso_sp)
    theme_hand = dict(theme, species=hand_sp)
    theme_foot = dict(theme, species=foot_sp)

    parts = {
        "head": ((64, 64), lambda d, w, h, s: draw_head(d, w, h, s, theme_head, s_int)),
        "torso": ((72, 64), lambda d, w, h, s: draw_torso(d, w, h, s, theme_torso, s_int)),
        "pelvis": ((64, 48), lambda d, w, h, s: draw_pelvis(d, w, h, s, theme_torso, s_int)),
        "arm_upper_L": ((44, 56), lambda d, w, h, s: draw_arm_upper(d, w, h, s, theme, True)),
        "arm_lower_L": ((36, 52), lambda d, w, h, s: draw_arm_lower(d, w, h, s, theme, True)),
        "hand_L": ((32, 32), lambda d, w, h, s: draw_hand(d, w, h, s, theme_hand, True)),
        "arm_upper_R": ((44, 56), lambda d, w, h, s: draw_arm_upper(d, w, h, s, theme, False)),
        "arm_lower_R": ((36, 52), lambda d, w, h, s: draw_arm_lower(d, w, h, s, theme, False)),
        "hand_R": ((32, 32), lambda d, w, h, s: draw_hand(d, w, h, s, theme_hand, False)),
        "leg_upper_L": ((40, 56), lambda d, w, h, s: draw_leg_upper(d, w, h, s, theme, True)),
        "leg_lower_L": ((36, 56), lambda d, w, h, s: draw_leg_lower(d, w, h, s, theme, True)),
        "foot_L": ((48, 32), lambda d, w, h, s: draw_foot(d, w, h, s, theme_foot, True)),
        "leg_upper_R": ((40, 56), lambda d, w, h, s: draw_leg_upper(d, w, h, s, theme, False)),
        "leg_lower_R": ((36, 56), lambda d, w, h, s: draw_leg_lower(d, w, h, s, theme, False)),
        "foot_R": ((48, 32), lambda d, w, h, s: draw_foot(d, w, h, s, theme_foot, False)),
    }

    # Optional wings (if prompt explicitly mentions wings or requested in custom features)
    has_wings = bool(feat.get("has_wings", False)) or bool(
        re.search(r'\b(wings?|winged|angel wings?|fairy wings?|bat wings?)\b', prompt.lower())
    )
    if has_wings:
        parts["wing_upper_L"] = ((48, 64), lambda d, w, h, s: draw_wing_upper(d, w, h, s, theme, True))
        parts["wing_upper_R"] = ((48, 64), lambda d, w, h, s: draw_wing_upper(d, w, h, s, theme, False))
        parts["wing_lower_L"] = ((48, 64), lambda d, w, h, s: draw_wing_lower(d, w, h, s, theme, True))
        parts["wing_lower_R"] = ((48, 64), lambda d, w, h, s: draw_wing_lower(d, w, h, s, theme, False))

    # Optional tail (if prompt explicitly mentions tail or requested in custom features)
    has_tail = bool(feat.get("has_tail", False)) or bool(
        re.search(r'\b(tails?|tailed)\b', prompt.lower())
    )
    if has_tail:
        parts["tail_01"] = ((36, 36), lambda d, w, h, s: draw_beast_tail(d, w, h, s, theme, 1))
        parts["tail_02"] = ((32, 32), lambda d, w, h, s: draw_beast_tail(d, w, h, s, theme, 2))
        parts["tail_03"] = ((28, 28), lambda d, w, h, s: draw_beast_tail(d, w, h, s, theme, 3))

    generated_paths = []
    for name, (size, fn) in parts.items():
        img = create_sprite(size, fn, art_style=art_style, detail_level=feat.get("detail_level", 3))
        out_path = os.path.join(out_dir, f"{prefix}_{name}.png")
        img.save(out_path, "PNG")
        generated_paths.append(out_path)

    # Automatically composite connected full-body preview
    try:
        preview_path = create_character_assembled_preview(out_dir, prefix=prefix, rig_type="biped")
        if preview_path and os.path.isfile(preview_path):
            generated_paths.append(str(preview_path))
    except Exception as e:
        print(f"[Generator] Warning: Could not create assembled preview for '{prefix}': {e}")

    print(f"[Generator] Created {len(generated_paths)} {theme['species'].upper()} sprites for '{prefix}' in: {out_dir}")
    return generated_paths


def generate_quadruped(out_dir, prefix="fenrir", archetype="beast", prompt="", seed=-1, art_style="anime", detail_level=3):
    """Generates all 20 quadruped body part sprites."""
    os.makedirs(out_dir, exist_ok=True)
    theme = build_palette(prompt, archetype, seed, art_style=art_style)
    s_int = seed if seed >= 0 else random.randint(1, 999999999)

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
        img = create_sprite(size, fn, art_style=art_style, detail_level=detail_level)
        out_path = os.path.join(out_dir, f"{prefix}_{name}.png")
        img.save(out_path, "PNG")
        generated_paths.append(out_path)

    # Automatically composite connected full-body preview
    try:
        preview_path = create_character_assembled_preview(out_dir, prefix=prefix, rig_type="quadruped")
        if preview_path and os.path.isfile(preview_path):
            generated_paths.append(str(preview_path))
    except Exception as e:
        print(f"[Generator] Warning: Could not create quadruped assembled preview for '{prefix}': {e}")

    print(f"[Generator] Created {len(generated_paths)} QUADRUPED sprites for '{prefix}' in: {out_dir}")
    return generated_paths


def create_character_assembled_preview(char_dir, prefix=None, rig_type="biped"):
    """
    Composites all sliced limb sprites in char_dir into a single full-body
    connected character preview ({prefix}_full.png).
    Returns the Path to the generated full-body preview image.
    """
    from pathlib import Path
    char_dir = Path(char_dir)
    if not prefix:
        prefix = char_dir.name

    limbs = {}
    for p in char_dir.glob("*.png"):
        if "_exploded" in p.name or "_full" in p.name or p.name.startswith("."):
            continue
        bone = p.stem
        if bone.startswith(prefix + "_"):
            bone = bone[len(prefix) + 1:]
        try:
            limbs[bone] = Image.open(p).convert("RGBA")
        except Exception:
            pass

    if not limbs:
        return None

    # Detect quadruped vs biped
    is_quadruped = rig_type.lower() == "quadruped" or "leg_front_upper_L" in limbs or "paw_front_L" in limbs

    if is_quadruped:
        # Quadruped layout
        tw, th = limbs.get("torso", Image.new("RGBA", (80, 64))).size
        hw, hh = limbs.get("head", Image.new("RGBA", (64, 64))).size
        pw, ph = limbs.get("pelvis", Image.new("RGBA", (64, 56))).size
        canvas_w = max(400, tw + hw + pw + 120)
        canvas_h = max(360, th + hh + ph + 120)
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        cx = canvas_w // 2
        cy = canvas_h // 2

        # Back legs (R)
        if "leg_back_upper_R" in limbs: canvas.alpha_composite(limbs["leg_back_upper_R"], (cx + 50, cy))
        if "leg_back_lower_R" in limbs: canvas.alpha_composite(limbs["leg_back_lower_R"], (cx + 54, cy + 40))
        if "paw_back_R" in limbs: canvas.alpha_composite(limbs["paw_back_R"], (cx + 56, cy + 80))
        if "leg_front_upper_R" in limbs: canvas.alpha_composite(limbs["leg_front_upper_R"], (cx - 70, cy))
        if "leg_front_lower_R" in limbs: canvas.alpha_composite(limbs["leg_front_lower_R"], (cx - 72, cy + 40))
        if "paw_front_R" in limbs: canvas.alpha_composite(limbs["paw_front_R"], (cx - 72, cy + 80))

        # Tail
        for t in ["tail_03", "tail_02", "tail_01"]:
            if t in limbs: canvas.alpha_composite(limbs[t], (cx + 70, cy - 20))
        # Spine & Pelvis
        if "pelvis" in limbs: canvas.alpha_composite(limbs["pelvis"], (cx + 30, cy - 20))
        if "spine" in limbs: canvas.alpha_composite(limbs["spine"], (cx, cy - 20))
        # Torso
        if "torso" in limbs: canvas.alpha_composite(limbs["torso"], (cx - 40, cy - 24))
        # Neck & Head
        if "neck" in limbs: canvas.alpha_composite(limbs["neck"], (cx - 80, cy - 40))
        if "head" in limbs: canvas.alpha_composite(limbs["head"], (cx - 120, cy - 60))

        # Front legs (L)
        if "leg_front_upper_L" in limbs: canvas.alpha_composite(limbs["leg_front_upper_L"], (cx - 85, cy + 10))
        if "leg_front_lower_L" in limbs: canvas.alpha_composite(limbs["leg_front_lower_L"], (cx - 87, cy + 50))
        if "paw_front_L" in limbs: canvas.alpha_composite(limbs["paw_front_L"], (cx - 87, cy + 90))
        if "leg_back_upper_L" in limbs: canvas.alpha_composite(limbs["leg_back_upper_L"], (cx + 35, cy + 10))
        if "leg_back_lower_L" in limbs: canvas.alpha_composite(limbs["leg_back_lower_L"], (cx + 38, cy + 50))
        if "paw_back_L" in limbs: canvas.alpha_composite(limbs["paw_back_L"], (cx + 40, cy + 90))
    else:
        # Biped layout
        tw, th = limbs.get("torso", Image.new("RGBA", (60, 60))).size
        pw, ph = limbs.get("pelvis", Image.new("RGBA", (50, 40))).size
        hw, hh = limbs.get("head", Image.new("RGBA", (60, 60))).size

        ulw, ulh = limbs.get("leg_upper_L", limbs.get("leg_upper_R", Image.new("RGBA", (40, 50)))).size
        llw, llh = limbs.get("leg_lower_L", limbs.get("leg_lower_R", Image.new("RGBA", (35, 50)))).size
        fw, fh = limbs.get("foot_L", limbs.get("foot_R", Image.new("RGBA", (40, 30)))).size

        uaw, uah = limbs.get("arm_upper_L", limbs.get("arm_upper_R", Image.new("RGBA", (40, 50)))).size
        law, lah = limbs.get("arm_lower_L", limbs.get("arm_lower_R", Image.new("RGBA", (35, 50)))).size
        haw, hah = limbs.get("hand_L", limbs.get("hand_R", Image.new("RGBA", (30, 30)))).size

        canvas_w = max(400, tw + uaw*2 + law*2 + 100)
        canvas_h = max(500, hh + th + ph + ulh + llh + fh + 100)
        cx = canvas_w // 2

        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

        torso_top = hh + 30
        torso_y = torso_top
        pelvis_y = torso_y + int(th * 0.82)
        leg_y = pelvis_y + int(ph * 0.75)

        # 1. Back Wings
        if "wing_upper_R" in limbs:
            w_img = limbs["wing_upper_R"]
            canvas.alpha_composite(w_img, (cx + int(tw * 0.2), torso_y - int(w_img.height * 0.4)))
        if "wing_lower_R" in limbs:
            w_img = limbs["wing_lower_R"]
            canvas.alpha_composite(w_img, (cx + int(tw * 0.4), torso_y))
        if "wing_upper_L" in limbs:
            w_img = limbs["wing_upper_L"]
            canvas.alpha_composite(w_img, (cx - int(tw * 0.2) - w_img.width, torso_y - int(w_img.height * 0.4)))
        if "wing_lower_L" in limbs:
            w_img = limbs["wing_lower_L"]
            canvas.alpha_composite(w_img, (cx - int(tw * 0.4) - w_img.width, torso_y))

        # Tail
        for t_name in ["tail_03", "tail_02", "tail_01", "tail"]:
            if t_name in limbs:
                t_img = limbs[t_name]
                canvas.alpha_composite(t_img, (cx + int(tw * 0.1), pelvis_y + int(ph * 0.2)))

        # 2. Right Arm (Back side)
        r_arm_x = cx + int(tw * 0.45) - int(uaw * 0.2)
        if "arm_upper_R" in limbs:
            canvas.alpha_composite(limbs["arm_upper_R"], (r_arm_x, torso_y + int(th * 0.1)))
        r_low_y = torso_y + int(th * 0.1) + int(uah * 0.8)
        if "arm_lower_R" in limbs:
            canvas.alpha_composite(limbs["arm_lower_R"], (r_arm_x + int(uaw * 0.1), r_low_y))
        if "hand_R" in limbs:
            canvas.alpha_composite(limbs["hand_R"], (r_arm_x + int(uaw * 0.1), r_low_y + int(lah * 0.8)))

        # 3. Legs
        r_leg_x = cx + int(pw * 0.1)
        if "leg_upper_R" in limbs:
            canvas.alpha_composite(limbs["leg_upper_R"], (r_leg_x, leg_y))
        r_leg_low_y = leg_y + int(ulh * 0.8)
        if "leg_lower_R" in limbs:
            canvas.alpha_composite(limbs["leg_lower_R"], (r_leg_x, r_leg_low_y))
        if "foot_R" in limbs:
            canvas.alpha_composite(limbs["foot_R"], (r_leg_x - int(fw * 0.1), r_leg_low_y + int(llh * 0.85)))

        l_leg_x = cx - int(pw * 0.1) - ulw
        if "leg_upper_L" in limbs:
            canvas.alpha_composite(limbs["leg_upper_L"], (l_leg_x, leg_y))
        l_leg_low_y = leg_y + int(ulh * 0.8)
        if "leg_lower_L" in limbs:
            canvas.alpha_composite(limbs["leg_lower_L"], (l_leg_x, l_leg_low_y))
        if "foot_L" in limbs:
            canvas.alpha_composite(limbs["foot_L"], (l_leg_x - int(fw * 0.2), l_leg_low_y + int(llh * 0.85)))

        # 4. Pelvis
        if "pelvis" in limbs:
            canvas.alpha_composite(limbs["pelvis"], (cx - pw // 2, pelvis_y))

        # 5. Torso
        if "torso" in limbs:
            canvas.alpha_composite(limbs["torso"], (cx - tw // 2, torso_y))

        # 6. Head
        if "head" in limbs:
            canvas.alpha_composite(limbs["head"], (cx - hw // 2, torso_y - int(hh * 0.82)))

        # 7. Left Arm (Front side)
        l_arm_x = cx - int(tw * 0.45) - int(uaw * 0.8)
        if "arm_upper_L" in limbs:
            canvas.alpha_composite(limbs["arm_upper_L"], (l_arm_x, torso_y + int(th * 0.1)))
        l_low_y = torso_y + int(th * 0.1) + int(uah * 0.8)
        if "arm_lower_L" in limbs:
            canvas.alpha_composite(limbs["arm_lower_L"], (l_arm_x - int(uaw * 0.05), l_low_y))
        if "hand_L" in limbs:
            canvas.alpha_composite(limbs["hand_L"], (l_arm_x - int(uaw * 0.05), l_low_y + int(lah * 0.8)))

    # Crop bounding box
    bbox = canvas.getbbox()
    if bbox:
        pad = 8
        bbox = (max(0, bbox[0]-pad), max(0, bbox[1]-pad), min(canvas.width, bbox[2]+pad), min(canvas.height, bbox[3]+pad))
        cropped = canvas.crop(bbox)
    else:
        cropped = canvas

    out_file = char_dir / f"{prefix}_full.png"
    cropped.save(out_file, "PNG")
    return out_file


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "sprites/test_char"
    char_name = sys.argv[2] if len(sys.argv) > 2 else "alien"
    concept = sys.argv[3] if len(sys.argv) > 3 else "cyberpunk warrior alien with glowing neon crest"
    generate_all(target, prefix=char_name, prompt=concept)
