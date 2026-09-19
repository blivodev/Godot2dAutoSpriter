@tool
extends EditorPlugin

## =============================================================================
## plugin.gd - Godot 2D Auto Spriter & Rigger Plugin Entry Point
##
## Initializes the Editor Dock and automatically opens scenes in the 2D viewport
## when requested via Web UI, CLI, or open_scene_request.txt.
## =============================================================================

const DOCK_SCENE := preload("res://addons/godot_2d_auto_spriter/dock.tscn")
var dock_instance: Control = null


func _enter_tree() -> void:
	dock_instance = DOCK_SCENE.instantiate()
	if dock_instance.has_method("set_plugin"):
		dock_instance.set_plugin(self)

	add_control_to_dock(EditorPlugin.DOCK_SLOT_RIGHT_UL, dock_instance)
	print("[Godot2dAutoSpriter] Plugin initialized. Auto Spriter dock added to right panel.")
	call_deferred("_handle_open_scene_request")


func _exit_tree() -> void:
	if dock_instance:
		remove_control_from_docks(dock_instance)
		dock_instance.free()
		dock_instance = null
	print("[Godot2dAutoSpriter] Plugin uninstalled.")


func _handle_open_scene_request() -> void:
	var scene_to_open := ""

	# 1. Check command line user args (-- --open-scene <path>)
	var user_args := OS.get_cmdline_user_args()
	for i in range(user_args.size()):
		if user_args[i] == "--open-scene" and i + 1 < user_args.size():
			scene_to_open = user_args[i + 1]
			break

	# 2. Check open scene request file (.godot/open_scene_request.txt)
	if scene_to_open.is_empty():
		var req_file := "res://.godot/open_scene_request.txt"
		if FileAccess.file_exists(req_file):
			var f := FileAccess.open(req_file, FileAccess.READ)
			if f:
				scene_to_open = f.get_as_text().strip_edges()
				f.close()
			DirAccess.remove_absolute(ProjectSettings.globalize_path(req_file))

	# 3. Check root fallback request file
	if scene_to_open.is_empty():
		var root_req := "res://open_scene_request.txt"
		if FileAccess.file_exists(root_req):
			var f2 := FileAccess.open(root_req, FileAccess.READ)
			if f2:
				scene_to_open = f2.get_as_text().strip_edges()
				f2.close()
			DirAccess.remove_absolute(ProjectSettings.globalize_path(root_req))

	if scene_to_open.is_empty():
		return

	if not scene_to_open.begins_with("res://"):
		scene_to_open = "res://" + scene_to_open.trim_prefix("/").trim_prefix("\\")

	if ResourceLoader.exists(scene_to_open):
		print("[Godot2dAutoSpriter] Auto-opening scene in 2D viewport: ", scene_to_open)
		var iface := get_editor_interface()
		if iface:
			iface.open_scene_from_path(scene_to_open)
			iface.set_main_screen_editor("2D")

		if dock_instance and dock_instance.has_method("populate_from_scene"):
			dock_instance.populate_from_scene(scene_to_open)
