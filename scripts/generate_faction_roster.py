#!/usr/bin/env python3
"""
generate_faction_roster.py - Complete 60-Unit Cyberpunk Post-Apocalyptic RTS Roster Generator

Generates:
- 5 Cyberpunk Factions (Neo-Terra Directorate, Rust Syndicate, Neuro-Covenant, Bio-Forge Legion, Silicon Hive)
- 12 RTS Archetypes per Faction (Soldier, Sniper, Grenadier, Rocket, SpecAgent, Medic, Engineer,
  Saboteur, Flamethrower, MindController, DroneOp, Flak)
- Total 60 distinct characters, each with:
  1. 15 sliced limb sprites in sprites/<name>/
  2. Master exploded sprite sheet <name>_exploded.png
  3. Assembled full character preview <name>_full.png
  4. 4 tailored/randomized signature special moves from SPECIAL_MOVES_CATALOG
  5. Full metadata.json (faction, role, weapon, special moves)
  6. Godot 4 .tscn skeletal rig scene in scenes/<name>_character.tscn with all 23 animations!
"""

import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from scripts.generate_sample_sprites import generate_all, create_character_assembled_preview
from scripts.generate_rig_animations import (
    SPECIAL_MOVES_CATALOG,
    build_character_animations,
    build_tscn_animation_text,
    randomize_character_specials
)

# ==============================================================================
# 5 FACTIONS & 12 ARCHETYPES DEFINITION
# ==============================================================================

FACTION_DEFINITIONS = {
    "directorate": {
        "name": "Neo-Terra Directorate",
        "desc": "High-tech authoritarian enforcers with polished gunmetal composite armor, glowing neon cyan optics, and precision energy weapons.",
        "colors": {
            "primary": "#344052",
            "accent": "#4e607a",
            "glow": "#00d7ff",
            "outline": "#101620"
        },
        "art_style": "anime",
        "units": {
            "soldier": {
                "display": "Directorate Enforcer",
                "role": "Soldier",
                "desc": "Standard frontline shock trooper armed with a high-velocity pulse rifle.",
                "weapon": "directorate_assault_rifle",
                "specials": ["special_heavy_gatling", "special_emp_blast", "special_ground_slam", "special_victory_flourish"]
            },
            "sniper": {
                "display": "Apex Sharpshooter",
                "role": "Sniper",
                "desc": "High-precision marksman with an overcharged magnetic railgun and optical rangefinders.",
                "weapon": "directorate_sniper_rifle",
                "specials": ["special_railgun_snipe", "special_active_camo", "special_power_charge", "special_victory_flourish"]
            },
            "grenadier": {
                "display": "Shock Grenadier",
                "role": "Grenadier",
                "desc": "Heavy riot grenadier equipped with an automated EMP cluster canister launcher.",
                "weapon": "directorate_grenade_launcher",
                "specials": ["special_emp_blast", "special_napalm_toss", "special_ground_slam", "special_orbital_strike"]
            },
            "rocket": {
                "display": "Havoc Missile Trooper",
                "role": "Rocket Trooper",
                "desc": "Exoskeleton-braced soldier with a shoulder-mounted smart-tracking missile pod.",
                "weapon": "directorate_rocket_launcher",
                "specials": ["special_mortar_barrage", "special_orbital_strike", "special_power_charge", "special_victory_flourish"]
            },
            "specagent": {
                "display": "Directorate Infiltrator",
                "role": "Special Agent",
                "desc": "Black-ops assassin with optical refraction cloak and silenced micro-SMG.",
                "weapon": "directorate_submachine_gun",
                "specials": ["special_active_camo", "special_cyber_dash", "special_stim_inject", "special_cyber_hack"]
            },
            "medic": {
                "display": "Biocore Combat Medic",
                "role": "Medic",
                "desc": "Field surgeon with pressurized nanite injectors and defibrillator shock paddles.",
                "weapon": "directorate_submachine_gun",
                "specials": ["special_defib_revive", "special_stim_inject", "special_nanite_barrier", "special_victory_flourish"]
            },
            "engineer": {
                "display": "Combat Field Tech",
                "role": "Engineer",
                "desc": "Combat fortifications specialist with deployable auto-sentries and repair arc welder.",
                "weapon": "directorate_shotgun",
                "specials": ["special_deploy_turret", "special_nanite_barrier", "special_cyber_hack", "special_victory_flourish"]
            },
            "saboteur": {
                "display": "Covert Interceptor",
                "role": "Spy / Saboteur",
                "desc": "Electronic warfare operative who infiltrates enemy grids with dataspike injects.",
                "weapon": "directorate_submachine_gun",
                "specials": ["special_cyber_hack", "special_active_camo", "special_emp_blast", "special_cyber_dash"]
            },
            "flamethrower": {
                "display": "Purge Incinerator",
                "role": "Flame Trooper",
                "desc": "Heavily armored cleanser armed with a pressurized liquid plasma flamethrower.",
                "weapon": "directorate_flamethrower",
                "specials": ["special_flame_inferno", "special_napalm_toss", "special_ground_slam", "special_power_charge"]
            },
            "mindcontroller": {
                "display": "Neural Taskmaster",
                "role": "Mind Controller",
                "desc": "Cybernetic psionic officer using neural override frequencies to hijack enemy minds.",
                "weapon": "directorate_psi_emitter",
                "specials": ["special_psi_overload", "special_power_charge", "special_sonic_screech", "special_orbital_strike"]
            },
            "drone_op": {
                "display": "Hunter Drone Commander",
                "role": "Drone Operator",
                "desc": "Tactical officer with holographic wrist comms commanding autonomous hunter drones.",
                "weapon": "directorate_drone_pad",
                "specials": ["special_drone_swarm", "special_deploy_turret", "special_orbital_strike", "special_victory_flourish"]
            },
            "flak": {
                "display": "Skyward Sentinel",
                "role": "Flak Trooper",
                "desc": "Anti-air gunner operating a quad-barrel heavy radar-guided flak cannon.",
                "weapon": "directorate_flak_cannon",
                "specials": ["special_flak_barrage", "special_heavy_gatling", "special_mortar_barrage", "special_victory_flourish"]
            }
        }
    },
    "syndicate": {
        "name": "Rust Syndicate",
        "desc": "Wasteland scavengers, scrap raiders, and cyber-nomads clad in welded rust armor, hazard stripes, and combustible weaponry.",
        "colors": {
            "primary": "#915a2d",
            "accent": "#e68c14",
            "glow": "#ffc300",
            "outline": "#23140a"
        },
        "art_style": "dark_fantasy",
        "units": {
            "soldier": {
                "display": "Scrap Marauder",
                "role": "Soldier",
                "desc": "Gunslinger soldier with a cobbled autogun welded from vehicle parts.",
                "weapon": "syndicate_assault_rifle",
                "specials": ["special_heavy_gatling", "special_napalm_toss", "special_ground_slam", "special_whirlwind"]
            },
            "sniper": {
                "display": "Wasteland Long-Shot",
                "role": "Sniper",
                "desc": "Patient wasteland hunter wielding an anti-materiel rifle chambered in tank rounds.",
                "weapon": "syndicate_sniper_rifle",
                "specials": ["special_railgun_snipe", "special_active_camo", "special_power_charge", "special_stim_inject"]
            },
            "grenadier": {
                "display": "Bomb Lobber",
                "role": "Grenadier",
                "desc": "Crazed demolitionist carrying bandoliers of pipe bombs and volatile shrapnel.",
                "weapon": "syndicate_grenade_launcher",
                "specials": ["special_napalm_toss", "special_emp_blast", "special_ground_slam", "special_whirlwind"]
            },
            "rocket": {
                "display": "Rust-Rocket Demolitionist",
                "role": "Rocket Trooper",
                "desc": "Heavy raider wielding a jury-rigged triple-barrel scrap iron rocket launcher.",
                "weapon": "syndicate_rocket_launcher",
                "specials": ["special_mortar_barrage", "special_orbital_strike", "special_ground_slam", "special_power_charge"]
            },
            "specagent": {
                "display": "Syndicate Enforcer Agent",
                "role": "Special Agent",
                "desc": "Brutal underworld hitman carrying a sawed-off scattergun and motorized shock baton.",
                "weapon": "syndicate_shotgun",
                "specials": ["special_cyber_dash", "special_stim_inject", "special_whirlwind", "special_ground_slam"]
            },
            "medic": {
                "display": "Junk Doc / Patch-Up",
                "role": "Medic",
                "desc": "Underground medic dispensing crude adrenaline cocktails and cauterizing torches.",
                "weapon": "syndicate_submachine_gun",
                "specials": ["special_stim_inject", "special_defib_revive", "special_nanite_barrier", "special_whirlwind"]
            },
            "engineer": {
                "display": "Scav Tinkerer",
                "role": "Engineer",
                "desc": "Scrap artisan who bolts together motorized junk barricades and scrap turrets.",
                "weapon": "syndicate_shotgun",
                "specials": ["special_deploy_turret", "special_cyber_hack", "special_emp_blast", "special_victory_flourish"]
            },
            "saboteur": {
                "display": "Shadow Rustler",
                "role": "Spy / Saboteur",
                "desc": "Infiltrator who cuts power cables, poisons fuel reserves, and vanishes in diesel smoke.",
                "weapon": "syndicate_submachine_gun",
                "specials": ["special_active_camo", "special_cyber_hack", "special_emp_blast", "special_cyber_dash"]
            },
            "flamethrower": {
                "display": "Scorcher Fiend",
                "role": "Flame Trooper",
                "desc": "Incendiary maniac spraying superheated crude petroleum across the battlefield.",
                "weapon": "syndicate_flamethrower",
                "specials": ["special_flame_inferno", "special_napalm_toss", "special_ground_slam", "special_whirlwind"]
            },
            "mindcontroller": {
                "display": "Brain-Melter Hermit",
                "role": "Mind Controller",
                "desc": "Radiation-scarred psyker with a cobbled radio-amplified hypno-crown.",
                "weapon": "syndicate_psi_emitter",
                "specials": ["special_psi_overload", "special_sonic_screech", "special_power_charge", "special_emp_blast"]
            },
            "drone_op": {
                "display": "Scrap Swarm Handler",
                "role": "Drone Operator",
                "desc": "Remote operator guiding buzzing quad-copters armed with explosive buzz-saws.",
                "weapon": "syndicate_drone_pad",
                "specials": ["special_drone_swarm", "special_deploy_turret", "special_emp_blast", "special_victory_flourish"]
            },
            "flak": {
                "display": "Anti-Air Scrap-Buster",
                "role": "Flak Trooper",
                "desc": "Gunner firing shrapnel cans out of dual boiler-iron blast tubes.",
                "weapon": "syndicate_flak_cannon",
                "specials": ["special_flak_barrage", "special_heavy_gatling", "special_mortar_barrage", "special_ground_slam"]
            }
        }
    },
    "covenant": {
        "name": "Neuro-Covenant",
        "desc": "Transhumanist psionic cult wearing synthetic carbon armor, glowing violet conduits, and levitating telepathic foci.",
        "colors": {
            "primary": "#262036",
            "accent": "#8c46d2",
            "glow": "#dc64ff",
            "outline": "#0e0a16"
        },
        "art_style": "anime",
        "units": {
            "soldier": {
                "display": "Covenant Zealot",
                "role": "Soldier",
                "desc": "Devoted warrior firing condensed psionic beam energy from a conduit carbine.",
                "weapon": "covenant_assault_rifle",
                "specials": ["special_psi_overload", "special_power_charge", "special_cyber_dash", "special_victory_flourish"]
            },
            "sniper": {
                "display": "Void Eye Gazer",
                "role": "Sniper",
                "desc": "Psionic sniper projecting clairvoyant rail-lances through physical cover.",
                "weapon": "covenant_sniper_rifle",
                "specials": ["special_railgun_snipe", "special_active_camo", "special_psi_overload", "special_power_charge"]
            },
            "grenadier": {
                "display": "Psy-Orb Dispenser",
                "role": "Grenadier",
                "desc": "Levitating warrior hurling telekinetic distortion spheres that implode on impact.",
                "weapon": "covenant_grenade_launcher",
                "specials": ["special_psi_overload", "special_ground_slam", "special_emp_blast", "special_power_charge"]
            },
            "rocket": {
                "display": "Nova Annihilator",
                "role": "Rocket Trooper",
                "desc": "Heavy disciple projecting miniature void singularities across the frontline.",
                "weapon": "covenant_rocket_launcher",
                "specials": ["special_orbital_strike", "special_mortar_barrage", "special_power_charge", "special_psi_overload"]
            },
            "specagent": {
                "display": "Covenant Archon",
                "role": "Special Agent",
                "desc": "Teleporting void assassin cutting targets down with dual psychokinetic blades.",
                "weapon": "covenant_submachine_gun",
                "specials": ["special_cyber_dash", "special_active_camo", "special_whirlwind", "special_psi_overload"]
            },
            "medic": {
                "display": "Vitalis Healer",
                "role": "Medic",
                "desc": "Covenant restorer repairing bio-synthetic tissue through telepathic conduits.",
                "weapon": "covenant_psi_emitter",
                "specials": ["special_defib_revive", "special_nanite_barrier", "special_power_charge", "special_stim_inject"]
            },
            "engineer": {
                "display": "Chrono-Architect",
                "role": "Engineer",
                "desc": "Synthesizes hard-light shielding arrays and temporal distortion anchors.",
                "weapon": "covenant_shotgun",
                "specials": ["special_nanite_barrier", "special_deploy_turret", "special_cyber_hack", "special_power_charge"]
            },
            "saboteur": {
                "display": "Phantom Spectre",
                "role": "Spy / Saboteur",
                "desc": "Phase-shifting operative who infiltrates security networks by mind-hijacking sentries.",
                "weapon": "covenant_submachine_gun",
                "specials": ["special_active_camo", "special_cyber_hack", "special_psi_overload", "special_cyber_dash"]
            },
            "flamethrower": {
                "display": "Soul-Fire Cleanser",
                "role": "Flame Trooper",
                "desc": "Wields a warp-fire projector bathing enemy ranks in violet entropic fire.",
                "weapon": "covenant_flamethrower",
                "specials": ["special_flame_inferno", "special_whirlwind", "special_power_charge", "special_ground_slam"]
            },
            "mindcontroller": {
                "display": "Grand Psionic Sovereign",
                "role": "Mind Controller",
                "desc": "Supreme psychic conduit capable of turning entire enemy squads against themselves.",
                "weapon": "covenant_psi_emitter",
                "specials": ["special_psi_overload", "special_sonic_screech", "special_orbital_strike", "special_power_charge"]
            },
            "drone_op": {
                "display": "Telepathic Monolith Relay",
                "role": "Drone Operator",
                "desc": "Commands floating obelisk relays that channel psychokinetic energy shields.",
                "weapon": "covenant_drone_pad",
                "specials": ["special_drone_swarm", "special_nanite_barrier", "special_orbital_strike", "special_victory_flourish"]
            },
            "flak": {
                "display": "Rift-Burst Warden",
                "role": "Flak Trooper",
                "desc": "Fires micro-dimensional fractures skyward to shred airborne targets in mid-flight.",
                "weapon": "covenant_flak_cannon",
                "specials": ["special_flak_barrage", "special_orbital_strike", "special_heavy_gatling", "special_power_charge"]
            }
        }
    },
    "bioforge": {
        "name": "Bio-Forge Legion",
        "desc": "Mutant gene-splicers and chem-warriors protected by chitinous carapaces, glowing radioactive bile, and toxic weaponry.",
        "colors": {
            "primary": "#2d4126",
            "accent": "#50aa32",
            "glow": "#8cff28",
            "outline": "#121c0e"
        },
        "art_style": "anime",
        "units": {
            "soldier": {
                "display": "Spliced Trooper",
                "role": "Soldier",
                "desc": "Mutant warrior firing hyper-accelerated bone spines from a living bio-weapon.",
                "weapon": "bioforge_assault_rifle",
                "specials": ["special_stim_inject", "special_ground_slam", "special_sonic_screech", "special_heavy_gatling"]
            },
            "sniper": {
                "display": "Venom Marksman",
                "role": "Sniper",
                "desc": "Patient chitin stalker launching neurotoxic dart needles that melt internal organs.",
                "weapon": "bioforge_sniper_rifle",
                "specials": ["special_railgun_snipe", "special_active_camo", "special_stim_inject", "special_victory_flourish"]
            },
            "grenadier": {
                "display": "Spore Lobber",
                "role": "Grenadier",
                "desc": "Slinging corrosive spore pods that burst into caustic cloud clouds upon detonation.",
                "weapon": "bioforge_grenade_launcher",
                "specials": ["special_napalm_toss", "special_ground_slam", "special_sonic_screech", "special_whirlwind"]
            },
            "rocket": {
                "display": "Bio-Mortar Behemoth",
                "role": "Rocket Trooper",
                "desc": "Massive mutated warrior with a living bio-mortar growing from its muscular shoulder.",
                "weapon": "bioforge_rocket_launcher",
                "specials": ["special_mortar_barrage", "special_ground_slam", "special_power_charge", "special_sonic_screech"]
            },
            "specagent": {
                "display": "Apex Predator Agent",
                "role": "Special Agent",
                "desc": "Gene-spliced hunter with chameleon skin, heightened reflexes, and razor bone talons.",
                "weapon": "bioforge_submachine_gun",
                "specials": ["special_active_camo", "special_cyber_dash", "special_stim_inject", "special_whirlwind"]
            },
            "medic": {
                "display": "Symbiote Triage",
                "role": "Medic",
                "desc": "Injects regenerative symbiotic larvae into fallen mutants to accelerate flesh repair.",
                "weapon": "bioforge_submachine_gun",
                "specials": ["special_defib_revive", "special_stim_inject", "special_nanite_barrier", "special_power_charge"]
            },
            "engineer": {
                "display": "Gene-Mechanic",
                "role": "Engineer",
                "desc": "Cultivates living chitinous barricades and bio-organic spore spitters.",
                "weapon": "bioforge_shotgun",
                "specials": ["special_deploy_turret", "special_nanite_barrier", "special_stim_inject", "special_victory_flourish"]
            },
            "saboteur": {
                "display": "Acid Infestor",
                "role": "Spy / Saboteur",
                "desc": "Creeps into enemy camps spraying corrosive saliva that dissolves armor and munitions.",
                "weapon": "bioforge_submachine_gun",
                "specials": ["special_active_camo", "special_cyber_hack", "special_cyber_dash", "special_sonic_screech"]
            },
            "flamethrower": {
                "display": "Caustic Chem-Spitter",
                "role": "Flame Trooper",
                "desc": "Spews boiling caustic acid streams from an enlarged pressurized venom gland.",
                "weapon": "bioforge_flamethrower",
                "specials": ["special_flame_inferno", "special_ground_slam", "special_napalm_toss", "special_power_charge"]
            },
            "mindcontroller": {
                "display": "Hive-Mind Broodcaller",
                "role": "Mind Controller",
                "desc": "Transmits psionic hive pheromones that overwhelm enemy cognition with mindless submission.",
                "weapon": "bioforge_psi_emitter",
                "specials": ["special_psi_overload", "special_sonic_screech", "special_orbital_strike", "special_power_charge"]
            },
            "drone_op": {
                "display": "Spore-Wasp Handler",
                "role": "Drone Operator",
                "desc": "Releases swarms of bio-engineered armor-piercing wasps with lethal neurotoxin stingers.",
                "weapon": "bioforge_drone_pad",
                "specials": ["special_drone_swarm", "special_deploy_turret", "special_stim_inject", "special_victory_flourish"]
            },
            "flak": {
                "display": "Bio-Flak Spitter",
                "role": "Flak Trooper",
                "desc": "Fires explosive bone-calcified shells that detonate into flying razor shrapnel.",
                "weapon": "bioforge_flak_cannon",
                "specials": ["special_flak_barrage", "special_mortar_barrage", "special_heavy_gatling", "special_ground_slam"]
            }
        }
    },
    "silicon": {
        "name": "Silicon Hive",
        "desc": "Autonomous combat androids, rogue AI frames, and mechanical warmachines built from matte black alloys and red laser optics.",
        "colors": {
            "primary": "#202226",
            "accent": "#5a5f69",
            "glow": "#ff2d3c",
            "outline": "#0a0c0e"
        },
        "art_style": "anime",
        "units": {
            "soldier": {
                "display": "Combat Android Unit",
                "role": "Soldier",
                "desc": "Mass-produced battle droid operating a high-frequency laser pulse rifle with zero recoil.",
                "weapon": "silicon_assault_rifle",
                "specials": ["special_heavy_gatling", "special_emp_blast", "special_power_charge", "special_victory_flourish"]
            },
            "sniper": {
                "display": "Targeting Unit Alpha",
                "role": "Sniper",
                "desc": "Automated precision chassis equipped with quantum targeting optics and heavy beam rifle.",
                "weapon": "silicon_sniper_rifle",
                "specials": ["special_railgun_snipe", "special_active_camo", "special_power_charge", "special_cyber_hack"]
            },
            "grenadier": {
                "display": "Cluster Disperser Drone",
                "role": "Grenadier",
                "desc": "Bipedal automaton firing micro-grenade drums that blanket targets in explosive cluster.",
                "weapon": "silicon_grenade_launcher",
                "specials": ["special_emp_blast", "special_napalm_toss", "special_ground_slam", "special_orbital_strike"]
            },
            "rocket": {
                "display": "Automated Siege Frame",
                "role": "Rocket Trooper",
                "desc": "Heavy mechanized walker chassis with dual fire-and-forget missile batteries.",
                "weapon": "silicon_rocket_launcher",
                "specials": ["special_mortar_barrage", "special_orbital_strike", "special_power_charge", "special_heavy_gatling"]
            },
            "specagent": {
                "display": "Cyber Recon Operative",
                "role": "Special Agent",
                "desc": "Silent assassin chassis fitted with thermal sensor baffles and monomolecular vibrating blade.",
                "weapon": "silicon_submachine_gun",
                "specials": ["special_active_camo", "special_cyber_dash", "special_cyber_hack", "special_stim_inject"]
            },
            "medic": {
                "display": "Nanite Repair Solder-Unit",
                "role": "Medic",
                "desc": "Mobile maintenance unit deploying solder-lasers and nanite swarms to repair friendly frames.",
                "weapon": "silicon_submachine_gun",
                "specials": ["special_defib_revive", "special_nanite_barrier", "special_power_charge", "special_stim_inject"]
            },
            "engineer": {
                "display": "Fortification Fabricator",
                "role": "Engineer",
                "desc": "Industrial chassis equipped with rapid 3D printer lasers to construct fortified gun emplacements.",
                "weapon": "silicon_shotgun",
                "specials": ["special_deploy_turret", "special_nanite_barrier", "special_cyber_hack", "special_victory_flourish"]
            },
            "saboteur": {
                "display": "Malware Infiltrator",
                "role": "Spy / Saboteur",
                "desc": "Electronic sabotage unit designed to inject logic bombs into power nodes and control grids.",
                "weapon": "silicon_submachine_gun",
                "specials": ["special_cyber_hack", "special_emp_blast", "special_active_camo", "special_cyber_dash"]
            },
            "flamethrower": {
                "display": "Thermal Vent Purger",
                "role": "Flame Trooper",
                "desc": "Overclocks its central cooling loop to expel incinerating exhaust jets at advancing infantry.",
                "weapon": "silicon_flamethrower",
                "specials": ["special_flame_inferno", "special_power_charge", "special_ground_slam", "special_napalm_toss"]
            },
            "mindcontroller": {
                "display": "Logic Corruptor Unit",
                "role": "Mind Controller",
                "desc": "Emits electromagnetic override pulses that hijack organic cyberware and electronic systems.",
                "weapon": "silicon_psi_emitter",
                "specials": ["special_psi_overload", "special_cyber_hack", "special_orbital_strike", "special_sonic_screech"]
            },
            "drone_op": {
                "display": "Carrier Drone Node",
                "role": "Drone Operator",
                "desc": "Mobile hive node coordinating flight sub-routines for swarms of micro-attack drones.",
                "weapon": "silicon_drone_pad",
                "specials": ["special_drone_swarm", "special_deploy_turret", "special_orbital_strike", "special_victory_flourish"]
            },
            "flak": {
                "display": "Area Denial Flak Array",
                "role": "Flak Trooper",
                "desc": "Heavy automated artillery droid calculating firing solutions for radar-fused airburst flak.",
                "weapon": "silicon_flak_cannon",
                "specials": ["special_flak_barrage", "special_heavy_gatling", "special_mortar_barrage", "special_orbital_strike"]
            }
        }
    }
}


def find_godot() -> str:
    """Finds Godot 4 executable path."""
    env_bin = os.environ.get("GODOT_BIN")
    if env_bin and os.path.isfile(env_bin):
        return env_bin
    for name in ["Godot_v4.7.2-stable_win64_console.exe", "godot4", "godot", "godot.exe"]:
        found = shutil.which(name)
        if found:
            return found
    local_winget = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"
    if local_winget.is_dir():
        for exe in local_winget.glob("Godot*.exe"):
            if "console" in exe.name.lower():
                return str(exe)
        for exe in local_winget.glob("Godot*.exe"):
            return str(exe)
    return "godot"


def generate_single_character(char_id: str, faction_key: str, role_key: str, unit_data: Dict[str, Any], godot_bin: str = None) -> Dict[str, Any]:
    """Generates all sliced limbs, exploded sheet, full preview, metadata, and rigs Godot 4 scene."""
    faction_data = FACTION_DEFINITIONS[faction_key]
    colors = faction_data["colors"]
    art_style = faction_data["art_style"]

    char_dir = PROJECT_ROOT / "sprites" / char_id
    char_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate Sliced Limbs & Exploded Sheet
    prompt_desc = f"{faction_data['name']} {unit_data['display']} {unit_data['role']}, {unit_data['desc']}, sci-fi cyberpunk post-apocalyptic"
    generate_all(
        out_dir=str(char_dir),
        prefix=char_id,
        archetype="mech" if faction_key == "silicon" else ("beast" if faction_key == "bioforge" else "warrior"),
        prompt=prompt_desc,
        seed=abs(hash(char_id)) % 2147483647,
        custom_colors=colors,
        art_style=art_style
    )

    # 2. Generate Assembled Full Model Preview
    create_character_assembled_preview(char_dir, prefix=char_id, rig_type="biped")

    # 3. Create Custom Template with Character's 4 Signature Specials
    specials = unit_data.get("specials", ["special_ground_slam", "special_whirlwind", "special_power_charge", "special_victory_flourish"])
    char_anims = build_character_animations(specials)

    # Generate custom tscn for character
    target_scene = f"res://scenes/{char_id}_character.tscn"
    target_scene_file = PROJECT_ROOT / "scenes" / f"{char_id}_character.tscn"

    # Assemble scene directly using Godot headless builder
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
        except Exception as e:
            pass

    # 4. Save metadata.json
    meta = {
        "character_name": char_id,
        "display_name": unit_data["display"],
        "faction_id": faction_key,
        "faction_name": faction_data["name"],
        "role": unit_data["role"],
        "description": unit_data["desc"],
        "weapon_id": unit_data.get("weapon", f"{faction_key}_assault_rifle"),
        "art_style": art_style,
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


def generate_all_60_faction_characters() -> List[Dict[str, Any]]:
    """Generates all 60 characters across 5 factions."""
    godot_bin = find_godot()
    print("\n========================================================")
    print("Generating 60 Cyberpunk Post-Apocalyptic RTS Characters")
    print(f"5 Factions x 12 Archetypes | Godot Engine: {godot_bin}")
    print("========================================================\n")

    roster = []
    total = sum(len(f["units"]) for f in FACTION_DEFINITIONS.values())
    curr = 0

    for faction_key, faction_data in FACTION_DEFINITIONS.items():
        print(f"\n--- Faction: {faction_data['name']} (12 Units) ---")
        for role_key, unit_data in faction_data["units"].items():
            curr += 1
            char_id = f"{faction_key}_{role_key}"
            print(f"[{curr:02d}/{total:02d}] Generating '{char_id}' ({unit_data['display']})...")
            meta = generate_single_character(char_id, faction_key, role_key, unit_data, godot_bin)
            roster.append(meta)

    # Save complete roster master index
    roster_file = PROJECT_ROOT / "sprites" / "faction_roster.json"
    with open(roster_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_characters": len(roster),
            "factions": [
                {
                    "id": k,
                    "name": v["name"],
                    "desc": v["desc"],
                    "colors": v["colors"],
                    "units": list(v["units"].keys())
                }
                for k, v in FACTION_DEFINITIONS.items()
            ],
            "roster": roster
        }, f, indent=2)

    print("\n========================================================")
    print(f"[OK] COMPLETE! Successfully generated and rigged all {len(roster)} characters!")
    print(f"Master Roster index: {roster_file}")
    print("========================================================\n")
    return roster


if __name__ == "__main__":
    generate_all_60_faction_characters()
