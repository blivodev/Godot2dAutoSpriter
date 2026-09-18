#!/usr/bin/env python3
"""
generate_openpose_templates.py

Generates the exploded OpenPose skeleton control templates used by ComfyUI
and ControlNet to force generative diffusion models to synthesize 2D characters
with modular, detached limbs for biped and quadruped characters.
"""

import math
from pathlib import Path
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUTS_DIR = PROJECT_ROOT / "workflows" / "inputs"

# Standard OpenPose 18-Keypoint Color Scheme (RGB)
COLORS = {
    "nose": (0, 0, 255),
    "neck": (255, 85, 0),
    "r_shoulder": (255, 0, 0),
    "r_elbow": (255, 85, 0),
    "r_wrist": (255, 170, 0),
    "l_shoulder": (0, 255, 0),
    "l_elbow": (0, 255, 85),
    "l_wrist": (0, 255, 170),
    "r_hip": (255, 0, 85),
    "r_knee": (255, 0, 170),
    "r_ankle": (255, 0, 255),
    "l_hip": (0, 85, 255),
    "l_knee": (0, 170, 255),
    "l_ankle": (0, 255, 255),
    "r_eye": (255, 0, 0),
    "l_eye": (0, 255, 0),
    "r_ear": (255, 0, 85),
    "l_ear": (0, 85, 255),
}

LIMB_COLORS = [
    ("neck", "r_shoulder", (255, 0, 0)),
    ("r_shoulder", "r_elbow", (255, 85, 0)),
    ("r_elbow", "r_wrist", (255, 170, 0)),
    ("neck", "l_shoulder", (0, 255, 0)),
    ("l_shoulder", "l_elbow", (0, 255, 85)),
    ("l_elbow", "l_wrist", (0, 255, 170)),
    ("neck", "r_hip", (255, 0, 85)),
    ("r_hip", "r_knee", (255, 0, 170)),
    ("r_knee", "r_ankle", (255, 0, 255)),
    ("neck", "l_hip", (0, 85, 255)),
    ("l_hip", "l_knee", (0, 170, 255)),
    ("l_knee", "l_ankle", (0, 255, 255)),
    ("neck", "nose", (0, 0, 255)),
    ("nose", "r_eye", (255, 0, 0)),
    ("r_eye", "r_ear", (255, 0, 85)),
    ("nose", "l_eye", (0, 255, 0)),
    ("l_eye", "l_ear", (0, 85, 255)),
]


def draw_openpose_limb(draw, p1, p2, color, thickness=12):
    """Draws a rounded OpenPose bone line between two points."""
    draw.line([p1, p2], fill=color, width=thickness)
    r = thickness // 2
    draw.ellipse([p1[0] - r, p1[1] - r, p1[0] + r, p1[1] + r], fill=color)
    draw.ellipse([p2[0] - r, p2[1] - r, p2[0] + r, p2[1] + r], fill=color)


def draw_joint_point(draw, pt, color, radius=8):
    """Draws a circular joint marker."""
    draw.ellipse([pt[0] - radius, pt[1] - radius, pt[0] + radius, pt[1] + radius], fill=color)


def generate_biped_exploded_template(size=(1536, 1536)):
    """
    Renders an orthographic exploded OpenPose template where limbs
    are disconnected and spread apart with genuine canvas margins.
    """
    img = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(img)
    w, h = size
    cx, cy = w // 2, h // 2

    # Detached limb keypoint coordinates
    points = {
        # Head cluster (top center)
        "nose": (cx, int(cy - 460)),
        "neck": (cx, int(cy - 390)),
        "r_eye": (cx - 30, int(cy - 485)),
        "l_eye": (cx + 30, int(cy - 485)),
        "r_ear": (cx - 70, int(cy - 460)),
        "l_ear": (cx + 70, int(cy - 460)),

        # Torso & Pelvis (center column)
        "torso_top": (cx, int(cy - 220)),
        "torso_bottom": (cx, int(cy - 60)),
        "pelvis_top": (cx, int(cy + 40)),
        "pelvis_bottom": (cx, int(cy + 130)),

        # Right Arm (Exploded outward to screen-left)
        "r_shoulder": (int(cx - 280), int(cy - 240)),
        "r_elbow": (int(cx - 440), int(cy - 160)),
        "r_wrist": (int(cx - 570), int(cy - 70)),

        # Left Arm (Exploded outward to screen-right)
        "l_shoulder": (int(cx + 280), int(cy - 240)),
        "l_elbow": (int(cx + 440), int(cy - 160)),
        "l_wrist": (int(cx + 570), int(cy - 70)),

        # Right Leg (Exploded downward screen-left)
        "r_hip": (int(cx - 220), int(cy + 220)),
        "r_knee": (int(cx - 340), int(cy + 400)),
        "r_ankle": (int(cx - 440), int(cy + 580)),

        # Left Leg (Exploded downward screen-right)
        "l_hip": (int(cx + 220), int(cy + 220)),
        "l_knee": (int(cx + 340), int(cy + 400)),
        "l_ankle": (int(cx + 440), int(cy + 580)),
    }

    # Draw head bones
    draw_openpose_limb(draw, points["nose"], points["neck"], COLORS["neck"], thickness=14)
    draw_openpose_limb(draw, points["nose"], points["r_eye"], COLORS["r_eye"], thickness=8)
    draw_openpose_limb(draw, points["r_eye"], points["r_ear"], COLORS["r_ear"], thickness=8)
    draw_openpose_limb(draw, points["nose"], points["l_eye"], COLORS["l_eye"], thickness=8)
    draw_openpose_limb(draw, points["l_eye"], points["l_ear"], COLORS["l_ear"], thickness=8)

    # Draw torso & pelvis
    draw_openpose_limb(draw, points["torso_top"], points["torso_bottom"], COLORS["neck"], thickness=22)
    draw_openpose_limb(draw, points["pelvis_top"], points["pelvis_bottom"], COLORS["r_hip"], thickness=20)

    # Draw Right Arm (detached)
    draw_openpose_limb(draw, points["r_shoulder"], points["r_elbow"], COLORS["r_shoulder"], thickness=16)
    draw_openpose_limb(draw, points["r_elbow"], points["r_wrist"], COLORS["r_elbow"], thickness=14)

    # Draw Left Arm (detached)
    draw_openpose_limb(draw, points["l_shoulder"], points["l_elbow"], COLORS["l_shoulder"], thickness=16)
    draw_openpose_limb(draw, points["l_elbow"], points["l_wrist"], COLORS["l_elbow"], thickness=14)

    # Draw Right Leg (detached)
    draw_openpose_limb(draw, points["r_hip"], points["r_knee"], COLORS["r_knee"], thickness=18)
    draw_openpose_limb(draw, points["r_knee"], points["r_ankle"], COLORS["r_ankle"], thickness=16)

    # Draw Left Leg (detached)
    draw_openpose_limb(draw, points["l_hip"], points["l_knee"], COLORS["l_knee"], thickness=18)
    draw_openpose_limb(draw, points["l_knee"], points["l_ankle"], COLORS["l_ankle"], thickness=16)

    # Draw Joint circles
    for name, pt in points.items():
        c = COLORS.get(name, (255, 255, 255))
        draw_joint_point(draw, pt, c, radius=10)

    return img


def generate_quadruped_exploded_template(size=(1536, 1536)):
    """
    Renders an orthographic exploded OpenPose template for quadrupeds / beasts
    with snout, 4 separated paws/legs, spine, torso, and tail segments.
    """
    img = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(img)
    w, h = size
    cx, cy = w // 2, h // 2

    # Quadruped exploded layout
    points = {
        # Head / Snout (Upper right)
        "snout": (int(cx + 420), int(cy - 360)),
        "head": (int(cx + 320), int(cy - 380)),
        "neck": (int(cx + 200), int(cy - 320)),

        # Spine & Torso & Pelvis (horizontal exploded mid band)
        "torso": (int(cx + 40), int(cy - 120)),
        "spine": (int(cx - 140), int(cy - 120)),
        "pelvis": (int(cx - 300), int(cy - 120)),

        # Tail chain (curving up and back)
        "tail_01": (int(cx - 440), int(cy - 170)),
        "tail_02": (int(cx - 540), int(cy - 250)),
        "tail_03": (int(cx - 610), int(cy - 350)),

        # Front Left Leg (lower right)
        "front_l_hip": (int(cx + 180), int(cy + 60)),
        "front_l_knee": (int(cx + 240), int(cy + 240)),
        "front_l_paw": (int(cx + 290), int(cy + 420)),

        # Front Right Leg (upper mid right)
        "front_r_hip": (int(cx + 440), int(cy - 80)),
        "front_r_knee": (int(cx + 520), int(cy + 80)),
        "front_r_paw": (int(cx + 570), int(cy + 240)),

        # Back Left Leg (lower left)
        "back_l_hip": (int(cx - 180), int(cy + 60)),
        "back_l_knee": (int(cx - 240), int(cy + 240)),
        "back_l_paw": (int(cx - 280), int(cy + 420)),

        # Back Right Leg (far left)
        "back_r_hip": (int(cx - 420), int(cy + 60)),
        "back_r_knee": (int(cx - 490), int(cy + 230)),
        "back_r_paw": (int(cx - 530), int(cy + 400)),
    }

    # Draw head / neck
    draw_openpose_limb(draw, points["snout"], points["head"], COLORS["nose"], thickness=14)
    draw_openpose_limb(draw, points["head"], points["neck"], COLORS["neck"], thickness=16)

    # Draw spine / torso / pelvis
    draw_openpose_limb(draw, points["pelvis"], points["spine"], COLORS["neck"], thickness=20)
    draw_openpose_limb(draw, points["spine"], points["torso"], COLORS["neck"], thickness=22)

    # Draw tail
    draw_openpose_limb(draw, points["pelvis"], points["tail_01"], COLORS["r_ear"], thickness=14)
    draw_openpose_limb(draw, points["tail_01"], points["tail_02"], COLORS["r_ear"], thickness=12)
    draw_openpose_limb(draw, points["tail_02"], points["tail_03"], COLORS["r_ear"], thickness=10)

    # Draw front legs
    draw_openpose_limb(draw, points["front_l_hip"], points["front_l_knee"], COLORS["l_shoulder"], thickness=16)
    draw_openpose_limb(draw, points["front_l_knee"], points["front_l_paw"], COLORS["l_elbow"], thickness=14)
    draw_openpose_limb(draw, points["front_r_hip"], points["front_r_knee"], COLORS["r_shoulder"], thickness=16)
    draw_openpose_limb(draw, points["front_r_knee"], points["front_r_paw"], COLORS["r_elbow"], thickness=14)

    # Draw back legs
    draw_openpose_limb(draw, points["back_l_hip"], points["back_l_knee"], COLORS["l_hip"], thickness=18)
    draw_openpose_limb(draw, points["back_l_knee"], points["back_l_paw"], COLORS["l_knee"], thickness=16)
    draw_openpose_limb(draw, points["back_r_hip"], points["back_r_knee"], COLORS["r_hip"], thickness=18)
    draw_openpose_limb(draw, points["back_r_knee"], points["back_r_paw"], COLORS["r_knee"], thickness=16)

    # Joints
    for name, pt in points.items():
        c = COLORS.get(name, (0, 255, 170))
        draw_joint_point(draw, pt, c, radius=10)

    return img


def main():
    INPUTS_DIR.mkdir(parents=True, exist_ok=True)

    biped_path = INPUTS_DIR / "exploded_openpose_template.png"
    biped_img = generate_biped_exploded_template((1536, 1536))
    biped_img.save(biped_path, "PNG")
    print(f"[OK] Generated Biped OpenPose Template: {biped_path}")

    quad_path = INPUTS_DIR / "exploded_quadruped_openpose_template.png"
    quad_img = generate_quadruped_exploded_template((1536, 1536))
    quad_img.save(quad_path, "PNG")
    print(f"[OK] Generated Quadruped OpenPose Template: {quad_path}")


if __name__ == "__main__":
    main()
