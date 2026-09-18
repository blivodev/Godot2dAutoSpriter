@tool
extends SceneTree

const AutoRigImporter = preload("res://auto_rig_importer.gd")

const BONE_NAMES = [
	"pelvis",
	"torso",
	"head",
	"arm_upper_L",
	"arm_lower_L",
	"hand_L",
	"arm_upper_R",
	"arm_lower_R",
	"hand_R",
	"leg_upper_L",
	"leg_lower_L",
	"foot_L",
	"leg_upper_R",
	"leg_lower_R",
	"foot_R"
]

const SPRITE_DIR = "res://sprites/warrior"

func _init() -> void:
	print("\n==========================================")
	print("Starting Godot 4 AutoRigImporter Test Suite")
	print("==========================================")

	var success := _run_tests()
	if success:
		print("\n[ALL TESTS PASSED SUCCESSFULLY!]")
		quit(0)
	else:
		push_error("\n[TESTS FAILED!]")
		quit(1)


func _run_tests() -> bool:
	# Step 1: Create fixture sprite files
	if not _generate_fixture_sprites():
		push_error("Failed to generate fixture sprites")
		return false

	# Step 2: Test Scene loading & Rigging
	var scene_res = load("res://scenes/character_rig_template.tscn")
	if not scene_res:
		push_error("Could not load character_rig_template.tscn")
		return false

	var root_node = scene_res.instantiate()
	if not root_node:
		push_error("Could not instantiate character rig template scene")
		return false

	root.add_child(root_node)

	var skeleton = root_node.get_node_or_null("Skeleton2D") as Skeleton2D
	if not skeleton:
		push_error("Could not find Skeleton2D in scene")
		return false

	var importer: AutoRigImporter = skeleton as AutoRigImporter
	if not importer:
		push_error("Skeleton2D is not an instance of AutoRigImporter")
		return false

	# Configure importer
	importer.character_sprites_dir = SPRITE_DIR
	importer.character_prefix = "warrior"
	importer.reset_sprite_offsets = true

	# Execute Auto-Rigging with force_run=true (headless mode)
	var res = importer.execute_auto_rig(true)
	print("Auto-rig result:", res)

	if not res.get("success", false):
		push_error("Auto-rig returned failure: %s" % res.get("reason", "Unknown"))
		return false

	if res.get("matched", 0) != BONE_NAMES.size():
		push_error("Expected %d matched bones, got %d" % [BONE_NAMES.size(), res.get("matched", 0)])
		return false

	# Verify each bone has its texture assigned
	for bone_name in BONE_NAMES:
		var bone := _find_bone_recursive(skeleton, bone_name)
		if not bone:
			push_error("Bone node not found in hierarchy: %s" % bone_name)
			return false

		var sprite := bone.get_node_or_null("Sprite2D") as Sprite2D
		if not sprite:
			push_error("Sprite2D not found under bone: %s" % bone_name)
			return false

		if not sprite.texture:
			push_error("Sprite2D under bone '%s' has null texture!" % bone_name)
			return false

		print("  Assertion OK: Bone '%s' has valid texture (%dx%d)" % [
			bone_name,
			sprite.texture.get_width(),
			sprite.texture.get_height()
		])

	# Step 3: Test dynamic prefix inference (blank character_prefix)
	importer.character_prefix = ""
	var res2 = importer.execute_auto_rig(true)
	if res2.get("matched", 0) != BONE_NAMES.size():
		push_error("Dynamic prefix inference failed! Expected %d matched, got %d" % [BONE_NAMES.size(), res2.get("matched", 0)])
		return false

	print("  Assertion OK: Dynamic prefix inference matched all %d bones without explicit prefix setting." % res2.get("matched", 0))

	# Step 4: Test Quadruped Template & Rigging
	print("\n--- Testing Quadruped Rigging Template ---")
	var quad_scene = load("res://scenes/quadruped_rig_template.tscn")
	if not quad_scene:
		push_error("Could not load quadruped_rig_template.tscn")
		return false

	var quad_root = quad_scene.instantiate()
	root.add_child(quad_root)

	var quad_skeleton = quad_root.get_node_or_null("Skeleton2D") as AutoRigImporter
	if not quad_skeleton:
		push_error("Could not find Skeleton2D AutoRigImporter in quadruped template")
		return false

	quad_skeleton.character_sprites_dir = "res://sprites/fenrir"
	quad_skeleton.character_prefix = "fenrir"
	quad_skeleton.reset_sprite_offsets = true

	var quad_res = quad_skeleton.execute_auto_rig(true)
	if not quad_res.get("success", false) or quad_res.get("matched", 0) != 20:
		push_error("Quadruped auto-rig failed! Result: %s" % str(quad_res))
		return false

	print("  Assertion OK: Quadruped rig matched all 20 bones with fenrir sprites.")
	quad_root.queue_free()
	root_node.queue_free()

	return true


func _generate_fixture_sprites() -> bool:
	DirAccess.make_dir_recursive_absolute(SPRITE_DIR)

	for bone_name in BONE_NAMES:
		var file_path = SPRITE_DIR.path_join("warrior_%s.png" % bone_name)
		# Preserve existing detailed sprites if already generated
		if FileAccess.file_exists(file_path):
			continue

		var img := Image.create(32, 32, false, Image.FORMAT_RGBA8)
		img.fill(Color(0.2, 0.6, 0.9, 0.85))
		var err = img.save_png(file_path)
		if err != OK:
			push_error("Failed to save fixture image: %s" % file_path)
			return false

	print("Validated %d fixture PNGs in %s" % [BONE_NAMES.size(), SPRITE_DIR])
	return true


func _find_bone_recursive(node: Node, target_name: String) -> Bone2D:
	if node is Bone2D and node.name == target_name:
		return node as Bone2D
	for child in node.get_children():
		var found = _find_bone_recursive(child, target_name)
		if found:
			return found
	return null
