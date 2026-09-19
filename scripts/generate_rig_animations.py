#!/usr/bin/env python3
"""
generate_rig_animations.py - Complete Godot 4 2D Skeletal Animation Generator

Generates 23 expressive, game-ready skeletal animations for Godot 4 Character rigs:
1. idle (breathe & subtle sway, loop)
2. walk (natural biped walk cycle, loop)
3. run (fast athletic sprint, loop)
4. jump (anticipation, launch, tuck)
5. double_jump (aerial somersault boost)
6. crouch (duck down into defensive stance)
7. crouch_walk (stealth low shuffle, loop)
8. dash (forward speed burst streak)
9. slide (action baseball slide on ground)
10. fire_weapon (aim forward & recoil)
11. punch (explosive straight jab)
12. hit (melee slash / strike arc)
13. kick (front snap extension kick)
14. jump_kick (mid-air flying dropkick)
15. crouch_kick (low floor sweep kick)
16. get_hit (hurt flinch & stagger recoil)
17. get_stunned (dizzy wobble loop)
18. death (dramatic collapse to floor)
19. drink_potion (raise vial, tilt head, chug)
20. special_01 (ground slam / shockwave smash)
21. special_02 (spinning whirlwind 360 attack, loop)
22. special_03 (arcane power charge / roar, loop)
23. special_04 (heroic victory flourish / sheath)
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Any

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

ANIMATION_DEFS: Dict[str, Dict[str, Any]] = {
    "idle": {
        "length": 1.8,
        "loop": 1,
        "desc": "Breathing rest stance with gentle head and arm sway",
        "tracks": {
            "Skeleton2D/pelvis/torso:position": [(0, (0, -40)), (0.9, (0, -42)), (1.8, (0, -40))],
            "Skeleton2D/pelvis/torso/head:rotation": [(0, 0.0), (0.9, -0.035), (1.8, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.0), (0.9, 0.045), (1.8, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, 0.0), (0.9, -0.045), (1.8, 0.0)],
        }
    },
    "walk": {
        "length": 0.8,
        "loop": 1,
        "desc": "Natural biped walk cycle with counter-swinging arms and legs",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, 0)), (0.2, (0, -3)), (0.4, (0, 0)), (0.6, (0, -3)), (0.8, (0, 0))],
            "Skeleton2D/pelvis/torso:rotation": [(0, -0.04), (0.4, 0.04), (0.8, -0.04)],
            "Skeleton2D/pelvis/torso/head:rotation": [(0, 0.02), (0.4, -0.02), (0.8, 0.02)],
            "Skeleton2D/pelvis/leg_upper_L:rotation": [(0, -0.45), (0.2, 0.1), (0.4, 0.45), (0.6, -0.1), (0.8, -0.45)],
            "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [(0, 0.1), (0.2, 0.6), (0.4, 0.0), (0.6, 0.2), (0.8, 0.1)],
            "Skeleton2D/pelvis/leg_upper_R:rotation": [(0, 0.45), (0.2, -0.1), (0.4, -0.45), (0.6, 0.1), (0.8, 0.45)],
            "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [(0, 0.0), (0.2, 0.2), (0.4, 0.1), (0.6, 0.6), (0.8, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.4), (0.4, -0.4), (0.8, 0.4)],
            "Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L:rotation": [(0, -0.2), (0.4, -0.5), (0.8, -0.2)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, -0.4), (0.4, 0.4), (0.8, -0.4)],
            "Skeleton2D/pelvis/torso/arm_upper_R/arm_lower_R:rotation": [(0, -0.5), (0.4, -0.2), (0.8, -0.5)],
        }
    },
    "run": {
        "length": 0.5,
        "loop": 1,
        "desc": "High-speed athletic sprint with forward torso lean and high knees",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, 0)), (0.125, (0, -7)), (0.25, (0, 2)), (0.375, (0, -7)), (0.5, (0, 0))],
            "Skeleton2D/pelvis/torso:rotation": [(0, -0.18), (0.25, -0.15), (0.5, -0.18)],
            "Skeleton2D/pelvis/leg_upper_L:rotation": [(0, -0.85), (0.125, -0.2), (0.25, 0.7), (0.375, 0.1), (0.5, -0.85)],
            "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [(0, 0.3), (0.125, 1.1), (0.25, 0.0), (0.375, 0.6), (0.5, 0.3)],
            "Skeleton2D/pelvis/leg_upper_R:rotation": [(0, 0.7), (0.125, 0.1), (0.25, -0.85), (0.375, -0.2), (0.5, 0.7)],
            "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [(0, 0.0), (0.125, 0.6), (0.25, 0.3), (0.375, 1.1), (0.5, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.75), (0.25, -0.75), (0.5, 0.75)],
            "Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L:rotation": [(0, -1.2), (0.25, -0.8), (0.5, -1.2)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, -0.75), (0.25, 0.75), (0.5, -0.75)],
            "Skeleton2D/pelvis/torso/arm_upper_R/arm_lower_R:rotation": [(0, -0.8), (0.25, -1.2), (0.5, -0.8)],
        }
    },
    "jump": {
        "length": 0.6,
        "loop": 0,
        "desc": "Anticipation dip, vertical thrust, airborne knee tuck",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, 0)), (0.1, (0, 8)), (0.3, (0, -32)), (0.6, (0, -20))],
            "Skeleton2D/pelvis/torso:rotation": [(0, 0.0), (0.1, 0.1), (0.3, -0.1), (0.6, -0.05)],
            "Skeleton2D/pelvis/leg_upper_L:rotation": [(0, 0.0), (0.1, -0.5), (0.3, -0.7), (0.6, -0.3)],
            "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [(0, 0.0), (0.1, 0.8), (0.3, 1.1), (0.6, 0.4)],
            "Skeleton2D/pelvis/leg_upper_R:rotation": [(0, 0.0), (0.1, -0.5), (0.3, -0.5), (0.6, -0.2)],
            "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [(0, 0.0), (0.1, 0.8), (0.3, 0.9), (0.6, 0.3)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.0), (0.1, 0.5), (0.3, -1.4), (0.6, -0.8)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, 0.0), (0.1, 0.5), (0.3, -1.4), (0.6, -0.8)],
        }
    },
    "double_jump": {
        "length": 0.5,
        "loop": 0,
        "desc": "Mid-air somersault tuck and explosive secondary boost",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, 0)), (0.2, (0, -18)), (0.5, (0, -35))],
            "Skeleton2D/pelvis/torso:rotation": [(0, 0.0), (0.15, -1.6), (0.3, -3.14), (0.5, 0.0)],
            "Skeleton2D/pelvis/leg_upper_L:rotation": [(0, -0.3), (0.2, -1.3), (0.5, -0.2)],
            "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [(0, 0.4), (0.2, 1.6), (0.5, 0.2)],
            "Skeleton2D/pelvis/leg_upper_R:rotation": [(0, -0.2), (0.2, -1.2), (0.5, -0.1)],
            "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [(0, 0.3), (0.2, 1.5), (0.5, 0.2)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, -0.5), (0.2, -2.0), (0.5, -0.6)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, -0.5), (0.2, -2.0), (0.5, -0.6)],
        }
    },
    "crouch": {
        "length": 0.4,
        "loop": 0,
        "desc": "Drops pelvis, knees bend, defensive low profile",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, 0)), (0.4, (0, 18))],
            "Skeleton2D/pelvis/torso:rotation": [(0, 0.0), (0.4, -0.15)],
            "Skeleton2D/pelvis/torso/head:rotation": [(0, 0.0), (0.4, 0.1)],
            "Skeleton2D/pelvis/leg_upper_L:rotation": [(0, 0.0), (0.4, -0.75)],
            "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [(0, 0.0), (0.4, 1.35)],
            "Skeleton2D/pelvis/leg_upper_R:rotation": [(0, 0.0), (0.4, -0.75)],
            "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [(0, 0.0), (0.4, 1.35)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.0), (0.4, -0.4)],
            "Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L:rotation": [(0, 0.0), (0.4, -0.9)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, 0.0), (0.4, -0.4)],
            "Skeleton2D/pelvis/torso/arm_upper_R/arm_lower_R:rotation": [(0, 0.0), (0.4, -0.9)],
        }
    },
    "crouch_walk": {
        "length": 0.9,
        "loop": 1,
        "desc": "Stealth low shuffle with crouched knees and arms tucked close",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, 16)), (0.45, (0, 14)), (0.9, (0, 16))],
            "Skeleton2D/pelvis/torso:rotation": [(0, -0.12), (0.45, -0.16), (0.9, -0.12)],
            "Skeleton2D/pelvis/leg_upper_L:rotation": [(0, -0.9), (0.45, -0.4), (0.9, -0.9)],
            "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [(0, 1.4), (0.45, 1.1), (0.9, 1.4)],
            "Skeleton2D/pelvis/leg_upper_R:rotation": [(0, -0.4), (0.45, -0.9), (0.9, -0.4)],
            "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [(0, 1.1), (0.45, 1.4), (0.9, 1.1)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, -0.2), (0.45, -0.5), (0.9, -0.2)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, -0.5), (0.45, -0.2), (0.9, -0.5)],
        }
    },
    "dash": {
        "length": 0.35,
        "loop": 0,
        "desc": "High velocity speed dash, aerodynamic forward thrust, arms pinned back",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, 0)), (0.1, (12, -4)), (0.35, (20, 0))],
            "Skeleton2D/pelvis/torso:rotation": [(0, 0.0), (0.1, -0.35), (0.35, -0.2)],
            "Skeleton2D/pelvis/torso/head:rotation": [(0, 0.0), (0.1, 0.2), (0.35, 0.1)],
            "Skeleton2D/pelvis/leg_upper_L:rotation": [(0, 0.0), (0.15, -0.9), (0.35, -0.4)],
            "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [(0, 0.0), (0.15, 0.5), (0.35, 0.2)],
            "Skeleton2D/pelvis/leg_upper_R:rotation": [(0, 0.0), (0.15, 0.8), (0.35, 0.3)],
            "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [(0, 0.0), (0.15, 0.1), (0.35, 0.1)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.0), (0.15, 0.95), (0.35, 0.4)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, 0.0), (0.15, 0.85), (0.35, 0.3)],
        }
    },
    "slide": {
        "length": 0.5,
        "loop": 0,
        "desc": "Baseball action slide on ground, lead leg straight, back leg bent under",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, 0)), (0.15, (0, 26)), (0.5, (0, 24))],
            "Skeleton2D/pelvis/torso:rotation": [(0, 0.0), (0.2, 0.42), (0.5, 0.35)],
            "Skeleton2D/pelvis/torso/head:rotation": [(0, 0.0), (0.2, -0.25), (0.5, -0.2)],
            "Skeleton2D/pelvis/leg_upper_L:rotation": [(0, 0.0), (0.2, -1.25), (0.5, -1.15)],
            "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [(0, 0.0), (0.2, 0.1), (0.5, 0.05)],
            "Skeleton2D/pelvis/leg_upper_R:rotation": [(0, 0.0), (0.2, 0.65), (0.5, 0.6)],
            "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [(0, 0.0), (0.2, 1.55), (0.5, 1.5)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.0), (0.2, -0.6), (0.5, -0.4)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, 0.0), (0.2, 0.9), (0.5, 0.7)],
        }
    },
    "fire_weapon": {
        "length": 0.4,
        "loop": 0,
        "desc": "Quick weapon draw, forward aim and crisp recoil kick",
        "tracks": {
            "Skeleton2D/pelvis/torso:rotation": [(0, 0.0), (0.08, -0.05), (0.15, 0.08), (0.4, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.0), (0.08, -1.45), (0.15, -1.65), (0.4, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L:rotation": [(0, 0.0), (0.08, -0.2), (0.15, -0.4), (0.4, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, 0.0), (0.08, -1.1), (0.15, -1.25), (0.4, 0.0)],
            "Skeleton2D/pelvis/torso/head:rotation": [(0, 0.0), (0.08, -0.05), (0.15, 0.05), (0.4, 0.0)],
        }
    },
    "punch": {
        "length": 0.35,
        "loop": 0,
        "desc": "Explosive straight jab punch with torso extension and fast snap-back",
        "tracks": {
            "Skeleton2D/pelvis/torso:rotation": [(0, 0.0), (0.08, 0.15), (0.16, -0.25), (0.35, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.0), (0.08, 0.3), (0.16, -1.4), (0.35, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L:rotation": [(0, 0.0), (0.08, -1.3), (0.16, 0.0), (0.35, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, 0.0), (0.16, 0.4), (0.35, 0.0)],
        }
    },
    "hit": {
        "length": 0.45,
        "loop": 0,
        "desc": "Heavy melee weapon downward cleaving strike with follow-through",
        "tracks": {
            "Skeleton2D/pelvis/torso:position": [(0, (0, -40)), (0.15, (0, -44)), (0.25, (0, -38)), (0.45, (0, -40))],
            "Skeleton2D/pelvis/torso:rotation": [(0, 0.0), (0.15, 0.2), (0.25, -0.25), (0.45, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.0), (0.15, -1.8), (0.25, 0.6), (0.45, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L:rotation": [(0, 0.0), (0.15, -0.8), (0.25, -0.2), (0.45, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, 0.0), (0.15, -1.5), (0.25, 0.4), (0.45, 0.0)],
        }
    },
    "kick": {
        "length": 0.45,
        "loop": 0,
        "desc": "High snap kick with lead leg extension and balance counter-arms",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, 0)), (0.18, (0, -4)), (0.45, (0, 0))],
            "Skeleton2D/pelvis/torso:rotation": [(0, 0.0), (0.18, 0.25), (0.45, 0.0)],
            "Skeleton2D/pelvis/leg_upper_L:rotation": [(0, 0.0), (0.1, -1.1), (0.2, -1.45), (0.3, -1.0), (0.45, 0.0)],
            "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [(0, 0.0), (0.1, 1.4), (0.2, 0.0), (0.3, 0.9), (0.45, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.0), (0.2, 0.5), (0.45, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, 0.0), (0.2, -0.6), (0.45, 0.0)],
        }
    },
    "jump_kick": {
        "length": 0.55,
        "loop": 0,
        "desc": "Aerial flying dropkick with horizontal body extension in mid-air",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, 0)), (0.2, (0, -28)), (0.55, (0, 0))],
            "Skeleton2D/pelvis/torso:rotation": [(0, 0.0), (0.2, -0.55), (0.55, 0.0)],
            "Skeleton2D/pelvis/leg_upper_L:rotation": [(0, 0.0), (0.2, -1.5), (0.55, 0.0)],
            "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [(0, 0.0), (0.2, 0.0), (0.55, 0.0)],
            "Skeleton2D/pelvis/leg_upper_R:rotation": [(0, 0.0), (0.2, 0.7), (0.55, 0.0)],
            "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [(0, 0.0), (0.2, 1.4), (0.55, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.0), (0.2, 0.8), (0.55, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, 0.0), (0.2, 0.7), (0.55, 0.0)],
        }
    },
    "crouch_kick": {
        "length": 0.4,
        "loop": 0,
        "desc": "Low floor sweep kick sweeping forward along ground from crouch",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, 18)), (0.18, (0, 22)), (0.4, (0, 18))],
            "Skeleton2D/pelvis/torso:rotation": [(0, -0.15), (0.18, 0.3), (0.4, -0.15)],
            "Skeleton2D/pelvis/leg_upper_L:rotation": [(0, -0.75), (0.18, -1.3), (0.4, -0.75)],
            "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [(0, 1.35), (0.18, 0.1), (0.4, 1.35)],
            "Skeleton2D/pelvis/leg_upper_R:rotation": [(0, -0.75), (0.18, 0.4), (0.4, -0.75)],
            "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [(0, 1.35), (0.18, 1.6), (0.4, 1.35)],
        }
    },
    "get_hit": {
        "length": 0.35,
        "loop": 0,
        "desc": "Impact hurt flinch, head snapped back and torso recoil stagger",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, 0)), (0.08, (-10, -2)), (0.35, (0, 0))],
            "Skeleton2D/pelvis/torso:rotation": [(0, 0.0), (0.08, 0.28), (0.35, 0.0)],
            "Skeleton2D/pelvis/torso/head:rotation": [(0, 0.0), (0.08, 0.35), (0.35, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.0), (0.08, -0.75), (0.35, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, 0.0), (0.08, 0.75), (0.35, 0.0)],
        }
    },
    "get_stunned": {
        "length": 1.0,
        "loop": 1,
        "desc": "Dazed dizzy wobble loop with limp arms and swaying head",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, 0)), (0.25, (3, -2)), (0.5, (0, 2)), (0.75, (-3, -2)), (1.0, (0, 0))],
            "Skeleton2D/pelvis/torso:rotation": [(0, -0.08), (0.5, 0.08), (1.0, -0.08)],
            "Skeleton2D/pelvis/torso/head:rotation": [(0, 0.2), (0.5, -0.2), (1.0, 0.2)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.15), (0.5, -0.15), (1.0, 0.15)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, -0.15), (0.5, 0.15), (1.0, -0.15)],
        }
    },
    "death": {
        "length": 0.8,
        "loop": 0,
        "desc": "Knees buckle, body goes limp and collapses flat to the floor",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, 0)), (0.25, (0, 15)), (0.55, (0, 36)), (0.8, (0, 36))],
            "Skeleton2D/pelvis/torso:rotation": [(0, 0.0), (0.25, 0.4), (0.55, 1.45), (0.8, 1.55)],
            "Skeleton2D/pelvis/torso/head:rotation": [(0, 0.0), (0.25, 0.2), (0.55, 0.5), (0.8, 0.5)],
            "Skeleton2D/pelvis/leg_upper_L:rotation": [(0, 0.0), (0.25, 0.6), (0.55, 1.4), (0.8, 1.45)],
            "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [(0, 0.0), (0.25, 1.2), (0.55, 0.2), (0.8, 0.1)],
            "Skeleton2D/pelvis/leg_upper_R:rotation": [(0, 0.0), (0.25, 0.5), (0.55, 1.3), (0.8, 1.35)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.0), (0.25, -0.4), (0.55, 1.2), (0.8, 1.3)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, 0.0), (0.25, 0.4), (0.55, 1.0), (0.8, 1.1)],
        }
    },
    "drink_potion": {
        "length": 1.0,
        "loop": 0,
        "desc": "Raise potion vial to mouth, head tilts back to chug, arm lowers",
        "tracks": {
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.0), (0.25, -1.35), (0.6, -1.45), (1.0, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L:rotation": [(0, 0.0), (0.25, -1.5), (0.6, -1.6), (1.0, 0.0)],
            "Skeleton2D/pelvis/torso/head:rotation": [(0, 0.0), (0.25, 0.0), (0.5, 0.38), (0.75, 0.38), (1.0, 0.0)],
            "Skeleton2D/pelvis/torso:rotation": [(0, 0.0), (0.5, 0.08), (1.0, 0.0)],
        }
    },
    "special_01": {
        "length": 0.8,
        "loop": 0,
        "desc": "Ground Slam: high airborne leap with dual overhead strike down to ground",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, 0)), (0.2, (0, -25)), (0.45, (0, 16)), (0.8, (0, 0))],
            "Skeleton2D/pelvis/torso:rotation": [(0, 0.0), (0.2, 0.3), (0.45, -0.35), (0.8, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.0), (0.2, -2.1), (0.45, 0.75), (0.8, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, 0.0), (0.2, -2.1), (0.45, 0.75), (0.8, 0.0)],
            "Skeleton2D/pelvis/leg_upper_L:rotation": [(0, 0.0), (0.2, -0.6), (0.45, -0.8), (0.8, 0.0)],
            "Skeleton2D/pelvis/leg_upper_L/leg_lower_L:rotation": [(0, 0.0), (0.2, 1.0), (0.45, 1.3), (0.8, 0.0)],
            "Skeleton2D/pelvis/leg_upper_R:rotation": [(0, 0.0), (0.2, -0.6), (0.45, -0.8), (0.8, 0.0)],
            "Skeleton2D/pelvis/leg_upper_R/leg_lower_R:rotation": [(0, 0.0), (0.2, 1.0), (0.45, 1.3), (0.8, 0.0)],
        }
    },
    "special_02": {
        "length": 0.6,
        "loop": 1,
        "desc": "Whirlwind Spin: rapid 360-degree blade spin with outstretched arms",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, -2)), (0.3, (0, -4)), (0.6, (0, -2))],
            "Skeleton2D/pelvis/torso:rotation": [(0, -0.05), (0.15, 0.05), (0.3, -0.05), (0.45, 0.05), (0.6, -0.05)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, -1.55), (0.3, -1.6), (0.6, -1.55)],
            "Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L:rotation": [(0, 0.0), (0.3, -0.1), (0.6, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, 1.55), (0.3, 1.6), (0.6, 1.55)],
            "Skeleton2D/pelvis/torso/arm_upper_R/arm_lower_R:rotation": [(0, 0.0), (0.3, 0.1), (0.6, 0.0)],
            "Skeleton2D/pelvis/leg_upper_L:rotation": [(0, -0.3), (0.3, 0.3), (0.6, -0.3)],
            "Skeleton2D/pelvis/leg_upper_R:rotation": [(0, 0.3), (0.3, -0.3), (0.6, 0.3)],
        }
    },
    "special_03": {
        "length": 1.2,
        "loop": 1,
        "desc": "Arcane Power Charge: chest arched, head back, vibrating with surge of energy",
        "tracks": {
            "Skeleton2D/pelvis:position": [(0, (0, 0)), (0.3, (0, 4)), (0.6, (0, -1)), (0.9, (0, 4)), (1.2, (0, 0))],
            "Skeleton2D/pelvis/torso:position": [(0, (0, -40)), (0.3, (0, -38)), (0.6, (0, -42)), (0.9, (0, -38)), (1.2, (0, -40))],
            "Skeleton2D/pelvis/torso:rotation": [(0, 0.0), (0.3, 0.12), (0.6, 0.15), (0.9, 0.12), (1.2, 0.0)],
            "Skeleton2D/pelvis/torso/head:rotation": [(0, 0.0), (0.3, 0.28), (0.6, 0.35), (0.9, 0.28), (1.2, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.0), (0.3, -0.65), (0.6, -0.75), (0.9, -0.65), (1.2, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L:rotation": [(0, 0.0), (0.3, -1.25), (0.6, -1.35), (0.9, -1.25), (1.2, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, 0.0), (0.3, 0.65), (0.6, 0.75), (0.9, 0.65), (1.2, 0.0)],
            "Skeleton2D/pelvis/torso/arm_upper_R/arm_lower_R:rotation": [(0, 0.0), (0.3, -1.25), (0.6, -1.35), (0.9, -1.25), (1.2, 0.0)],
        }
    },
    "special_04": {
        "length": 1.1,
        "loop": 0,
        "desc": "Heroic Victory Flourish: spin weapon, crisp hip sheath, noble victory salute",
        "tracks": {
            "Skeleton2D/pelvis/torso:position": [(0, (0, -40)), (0.4, (0, -40)), (0.7, (0, -43)), (1.1, (0, -42))],
            "Skeleton2D/pelvis/torso:rotation": [(0, 0.0), (0.4, -0.1), (0.7, -0.05), (1.1, -0.05)],
            "Skeleton2D/pelvis/torso/head:rotation": [(0, 0.0), (0.4, 0.1), (0.7, -0.08), (1.1, -0.05)],
            "Skeleton2D/pelvis/torso/arm_upper_L:rotation": [(0, 0.0), (0.3, -1.6), (0.6, 0.3), (0.85, -1.2), (1.1, -0.8)],
            "Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L:rotation": [(0, 0.0), (0.3, -0.3), (0.6, -0.8), (0.85, -0.5), (1.1, -0.3)],
            "Skeleton2D/pelvis/torso/arm_upper_R:rotation": [(0, 0.0), (0.4, 0.2), (0.7, -0.4), (1.1, -0.3)],
        }
    }
}


def build_tscn_animation_text(anim_name: str, anim_data: Dict[str, Any]) -> str:
    """Generates standard Godot 4 .tscn text resource for an animation."""
    length = anim_data.get("length", 1.0)
    loop = anim_data.get("loop", 0)
    tracks = anim_data.get("tracks", {})

    lines = [
        f'[sub_resource type="Animation" id="Animation_{anim_name}"]',
        f'resource_name = "{anim_name}"',
        f'length = {length}',
    ]
    if loop:
        lines.append(f'loop_mode = {loop}')

    track_idx = 0
    for path, keyframes in tracks.items():
        lines.append(f'tracks/{track_idx}/type = "value"')
        lines.append(f'tracks/{track_idx}/imported = false')
        lines.append(f'tracks/{track_idx}/enabled = true')
        lines.append(f'tracks/{track_idx}/path = NodePath("{path}")')
        lines.append(f'tracks/{track_idx}/interp = 2')
        lines.append(f'tracks/{track_idx}/loop_wrap = true')

        times = ", ".join(f"{t}" for t, _ in keyframes)
        transitions = ", ".join("1" for _ in keyframes)
        
        is_vec2 = isinstance(keyframes[0][1], (tuple, list))
        if is_vec2:
            val_strs = [f"Vector2({v[0]}, {v[1]})" for _, v in keyframes]
        else:
            val_strs = [f"{v:.4f}" if isinstance(v, float) else f"{v}" for _, v in keyframes]
        values_str = ", ".join(val_strs)

        lines.append(f'tracks/{track_idx}/keys = {{')
        lines.append(f'"times": PackedFloat32Array({times}),')
        lines.append(f'"transitions": PackedFloat32Array({transitions}),')
        lines.append(f'"update": 0,')
        lines.append(f'"values": [{values_str}]')
        lines.append('}')
        track_idx += 1

    return "\n".join(lines)


def build_full_template_tscn(template_path: Path) -> None:
    """Rebuilds character_rig_template.tscn with all 23 animations."""
    anim_blocks = []
    lib_dict_entries = []

    for name, data in ANIMATION_DEFS.items():
        anim_blocks.append(build_tscn_animation_text(name, data))
        lib_dict_entries.append(f'&"{name}": SubResource("Animation_{name}")')

    anims_combined = "\n\n".join(anim_blocks)
    lib_dict_str = ",\n".join(lib_dict_entries)

    library_block = f"""[sub_resource type="AnimationLibrary" id="AnimationLibrary_char"]
_data = {{
{lib_dict_str}
}}"""

    hierarchy_block = """[node name="CharacterRoot" type="Node2D"]

[node name="AnimationPlayer" type="AnimationPlayer" parent="."]
libraries/ = SubResource("AnimationLibrary_char")
autoplay = "idle"

[node name="Skeleton2D" type="Skeleton2D" parent="."]
script = ExtResource("1_importer")
character_sprites_dir = "res://sprites/warrior"

[node name="pelvis" type="Bone2D" parent="Skeleton2D"]
rest = Transform2D(1, 0, 0, 1, 0, 0)

[node name="Sprite2D" type="Sprite2D" parent="Skeleton2D/pelvis"]
offset = Vector2(0, 4)

[node name="torso" type="Bone2D" parent="Skeleton2D/pelvis"]
position = Vector2(0, -40)
rest = Transform2D(1, 0, 0, 1, 0, -40)

[node name="Sprite2D" type="Sprite2D" parent="Skeleton2D/pelvis/torso"]
z_index = 1
offset = Vector2(0, -4)

[node name="BackSlot" type="Marker2D" parent="Skeleton2D/pelvis/torso"]
position = Vector2(0, 0)

[node name="head" type="Bone2D" parent="Skeleton2D/pelvis/torso"]
position = Vector2(0, -42)
rest = Transform2D(1, 0, 0, 1, 0, -42)
auto_calculate_length_and_angle = false
length = 20.0
bone_angle = -1.5708

[node name="Sprite2D" type="Sprite2D" parent="Skeleton2D/pelvis/torso/head"]
z_index = 3
offset = Vector2(0, -8)

[node name="HatSlot" type="Marker2D" parent="Skeleton2D/pelvis/torso/head"]
position = Vector2(0, -26)

[node name="arm_upper_L" type="Bone2D" parent="Skeleton2D/pelvis/torso"]
z_index = 2
position = Vector2(32, -20)
rest = Transform2D(1, 0, 0, 1, 32, -20)

[node name="Sprite2D" type="Sprite2D" parent="Skeleton2D/pelvis/torso/arm_upper_L"]
offset = Vector2(2, 18)

[node name="arm_lower_L" type="Bone2D" parent="Skeleton2D/pelvis/torso/arm_upper_L"]
position = Vector2(8, 36)
rest = Transform2D(1, 0, 0, 1, 8, 36)

[node name="Sprite2D" type="Sprite2D" parent="Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L"]
offset = Vector2(1, 16)

[node name="hand_L" type="Bone2D" parent="Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L"]
position = Vector2(4, 30)
rest = Transform2D(1, 0, 0, 1, 4, 30)
auto_calculate_length_and_angle = false
length = 16.0
bone_angle = 1.45

[node name="Sprite2D" type="Sprite2D" parent="Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L/hand_L"]
offset = Vector2(0, 10)

[node name="WeaponSlot_L" type="Marker2D" parent="Skeleton2D/pelvis/torso/arm_upper_L/arm_lower_L/hand_L"]
position = Vector2(0, 14)

[node name="arm_upper_R" type="Bone2D" parent="Skeleton2D/pelvis/torso"]
z_index = -1
position = Vector2(-32, -20)
rest = Transform2D(1, 0, 0, 1, -32, -20)

[node name="Sprite2D" type="Sprite2D" parent="Skeleton2D/pelvis/torso/arm_upper_R"]
offset = Vector2(-2, 18)

[node name="arm_lower_R" type="Bone2D" parent="Skeleton2D/pelvis/torso/arm_upper_R"]
position = Vector2(-8, 36)
rest = Transform2D(1, 0, 0, 1, -8, 36)

[node name="Sprite2D" type="Sprite2D" parent="Skeleton2D/pelvis/torso/arm_upper_R/arm_lower_R"]
offset = Vector2(-1, 16)

[node name="hand_R" type="Bone2D" parent="Skeleton2D/pelvis/torso/arm_upper_R/arm_lower_R"]
position = Vector2(-4, 30)
rest = Transform2D(1, 0, 0, 1, -4, 30)
auto_calculate_length_and_angle = false
length = 16.0
bone_angle = 1.69

[node name="Sprite2D" type="Sprite2D" parent="Skeleton2D/pelvis/torso/arm_upper_R/arm_lower_R/hand_R"]
offset = Vector2(0, 10)

[node name="WeaponSlot_R" type="Marker2D" parent="Skeleton2D/pelvis/torso/arm_upper_R/arm_lower_R/hand_R"]
position = Vector2(0, 14)

[node name="leg_upper_L" type="Bone2D" parent="Skeleton2D/pelvis"]
position = Vector2(20, 20)
rest = Transform2D(1, 0, 0, 1, 20, 20)

[node name="Sprite2D" type="Sprite2D" parent="Skeleton2D/pelvis/leg_upper_L"]
offset = Vector2(0, 18)

[node name="leg_lower_L" type="Bone2D" parent="Skeleton2D/pelvis/leg_upper_L"]
position = Vector2(0, 40)
rest = Transform2D(1, 0, 0, 1, 0, 40)

[node name="Sprite2D" type="Sprite2D" parent="Skeleton2D/pelvis/leg_upper_L/leg_lower_L"]
offset = Vector2(0, 16)

[node name="foot_L" type="Bone2D" parent="Skeleton2D/pelvis/leg_upper_L/leg_lower_L"]
position = Vector2(10, 30)
rest = Transform2D(1, 0, 0, 1, 10, 30)
auto_calculate_length_and_angle = false
length = 16.0
bone_angle = 1.5708

[node name="Sprite2D" type="Sprite2D" parent="Skeleton2D/pelvis/leg_upper_L/leg_lower_L/foot_L"]
offset = Vector2(8, 8)

[node name="leg_upper_R" type="Bone2D" parent="Skeleton2D/pelvis"]
z_index = -1
position = Vector2(-20, 20)
rest = Transform2D(1, 0, 0, 1, -20, 20)

[node name="Sprite2D" type="Sprite2D" parent="Skeleton2D/pelvis/leg_upper_R"]
offset = Vector2(0, 18)

[node name="leg_lower_R" type="Bone2D" parent="Skeleton2D/pelvis/leg_upper_R"]
position = Vector2(0, 40)
rest = Transform2D(1, 0, 0, 1, 0, 40)

[node name="Sprite2D" type="Sprite2D" parent="Skeleton2D/pelvis/leg_upper_R/leg_lower_R"]
offset = Vector2(0, 16)

[node name="foot_R" type="Bone2D" parent="Skeleton2D/pelvis/leg_upper_R/leg_lower_R"]
position = Vector2(-10, 30)
rest = Transform2D(1, 0, 0, 1, -10, 30)
auto_calculate_length_and_angle = false
length = 16.0
bone_angle = 1.5708

[node name="Sprite2D" type="Sprite2D" parent="Skeleton2D/pelvis/leg_upper_R/leg_lower_R/foot_R"]
offset = Vector2(-8, 8)
"""

    full_content = f"""[gd_scene load_steps={len(ANIMATION_DEFS) + 4} format=3 uid="uid://dmfx8qk4k5rig"]

[ext_resource type="Script" path="res://auto_rig_importer.gd" id="1_importer"]

{anims_combined}

{library_block}

{hierarchy_block}
"""
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(full_content)
    print(f"✓ Rebuilt template '{template_path.name}' with {len(ANIMATION_DEFS)} animations.")


def rerig_all_existing_scenes() -> List[str]:
    """Re-rigs all characters using the new animation-packed template."""
    import server
    sprites_root = PROJECT_ROOT / "sprites"
    updated = []
    if sprites_root.is_dir():
        for d in sorted(sprites_root.iterdir()):
            if not d.is_dir():
                continue
            char_name = d.name
            target_scene = f"res://scenes/{char_name}_character.tscn"
            rig_type = "quadruped" if char_name in ["fenrir", "celestial_wolf"] else "biped"
            res_str = server.assemble_godot_rig(
                character_name=char_name,
                assets_dir=f"res://sprites/{char_name}",
                target_scene_path=target_scene,
                rig_type=rig_type
            )
            updated.append(char_name)
    return updated


if __name__ == "__main__":
    tmpl = PROJECT_ROOT / "scenes" / "character_rig_template.tscn"
    build_full_template_tscn(tmpl)
    updated = rerig_all_existing_scenes()
    print(f"✓ Successfully re-rigged {len(updated)} character scenes with 23 default animations.")
