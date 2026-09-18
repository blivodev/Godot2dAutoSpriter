import os
from PIL import Image, ImageDraw, ImageFilter

def create_sprite(size, draw_func):
    # Render at 4x resolution for smooth anti-aliased edges, then downsample
    scale = 4
    w, h = size[0] * scale, size[1] * scale
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw_func(draw, w, h, scale)
    return img.resize(size, Image.Resampling.LANCZOS)

# Palette
STEEL_DARK = (32, 36, 48, 255)
STEEL_MID = (55, 62, 82, 255)
STEEL_LIGHT = (90, 102, 130, 255)
STEEL_HIGHLIGHT = (140, 158, 195, 255)

GOLD_DARK = (150, 95, 20, 255)
GOLD_MID = (225, 160, 40, 255)
GOLD_LIGHT = (255, 215, 90, 255)

CYAN_CORE = (200, 255, 255, 255)
CYAN_GLOW = (0, 230, 255, 255)
CYAN_DARK = (0, 140, 170, 255)

OUTLINE = (15, 17, 24, 255)

def draw_head(draw, w, h, s):
    # Helmet base
    cx, cy = w // 2, h // 2
    # Skull cap
    draw.polygon([
        (cx - 18*s, cy + 16*s),
        (cx - 22*s, cy - 6*s),
        (cx - 14*s, cy - 22*s),
        (cx, cy - 26*s),
        (cx + 14*s, cy - 22*s),
        (cx + 22*s, cy - 6*s),
        (cx + 18*s, cy + 16*s),
        (cx, cy + 24*s)
    ], fill=STEEL_MID, outline=OUTLINE, width=2*s)
    
    # Helmet highlight & faceplate
    draw.polygon([
        (cx - 15*s, cy + 14*s),
        (cx - 18*s, cy - 4*s),
        (cx - 10*s, cy - 18*s),
        (cx, cy - 21*s),
        (cx + 10*s, cy - 18*s),
        (cx + 18*s, cy - 4*s),
        (cx + 15*s, cy + 14*s),
        (cx, cy + 20*s)
    ], fill=STEEL_LIGHT)

    # Gold forehead crest
    draw.polygon([
        (cx, cy - 28*s),
        (cx + 7*s, cy - 12*s),
        (cx, cy - 8*s),
        (cx - 7*s, cy - 12*s)
    ], fill=GOLD_MID, outline=OUTLINE, width=2*s)
    draw.polygon([(cx, cy - 25*s), (cx + 4*s, cy - 12*s), (cx, cy - 10*s)], fill=GOLD_LIGHT)

    # Glowing Cyan T-Visor
    draw.polygon([
        (cx - 14*s, cy - 2*s),
        (cx + 14*s, cy - 2*s),
        (cx + 14*s, cy + 3*s),
        (cx + 4*s, cy + 4*s),
        (cx + 3*s, cy + 14*s),
        (cx - 3*s, cy + 14*s),
        (cx - 4*s, cy + 4*s),
        (cx - 14*s, cy + 3*s)
    ], fill=CYAN_GLOW, outline=OUTLINE, width=s)
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
    ], fill=CYAN_CORE)

def draw_torso(draw, w, h, s):
    cx, cy = w // 2, h // 2
    # Armored Chest Plate
    draw.polygon([
        (cx - 28*s, cy - 24*s),
        (cx + 28*s, cy - 24*s),
        (cx + 24*s, cy + 6*s),
        (cx + 16*s, cy + 26*s),
        (cx, cy + 30*s),
        (cx - 16*s, cy + 26*s),
        (cx - 24*s, cy + 6*s)
    ], fill=STEEL_DARK, outline=OUTLINE, width=2*s)

    # Pectoral Plates
    draw.polygon([
        (cx - 24*s, cy - 20*s),
        (cx - 3*s, cy - 20*s),
        (cx - 2*s, cy + 6*s),
        (cx - 20*s, cy + 4*s)
    ], fill=STEEL_MID, outline=OUTLINE, width=s)
    draw.polygon([
        (cx + 24*s, cy - 20*s),
        (cx + 3*s, cy - 20*s),
        (cx + 2*s, cy + 6*s),
        (cx + 20*s, cy + 4*s)
    ], fill=STEEL_LIGHT, outline=OUTLINE, width=s)

    # Gold Trim on Shoulders
    draw.polygon([
        (cx - 28*s, cy - 24*s),
        (cx - 14*s, cy - 24*s),
        (cx - 16*s, cy - 18*s),
        (cx - 27*s, cy - 18*s)
    ], fill=GOLD_MID, outline=OUTLINE, width=s)
    draw.polygon([
        (cx + 28*s, cy - 24*s),
        (cx + 14*s, cy - 24*s),
        (cx + 16*s, cy - 18*s),
        (cx + 27*s, cy - 18*s)
    ], fill=GOLD_MID, outline=OUTLINE, width=s)

    # Central Arc-Reactor / Power Core
    draw.ellipse([cx - 8*s, cy - 6*s, cx + 8*s, cy + 10*s], fill=STEEL_DARK, outline=GOLD_MID, width=2*s)
    draw.ellipse([cx - 5*s, cy - 3*s, cx + 5*s, cy + 7*s], fill=CYAN_GLOW)
    draw.ellipse([cx - 2*s, cy - 1*s, cx + 2*s, cy + 3*s], fill=CYAN_CORE)

def draw_pelvis(draw, w, h, s):
    cx, cy = w // 2, h // 2
    # Armored belt / faulds
    draw.polygon([
        (cx - 24*s, cy - 12*s),
        (cx + 24*s, cy - 12*s),
        (cx + 20*s, cy + 14*s),
        (cx + 8*s, cy + 18*s),
        (cx, cy + 10*s),
        (cx - 8*s, cy + 18*s),
        (cx - 20*s, cy + 14*s)
    ], fill=STEEL_MID, outline=OUTLINE, width=2*s)

    # Belt strap
    draw.rectangle([cx - 24*s, cy - 12*s, cx + 24*s, cy - 4*s], fill=STEEL_DARK, outline=OUTLINE, width=s)
    
    # Gold Center Buckle
    draw.polygon([
        (cx, cy - 14*s),
        (cx + 8*s, cy - 7*s),
        (cx, cy),
        (cx - 8*s, cy - 7*s)
    ], fill=GOLD_MID, outline=OUTLINE, width=2*s)
    draw.polygon([(cx, cy - 12*s), (cx + 5*s, cy - 7*s), (cx, cy - 2*s)], fill=GOLD_LIGHT)

    # Hip joint sockets
    draw.ellipse([cx - 22*s, cy, cx - 12*s, cy + 10*s], fill=STEEL_DARK, outline=OUTLINE, width=s)
    draw.ellipse([cx + 12*s, cy, cx + 22*s, cy + 10*s], fill=STEEL_DARK, outline=OUTLINE, width=s)

def draw_arm_upper(draw, w, h, s, is_left=True):
    cx, cy = w // 2, h // 2
    # Pauldron dome + Bicep
    draw.polygon([
        (cx - 14*s, cy - 20*s),
        (cx + 14*s, cy - 20*s),
        (cx + 16*s, cy - 4*s),
        (cx + 10*s, cy + 18*s),
        (cx, cy + 22*s),
        (cx - 10*s, cy + 18*s),
        (cx - 16*s, cy - 4*s)
    ], fill=STEEL_MID, outline=OUTLINE, width=2*s)

    # Gold Pauldron Rim
    rim_y = cy - 6*s
    draw.rectangle([cx - 15*s, rim_y, cx + 15*s, rim_y + 5*s], fill=GOLD_MID, outline=OUTLINE, width=s)
    
    # Bicep plate highlight
    draw.rectangle([cx - 6*s, cy + 2*s, cx + 6*s, cy + 16*s], fill=STEEL_LIGHT, outline=OUTLINE, width=s)

def draw_arm_lower(draw, w, h, s, is_left=True):
    cx, cy = w // 2, h // 2
    # Vambrace / Forearm
    draw.polygon([
        (cx - 12*s, cy - 18*s),
        (cx + 12*s, cy - 18*s),
        (cx + 14*s, cy + 6*s),
        (cx + 8*s, cy + 20*s),
        (cx - 8*s, cy + 20*s),
        (cx - 14*s, cy + 6*s)
    ], fill=STEEL_MID, outline=OUTLINE, width=2*s)

    # Forearm Plate
    draw.polygon([
        (cx - 6*s, cy - 14*s),
        (cx + 6*s, cy - 14*s),
        (cx + 7*s, cy + 12*s),
        (cx - 7*s, cy + 12*s)
    ], fill=STEEL_LIGHT, outline=OUTLINE, width=s)

    # Cyan power conduit line
    draw.line([(cx, cy - 12*s), (cx, cy + 10*s)], fill=CYAN_GLOW, width=2*s)

def draw_hand(draw, w, h, s, is_left=True):
    cx, cy = w // 2, h // 2
    # Armored Gauntlet Fist
    draw.ellipse([cx - 12*s, cy - 12*s, cx + 12*s, cy + 12*s], fill=STEEL_DARK, outline=OUTLINE, width=2*s)
    # Knuckle Plate
    draw.rectangle([cx - 10*s, cy - 6*s, cx + 10*s, cy + 4*s], fill=STEEL_LIGHT, outline=OUTLINE, width=s)
    # Gold Knuckle Studs
    for i in [-6, -2, 2, 6]:
        draw.rectangle([cx + (i-1)*s, cy - 4*s, cx + (i+1)*s, cy - 2*s], fill=GOLD_MID)

def draw_leg_upper(draw, w, h, s, is_left=True):
    cx, cy = w // 2, h // 2
    # Armored Cuisse / Thigh
    draw.polygon([
        (cx - 12*s, cy - 22*s),
        (cx + 12*s, cy - 22*s),
        (cx + 14*s, cy + 8*s),
        (cx + 8*s, cy + 22*s),
        (cx, cy + 24*s),
        (cx - 8*s, cy + 22*s),
        (cx - 14*s, cy + 8*s)
    ], fill=STEEL_MID, outline=OUTLINE, width=2*s)

    # Knee Poleyn (armor cap)
    draw.ellipse([cx - 10*s, cy + 10*s, cx + 10*s, cy + 24*s], fill=STEEL_DARK, outline=OUTLINE, width=s)
    draw.ellipse([cx - 5*s, cy + 13*s, cx + 5*s, cy + 21*s], fill=GOLD_MID)

def draw_leg_lower(draw, w, h, s, is_left=True):
    cx, cy = w // 2, h // 2
    # Armored Greave / Shin
    draw.polygon([
        (cx - 11*s, cy - 22*s),
        (cx + 11*s, cy - 22*s),
        (cx + 13*s, cy + 4*s),
        (cx + 8*s, cy + 22*s),
        (cx - 8*s, cy + 22*s),
        (cx - 13*s, cy + 4*s)
    ], fill=STEEL_MID, outline=OUTLINE, width=2*s)

    # Shin crest
    draw.polygon([
        (cx, cy - 18*s),
        (cx + 5*s, cy + 12*s),
        (cx - 5*s, cy + 12*s)
    ], fill=STEEL_LIGHT, outline=OUTLINE, width=s)
    # Cyan accent slit
    draw.line([(cx, cy - 14*s), (cx, cy + 4*s)], fill=CYAN_GLOW, width=2*s)

def draw_foot(draw, w, h, s, is_left=True):
    cx, cy = w // 2, h // 2
    # Sabaton Boot
    dir_mul = 1 if is_left else -1
    draw.polygon([
        (cx - 14*s * dir_mul, cy - 10*s),
        (cx + 6*s * dir_mul, cy - 10*s),
        (cx + 20*s * dir_mul, cy + 2*s),
        (cx + 22*s * dir_mul, cy + 10*s),
        (cx - 16*s * dir_mul, cy + 10*s),
        (cx - 16*s * dir_mul, cy - 2*s)
    ], fill=STEEL_DARK, outline=OUTLINE, width=2*s)

    # Steel Toe Cap
    draw.polygon([
        (cx + 8*s * dir_mul, cy),
        (cx + 20*s * dir_mul, cy + 3*s),
        (cx + 20*s * dir_mul, cy + 8*s),
        (cx + 6*s * dir_mul, cy + 8*s)
    ], fill=STEEL_LIGHT, outline=OUTLINE, width=s)
    # Gold heel accent
    hx0 = min(cx - 15*s * dir_mul, cx - 8*s * dir_mul)
    hx1 = max(cx - 15*s * dir_mul, cx - 8*s * dir_mul)
    draw.rectangle([hx0, cy + 4*s, hx1, cy + 8*s], fill=GOLD_MID)

def generate_all(out_dir, prefix="warrior"):
    os.makedirs(out_dir, exist_ok=True)
    parts = {
        "head": ((64, 64), draw_head),
        "torso": ((72, 64), draw_torso),
        "pelvis": ((64, 48), draw_pelvis),
        "arm_upper_L": ((44, 56), lambda d, w, h, s: draw_arm_upper(d, w, h, s, True)),
        "arm_lower_L": ((36, 52), lambda d, w, h, s: draw_arm_lower(d, w, h, s, True)),
        "hand_L": ((32, 32), lambda d, w, h, s: draw_hand(d, w, h, s, True)),
        "arm_upper_R": ((44, 56), lambda d, w, h, s: draw_arm_upper(d, w, h, s, False)),
        "arm_lower_R": ((36, 52), lambda d, w, h, s: draw_arm_lower(d, w, h, s, False)),
        "hand_R": ((32, 32), lambda d, w, h, s: draw_hand(d, w, h, s, False)),
        "leg_upper_L": ((40, 56), lambda d, w, h, s: draw_leg_upper(d, w, h, s, True)),
        "leg_lower_L": ((36, 56), lambda d, w, h, s: draw_leg_lower(d, w, h, s, True)),
        "foot_L": ((48, 32), lambda d, w, h, s: draw_foot(d, w, h, s, True)),
        "leg_upper_R": ((40, 56), lambda d, w, h, s: draw_leg_upper(d, w, h, s, False)),
        "leg_lower_R": ((36, 56), lambda d, w, h, s: draw_leg_lower(d, w, h, s, False)),
        "foot_R": ((48, 32), lambda d, w, h, s: draw_foot(d, w, h, s, False)),
    }

    for name, (size, fn) in parts.items():
        img = create_sprite(size, fn)
        out_path = os.path.join(out_dir, f"{prefix}_{name}.png")
        img.save(out_path, "PNG")
        print(f"Generated {out_path} ({size[0]}x{size[1]}, True Alpha)")

if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "sprites/warrior"
    generate_all(target)
