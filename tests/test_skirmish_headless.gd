extends SceneTree

func _init() -> void:
	call_deferred("_run_test")

func _run_test() -> void:
	print("--- Running RTS Skirmish Headless Test ---")
	var scene: PackedScene = load("res://scenes/rts_battle_demo.tscn")
	if not scene:
		printerr("FAILED to load res://scenes/rts_battle_demo.tscn")
		quit(1)
		return

	var demo = scene.instantiate()
	root.add_child(demo)

	await process_frame
	await process_frame

	print("Units spawned count: ", demo.all_units.size())
	if demo.all_units.size() < 10:
		printerr("ERROR: Expected at least 10 units spawned, got ", demo.all_units.size())
		quit(1)
		return

	# Test Fog of War toggle
	demo._on_fog_toggled()
	print("Fog of war toggled: ", demo.fog_of_war_enabled)

	# Test Abilities
	demo._on_orbital_clicked()
	demo._on_dash_clicked()
	demo._on_emp_clicked()
	demo._on_nanite_clicked()
	demo._process(0.05)

	print("Ability effects active: orbital=%d, emp=%d, nanite=%d, dash=%d" % [
		demo.active_orbital_strikes.size(),
		demo.active_emp_waves.size(),
		demo.active_nanite_clouds.size(),
		demo.active_dash_trails.size()
	])

	# Test Stance toggling
	demo._on_stance_toggled()
	demo._process(0.016)

	print("--- RTS Skirmish Headless Test PASSED cleanly! ---")
	quit(0)
