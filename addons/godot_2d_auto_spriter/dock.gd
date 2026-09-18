@tool
extends Control

## =============================================================================
## dock.gd - Godot 2D Auto Spriter & Rigger Editor Dock
##
## Provides a GUI dock in the Godot 4 Editor to:
## 1. Configure character name, archetype, and rig hierarchy type (Biped / Quadruped / Custom).
## 2. One-click instantiate or assemble rigged character scenes.
## 3. Auto-rig Skeleton2D nodes in the active edited scene from sliced PNG directories.
## 4. Add multi-limb expansions (extra arms, wings, tail segments).
## =============================================================================

const AutoRigImporter = preload("res://auto_rig_importer.gd")

const BIPED_TEMPLATE = "res://scenes/character_rig_template.tscn"
const QUADRUPED_TEMPLATE = "res://scenes/quadruped_rig_template.tscn"

@onready var char_name_edit: LineEdit = $VBox/Scroll/Content/CharSection/NameInput
@onready var rig_type_option: OptionButton = $VBox/Scroll/Content/CharSection/RigTypeOption
@onready var dir_input: LineEdit = $VBox/Scroll/Content/DirSection/DirHBox/DirInput
@onready var custom_template_box: VBoxContainer = $VBox/Scroll/Content/CustomTemplateSection
@onready var custom_template_input: LineEdit = $VBox/Scroll/Content/CustomTemplateSection/CustomTemplateInput
@onready var status_label: RichTextLabel = $VBox/Scroll/Content/StatusSection/StatusLabel
@onready var file_dialog: FileDialog = $FileDialog

var _plugin_ref: EditorPlugin = null


func set_plugin(plugin: EditorPlugin) -> void:
	_plugin_ref = plugin


func _ready() -> void:
	if not Engine.is_editor_hint():
		return

	_setup_options()
	_update_dir_from_name()
	_connect_signals()


func _setup_options() -> void:
	if rig_type_option.item_count == 0:
		rig_type_option.add_item("Humanoid Biped (15 bones)", 0)
		rig_type_option.add_item("Beast / Quadruped (20 bones)", 1)
		rig_type_option.add_item("Custom Template...", 2)
	custom_template_box.visible = (rig_type_option.selected == 2)


func _connect_signals() -> void:
	if not char_name_edit.text_changed.is_connected(_on_char_name_changed):
		char_name_edit.text_changed.connect(_on_char_name_changed)
	if not rig_type_option.item_selected.is_connected(_on_rig_type_selected):
		rig_type_option.item_selected.connect(_on_rig_type_selected)


func _on_char_name_changed(_new_text: String) -> void:
	_update_dir_from_name()


func _update_dir_from_name() -> void:
	var cname := char_name_edit.text.strip_edges().to_lower().replace(" ", "_")
	if cname.is_empty():
		cname = "warrior"
	dir_input.text = "res://sprites/" + cname


func _on_rig_type_selected(index: int) -> void:
	custom_template_box.visible = (index == 2)


func _get_selected_template_path() -> String:
	match rig_type_option.selected:
		0:
			return BIPED_TEMPLATE
		1:
			return QUADRUPED_TEMPLATE
		2:
			return custom_template_input.text.strip_edges()
		_:
			return BIPED_TEMPLATE


func _log(msg: String, color: String = "#d4d4d4") -> void:
	status_label.append_text("[color=%s]%s[/color]\n" % [color, msg])
	print("[AutoSpriter Dock] %s" % msg)


func _on_browse_button_pressed() -> void:
	file_dialog.popup_centered_ratio(0.7)


func _on_dir_selected(dir: String) -> void:
	dir_input.text = dir
	_log("Selected sprite directory: %s" % dir, "#4ec9b0")


## Creates a new scene in the editor instantiated from the selected rig template
func _on_instantiate_template_pressed() -> void:
	var tpl_path := _get_selected_template_path()
	if not ResourceLoader.exists(tpl_path):
		_log("Template not found: %s" % tpl_path, "#f44747")
		return

	var char_name := char_name_edit.text.strip_edges().to_lower().replace(" ", "_")
	if char_name.is_empty():
		char_name = "character"

	var out_path := "res://scenes/%s_rig.tscn" % char_name
	var tpl := load(tpl_path) as PackedScene
	var instance := tpl.instantiate()
	instance.name = char_name.capitalize() + "Rig"
	_set_owner_recursive(instance, instance)

	var packed := PackedScene.new()
	var pack_err := packed.pack(instance)
	if pack_err == OK:
		var save_err := ResourceSaver.save(packed, out_path)
		if save_err == OK:
			_log("Created rig template scene: %s" % out_path, "#6a9955")
			_rescan_and_open(out_path)
		else:
			_log("Failed to save template scene: code %d" % save_err, "#f44747")
	else:
		_log("Failed to pack template scene: code %d" % pack_err, "#f44747")

	instance.queue_free()


## Auto-rigs the Skeleton2D in the active edited scene
func _on_auto_rig_active_pressed() -> void:
	var edited_root := EditorInterface.get_edited_scene_root()
	if not edited_root:
		_log("No scene currently open in editor!", "#f44747")
		return

	var skeleton := _find_skeleton_in_node(edited_root)
	if not skeleton:
		_log("No Skeleton2D found in the open scene!", "#f44747")
		return

	var sprites_dir := dir_input.text.strip_edges()
	var char_name := char_name_edit.text.strip_edges().to_lower().replace(" ", "_")

	# If skeleton doesn't have AutoRigImporter attached, we can attach or wrap it
	var importer: AutoRigImporter = skeleton as AutoRigImporter
	if not importer:
		_log("Skeleton2D does not have AutoRigImporter script. Attaching now...", "#ce9178")
		skeleton.set_script(AutoRigImporter)
		importer = skeleton as AutoRigImporter

	importer.character_sprites_dir = sprites_dir
	importer.character_prefix = char_name
	importer.reset_sprite_offsets = true

	var res := importer.execute_auto_rig(true)
	if res.get("success", false):
		var matched: int = res.get("matched", 0)
		var total: int = res.get("total_bones", 0)
		_log("Auto-rig complete: %d/%d bones matched from '%s'" % [matched, total, sprites_dir], "#4ec9b0")
		EditorInterface.mark_scene_as_unsaved()
	else:
		_log("Auto-rig failed: %s" % res.get("reason", "Unknown error"), "#f44747")


## One-click builds a complete standalone character scene and saves to disk
func _on_build_and_save_pressed() -> void:
	var char_name := char_name_edit.text.strip_edges().to_lower().replace(" ", "_")
	if char_name.is_empty():
		char_name = "warrior"

	var sprites_dir := dir_input.text.strip_edges()
	var tpl_path := _get_selected_template_path()
	var out_path := "res://scenes/%s_character.tscn" % char_name

	_log("Building character '%s' using template '%s'..." % [char_name, tpl_path.get_file()], "#569cd6")

	if not ResourceLoader.exists(tpl_path):
		_log("Error: Template not found at: %s" % tpl_path, "#f44747")
		return

	var scene_res := load(tpl_path) as PackedScene
	var root_node := scene_res.instantiate()
	if not root_node:
		_log("Error: Failed to instantiate template scene", "#f44747")
		return

	# Temporary attach to tree to ensure node references resolve
	EditorInterface.get_edited_scene_root() # ping
	var skeleton := _find_skeleton_in_node(root_node)
	if not skeleton:
		_log("Error: Skeleton2D not found in template", "#f44747")
		root_node.queue_free()
		return

	var importer: AutoRigImporter = skeleton as AutoRigImporter
	if not importer:
		skeleton.set_script(AutoRigImporter)
		importer = skeleton as AutoRigImporter

	importer.character_sprites_dir = sprites_dir
	importer.character_prefix = char_name
	importer.reset_sprite_offsets = true

	var res := importer.execute_auto_rig(true)
	if not res.get("success", false):
		_log("Error: Auto-rig sequence failed.", "#f44747")
		root_node.queue_free()
		return

	root_node.name = char_name.capitalize() + "Root"
	_set_owner_recursive(root_node, root_node)

	var packed := PackedScene.new()
	var pack_err := packed.pack(root_node)
	if pack_err != OK:
		_log("Error packing scene: code %d" % pack_err, "#f44747")
		root_node.queue_free()
		return

	var save_err := ResourceSaver.save(packed, out_path)
	root_node.queue_free()

	if save_err == OK:
		_log("SUCCESS: Built character scene -> %s" % out_path, "#4ec9b0")
		_rescan_and_open(out_path)
	else:
		_log("Error saving scene: code %d" % save_err, "#f44747")


## Helper: Add extra pair of wings under the torso bone
func _on_add_wings_pressed() -> void:
	var skeleton := _get_target_skeleton()
	if not skeleton:
		return

	var torso := skeleton.find_child("torso", true, false)
	if not torso:
		_log("Could not find 'torso' bone to attach wings to!", "#f44747")
		return

	var root_node := EditorInterface.get_edited_scene_root()

	# Left wing
	var wing_up_l := _create_bone_with_sprite("wing_upper_L", torso, root_node, Vector2(35, -25))
	var _wing_low_l := _create_bone_with_sprite("wing_lower_L", wing_up_l, root_node, Vector2(25, -20), true)

	# Right wing
	var wing_up_r := _create_bone_with_sprite("wing_upper_R", torso, root_node, Vector2(-35, -25))
	var _wing_low_r := _create_bone_with_sprite("wing_lower_R", wing_up_r, root_node, Vector2(-25, -20), true)

	EditorInterface.mark_scene_as_unsaved()
	_log("Added 4 wing bones (wing_upper_L/R, wing_lower_L/R) under 'torso'.", "#4ec9b0")


## Helper: Add an extra arm pair under torso (for 4-armed or 6-armed creatures)
func _on_add_extra_arms_pressed() -> void:
	var skeleton := _get_target_skeleton()
	if not skeleton:
		return

	var torso := skeleton.find_child("torso", true, false)
	if not torso:
		_log("Could not find 'torso' bone to attach extra arms to!", "#f44747")
		return

	var root_node := EditorInterface.get_edited_scene_root()

	# Find next index (e.g. arm_upper_L2 or L3)
	var suffix := "2"
	if skeleton.find_child("arm_upper_L2", true, false):
		suffix = "3"

	# Left extra arm
	var arm_up_l := _create_bone_with_sprite("arm_upper_L" + suffix, torso, root_node, Vector2(25, 10))
	var arm_low_l := _create_bone_with_sprite("arm_lower_L" + suffix, arm_up_l, root_node, Vector2(0, 20))
	var _hand_l := _create_bone_with_sprite("hand_L" + suffix, arm_low_l, root_node, Vector2(0, 16), true)

	# Right extra arm
	var arm_up_r := _create_bone_with_sprite("arm_upper_R" + suffix, torso, root_node, Vector2(-25, 10))
	var arm_low_r := _create_bone_with_sprite("arm_lower_R" + suffix, arm_up_r, root_node, Vector2(0, 20))
	var _hand_r := _create_bone_with_sprite("hand_R" + suffix, arm_low_r, root_node, Vector2(0, 16), true)

	EditorInterface.mark_scene_as_unsaved()
	_log("Added extra arm pair (suffix: %s) under 'torso'." % suffix, "#4ec9b0")


## Helper: Add next tail segment
func _on_add_tail_segment_pressed() -> void:
	var skeleton := _get_target_skeleton()
	if not skeleton:
		return

	var root_node := EditorInterface.get_edited_scene_root()

	# Find highest tail segment
	var parent_bone: Node = null
	var seg_num := 1
	while true:
		var name_candidate := "tail_%02d" % seg_num
		var found := skeleton.find_child(name_candidate, true, false)
		if found:
			parent_bone = found
			seg_num += 1
		else:
			break

	if not parent_bone:
		# If no tail exists yet, attach to pelvis
		parent_bone = skeleton.find_child("pelvis", true, false)
		if not parent_bone:
			parent_bone = skeleton

	# If previous tail bone was leaf, enable auto_calc or set angle
	if parent_bone is Bone2D and parent_bone.name.begins_with("tail_"):
		(parent_bone as Bone2D).auto_calculate_length_and_angle = true

	var new_name := "tail_%02d" % seg_num
	var _new_tail := _create_bone_with_sprite(new_name, parent_bone, root_node, Vector2(-20, 15), true)

	EditorInterface.mark_scene_as_unsaved()
	_log("Added tail segment '%s' under '%s'." % [new_name, parent_bone.name], "#4ec9b0")


func _create_bone_with_sprite(bone_name: String, parent_node: Node, scene_root: Node, pos: Vector2, is_leaf: bool = false) -> Bone2D:
	var bone := Bone2D.new()
	bone.name = bone_name
	bone.position = pos
	bone.rest = Transform2D(0.0, pos)
	if is_leaf:
		bone.auto_calculate_length_and_angle = false
		bone.length = 16.0

	var sprite := Sprite2D.new()
	sprite.name = "Sprite2D"

	parent_node.add_child(bone)
	bone.add_child(sprite)

	bone.owner = scene_root
	sprite.owner = scene_root

	return bone


func _get_target_skeleton() -> Skeleton2D:
	var edited_root := EditorInterface.get_edited_scene_root()
	if not edited_root:
		_log("No scene currently open in editor!", "#f44747")
		return null
	var skeleton := _find_skeleton_in_node(edited_root)
	if not skeleton:
		_log("No Skeleton2D found in open scene!", "#f44747")
		return null
	return skeleton


func _find_skeleton_in_node(node: Node) -> Skeleton2D:
	if node is Skeleton2D:
		return node as Skeleton2D
	for child in node.get_children():
		var s := _find_skeleton_in_node(child)
		if s:
			return s
	return null


func _set_owner_recursive(node: Node, scene_root: Node) -> void:
	for child in node.get_children():
		child.owner = scene_root
		_set_owner_recursive(child, scene_root)


func _rescan_and_open(scene_path: String) -> void:
	var fs := EditorInterface.get_resource_filesystem()
	if fs:
		fs.scan()
	EditorInterface.open_scene_from_path(scene_path)
