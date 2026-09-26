extends Node2D

## =============================================================================
## rts_battle_demo.gd - Godot 4 Advanced Cyberpunk RTS Skirmish Arena
##
## Features:
##   - Real-time squad combat between 15 Cyberpunk factions with 23 animations
##   - Multi-unit drag-box selection and formation movement
##   - Overhead segmented health & energy shield bars with team colors
##   - Tactical Fog of War vision system (toggleable with 'F' or HUD button)
##   - Signature tactical abilities: Orbital Strike, Tachyon Dash, EMP Shockwave, Nanite Cloud
##   - Floating combat text with crits, shield deflections, and status effects
##   - Stance controls: Aggressive Assault, Hold Position, Tactical Retreat
##   - Interactive tactical HUD with mouse-clickable action buttons
##
## Controls:
##   - Left Click & Drag: Box select multiple units
##   - Left Click: Select single unit
##   - Right Click: Issue squad Move / Attack order (maintains formation)
##   - 1: Orbital Laser Strike at cursor / selected target
##   - 2: Tachyon Dash forward / towards cursor
##   - 3: EMP Shockwave stun nova
##   - 4: Toxic Nanite Corrosive Cloud
##   - F: Toggle Tactical Fog of War
##   - H: Hold Position Stance
##   - B: Fall Back / Tactical Retreat
##   - A: Aggressive Assault Stance
##   - Space: Pause / Resume Battle
##   - R: Respawn / Reset Skirmish
##   - WASD / Arrow Keys: Pan Battlefield Camera
##   - Mouse Wheel: Zoom Camera In / Out
## =============================================================================

const ARENA_WIDTH := 1600.0
const ARENA_HEIGHT := 900.0

enum Stance { AGGRESSIVE, HOLD, RETREAT }

# Selection & State
var selected_units: Array[Node2D] = []
var is_paused := false
var fog_of_war_enabled := false
var current_stance: Stance = Stance.AGGRESSIVE

# Drag selection state
var is_dragging_box := false
var drag_box_start := Vector2.ZERO
var drag_box_current := Vector2.ZERO

# Active FX systems
var active_orbital_strikes: Array[Dictionary] = []
var active_emp_waves: Array[Dictionary] = []
var active_nanite_clouds: Array[Dictionary] = []
var active_dash_trails: Array[Dictionary] = []

# Squad Roster Scenes
var blue_squad_scenes := [
	"res://scenes/tachyon_striker_character.tscn",
	"res://scenes/aegis_sentinel_character.tscn",
	"res://scenes/orbital_ranger_character.tscn",
	"res://scenes/cyber_kunoichi_character.tscn",
	"res://scenes/directorate_soldier_character.tscn"
]

var red_squad_scenes := [
	"res://scenes/rust_marauder_character.tscn",
	"res://scenes/acid_vulture_character.tscn",
	"res://scenes/slag_berserker_character.tscn",
	"res://scenes/toxic_desperado_character.tscn",
	"res://scenes/syndicate_soldier_character.tscn"
]

var all_units: Array[Node2D] = []

@onready var camera: Camera2D = $Camera2D
@onready var units_container: Node2D = $Units
@onready var effects_container: Node2D = $Effects
@onready var hud: CanvasLayer = $HUD

# HUD interactive controls
var btn_orbital: Button
var btn_dash: Button
var btn_emp: Button
var btn_nanite: Button
var btn_fog: Button
var btn_stance: Button
var btn_pause: Button
var btn_reset: Button
var lbl_status: Label
var lbl_selection_info: Label
var lbl_squad_counts: Label


func _ready() -> void:
	setup_enhanced_hud()
	spawn_skirmish()


func setup_enhanced_hud() -> void:
	var panel: Panel = hud.get_node_or_null("Panel")
	if not panel:
		return
	
	panel.custom_minimum_size = Vector2(0, 84.0)
	panel.offset_bottom = 84.0
	
	var vbox: VBoxContainer = panel.get_node_or_null("VBox")
	if not vbox:
		return
	
	# Title & Status row
	var top_row := HBoxContainer.new()
	top_row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	
	var title_lbl: Label = vbox.get_node_or_null("Title")
	if title_lbl:
		title_lbl.text = "⚡ CYBERPUNK RTS TACTICAL BATTLEFIELD"
		title_lbl.add_theme_color_override("font_color", Color(0.0, 0.95, 1.0))
		title_lbl.reparent(top_row)
	
	lbl_squad_counts = Label.new()
	lbl_squad_counts.text = "🔵 Blue Alliance: 5  |  🔴 Red Syndicate: 5"
	lbl_squad_counts.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	lbl_squad_counts.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	lbl_squad_counts.add_theme_color_override("font_color", Color(0.9, 0.9, 0.9))
	lbl_squad_counts.add_theme_font_size_override("font_size", 13)
	top_row.add_child(lbl_squad_counts)
	vbox.add_child(top_row)
	vbox.move_child(top_row, 0)
	
	# Remove old stats label or reparent it
	var old_stats: Label = vbox.get_node_or_null("Stats")
	if old_stats:
		old_stats.queue_free()

	# Middle Tactical Command Buttons Row
	var btn_row := HBoxContainer.new()
	btn_row.add_theme_constant_override("separation", 8)
	
	btn_orbital = create_hud_button("🛰️ Orbital [1]", Color(0.0, 0.85, 1.0), Callable(self, "_on_orbital_clicked"))
	btn_dash = create_hud_button("⚡ Dash [2]", Color(0.4, 0.8, 1.0), Callable(self, "_on_dash_clicked"))
	btn_emp = create_hud_button("💥 EMP [3]", Color(0.8, 0.4, 1.0), Callable(self, "_on_emp_clicked"))
	btn_nanite = create_hud_button("☣️ Nanite [4]", Color(0.3, 1.0, 0.4), Callable(self, "_on_nanite_clicked"))
	btn_fog = create_hud_button("👁️ Fog: OFF [F]", Color(0.7, 0.8, 0.9), Callable(self, "_on_fog_toggled"))
	btn_stance = create_hud_button("🛡️ Stance: Assault [H]", Color(0.3, 0.9, 1.0), Callable(self, "_on_stance_toggled"))
	btn_pause = create_hud_button("⏸️ Pause [Space]", Color(1.0, 0.8, 0.2), Callable(self, "_on_pause_toggled"))
	btn_reset = create_hud_button("🔄 Respawn [R]", Color(0.9, 0.4, 0.3), Callable(self, "spawn_skirmish"))
	
	btn_row.add_child(btn_orbital)
	btn_row.add_child(btn_dash)
	btn_row.add_child(btn_emp)
	btn_row.add_child(btn_nanite)
	btn_row.add_child(btn_fog)
	btn_row.add_child(btn_stance)
	btn_row.add_child(btn_pause)
	btn_row.add_child(btn_reset)
	vbox.add_child(btn_row)
	
	# Bottom Status row
	var info_row := HBoxContainer.new()
	lbl_selection_info = Label.new()
	lbl_selection_info.text = "Click / Drag-Box to select units • Right-Click to direct squad in formation • Hotkeys: 1-4, F, H, B, A"
	lbl_selection_info.add_theme_font_size_override("font_size", 11)
	lbl_selection_info.add_theme_color_override("font_color", Color(0.65, 0.75, 0.85))
	info_row.add_child(lbl_selection_info)
	vbox.add_child(info_row)


func create_hud_button(text: String, color: Color, callback: Callable) -> Button:
	var btn := Button.new()
	btn.text = text
	btn.add_theme_font_size_override("font_size", 11)
	btn.add_theme_color_override("font_color", color)
	btn.pressed.connect(callback)
	return btn


func spawn_skirmish() -> void:
	for child in units_container.get_children():
		child.queue_free()
	all_units.clear()
	selected_units.clear()
	active_orbital_strikes.clear()
	active_emp_waves.clear()
	active_nanite_clouds.clear()
	active_dash_trails.clear()

	# Spawn Team Blue (Neo-Tokyo & Directorate Alliance) on Left
	for i in range(blue_squad_scenes.size()):
		var sc_path: String = blue_squad_scenes[i]
		if ResourceLoader.exists(sc_path):
			var packed: PackedScene = load(sc_path)
			var u: Node2D = packed.instantiate()
			u.position = Vector2(160 + (i % 2) * 90, 180 + i * 130)
			
			var role := get_unit_role_data(sc_path, "blue")
			u.set_meta("team", "blue")
			u.set_meta("role_title", role.title)
			u.set_meta("max_hp", role.hp)
			u.set_meta("hp", role.hp)
			u.set_meta("max_shield", role.shield)
			u.set_meta("shield", role.shield)
			u.set_meta("shield_regen_delay", 0.0)
			u.set_meta("attack_range", role.range)
			u.set_meta("vision_range", role.vision)
			u.set_meta("cooldown", 0.0)
			u.set_meta("is_stunned", 0.0)
			u.set_meta("order_stance", Stance.AGGRESSIVE)
			u.set_meta("state", "march")
			u.set_meta("move_target", Vector2.ZERO)
			u.set_meta("display_name", u.name.replace("_character", "").replace("_", " ").capitalize())
			
			create_unit_overhead_tag(u, role.title, Color(0.0, 0.9, 1.0))
			units_container.add_child(u)
			all_units.append(u)

	# Spawn Team Red (Abyssal & Rust Syndicate Outcasts) on Right
	for i in range(red_squad_scenes.size()):
		var sc_path: String = red_squad_scenes[i]
		if ResourceLoader.exists(sc_path):
			var packed: PackedScene = load(sc_path)
			var u: Node2D = packed.instantiate()
			u.position = Vector2(ARENA_WIDTH - 200 - (i % 2) * 90, 180 + i * 130)
			u.scale.x = -1.0 # Face left
			
			var role := get_unit_role_data(sc_path, "red")
			u.set_meta("team", "red")
			u.set_meta("role_title", role.title)
			u.set_meta("max_hp", role.hp)
			u.set_meta("hp", role.hp)
			u.set_meta("max_shield", role.shield)
			u.set_meta("shield", role.shield)
			u.set_meta("shield_regen_delay", 0.0)
			u.set_meta("attack_range", role.range)
			u.set_meta("vision_range", role.vision)
			u.set_meta("cooldown", 0.0)
			u.set_meta("is_stunned", 0.0)
			u.set_meta("order_stance", Stance.AGGRESSIVE)
			u.set_meta("state", "march")
			u.set_meta("move_target", Vector2.ZERO)
			u.set_meta("display_name", u.name.replace("_character", "").replace("_", " ").capitalize())
			
			create_unit_overhead_tag(u, role.title, Color(1.0, 0.45, 0.2))
			units_container.add_child(u)
			all_units.append(u)

	update_hud()


func get_unit_role_data(path: String, team: String) -> Dictionary:
	var p := path.to_lower()
	if "striker" in p or "marauder" in p:
		return { "title": "STRIKER", "hp": 150.0, "shield": 60.0, "range": 280.0, "vision": 400.0 }
	elif "sentinel" in p or "berserker" in p:
		return { "title": "SENTINEL", "hp": 220.0, "shield": 100.0, "range": 200.0, "vision": 350.0 }
	elif "ranger" in p or "vulture" in p:
		return { "title": "SNIPER", "hp": 110.0, "shield": 50.0, "range": 440.0, "vision": 540.0 }
	elif "kunoichi" in p or "desperado" in p:
		return { "title": "SPEC-OPS", "hp": 130.0, "shield": 70.0, "range": 260.0, "vision": 420.0 }
	else:
		return { "title": "SOLDIER", "hp": 160.0, "shield": 70.0, "range": 320.0, "vision": 380.0 }


func create_unit_overhead_tag(u: Node2D, role_title: String, col: Color) -> void:
	var lbl := Label.new()
	lbl.name = "OverheadLabel"
	lbl.text = "[%s]" % role_title
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	lbl.position = Vector2(-60, -78)
	lbl.size = Vector2(120, 20)
	lbl.add_theme_font_size_override("font_size", 9)
	lbl.add_theme_color_override("font_color", col)
	lbl.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	lbl.add_theme_constant_override("outline_size", 3)
	u.add_child(lbl)


func _draw() -> void:
	# 1. Base Arena Floor & Boundaries
	draw_rect(Rect2(0, 0, ARENA_WIDTH, ARENA_HEIGHT), Color(0.04, 0.05, 0.08, 1.0), true)
	
	# Neon Cyberpunk Grid
	var grid_step := 64.0
	var grid_color := Color(0.12, 0.16, 0.24, 0.4)
	for x in range(0, int(ARENA_WIDTH), int(grid_step)):
		draw_line(Vector2(x, 0), Vector2(x, ARENA_HEIGHT), grid_color, 1.0)
	for y in range(0, int(ARENA_HEIGHT), int(grid_step)):
		draw_line(Vector2(0, y), Vector2(ARENA_WIDTH, y), grid_color, 1.0)

	# Faction Territory Dividing Line
	draw_line(Vector2(ARENA_WIDTH * 0.5, 0), Vector2(ARENA_WIDTH * 0.5, ARENA_HEIGHT), Color(0.0, 0.8, 1.0, 0.25), 2.0)
	
	# Arena Perimeter Border
	draw_rect(Rect2(0, 0, ARENA_WIDTH, ARENA_HEIGHT), Color(0.0, 0.9, 1.0, 0.8), false, 4.0)

	# Defensive Obstacles
	var barrier_color := Color(0.15, 0.2, 0.3, 0.9)
	var barrier_outline := Color(0.8, 0.5, 0.2, 0.8)
	draw_rect(Rect2(ARENA_WIDTH * 0.35, ARENA_HEIGHT * 0.25, 60, 160), barrier_color, true)
	draw_rect(Rect2(ARENA_WIDTH * 0.35, ARENA_HEIGHT * 0.25, 60, 160), barrier_outline, false, 2.0)
	draw_rect(Rect2(ARENA_WIDTH * 0.60, ARENA_HEIGHT * 0.55, 60, 160), barrier_color, true)
	draw_rect(Rect2(ARENA_WIDTH * 0.60, ARENA_HEIGHT * 0.55, 60, 160), barrier_outline, false, 2.0)

	# 2. Render Active Ability FX (Orbital Strike, EMP Wave, Nanite Cloud, Dash Trails)
	draw_ability_fx()

	# 3. Render Tactical Fog of War Shroud
	if fog_of_war_enabled:
		draw_fog_of_war()

	# 4. Render Unit Overhead Segmented Bars & Selection Rings
	draw_units_overhead_bars()

	# 5. Render Drag-Box Selection Marquee
	if is_dragging_box:
		var rect := get_selection_rect(drag_box_start, drag_box_current)
		draw_rect(rect, Color(0.0, 0.85, 1.0, 0.18), true)
		draw_rect(rect, Color(0.0, 1.0, 1.0, 0.9), false, 1.5)


func draw_ability_fx() -> void:
	# Orbital Laser Strikes
	for strike in active_orbital_strikes:
		var pos: Vector2 = strike.pos
		var progress: float = strike.timer / strike.duration
		var beam_alpha: float = clamp(progress * 1.5, 0.0, 1.0)
		var beam_w: float = 28.0 * (1.0 - progress * 0.3)
		# Outer blue beam
		draw_line(Vector2(pos.x, -50), pos, Color(0.0, 0.7, 1.0, beam_alpha * 0.6), beam_w + 14.0)
		# Inner piercing core
		draw_line(Vector2(pos.x, -50), pos, Color(0.85, 0.95, 1.0, beam_alpha * 0.95), beam_w)
		# Ground impact ring
		var ring_r: float = strike.radius * (1.0 - progress)
		draw_circle(pos, ring_r * 0.4, Color(0.0, 0.9, 1.0, beam_alpha * 0.4))
		draw_arc(pos, ring_r, 0, TAU, 32, Color(0.3, 0.95, 1.0, beam_alpha * 0.9), 3.0)

	# EMP Waves
	for emp in active_emp_waves:
		var pos: Vector2 = emp.pos
		var t: float = 1.0 - (emp.timer / emp.duration)
		var curr_r: float = emp.max_radius * t
		var emp_alpha: float = (1.0 - t) * 0.85
		draw_arc(pos, curr_r, 0, TAU, 48, Color(0.8, 0.3, 1.0, emp_alpha), 3.5)
		draw_arc(pos, curr_r * 0.85, 0, TAU, 36, Color(0.0, 0.85, 1.0, emp_alpha * 0.6), 2.0)

	# Nanite Toxic Clouds
	for cloud in active_nanite_clouds:
		var pos: Vector2 = cloud.pos
		var c_alpha: float = clamp(cloud.timer / cloud.duration, 0.0, 1.0) * 0.35
		draw_circle(pos, cloud.radius, Color(0.2, 0.9, 0.3, c_alpha))
		draw_circle(pos + Vector2(15, -10), cloud.radius * 0.65, Color(0.4, 1.0, 0.2, c_alpha * 0.7))
		draw_arc(pos, cloud.radius, 0, TAU, 32, Color(0.5, 1.0, 0.3, c_alpha * 1.5), 1.5)

	# Dash Afterimages
	for trail in active_dash_trails:
		var pos: Vector2 = trail.pos
		var a: float = (trail.timer / trail.duration) * 0.5
		draw_circle(pos, 22.0, Color(0.0, 0.9, 1.0, a))


func draw_fog_of_war() -> void:
	# Shroud overlay
	var shroud_col := Color(0.02, 0.03, 0.06, 0.82)
	draw_rect(Rect2(0, 0, ARENA_WIDTH, ARENA_HEIGHT), shroud_col, true)
	
	# Clear / illuminate around living allied Blue units
	for u in all_units:
		if is_instance_valid(u) and u.get_meta("team", "") == "blue" and u.get_meta("hp", 0.0) > 0.0:
			var vrange: float = u.get_meta("vision_range", 380.0)
			# Radial soft cutout
			draw_circle(u.position, vrange * 0.95, Color(0.04, 0.06, 0.1, 0.6))
			draw_circle(u.position, vrange * 0.6, Color(0.04, 0.08, 0.14, 0.5))
			draw_arc(u.position, vrange, 0, TAU, 36, Color(0.0, 0.85, 1.0, 0.2), 1.0)


func draw_units_overhead_bars() -> void:
	for u in all_units:
		if not is_instance_valid(u) or u.get_meta("hp", 0.0) <= 0.0:
			continue
		
		# If fog is active, do not draw bars for hidden enemies
		if fog_of_war_enabled and not u.visible:
			continue
		
		var pos := u.position
		var is_selected := selected_units.has(u)
		var team: String = u.get_meta("team", "blue")
		var hp: float = u.get_meta("hp", 0.0)
		var max_hp: float = u.get_meta("max_hp", 150.0)
		var shield: float = u.get_meta("shield", 0.0)
		var max_shield: float = u.get_meta("max_shield", 60.0)
		var is_stunned: float = u.get_meta("is_stunned", 0.0)

		# Ground Selection Ring & Brackets
		if is_selected:
			var ring_col := Color(0.0, 1.0, 0.95, 0.9) if team == "blue" else Color(1.0, 0.45, 0.2, 0.9)
			draw_arc(pos + Vector2(0, 14), 26.0, 0, TAU, 24, ring_col, 2.0)
			# Corner tactical reticle brackets
			var r := 30.0
			draw_line(pos + Vector2(-r, 14 - 6), pos + Vector2(-r, 14 + 6), ring_col, 2.0)
			draw_line(pos + Vector2(r, 14 - 6), pos + Vector2(r, 14 + 6), ring_col, 2.0)
		
		# Overhead Bar Dimensions
		var bar_w := 46.0
		var bar_h := 5.0
		var bar_pos := pos + Vector2(-bar_w * 0.5, -56.0)

		# 1. Health Bar
		# Background
		draw_rect(Rect2(bar_pos.x - 1, bar_pos.y - 1, bar_w + 2, bar_h + 2), Color(0.05, 0.08, 0.12, 0.85), true)
		draw_rect(Rect2(bar_pos.x - 1, bar_pos.y - 1, bar_w + 2, bar_h + 2), Color(0.2, 0.25, 0.35, 0.8), false, 1.0)
		
		# Health Fill
		var hp_pct: float = clamp(hp / max_hp, 0.0, 1.0)
		var hp_col: Color
		if hp_pct < 0.25:
			hp_col = Color(1.0, 0.2, 0.2) # Critical warning red
		elif team == "blue":
			hp_col = Color(0.0, 0.9, 1.0) # Alliance Cyan
		else:
			hp_col = Color(1.0, 0.45, 0.15) # Syndicate Ember
		draw_rect(Rect2(bar_pos.x, bar_pos.y, bar_w * hp_pct, bar_h), hp_col, true)

		# Segment Dividers (Notches every 25% for tactical readability)
		for s in [0.25, 0.5, 0.75]:
			var sx: float = bar_pos.x + bar_w * s
			draw_line(Vector2(sx, bar_pos.y), Vector2(sx, bar_pos.y + bar_h), Color(0.0, 0.0, 0.0, 0.5), 1.0)

		# 2. Energy Shield Bar (Right above Health Bar)
		if max_shield > 0.0:
			var shield_y := bar_pos.y - 5.0
			var shield_h := 3.0
			draw_rect(Rect2(bar_pos.x - 1, shield_y - 1, bar_w + 2, shield_h + 2), Color(0.05, 0.05, 0.1, 0.8), true)
			var sh_pct: float = clamp(shield / max_shield, 0.0, 1.0)
			if sh_pct > 0.0:
				draw_rect(Rect2(bar_pos.x, shield_y, bar_w * sh_pct, shield_h), Color(0.65, 0.4, 1.0), true)

		# 3. EMP Stun Icon / Electrical Spark Indication
		if is_stunned > 0.0:
			draw_arc(pos + Vector2(0, -30), 16.0, 0, TAU, 16, Color(1.0, 0.9, 0.2, 0.9), 2.0)


func _process(delta: float) -> void:
	handle_camera_pan(delta)
	update_abilities(delta)
	queue_redraw()

	if is_paused:
		return

	# Update Fog of War visibility
	update_fog_visibility()

	# Update combat AI & orders for each living unit
	for unit in all_units:
		if not is_instance_valid(unit) or unit.get_meta("hp", 0.0) <= 0.0:
			continue

		# Update Shield Regeneration
		var s_delay: float = unit.get_meta("shield_regen_delay", 0.0) - delta
		unit.set_meta("shield_regen_delay", max(0.0, s_delay))
		if s_delay <= 0.0:
			var cur_s: float = unit.get_meta("shield", 0.0)
			var max_s: float = unit.get_meta("max_shield", 60.0)
			if cur_s < max_s:
				unit.set_meta("shield", min(max_s, cur_s + 14.0 * delta))

		# Update EMP Stun
		var stunned: float = unit.get_meta("is_stunned", 0.0) - delta
		unit.set_meta("is_stunned", max(0.0, stunned))
		if stunned > 0.0:
			continue # Immobilized and disabled while stunned

		# Attack cooldown
		var cd: float = unit.get_meta("cooldown", 0.0) - delta
		unit.set_meta("cooldown", max(0.0, cd))

		var team: String = unit.get_meta("team", "blue")
		var target: Node2D = find_nearest_enemy(unit, team)
		var anim_player: AnimationPlayer = unit.get_node_or_null("AnimationPlayer")
		var stance: Stance = unit.get_meta("order_stance", Stance.AGGRESSIVE)
		var move_target: Vector2 = unit.get_meta("move_target", Vector2.ZERO)

		# Check manual move target order
		if move_target != Vector2.ZERO:
			var d_order: float = unit.position.distance_to(move_target)
			if d_order > 14.0:
				var dir: Vector2 = (move_target - unit.position).normalized()
				unit.position += dir * 115.0 * delta
				unit.scale.x = -abs(unit.scale.x) if dir.x < 0 else abs(unit.scale.x)
				if anim_player and anim_player.has_animation("walk") and anim_player.current_animation != "walk":
					anim_player.play("walk")
				continue
			else:
				unit.set_meta("move_target", Vector2.ZERO)

		# Tactical Stance Handling
		if stance == Stance.RETREAT:
			var retreat_x := 120.0 if team == "blue" else ARENA_WIDTH - 120.0
			var retreat_target := Vector2(retreat_x, unit.position.y)
			if unit.position.distance_to(retreat_target) > 20.0:
				var dir: Vector2 = (retreat_target - unit.position).normalized()
				unit.position += dir * 125.0 * delta
				unit.scale.x = -abs(unit.scale.x) if dir.x < 0 else abs(unit.scale.x)
				if anim_player and anim_player.has_animation("walk") and anim_player.current_animation != "walk":
					anim_player.play("walk")
			continue

		if target != null and is_instance_valid(target):
			var dist: float = unit.position.distance_to(target.position)
			var attack_range: float = unit.get_meta("attack_range", 300.0)

			# Face target
			if target.position.x < unit.position.x:
				unit.scale.x = -abs(unit.scale.x)
			else:
				unit.scale.x = abs(unit.scale.x)

			if dist <= attack_range:
				# Within firing envelope
				if cd <= 0.0:
					perform_attack(unit, target, anim_player)
			elif stance == Stance.AGGRESSIVE:
				# March towards enemy
				var dir: Vector2 = (target.position - unit.position).normalized()
				unit.position += dir * 95.0 * delta
				if anim_player and anim_player.has_animation("walk") and anim_player.current_animation != "walk":
					anim_player.play("walk")
			else:
				# Stance == HOLD: remain stationary
				if anim_player and anim_player.has_animation("idle") and anim_player.current_animation != "idle":
					anim_player.play("idle")
		else:
			if anim_player and anim_player.has_animation("idle") and anim_player.current_animation != "idle":
				anim_player.play("idle")


func update_fog_visibility() -> void:
	if not fog_of_war_enabled:
		for u in all_units:
			if is_instance_valid(u):
				u.visible = true
		return

	# In Fog of War mode:
	# Team Blue is always visible to player
	# Team Red is only visible if within any living Blue unit's vision_range
	for u in all_units:
		if not is_instance_valid(u):
			continue
		if u.get_meta("team", "") == "blue":
			u.visible = true
		else:
			var can_see := false
			for b in all_units:
				if is_instance_valid(b) and b.get_meta("team", "") == "blue" and b.get_meta("hp", 0.0) > 0.0:
					var vrange: float = b.get_meta("vision_range", 380.0)
					if b.position.distance_to(u.position) <= vrange:
						can_see = true
						break
			u.visible = can_see


func update_abilities(delta: float) -> void:
	# 1. Orbital Strikes
	for i in range(active_orbital_strikes.size() - 1, -1, -1):
		var s: Dictionary = active_orbital_strikes[i]
		s.timer -= delta
		if s.timer <= 0.0:
			active_orbital_strikes.remove_at(i)

	# 2. EMP Shockwaves
	for i in range(active_emp_waves.size() - 1, -1, -1):
		var e: Dictionary = active_emp_waves[i]
		e.timer -= delta
		if e.timer <= 0.0:
			active_emp_waves.remove_at(i)

	# 3. Nanite Clouds
	for i in range(active_nanite_clouds.size() - 1, -1, -1):
		var c: Dictionary = active_nanite_clouds[i]
		c.timer -= delta
		c.tick_cooldown -= delta
		if c.tick_cooldown <= 0.0:
			c.tick_cooldown = 0.5
			# Damage enemies caught in cloud
			for u in all_units:
				if is_instance_valid(u) and u.get_meta("team", "") == "red" and u.get_meta("hp", 0.0) > 0.0:
					if u.position.distance_to(c.pos) <= c.radius:
						apply_damage(u, 12.0, false, "☣️ Nanite Corrosive")
		if c.timer <= 0.0:
			active_nanite_clouds.remove_at(i)

	# 4. Dash Trails
	for i in range(active_dash_trails.size() - 1, -1, -1):
		var t: Dictionary = active_dash_trails[i]
		t.timer -= delta
		if t.timer <= 0.0:
			active_dash_trails.remove_at(i)


func find_nearest_enemy(unit: Node2D, my_team: String) -> Node2D:
	var closest: Node2D = null
	var min_dist := 99999.0
	for other in all_units:
		if not is_instance_valid(other):
			continue
		if other.get_meta("team", "") != my_team and other.get_meta("hp", 0.0) > 0.0:
			var d: float = unit.position.distance_to(other.position)
			if d < min_dist:
				min_dist = d
				closest = other
	return closest


func perform_attack(attacker: Node2D, target: Node2D, anim_player: AnimationPlayer) -> void:
	attacker.set_meta("cooldown", 1.35)
	
	if anim_player:
		if anim_player.has_animation("fire_weapon"):
			anim_player.play("fire_weapon")
		elif anim_player.has_animation("hit"):
			anim_player.play("hit")
		elif anim_player.has_animation("punch"):
			anim_player.play("punch")

	var is_crit := randf() < 0.22
	var base_dmg: float = randf_range(22.0, 38.0)
	if is_crit:
		base_dmg *= 1.8

	apply_damage(target, base_dmg, is_crit)


func apply_damage(target: Node2D, raw_damage: float, is_crit: bool = false, label_prefix: String = "") -> void:
	if not is_instance_valid(target) or target.get_meta("hp", 0.0) <= 0.0:
		return

	target.set_meta("shield_regen_delay", 3.5)
	var shield: float = target.get_meta("shield", 0.0)
	var hp: float = target.get_meta("hp", 150.0)
	var final_damage := raw_damage

	# Absorb via Energy Shield first
	var absorbed_by_shield := false
	if shield > 0.0:
		absorbed_by_shield = true
		if shield >= final_damage:
			shield -= final_damage
			final_damage = 0.0
		else:
			final_damage -= shield
			shield = 0.0
			spawn_damage_text(target.position + Vector2(0, -68), "⚡ SHIELD BREAK!", Color(0.8, 0.4, 1.0))
		target.set_meta("shield", shield)

	# Remaining damage to HP
	if final_damage > 0.0:
		hp = max(0.0, hp - final_damage)
		target.set_meta("hp", hp)

	# Floating damage text formatting
	var text := ""
	var col := Color(1.0, 0.35, 0.35)
	if is_crit:
		text = "💥 CRIT -%d!" % int(raw_damage)
		col = Color(1.0, 0.85, 0.1)
	elif absorbed_by_shield and final_damage <= 0.0:
		text = "🛡️ ABSORB -%d" % int(raw_damage)
		col = Color(0.65, 0.4, 1.0)
	else:
		text = "-%d" % int(raw_damage)

	if label_prefix != "":
		text = "%s %s" % [label_prefix, text]

	spawn_damage_text(target.position + Vector2(randf_range(-12, 12), -52), text, col)

	var target_anim: AnimationPlayer = target.get_node_or_null("AnimationPlayer")
	if hp <= 0.0:
		if target_anim and target_anim.has_animation("death"):
			target_anim.play("death")
		spawn_damage_text(target.position + Vector2(0, -84), "ELIMINATED", Color(1.0, 0.25, 0.25))
		update_hud()
	else:
		if target_anim and target_anim.has_animation("get_hit") and randf() < 0.45:
			target_anim.play("get_hit")


func spawn_damage_text(pos: Vector2, text: String, color: Color) -> void:
	var label := Label.new()
	label.text = text
	label.modulate = color
	label.position = pos
	label.add_theme_font_size_override("font_size", 11)
	label.add_theme_color_override("font_outline_color", Color.BLACK)
	label.add_theme_constant_override("outline_size", 3)
	effects_container.add_child(label)
	
	var tween := create_tween()
	tween.tween_property(label, "position:y", pos.y - 42.0, 0.75)
	tween.parallel().tween_property(label, "modulate:a", 0.0, 0.75)
	tween.tween_callback(label.queue_free)


func handle_camera_pan(delta: float) -> void:
	var move := Vector2.ZERO
	if Input.is_action_pressed("ui_right") or Input.is_key_pressed(KEY_D):
		move.x += 1
	if Input.is_action_pressed("ui_left") or Input.is_key_pressed(KEY_A):
		move.x -= 1
	if Input.is_action_pressed("ui_down") or Input.is_key_pressed(KEY_S):
		move.y += 1
	if Input.is_action_pressed("ui_up") or Input.is_key_pressed(KEY_W):
		move.y -= 1
	
	if move != Vector2.ZERO:
		camera.position += move.normalized() * 650.0 * delta


func _unhandled_input(event: InputEvent) -> void:
	# Mouse Drag Box Selection & Single Clicks
	if event is InputEventMouseButton:
		var mouse_pos := get_global_mouse_position()
		if event.button_index == MOUSE_BUTTON_LEFT:
			if event.pressed:
				is_dragging_box = true
				drag_box_start = mouse_pos
				drag_box_current = mouse_pos
			else:
				is_dragging_box = false
				finish_drag_selection(drag_box_start, mouse_pos)
		elif event.button_index == MOUSE_BUTTON_RIGHT and event.pressed:
			# Issue squad command to all selected units
			issue_squad_order(mouse_pos)
		elif event.button_index == MOUSE_BUTTON_WHEEL_UP:
			camera.zoom = (camera.zoom * 1.08).clamp(Vector2(0.5, 0.5), Vector2(2.0, 2.0))
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			camera.zoom = (camera.zoom * 0.92).clamp(Vector2(0.5, 0.5), Vector2(2.0, 2.0))

	elif event is InputEventMouseMotion and is_dragging_box:
		drag_box_current = get_global_mouse_position()

	# Keyboard Hotkeys
	if event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_SPACE:
				_on_pause_toggled()
			KEY_R:
				spawn_skirmish()
			KEY_F:
				_on_fog_toggled()
			KEY_H:
				set_squad_stance(Stance.HOLD)
			KEY_B:
				set_squad_stance(Stance.RETREAT)
			KEY_A:
				set_squad_stance(Stance.AGGRESSIVE)
			KEY_1:
				_on_orbital_clicked()
			KEY_2:
				_on_dash_clicked()
			KEY_3:
				_on_emp_clicked()
			KEY_4:
				_on_nanite_clicked()


func finish_drag_selection(start_pos: Vector2, end_pos: Vector2) -> void:
	var dist := start_pos.distance_to(end_pos)
	if dist > 8.0:
		# Box selection
		selected_units.clear()
		var rect := get_selection_rect(start_pos, end_pos)
		for u in all_units:
			if is_instance_valid(u) and u.get_meta("team", "") == "blue" and u.get_meta("hp", 0.0) > 0.0:
				if rect.has_point(u.position):
					selected_units.append(u)
	else:
		# Single click selection
		selected_units.clear()
		for u in all_units:
			if is_instance_valid(u) and u.position.distance_to(end_pos) < 45.0:
				selected_units.append(u)
				break

	update_hud()


func get_selection_rect(p1: Vector2, p2: Vector2) -> Rect2:
	var top_left := Vector2(min(p1.x, p2.x), min(p1.y, p2.y))
	var size := Vector2(abs(p1.x - p2.x), abs(p1.y - p2.y))
	return Rect2(top_left, size)


func issue_squad_order(dest_pos: Vector2) -> void:
	if selected_units.is_empty():
		return

	# Calculate squad formation offsets so units do not collapse into a single point
	var count := selected_units.size()
	var cols := int(ceil(sqrt(count)))
	var spacing := 55.0

	for i in range(count):
		var u: Node2D = selected_units[i]
		if not is_instance_valid(u):
			continue
		
		var row: int = i / cols
		var col: int = i % cols
		var offset := Vector2((col - cols * 0.5) * spacing, (row - cols * 0.5) * spacing)
		u.set_meta("move_target", dest_pos + offset)
		u.set_meta("cooldown", 0.2)

	spawn_damage_text(dest_pos, "ORDER: ADVANCE", Color(0.0, 0.9, 1.0))


# =============================================================================
# Tactical Abilities Implementation
# =============================================================================

func _on_orbital_clicked() -> void:
	var target_pos := get_global_mouse_position()
	active_orbital_strikes.append({
		"pos": target_pos,
		"radius": 130.0,
		"timer": 0.65,
		"duration": 0.65
	})
	
	# Blast damage to enemies
	for u in all_units:
		if is_instance_valid(u) and u.get_meta("team", "") == "red" and u.get_meta("hp", 0.0) > 0.0:
			if u.position.distance_to(target_pos) <= 130.0:
				apply_damage(u, 75.0, true, "🛰️ ORBITAL")
	
	spawn_damage_text(target_pos, "ORBITAL STRIKE INCOMING!", Color(0.0, 0.95, 1.0))


func _on_dash_clicked() -> void:
	if selected_units.is_empty():
		for u in all_units:
			if is_instance_valid(u) and u.get_meta("team", "") == "blue" and u.get_meta("hp", 0.0) > 0.0:
				selected_units.append(u)
				break

	for u in selected_units:
		if not is_instance_valid(u):
			continue
		var forward := Vector2(u.scale.x, 0).normalized() * 180.0
		var orig_pos := u.position
		u.position += forward
		active_dash_trails.append({
			"pos": orig_pos,
			"timer": 0.4,
			"duration": 0.4
		})
		var anim: AnimationPlayer = u.get_node_or_null("AnimationPlayer")
		if anim and anim.has_animation("special_01"):
			anim.play("special_01")
		spawn_damage_text(u.position + Vector2(0, -60), "TACHYON DASH!", Color(0.4, 0.8, 1.0))


func _on_emp_clicked() -> void:
	var center := get_global_mouse_position()
	if not selected_units.is_empty() and is_instance_valid(selected_units[0]):
		center = selected_units[0].position

	active_emp_waves.append({
		"pos": center,
		"max_radius": 240.0,
		"timer": 0.6,
		"duration": 0.6
	})

	# Stun enemies within shockwave
	for u in all_units:
		if is_instance_valid(u) and u.get_meta("team", "") == "red" and u.get_meta("hp", 0.0) > 0.0:
			if u.position.distance_to(center) <= 240.0:
				u.set_meta("is_stunned", 2.2)
				u.set_meta("shield", max(0.0, u.get_meta("shield", 0.0) - 45.0))
				spawn_damage_text(u.position + Vector2(0, -65), "⚡ EMP STUNNED!", Color(0.8, 0.4, 1.0))


func _on_nanite_clicked() -> void:
	var center := get_global_mouse_position()
	active_nanite_clouds.append({
		"pos": center,
		"radius": 110.0,
		"timer": 4.5,
		"duration": 4.5,
		"tick_cooldown": 0.2
	})
	spawn_damage_text(center, "☣️ NANITE CLOUD DEPLOYED", Color(0.3, 1.0, 0.4))


func _on_fog_toggled() -> void:
	fog_of_war_enabled = !fog_of_war_enabled
	if btn_fog:
		btn_fog.text = "👁️ Fog: %s [F]" % ("ON" if fog_of_war_enabled else "OFF")
		btn_fog.add_theme_color_override("font_color", Color(0.0, 1.0, 0.8) if fog_of_war_enabled else Color(0.7, 0.8, 0.9))
	update_fog_visibility()
	queue_redraw()


func _on_pause_toggled() -> void:
	is_paused = !is_paused
	if btn_pause:
		btn_pause.text = "▶️ Resume [Space]" if is_paused else "⏸️ Pause [Space]"
	update_hud()


func _on_stance_toggled() -> void:
	if current_stance == Stance.AGGRESSIVE:
		set_squad_stance(Stance.HOLD)
	elif current_stance == Stance.HOLD:
		set_squad_stance(Stance.RETREAT)
	else:
		set_squad_stance(Stance.AGGRESSIVE)


func set_squad_stance(stance: Stance) -> void:
	current_stance = stance
	var stance_name := "Assault"
	var stance_col := Color(0.3, 0.9, 1.0)
	if stance == Stance.HOLD:
		stance_name = "Hold Position"
		stance_col = Color(1.0, 0.8, 0.2)
	elif stance == Stance.RETREAT:
		stance_name = "Fall Back"
		stance_col = Color(1.0, 0.4, 0.3)

	if btn_stance:
		btn_stance.text = "🛡️ Stance: %s [H]" % stance_name
		btn_stance.add_theme_color_override("font_color", stance_col)

	var targets := selected_units if not selected_units.is_empty() else all_units
	for u in targets:
		if is_instance_valid(u) and u.get_meta("team", "") == "blue":
			u.set_meta("order_stance", stance)

	if lbl_selection_info:
		lbl_selection_info.text = "Squad stance set to: %s" % stance_name.to_upper()


func update_hud() -> void:
	var blue_alive := 0
	var red_alive := 0
	for u in all_units:
		if is_instance_valid(u) and u.get_meta("hp", 0.0) > 0.0:
			if u.get_meta("team", "") == "blue":
				blue_alive += 1
			else:
				red_alive += 1

	if lbl_squad_counts:
		lbl_squad_counts.text = "🔵 Blue Alliance: %d  |  🔴 Red Syndicate: %d" % [blue_alive, red_alive]

	if lbl_selection_info:
		if selected_units.size() == 1 and is_instance_valid(selected_units[0]):
			var u: Node2D = selected_units[0]
			var dname: String = u.get_meta("display_name", "Unit")
			var rtitle: String = u.get_meta("role_title", "TROOPER")
			var hp: float = u.get_meta("hp", 0.0)
			var mhp: float = u.get_meta("max_hp", 150.0)
			var sh: float = u.get_meta("shield", 0.0)
			var msh: float = u.get_meta("max_shield", 60.0)
			lbl_selection_info.text = "SELECTED: [%s] %s  |  HP: %d/%d  •  SHIELD: %d/%d  |  Hotkeys: 1-4 Abilities" % [
				rtitle, dname, int(hp), int(mhp), int(sh), int(msh)
			]
		elif selected_units.size() > 1:
			lbl_selection_info.text = "SQUAD SELECTED: %d Units  |  Right-click to command formation move/attack" % selected_units.size()
		else:
			lbl_selection_info.text = "Drag-box / click to select units • Right-click to direct squad • 1-4: Abilities • F: Fog of War"
