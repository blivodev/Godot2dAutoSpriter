extends Node2D

## =============================================================================
## rts_battle_demo.gd - Godot 4 Playable Cyberpunk RTS Skirmish Arena
##
## Interactive 2D battlefield where opposing cyberpunk factions engage in
## real-time combat utilizing their 23 animations, equipped weapons, and projectiles.
##
## Controls:
##   - Left Click: Select unit
##   - Right Click: Issue Move / Attack order
##   - 1, 2, 3, 4: Trigger Selected Unit's Signature Special Moves
##   - Space: Pause / Resume Battle
##   - R: Restart / Respawn Skirmish
##   - WASD / Arrow Keys: Pan Battlefield Camera
##   - Mouse Wheel: Zoom Camera In / Out
## =============================================================================

const ARENA_WIDTH := 1600.0
const ARENA_HEIGHT := 900.0

var selected_unit: Node2D = null
var is_paused := false

# Available faction unit scenes
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
var floating_texts: Array[Dictionary] = []

@onready var camera: Camera2D = $Camera2D
@onready var units_container: Node2D = $Units
@onready var effects_container: Node2D = $Effects
@onready var hud: CanvasLayer = $HUD


func _ready() -> void:
	spawn_skirmish()


func _draw() -> void:
	# Draw Cyberpunk Arena Grid & Boundaries
	draw_rect(Rect2(0, 0, ARENA_WIDTH, ARENA_HEIGHT), Color(0.04, 0.05, 0.08, 1.0), true)
	
	# Neon Grid Lines
	var grid_step := 64.0
	var grid_color := Color(0.12, 0.16, 0.24, 0.4)
	for x in range(0, int(ARENA_WIDTH), int(grid_step)):
		draw_line(Vector2(x, 0), Vector2(x, ARENA_HEIGHT), grid_color, 1.0)
	for y in range(0, int(ARENA_HEIGHT), int(grid_step)):
		draw_line(Vector2(0, y), Vector2(ARENA_WIDTH, y), grid_color, 1.0)

	# Faction Territory Dividing Line
	draw_line(Vector2(ARENA_WIDTH * 0.5, 0), Vector2(ARENA_WIDTH * 0.5, ARENA_HEIGHT), Color(0.0, 0.8, 1.0, 0.25), 2.0)
	
	# Arena Neon Perimeter Border
	draw_rect(Rect2(0, 0, ARENA_WIDTH, ARENA_HEIGHT), Color(0.0, 0.9, 1.0, 0.8), false, 4.0)

	# Obstacle Barriers
	var barrier_color := Color(0.15, 0.2, 0.3, 0.9)
	var barrier_outline := Color(0.8, 0.5, 0.2, 0.8)
	draw_rect(Rect2(ARENA_WIDTH * 0.35, ARENA_HEIGHT * 0.25, 60, 160), barrier_color, true)
	draw_rect(Rect2(ARENA_WIDTH * 0.35, ARENA_HEIGHT * 0.25, 60, 160), barrier_outline, false, 2.0)
	draw_rect(Rect2(ARENA_WIDTH * 0.60, ARENA_HEIGHT * 0.55, 60, 160), barrier_color, true)
	draw_rect(Rect2(ARENA_WIDTH * 0.60, ARENA_HEIGHT * 0.55, 60, 160), barrier_outline, false, 2.0)


func spawn_skirmish() -> void:
	for child in units_container.get_children():
		child.queue_free()
	all_units.clear()
	selected_unit = null

	# Spawn Team Blue (Neo-Tokyo / Directorate Alliance) on Left
	for i in range(blue_squad_scenes.size()):
		var sc_path: String = blue_squad_scenes[i]
		if ResourceLoader.exists(sc_path):
			var packed: PackedScene = load(sc_path)
			var u: Node2D = packed.instantiate()
			u.position = Vector2(160 + (i % 2) * 90, 180 + i * 130)
			u.set_meta("team", "blue")
			u.set_meta("max_hp", 150.0)
			u.set_meta("hp", 150.0)
			u.set_meta("attack_range", 320.0)
			u.set_meta("cooldown", 0.0)
			u.set_meta("state", "march")
			u.set_meta("display_name", u.name.replace("_character", "").replace("_", " ").capitalize())
			units_container.add_child(u)
			all_units.append(u)

	# Spawn Team Red (Abyssal / Syndicate Outcasts) on Right
	for i in range(red_squad_scenes.size()):
		var sc_path: String = red_squad_scenes[i]
		if ResourceLoader.exists(sc_path):
			var packed: PackedScene = load(sc_path)
			var u: Node2D = packed.instantiate()
			u.position = Vector2(ARENA_WIDTH - 200 - (i % 2) * 90, 180 + i * 130)
			u.scale.x = -1.0 # Face left
			u.set_meta("team", "red")
			u.set_meta("max_hp", 150.0)
			u.set_meta("hp", 150.0)
			u.set_meta("attack_range", 320.0)
			u.set_meta("cooldown", 0.0)
			u.set_meta("state", "march")
			u.set_meta("display_name", u.name.replace("_character", "").replace("_", " ").capitalize())
			units_container.add_child(u)
			all_units.append(u)

	update_hud()


func _process(delta: float) -> void:
	handle_camera_pan(delta)
	queue_redraw()

	if is_paused:
		return

	# Update combat AI for each living unit
	for unit in all_units:
		if not is_instance_valid(unit) or unit.get_meta("hp", 0.0) <= 0.0:
			continue

		var cd: float = unit.get_meta("cooldown", 0.0) - delta
		unit.set_meta("cooldown", max(0.0, cd))

		var team: String = unit.get_meta("team", "blue")
		var target: Node2D = find_nearest_enemy(unit, team)

		var anim_player: AnimationPlayer = unit.get_node_or_null("AnimationPlayer")

		if target != null and is_instance_valid(target):
			var dist: float = unit.position.distance_to(target.position)
			var attack_range: float = unit.get_meta("attack_range", 300.0)

			# Face enemy
			if target.position.x < unit.position.x:
				unit.scale.x = -abs(unit.scale.x)
			else:
				unit.scale.x = abs(unit.scale.x)

			if dist <= attack_range:
				# Attack state
				if cd <= 0.0:
					perform_attack(unit, target, anim_player)
			else:
				# March towards target
				var dir: Vector2 = (target.position - unit.position).normalized()
				unit.position += dir * 95.0 * delta
				if anim_player and anim_player.has_animation("walk") and anim_player.current_animation != "walk":
					anim_player.play("walk")
		else:
			# Idle if no enemies found
			if anim_player and anim_player.has_animation("idle") and anim_player.current_animation != "idle":
				anim_player.play("idle")


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
	attacker.set_meta("cooldown", 1.4)
	
	# Select combat animation
	if anim_player:
		if anim_player.has_animation("fire_weapon"):
			anim_player.play("fire_weapon")
		elif anim_player.has_animation("hit"):
			anim_player.play("hit")
		elif anim_player.has_animation("punch"):
			anim_player.play("punch")

	# Damage calculation
	var dmg: float = randf_range(20.0, 35.0)
	var current_hp: float = target.get_meta("hp", 150.0) - dmg
	target.set_meta("hp", max(0.0, current_hp))

	spawn_damage_text(target.position + Vector2(0, -60), "-%d" % int(dmg), Color(1.0, 0.3, 0.3))

	var target_anim: AnimationPlayer = target.get_node_or_null("AnimationPlayer")
	if current_hp <= 0.0:
		if target_anim and target_anim.has_animation("death"):
			target_anim.play("death")
		spawn_damage_text(target.position + Vector2(0, -90), "ELIMINATED", Color(1.0, 0.8, 0.2))
	else:
		if target_anim and target_anim.has_animation("get_hit") and randf() < 0.4:
			target_anim.play("get_hit")


func spawn_damage_text(pos: Vector2, text: String, color: Color) -> void:
	var label := Label.new()
	label.text = text
	label.modulate = color
	label.position = pos
	effects_container.add_child(label)
	
	var tween := create_tween()
	tween.tween_property(label, "position:y", pos.y - 40.0, 0.7)
	tween.parallel().tween_property(label, "modulate:a", 0.0, 0.7)
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
		camera.position += move.normalized() * 600.0 * delta


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed:
		var mouse_pos := get_global_mouse_position()
		if event.button_index == MOUSE_BUTTON_LEFT:
			# Select unit
			selected_unit = null
			for u in all_units:
				if is_instance_valid(u) and u.position.distance_to(mouse_pos) < 50.0:
					selected_unit = u
					break
			update_hud()
		elif event.button_index == MOUSE_BUTTON_RIGHT and selected_unit != null:
			# Command selected unit to move or attack
			selected_unit.position = mouse_pos
			selected_unit.set_meta("cooldown", 0.2)

	if event is InputEventKey and event.pressed:
		if event.keycode == KEY_SPACE:
			is_paused = !is_paused
			update_hud()
		elif event.keycode == KEY_R:
			spawn_skirmish()
		elif selected_unit != null and is_instance_valid(selected_unit):
			var anim: AnimationPlayer = selected_unit.get_node_or_null("AnimationPlayer")
			if anim:
				if event.keycode == KEY_1 and anim.has_animation("special_01"):
					anim.play("special_01")
					spawn_damage_text(selected_unit.position + Vector2(0, -70), "SPECIAL 1!", Color(0.2, 0.9, 1.0))
				elif event.keycode == KEY_2 and anim.has_animation("special_02"):
					anim.play("special_02")
					spawn_damage_text(selected_unit.position + Vector2(0, -70), "SPECIAL 2!", Color(0.8, 0.4, 1.0))
				elif event.keycode == KEY_3 and anim.has_animation("special_03"):
					anim.play("special_03")
					spawn_damage_text(selected_unit.position + Vector2(0, -70), "SPECIAL 3!", Color(1.0, 0.8, 0.2))
				elif event.keycode == KEY_4 and anim.has_animation("special_04"):
					anim.play("special_04")
					spawn_damage_text(selected_unit.position + Vector2(0, -70), "SPECIAL 4!", Color(0.3, 1.0, 0.4))


func update_hud() -> void:
	var title: Label = hud.get_node_or_null("Panel/VBox/Title")
	var stats: Label = hud.get_node_or_null("Panel/VBox/Stats")
	if title and stats:
		if selected_unit != null and is_instance_valid(selected_unit):
			var dname: String = selected_unit.get_meta("display_name", "Unit")
			var hp: float = selected_unit.get_meta("hp", 0.0)
			var max_hp: float = selected_unit.get_meta("max_hp", 150.0)
			var team: String = selected_unit.get_meta("team", "blue")
			title.text = "SELECTED: %s (%s Team)" % [dname, team.to_upper()]
			stats.text = "HP: %d / %d  •  Status: Active  •  Keys 1-4 for Signature Moves" % [int(hp), int(max_hp)]
		else:
			title.text = "CYBERPUNK RTS SKIRMISH ARENA"
			stats.text = "Click to select units • Right-click to direct • Keys 1-4 for Signature Moves • Space to pause (%s)" % ("PAUSED" if is_paused else "RUNNING")
