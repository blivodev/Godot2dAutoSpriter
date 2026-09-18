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
			
			# Notify editor of modification
			sprite_node.notify_property_list_changed()
			match_count += 1
			print("  ✓ Assigned [%s] -> Bone2D: '%s' (Sprite: '%s')" % [matched_path.get_file(), bone.name, sprite_node.name])
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
## e.g. "warrior_arm_upper_L" -> "arm_upper_l"
## e.g. "arm_upper_L" -> "arm_upper_l"
func _extract_bone_suffix(filename_no_ext: String) -> String:
	var clean := filename_no_ext.strip_edges()

	# If explicit character_prefix was specified (e.g. "warrior")
	if not character_prefix.is_empty() and clean.to_lower().begins_with(character_prefix.to_lower() + "_"):
		return clean.substr(character_prefix.length() + 1).to_lower()

	# Otherwise, split by first underscore: [CharacterName]_[bone_name]
	var first_underscore := clean.find("_")
	if first_underscore != -1 and first_underscore < clean.length() - 1:
		return clean.substr(first_underscore + 1).to_lower()

	return clean.to_lower()


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
