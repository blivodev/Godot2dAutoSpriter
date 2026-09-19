@tool
extends SceneTree

## =============================================================================
## headless_rig_builder.gd
##
## CLI entry point called by the MCP server or automation scripts to assemble
## a complete rigged character scene in Godot 4 without GUI interaction.
##
## Usage:
##   godot --headless --script scripts/headless_rig_builder.gd -- \
##         --character-name <name> \
##         --assets-dir <path> \
##         --target-scene <path>
## =============================================================================

const AutoRigImporter = preload("res://auto_rig_importer.gd")

func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var character_name := ""
	var assets_dir := ""
	var target_scene := ""
	var rig_type := "biped"
	var custom_template := ""

	var i := 0
	while i < args.size():
		var arg := args[i]
		if arg == "--character-name" and i + 1 < args.size():
			character_name = args[i + 1]
			i += 2
		elif arg == "--assets-dir" and i + 1 < args.size():
			assets_dir = args[i + 1]
			i += 2
		elif arg == "--target-scene" and i + 1 < args.size():
			target_scene = args[i + 1]
			i += 2
		elif arg == "--rig-type" and i + 1 < args.size():
			rig_type = args[i + 1].to_lower()
			i += 2
		elif arg == "--template" and i + 1 < args.size():
			custom_template = args[i + 1]
			i += 2
		else:
			i += 1

	if character_name.is_empty():
		character_name = "warrior"
	if assets_dir.is_empty():
		assets_dir = "res://sprites/" + character_name
	if target_scene.is_empty():
		target_scene = "res://scenes/" + character_name + "_character.tscn"

	var template_path := custom_template
	if template_path.is_empty():
		if rig_type == "quadruped":
			template_path = "res://scenes/quadruped_rig_template.tscn"
		else:
			template_path = "res://scenes/character_rig_template.tscn"

	print(JSON.stringify({
		"status": "starting",
		"character_name": character_name,
		"assets_dir": assets_dir,
		"target_scene": target_scene,
		"rig_type": rig_type,
		"template": template_path
	}))

	var success := _build_rig(character_name, assets_dir, target_scene, template_path)
	if success:
		print(JSON.stringify({
			"status": "success",
			"target_scene": target_scene,
			"character_name": character_name
		}))
		quit(0)
	else:
		print(JSON.stringify({
			"status": "error",
			"message": "Failed to build rigged character scene"
		}))
		quit(1)


func _build_rig(char_name: String, dir_path: String, out_scene_path: String, template_path: String = "res://scenes/character_rig_template.tscn") -> bool:
	var scene_res := load(template_path) as PackedScene
	if not scene_res:
		push_error("Could not load template: %s" % template_path)
		return false

	var root_node := scene_res.instantiate()
	if not root_node:
		push_error("Failed to instantiate template scene")
		return false

	root.add_child(root_node)

	var skeleton := root_node.get_node_or_null("Skeleton2D") as AutoRigImporter
	if not skeleton:
		push_error("Could not find Skeleton2D node with AutoRigImporter")
		root_node.queue_free()
		return false

	skeleton.character_sprites_dir = dir_path
	skeleton.character_prefix = char_name
	skeleton.reset_sprite_offsets = false

	var rig_res := skeleton.execute_auto_rig(true)
	if not rig_res.get("success", false):
		push_error("Auto-rig execution returned failure: %s" % str(rig_res))
		root_node.queue_free()
		return false

	# Set recursive ownership for proper scene packing
	root_node.name = char_name.capitalize() + "Root"
	_set_owner_recursive(root_node, root_node)

	# Ensure parent directory exists
	var global_out_dir := ProjectSettings.globalize_path(out_scene_path.get_base_dir())
	DirAccess.make_dir_recursive_absolute(global_out_dir)

	var packed := PackedScene.new()
	var pack_err := packed.pack(root_node)
	if pack_err != OK:
		push_error("PackedScene.pack failed with code: %d" % pack_err)
		root_node.queue_free()
		return false

	var save_err := ResourceSaver.save(packed, out_scene_path)
	if save_err != OK:
		push_error("ResourceSaver.save failed with code: %d" % save_err)
		root_node.queue_free()
		return false

	root_node.queue_free()
	return true


func _set_owner_recursive(node: Node, scene_root: Node) -> void:
	for child in node.get_children():
		child.owner = scene_root
		_set_owner_recursive(child, scene_root)
