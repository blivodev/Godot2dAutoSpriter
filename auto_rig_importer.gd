@tool
class_name AutoRigImporter
extends Skeleton2D

## =============================================================================
## AutoRigImporter.gd
##
## Godot 4 @tool script to automate assigning SAM-exported cut-out character
## sprite parts to a template Skeleton2D hierarchy.
##
## Usage:
## 1. Attach this script to your Skeleton2D node (or a parent controller node).
## 2. In the Inspector, specify the 'character_sprites_dir' (e.g. res://sprites/warrior/).
## 3. If attached to a node other than Skeleton2D, assign the 'skeleton' property.
## 4. Click the 'trigger_auto_rig' checkbox in the Inspector to execute.
## =============================================================================

## Directory containing the transparent PNG cut-out files for this character.
@export_dir var character_sprites_dir: String = ""

## Prefix or name of the character (optional; e.g. "warrior").
## If empty, the script automatically parses everything after the character prefix delimiter '_'.
@export var character_prefix: String = ""

## If true, automatically re-centers the Sprite2D offset to (0, 0).
## Set to false if you manually maintain custom sprite offsets on the template.
@export var reset_sprite_offsets: bool = false

## Button trigger for the Godot Editor Inspector.
@export var trigger_auto_rig: bool = false:
	set(value):
		if value:
			execute_auto_rig()
		trigger_auto_rig = false

## Fallback anatomical offsets ensuring limb sprites pivot at their joints
const DEFAULT_BONE_OFFSETS := {
	"head": Vector2(0, -26),
	"torso": Vector2(0, -4),
	"pelvis": Vector2(0, 4),
	"arm_upper_l": Vector2(2, 18),
	"arm_lower_l": Vector2(1, 16),
	"hand_l": Vector2(0, 10),
	"arm_upper_r": Vector2(-2, 18),
	"arm_lower_r": Vector2(-1, 16),
	"hand_r": Vector2(0, 10),
	"leg_upper_l": Vector2(0, 18),
	"leg_lower_l": Vector2(0, 16),
	"foot_l": Vector2(8, 8),
	"leg_upper_r": Vector2(0, 18),
	"leg_lower_r": Vector2(0, 16),
	"foot_r": Vector2(-8, 8),
	"wing_upper_l": Vector2(16, 20),
	"wing_lower_l": Vector2(20, 22),
	"wing_upper_r": Vector2(-16, 20),
	"wing_lower_r": Vector2(-20, 22),
	"tail": Vector2(0, 16),
	"tail_01": Vector2(-10, 10),
	"tail_02": Vector2(-8, 8),
	"tail_03": Vector2(-6, 6)
}


func _ready() -> void:
	# Ensure editor-only logic doesn't interfere during runtime
	if not Engine.is_editor_hint():
		set_process(false)


## Main execution routine.
## Returns a Dictionary with execution metrics: { "success": bool, "matched": int, "missing": Array[String] }
func execute_auto_rig(force_run: bool = false) -> Dictionary:
	if not Engine.is_editor_hint() and not force_run:
		push_warning("AutoRigImporter: This tool is intended to be run in the Godot Editor.")
		return {"success": false, "reason": "Not in editor"}

	print("\n--- [AutoRigImporter] Starting Auto-Rigging Sequence ---")

	# 1. Resolve Skeleton2D reference
	var target_skeleton: Skeleton2D = _resolve_skeleton()
	if not target_skeleton:
		push_error("AutoRigImporter: No Skeleton2D found! Please assign one in the Inspector or attach this script to a Skeleton2D.")
		return {"success": false, "reason": "No Skeleton2D found"}

	# 2. Validate sprite directory
	if character_sprites_dir.is_empty():
		push_error("AutoRigImporter: 'character_sprites_dir' is empty. Please select a valid folder.")
		return {"success": false, "reason": "Empty directory"}

	if not DirAccess.dir_exists_absolute(character_sprites_dir):
		push_error("AutoRigImporter: Directory does not exist: %s" % character_sprites_dir)
		return {"success": false, "reason": "Directory does not exist"}

	# 3. Ask Godot's editor filesystem to rescan so newly generated files are imported
	_rescan_editor_filesystem()

	# 4. Map available PNG files in the directory
	var texture_map: Dictionary = _build_texture_map(character_sprites_dir)
	if texture_map.is_empty():
		push_error("AutoRigImporter: No .png files found in %s" % character_sprites_dir)
		return {"success": false, "reason": "No PNG files found"}

	var unique_files: Array = []
	for p in texture_map.values():
		if not unique_files.has(p):
			unique_files.append(p)
	print("[AutoRigImporter] Indexed %d sprite files from: %s" % [unique_files.size(), character_sprites_dir])

	# 5. Recursively traverse Skeleton2D bones and assign matching textures
	var match_count: int = 0
	var missing_bones: Array[String] = []

	# Attach extra creature appendages (wings, tail) if present in textures
	_attach_extra_appendages(target_skeleton, texture_map)

	var bone_nodes: Array[Bone2D] = _collect_all_bones(target_skeleton)
	print("[AutoRigImporter] Found %d Bone2D nodes in skeleton '%s'" % [bone_nodes.size(), target_skeleton.name])

	for bone in bone_nodes:
		var sprite_node: Sprite2D = _find_placeholder_sprite(bone)
		if not sprite_node:
			# Not every bone strictly requires a visual sprite (e.g. Root, IK targets)
			continue

		var matched_path: String = _find_matching_texture(bone.name, texture_map)
		if matched_path.is_empty():
			missing_bones.append(bone.name)
			continue

		# Load and apply texture with fallback support
		var tex: Texture2D = _load_texture(matched_path)
		if tex:
			sprite_node.texture = tex
			if reset_sprite_offsets:
				sprite_node.offset = Vector2.ZERO
			elif sprite_node.offset == Vector2.ZERO:
				var sfx := _extract_bone_suffix(bone.name).to_lower()
				if DEFAULT_BONE_OFFSETS.has(sfx):
					sprite_node.offset = DEFAULT_BONE_OFFSETS[sfx]
			
			# Notify editor of modification
			sprite_node.notify_property_list_changed()
			match_count += 1
			print("  ✓ Assigned [%s] -> Bone2D: '%s' (Sprite: '%s', Offset: %s)" % [matched_path.get_file(), bone.name, sprite_node.name, str(sprite_node.offset)])
		else:
			push_warning("  ✗ Failed to load texture resource at: %s" % matched_path)

	# 6. Report summary
	print("\n--- [AutoRigImporter] Finished Auto-Rigging ---")
	print("Successfully rigged %d/%d visual bones." % [match_count, bone_nodes.size()])
	if not missing_bones.is_empty():
		push_warning("Bones without matching textures (%d): %s" % [missing_bones.size(), str(missing_bones)])

	# 7. Mark current scene unsaved so changes can be saved with Ctrl+S in editor
	if match_count > 0 and Engine.is_editor_hint():
		if ClassDB.class_exists("EditorInterface"):
			var edited_root: Node = EditorInterface.get_edited_scene_root()
			if edited_root:
				EditorInterface.mark_scene_as_unsaved()

	return {
		"success": true,
		"matched": match_count,
		"missing": missing_bones,
		"total_bones": bone_nodes.size()
	}


## Resolves the Skeleton2D instance (self since script extends Skeleton2D)
func _resolve_skeleton() -> Skeleton2D:
	return self


## Refreshes Godot's filesystem cache
func _rescan_editor_filesystem() -> void:
	if Engine.is_editor_hint():
		if ClassDB.class_exists("EditorInterface"):
			var fs = EditorInterface.get_resource_filesystem()
			if fs:
				fs.scan()


## Robust texture loader with fallback for raw unimported PNGs
func _load_texture(path: String) -> Texture2D:
	if ResourceLoader.exists(path):
		var res := ResourceLoader.load(path)
		if res is Texture2D:
			return res as Texture2D

	var img := Image.new()
	var err := img.load(path)
	if err == OK:
		return ImageTexture.create_from_image(img)

	return null


## Scans the directory and maps normalized suffix identifiers to file paths
## Example: "warrior_arm_upper_L.png" -> key: "arm_upper_l", path: "res://.../warrior_arm_upper_L.png"
func _build_texture_map(dir_path: String) -> Dictionary:
	var map: Dictionary = {}
	var dir := DirAccess.open(dir_path)
	if not dir:
		return map

	dir.list_dir_begin()
	var file_name := dir.get_next()

	while not file_name.is_empty():
		if not dir.current_is_dir() and file_name.to_lower().ends_with(".png"):
			var full_path := dir_path.path_join(file_name)
			var base_name := file_name.get_basename()

			# Extract suffix: if file is "warrior_arm_upper_L", extract "arm_upper_l"
			var suffix_key := _extract_bone_suffix(base_name)
			map[suffix_key] = full_path
			
			# Also store full lowercased base name as fallback
			map[base_name.to_lower()] = full_path

		file_name = dir.get_next()

	return map


## Extracts the suffix after the character prefix delimiter
## e.g. "winged_demon_arm_lower_L" -> "arm_lower_l"
## e.g. "arm_upper_L" -> "arm_upper_l"
func _extract_bone_suffix(filename_no_ext: String) -> String:
	var clean := filename_no_ext.strip_edges()

	# If explicit character_prefix was specified (e.g. "winged_demon")
	if not character_prefix.is_empty() and clean.to_lower().begins_with(character_prefix.to_lower() + "_"):
		return clean.substr(character_prefix.length() + 1).to_lower()

	# Check known anatomical suffixes to handle names with multiple underscores
	const KNOWN_SUFFIXES := [
		"wing_upper_l", "wing_lower_l", "wing_upper_r", "wing_lower_r",
		"arm_upper_l", "arm_lower_l", "hand_l",
		"arm_upper_r", "arm_lower_r", "hand_r",
		"leg_upper_l", "leg_lower_l", "foot_l",
		"leg_upper_r", "leg_lower_r", "foot_r",
		"pelvis", "torso", "head", "neck", "spine",
		"paw_front_l", "paw_front_r", "paw_back_l", "paw_back_r",
		"leg_front_upper_l", "leg_front_lower_l", "leg_front_upper_r", "leg_front_lower_r",
		"leg_back_upper_l", "leg_back_lower_l", "leg_back_upper_r", "leg_back_lower_r",
		"tail", "tail_01", "tail_02", "tail_03", "horns", "ears"
	]
	var lower := clean.to_lower()
	for sfx in KNOWN_SUFFIXES:
		if lower.ends_with("_" + sfx) or lower == sfx:
			return sfx

	# Otherwise, split by first underscore: [CharacterName]_[bone_name]
	var first_underscore := clean.find("_")
	if first_underscore != -1 and first_underscore < clean.length() - 1:
		return clean.substr(first_underscore + 1).to_lower()

	return clean.to_lower()


## Dynamically creates Bone2D + Sprite2D nodes for extra anatomical parts (wings, tail)
func _attach_extra_appendages(target_skeleton: Skeleton2D, texture_map: Dictionary) -> void:
	var torso_node := target_skeleton.find_child("torso", true, false)
	if torso_node:
		# Left Wing Upper (Character's Left = Screen Right = Positive X)
		if texture_map.has("wing_upper_l") and not target_skeleton.find_child("wing_upper_L", true, false):
			var wing_up_L := Bone2D.new()
			wing_up_L.name = "wing_upper_L"
			wing_up_L.position = Vector2(28, -20)
			wing_up_L.default_length = 24.0
			wing_up_L.bone_angle = -0.5
			wing_up_L.auto_calculate_length_and_angle = false
			wing_up_L.rest = Transform2D(0, wing_up_L.position)
			torso_node.add_child(wing_up_L)
			var spr := Sprite2D.new()
			spr.name = "Sprite2D"
			spr.z_index = -2
			spr.offset = Vector2(16, 20)
			wing_up_L.add_child(spr)

		# Left Wing Lower
		if texture_map.has("wing_lower_l") and not target_skeleton.find_child("wing_lower_L", true, false):
			var parent_node := target_skeleton.find_child("wing_upper_L", true, false)
			if not parent_node:
				parent_node = torso_node
			var wing_low_L := Bone2D.new()
			wing_low_L.name = "wing_lower_L"
			wing_low_L.position = Vector2(24, 28)
			wing_low_L.default_length = 24.0
			wing_low_L.bone_angle = 0.5
			wing_low_L.auto_calculate_length_and_angle = false
			wing_low_L.rest = Transform2D(0, wing_low_L.position)
			parent_node.add_child(wing_low_L)
			var spr := Sprite2D.new()
			spr.name = "Sprite2D"
			spr.z_index = -2
			spr.offset = Vector2(20, 22)
			wing_low_L.add_child(spr)

		# Right Wing Upper (Character's Right = Screen Left = Negative X)
		if texture_map.has("wing_upper_r") and not target_skeleton.find_child("wing_upper_R", true, false):
			var wing_up_R := Bone2D.new()
			wing_up_R.name = "wing_upper_R"
			wing_up_R.position = Vector2(-28, -20)
			wing_up_R.default_length = 24.0
			wing_up_R.bone_angle = 3.64
			wing_up_R.auto_calculate_length_and_angle = false
			wing_up_R.rest = Transform2D(0, wing_up_R.position)
			torso_node.add_child(wing_up_R)
			var spr := Sprite2D.new()
			spr.name = "Sprite2D"
			spr.z_index = -2
			spr.offset = Vector2(-16, 20)
			wing_up_R.add_child(spr)

		# Right Wing Lower
		if texture_map.has("wing_lower_r") and not target_skeleton.find_child("wing_lower_R", true, false):
			var parent_node := target_skeleton.find_child("wing_upper_R", true, false)
			if not parent_node:
				parent_node = torso_node
			var wing_low_R := Bone2D.new()
			wing_low_R.name = "wing_lower_R"
			wing_low_R.position = Vector2(-24, 28)
			wing_low_R.default_length = 24.0
			wing_low_R.bone_angle = 2.64
			wing_low_R.auto_calculate_length_and_angle = false
			wing_low_R.rest = Transform2D(0, wing_low_R.position)
			parent_node.add_child(wing_low_R)
			var spr := Sprite2D.new()
			spr.name = "Sprite2D"
			spr.z_index = -2
			spr.offset = Vector2(-20, 22)
			wing_low_R.add_child(spr)

	var pelvis_node := target_skeleton.find_child("pelvis", true, false)
	if pelvis_node:
		if texture_map.has("tail") and not target_skeleton.find_child("tail", true, false):
			var tail_bone := Bone2D.new()
			tail_bone.name = "tail"
			tail_bone.position = Vector2(0, 16)
			tail_bone.default_length = 20.0
			tail_bone.bone_angle = 1.5708
			tail_bone.auto_calculate_length_and_angle = false
			tail_bone.rest = Transform2D(0, tail_bone.position)
			pelvis_node.add_child(tail_bone)
			var spr := Sprite2D.new()
			spr.name = "Sprite2D"
			spr.z_index = -2
			spr.offset = Vector2(0, 16)
			tail_bone.add_child(spr)
		elif texture_map.has("tail_01") and not target_skeleton.find_child("tail_01", true, false):
			var t1 := Bone2D.new()
			t1.name = "tail_01"
			t1.position = Vector2(0, 16)
			t1.default_length = 16.0
			t1.rest = Transform2D(0, t1.position)
			pelvis_node.add_child(t1)
			var spr1 := Sprite2D.new()
			spr1.name = "Sprite2D"
			spr1.z_index = -2
			spr1.offset = Vector2(-10, 10)
			t1.add_child(spr1)

			if texture_map.has("tail_02"):
				var t2 := Bone2D.new()
				t2.name = "tail_02"
				t2.position = Vector2(-15, 15)
				t2.default_length = 16.0
				t2.rest = Transform2D(0, t2.position)
				t1.add_child(t2)
				var spr2 := Sprite2D.new()
				spr2.name = "Sprite2D"
				spr2.z_index = -2
				spr2.offset = Vector2(-8, 8)
				t2.add_child(spr2)

				if texture_map.has("tail_03"):
					var t3 := Bone2D.new()
					t3.name = "tail_03"
					t3.position = Vector2(-15, 15)
					t3.default_length = 16.0
					t3.bone_angle = 2.356
					t3.auto_calculate_length_and_angle = false
					t3.rest = Transform2D(0, t3.position)
					t2.add_child(t3)
					var spr3 := Sprite2D.new()
					spr3.name = "Sprite2D"
					spr3.z_index = -2
					spr3.offset = Vector2(-6, 6)
					t3.add_child(spr3)


## Finds the Sprite2D node attached directly to this Bone2D
func _find_placeholder_sprite(bone: Bone2D) -> Sprite2D:
	for child in bone.get_children():
		if child is Sprite2D:
			return child as Sprite2D
	return null


## Finds a matching file path for a given bone name
func _find_matching_texture(bone_name: String, texture_map: Dictionary) -> String:
	var normalized_bone := bone_name.to_lower().strip_edges()

	# 1. Direct match with extracted suffix
	if texture_map.has(normalized_bone):
		return texture_map[normalized_bone]

	# 2. Check if any suffix key matches when stripping common naming variations
	for key in texture_map.keys():
		if normalized_bone.ends_with(key) or key.ends_with(normalized_bone):
			return texture_map[key]

	return ""


## Gathers all Bone2D nodes recursively under the Skeleton2D
func _collect_all_bones(node: Node) -> Array[Bone2D]:
	var list: Array[Bone2D] = []
	for child in node.get_children():
		if child is Bone2D:
			list.append(child as Bone2D)
		# Bone2D nodes are nested hierarchically
		list.append_array(_collect_all_bones(child))
	return list
