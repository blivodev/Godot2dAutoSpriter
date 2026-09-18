@tool
extends SceneTree

const AutoRigImporter = preload("res://auto_rig_importer.gd")

func _init() -> void:
	var scene_res = load("res://scenes/character_rig_template.tscn")
	var root_node = scene_res.instantiate()
	root.add_child(root_node)

	var skeleton = root_node.get_node("Skeleton2D") as AutoRigImporter
	skeleton.character_sprites_dir = "res://sprites/warrior"
	skeleton.character_prefix = "warrior"
	var res = skeleton.execute_auto_rig(true)
	print("Auto-rig result:", res)

	# Set owners for all recursive children so PackedScene packs the whole tree
	_set_owner_recursive(root_node, root_node)

	var packed := PackedScene.new()
	var err := packed.pack(root_node)
	if err == OK:
		ResourceSaver.save(packed, "res://scenes/warrior_rigged.tscn")
		print("Saved fully rigged warrior scene to res://scenes/warrior_rigged.tscn")
	else:
		push_error("Failed to pack scene: %d" % err)

	quit(0)

func _set_owner_recursive(node: Node, scene_root: Node) -> void:
	for child in node.get_children():
		child.owner = scene_root
		_set_owner_recursive(child, scene_root)
