@tool
extends EditorPlugin

## =============================================================================
## plugin.gd - Godot 2D Auto Spriter & Rigger Plugin Entry Point
## =============================================================================

const DOCK_SCENE := preload("res://addons/godot_2d_auto_spriter/dock.tscn")
var dock_instance: Control = null


func _enter_tree() -> void:
	dock_instance = DOCK_SCENE.instantiate()
	if dock_instance.has_method("set_plugin"):
		dock_instance.set_plugin(self)

	add_control_to_dock(EditorPlugin.DOCK_SLOT_RIGHT_UL, dock_instance)
	print("[Godot2dAutoSpriter] Plugin initialized. Auto Spriter dock added to right panel.")


func _exit_tree() -> void:
	if dock_instance:
		remove_control_from_docks(dock_instance)
		dock_instance.free()
		dock_instance = null
	print("[Godot2dAutoSpriter] Plugin uninstalled.")
