import os
import sys
from PIL import Image, ImageDraw

def create_sprite(size, draw_func):
    # Render at 4x resolution for smooth anti-aliased edges, then downsample
    scale = 4
    w, h = size[0] * scale, size[1] * scale
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw_func(draw, w, h, scale)
    return img.resize(size, Image.Resampling.LANCZOS)

# Archetype color palettes
ARCHETYPES = {
    "warrior": {
        "primary_dark": (32, 36, 48, 255),
        "primary_mid": (55, 62, 82, 255),
        "primary_light": (90, 102, 130, 255),
        "accent_dark": (150, 95, 20, 255),
        "accent_mid": (225, 160, 40, 255),
        "accent_light": (255, 215, 90, 255),
        "glow_core": (200, 255, 255, 255),
        "glow": (0, 230, 255, 255),
        "outline": (15, 17, 24, 255),
    },
    "mage": {
        "primary_dark": (35, 22, 55, 255),
        "primary_mid": (68, 40, 105, 255),
        "primary_light": (115, 75, 165, 255),
        "accent_dark": (130, 80, 20, 255),
        "accent_mid": (210, 150, 40, 255),
        "accent_light": (250, 205, 95, 255),
        "glow_core": (255, 220, 255, 255),
        "glow": (255, 40, 220, 255), # Arcane violet/magenta
        "outline": (20, 12, 32, 255),
    },
    "assassin": {
        "primary_dark": (20, 22, 28, 255),
        "primary_mid": (38, 42, 52, 255),
        "primary_light": (68, 74, 88, 255),
        "accent_dark": (85, 15, 22, 255),
        "accent_mid": (170, 32, 45, 255),
        "accent_light": (230, 65, 75, 255),
        "glow_core": (255, 210, 210, 255),
        "glow": (255, 30, 50, 255), # Crimson blood glow
        "outline": (10, 10, 16, 255),
    },
    "ranger": {
        "primary_dark": (25, 42, 30, 255),
        "primary_mid": (48, 80, 55, 255),
        "primary_light": (85, 130, 95, 255),
        "accent_dark": (95, 65, 35, 255),
        "accent_mid": (165, 115, 65, 255),
        "accent_light": (220, 170, 110, 255),
        "glow_core": (220, 255, 220, 255),
        "glow": (45, 240, 120, 255), # Emerald nature glow
        "outline": (14, 26, 16, 255),
    },
    "mech": {
        "primary_dark": (45, 45, 48, 255),
        "primary_mid": (78, 80, 85, 255),
        "primary_light": (125, 128, 135, 255),
        "accent_dark": (165, 80, 0, 255),
        "accent_mid": (245, 140, 0, 255),
        "accent_light": (255, 195, 50, 255),
        "glow_core": (255, 245, 210, 255),
        "glow": (255, 130, 0, 255), # Amber furnace glow
        "outline": (18, 18, 20, 255),
    }
}


def draw_head(draw, w, h, s, theme):
    cx, cy = w // 2, h // 2
    # Skull cap / helmet / hood
    draw.polygon([
        (cx - 18*s, cy + 16*s),
        (cx - 22*s, cy - 6*s),
        (cx - 14*s, cy - 22*s),
        (cx, cy - 26*s),
        (cx + 14*s, cy - 22*s),
        (cx + 22*s, cy - 6*s),
        (cx + 18*s, cy + 16*s),
        (cx, cy + 24*s)
    ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)
    
    # Faceplate / hood highlight
    draw.polygon([
        (cx - 15*s, cy + 14*s),
        (cx - 18*s, cy - 4*s),
        (cx - 10*s, cy - 18*s),
        (cx, cy - 21*s),
        (cx + 10*s, cy - 18*s),
        (cx + 18*s, cy - 4*s),
        (cx + 15*s, cy + 14*s),
        (cx, cy + 20*s)
    ], fill=theme["primary_light"])

    # Forehead crest / gem
    draw.polygon([
        (cx, cy - 28*s),
        (cx + 7*s, cy - 12*s),
        (cx, cy - 8*s),
        (cx - 7*s, cy - 12*s)
    ], fill=theme["accent_mid"], outline=theme["outline"], width=2*s)
    draw.polygon([(cx, cy - 25*s), (cx + 4*s, cy - 12*s), (cx, cy - 10*s)], fill=theme["accent_light"])

    # Glowing T-Visor / Eye Slits
    draw.polygon([
        (cx - 14*s, cy - 2*s),
        (cx + 14*s, cy - 2*s),
        (cx + 14*s, cy + 3*s),
        (cx + 4*s, cy + 4*s),
        (cx + 3*s, cy + 14*s),
        (cx - 3*s, cy + 14*s),
        (cx - 4*s, cy + 4*s),
        (cx - 14*s, cy + 3*s)
    ], fill=theme["glow"], outline=theme["outline"], width=s)
    # Inner bright core
    draw.polygon([
        (cx - 10*s, cy),
        (cx + 10*s, cy),
        (cx + 10*s, cy + 2*s),
        (cx + 2*s, cy + 2*s),
        (cx + 1*s, cy + 12*s),
        (cx - 1*s, cy + 12*s),
        (cx - 2*s, cy + 2*s),
        (cx - 10*s, cy + 2*s)
    ], fill=theme["glow_core"])


def draw_torso(draw, w, h, s, theme):
    cx, cy = w // 2, h // 2
    # Chestplate / Robe base
    draw.polygon([
        (cx - 28*s, cy - 24*s),
        (cx + 28*s, cy - 24*s),
        (cx + 24*s, cy + 6*s),
        (cx + 16*s, cy + 26*s),
        (cx, cy + 30*s),
        (cx - 16*s, cy + 26*s),
        (cx - 24*s, cy + 6*s)
    ], fill=theme["primary_dark"], outline=theme["outline"], width=2*s)

    # Front plates / Robe lapels
    draw.polygon([
        (cx - 24*s, cy - 20*s),
        (cx - 3*s, cy - 20*s),
        (cx - 2*s, cy + 6*s),
        (cx - 20*s, cy + 4*s)
    ], fill=theme["primary_mid"], outline=theme["outline"], width=s)
    draw.polygon([
        (cx + 24*s, cy - 20*s),
        (cx + 3*s, cy - 20*s),
        (cx + 2*s, cy + 6*s),
        (cx + 20*s, cy + 4*s)
    ], fill=theme["primary_light"], outline=theme["outline"], width=s)

    # Accent Trim on Shoulders
    draw.polygon([
        (cx - 28*s, cy - 24*s),
        (cx - 14*s, cy - 24*s),
        (cx - 16*s, cy - 18*s),
        (cx - 27*s, cy - 18*s)
    ], fill=theme["accent_mid"], outline=theme["outline"], width=s)
    draw.polygon([
        (cx + 28*s, cy - 24*s),
        (cx + 14*s, cy - 24*s),
        (cx + 16*s, cy - 18*s),
        (cx + 27*s, cy - 18*s)
    ], fill=theme["accent_mid"], outline=theme["outline"], width=s)

    # Central Arc-Core / Mystic Rune
    draw.ellipse([cx - 8*s, cy - 6*s, cx + 8*s, cy + 10*s], fill=theme["primary_dark"], outline=theme["accent_mid"], width=2*s)
    draw.ellipse([cx - 5*s, cy - 3*s, cx + 5*s, cy + 7*s], fill=theme["glow"])
    draw.ellipse([cx - 2*s, cy - 1*s, cx + 2*s, cy + 3*s], fill=theme["glow_core"])


def draw_pelvis(draw, w, h, s, theme):
    cx, cy = w // 2, h // 2
    # Belt / Tassets / Sash
    draw.polygon([
        (cx - 24*s, cy - 12*s),
        (cx + 24*s, cy - 12*s),
        (cx + 20*s, cy + 14*s),
        (cx + 8*s, cy + 18*s),
        (cx, cy + 10*s),
        (cx - 8*s, cy + 18*s),
        (cx - 20*s, cy + 14*s)
    ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

    draw.rectangle([cx - 24*s, cy - 12*s, cx + 24*s, cy - 4*s], fill=theme["primary_dark"], outline=theme["outline"], width=s)
    
    # Center Buckle / Emblem
    draw.polygon([
        (cx, cy - 14*s),
        (cx + 8*s, cy - 7*s),
        (cx, cy),
        (cx - 8*s, cy - 7*s)
    ], fill=theme["accent_mid"], outline=theme["outline"], width=2*s)
    draw.polygon([(cx, cy - 12*s), (cx + 5*s, cy - 7*s), (cx, cy - 2*s)], fill=theme["accent_light"])

    # Hip joints
    draw.ellipse([cx - 22*s, cy, cx - 12*s, cy + 10*s], fill=theme["primary_dark"], outline=theme["outline"], width=s)
    draw.ellipse([cx + 12*s, cy, cx + 22*s, cy + 10*s], fill=theme["primary_dark"], outline=theme["outline"], width=s)


def draw_arm_upper(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    draw.polygon([
        (cx - 14*s, cy - 20*s),
        (cx + 14*s, cy - 20*s),
        (cx + 16*s, cy - 4*s),
        (cx + 10*s, cy + 18*s),
        (cx, cy + 22*s),
        (cx - 10*s, cy + 18*s),
        (cx - 16*s, cy - 4*s)
    ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

    rim_y = cy - 6*s
    draw.rectangle([cx - 15*s, rim_y, cx + 15*s, rim_y + 5*s], fill=theme["accent_mid"], outline=theme["outline"], width=s)
    draw.rectangle([cx - 6*s, cy + 2*s, cx + 6*s, cy + 16*s], fill=theme["primary_light"], outline=theme["outline"], width=s)


def draw_arm_lower(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    draw.polygon([
        (cx - 12*s, cy - 18*s),
        (cx + 12*s, cy - 18*s),
        (cx + 14*s, cy + 6*s),
        (cx + 8*s, cy + 20*s),
        (cx - 8*s, cy + 20*s),
        (cx - 14*s, cy + 6*s)
    ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

    draw.polygon([
        (cx - 6*s, cy - 14*s),
        (cx + 6*s, cy - 14*s),
        (cx + 7*s, cy + 12*s),
        (cx - 7*s, cy + 12*s)
    ], fill=theme["primary_light"], outline=theme["outline"], width=s)

    draw.line([(cx, cy - 12*s), (cx, cy + 10*s)], fill=theme["glow"], width=2*s)


def draw_hand(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    draw.ellipse([cx - 12*s, cy - 12*s, cx + 12*s, cy + 12*s], fill=theme["primary_dark"], outline=theme["outline"], width=2*s)
    draw.rectangle([cx - 10*s, cy - 6*s, cx + 10*s, cy + 4*s], fill=theme["primary_light"], outline=theme["outline"], width=s)
    for i in [-6, -2, 2, 6]:
        draw.rectangle([cx + (i-1)*s, cy - 4*s, cx + (i+1)*s, cy - 2*s], fill=theme["accent_mid"])


def draw_leg_upper(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    draw.polygon([
        (cx - 12*s, cy - 22*s),
        (cx + 12*s, cy - 22*s),
        (cx + 14*s, cy + 8*s),
        (cx + 8*s, cy + 22*s),
        (cx, cy + 24*s),
        (cx - 8*s, cy + 22*s),
        (cx - 14*s, cy + 8*s)
    ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

    draw.ellipse([cx - 10*s, cy + 10*s, cx + 10*s, cy + 24*s], fill=theme["primary_dark"], outline=theme["outline"], width=s)
    draw.ellipse([cx - 5*s, cy + 13*s, cx + 5*s, cy + 21*s], fill=theme["accent_mid"])


def draw_leg_lower(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    draw.polygon([
        (cx - 11*s, cy - 22*s),
        (cx + 11*s, cy - 22*s),
        (cx + 13*s, cy + 4*s),
        (cx + 8*s, cy + 22*s),
        (cx - 8*s, cy + 22*s),
        (cx - 13*s, cy + 4*s)
    ], fill=theme["primary_mid"], outline=theme["outline"], width=2*s)

    draw.polygon([
        (cx, cy - 18*s),
        (cx + 5*s, cy + 12*s),
        (cx - 5*s, cy + 12*s)
    ], fill=theme["primary_light"], outline=theme["outline"], width=s)
    draw.line([(cx, cy - 14*s), (cx, cy + 4*s)], fill=theme["glow"], width=2*s)


def draw_foot(draw, w, h, s, theme, is_left=True):
    cx, cy = w // 2, h // 2
    dir_mul = 1 if is_left else -1
    draw.polygon([
        (cx - 14*s * dir_mul, cy - 10*s),
        (cx + 6*s * dir_mul, cy - 10*s),
        (cx + 20*s * dir_mul, cy + 2*s),
        (cx + 22*s * dir_mul, cy + 10*s),
        (cx - 16*s * dir_mul, cy + 10*s),
        (cx - 16*s * dir_mul, cy - 2*s)
    ], fill=theme["primary_dark"], outline=theme["outline"], width=2*s)

    draw.polygon([
        (cx + 8*s * dir_mul, cy),
        (cx + 20*s * dir_mul, cy + 3*s),
        (cx + 20*s * dir_mul, cy + 8*s),
        (cx + 6*s * dir_mul, cy + 8*s)
    ], fill=theme["primary_light"], outline=theme["outline"], width=s)

    hx0 = min(cx - 15*s * dir_mul, cx - 8*s * dir_mul)
    hx1 = max(cx - 15*s * dir_mul, cx - 8*s * dir_mul)
    draw.rectangle([hx0, cy + 4*s, hx1, cy + 8*s], fill=theme["accent_mid"])


def generate_all(out_dir, prefix="warrior", archetype="warrior"):
    """Generates all 15 limb sprites for a given character and archetype."""
    os.makedirs(out_dir, exist_ok=True)
    theme = ARCHETYPES.get(archetype.lower(), ARCHETYPES["warrior"])

    parts = {
        "head": ((64, 64), lambda d, w, h, s: draw_head(d, w, h, s, theme)),
        "torso": ((72, 64), lambda d, w, h, s: draw_torso(d, w, h, s, theme)),
        "pelvis": ((64, 48), lambda d, w, h, s: draw_pelvis(d, w, h, s, theme)),
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

    print(f"[Generator] Created 15 {archetype.upper()} sprites for '{prefix}' in: {out_dir}")
    return generated_paths

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "sprites/warrior"
    char_name = sys.argv[2] if len(sys.argv) > 2 else "warrior"
    arch = sys.argv[3] if len(sys.argv) > 3 else "warrior"
    generate_all(target, prefix=char_name, archetype=arch)
