# 7. Troubleshooting

Most problems in this pipeline do not raise an error. They produce a result that looks slightly wrong, or right until you look closely. This page is organised by symptom.

## Blender

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Poly Hammer 'Character DNA' extension not found` | Addon not installed in this Blender, or `--factory-startup` was used | Install it (see [prerequisites](01-prerequisites.md#poly-hammer-character-dna)); run without `--factory-startup` |
| Face looks like speckled noise in Blender | The addon's normal import was used | The pipeline imports with `import_normals=False`. If you imported by hand, reimport without normals |
| Expressions look stiff: lips do not roll, cheeks do not bunch | Corrective shapes were not applied during the bake | Use the pipeline, not the addon's own shape-key import; check stderr for `internal error setting the array` if you changed `riglogic_core.py` |
| `mouthClose` on its own makes the lips intersect | Expected. It is defined relative to an open jaw | Use it with `jawOpen`, as ARKit does |
| Eyebrows stay still while the forehead moves | Eyebrow cards were not given the expressions | Make sure `eyebrow_fbx` is set; stage 08 bakes the expressions onto the cards |
| Hair shows as opaque grey strips in Blender renders | No atlas assigned in Blender | Normal. The atlas is applied in Unity |

## Textures

| Symptom | Cause | Fix |
| --- | --- | --- |
| Skin pores look lit from the wrong side | Normal map green channel flipped twice, or not at all | `build_textures.py` flips once. Do not tick "Flip Green Channel" in Unity |
| Hair looks silver or white | A computed colour was written without sRGB encoding | Use the scripts as they are; if you edit colours, keep the `linear_to_srgb` step |
| Eyebrows are a solid black block with rectangular edges | Brow zone of the atlas too opaque | Lower the brow `strands` range in `hair_atlas.py` |
| Eyebrows look grey and washed out | Alpha-to-coverage on the hair material | Turn A2C off (the preset does) |
| Body texture stretched after switching to Clamp | Body UVs were in UDIM tile 1 | The pipeline moves them to 0-1; re-export from Blender |

## Unity

| Symptom | Cause | Fix |
| --- | --- | --- |
| Avatar is about 170 m tall | Convert Units (`useFileScale`) turned off | Turn it on. The FBX relies on it |
| Build fails: meshes imported with Read/Write disabled | Read/Write off | Run Tools > MetaHuman to VRChat > Advanced > 1 again |
| Build fails: mipmapped textures without Streaming Mip Maps | Streaming Mip Maps off | Run Tools > MetaHuman to VRChat > Advanced > 1 again |
| Reimport seems stuck for minutes | Blend Shape Normals = Import with 172 shapes | Normal. About 8 minutes on my machine. Watch `Editor.log` for `Start importing ... Avatar.fbx` and the matching `in N seconds` line |
| Build hangs with no log output and no CPU use | A hidden modal dialog (often Thry's "Automatic Lighting Fix") | Find and answer the dialog |
| Pore detail missing although `_DetailNormalMap` is set | `_DetailEnabled` is 0; Poiyomi strips the texture on lock | Set `_DetailEnabled = 1` (the preset does). The pre-upload check warns about this |
| Material edits have no effect | Material is locked | Unlock, edit, relock |
| An object renders not at all, though every property looks fine | Mesh asset overwritten with `EditorUtility.CopySerialized` in a script | Create a new asset with `AssetDatabase.CreateAsset` instead |
| Eyes move twice as far as they should while tracking | `VF_EyeRotation` still under the template | Delete it (setup does); the pre-upload check reports it as an error |

If you drive Unity from scripts or an AI assistant: long editor operations can time out on the caller's side while Unity keeps working, and some tools resend the command. One timed-out `SaveAndReimport()` queued three extra 8-minute reimports for me. Split long operations into small batches and check `Editor.log` before retrying anything with side effects.

## VRChat

| Symptom | Cause | Fix |
| --- | --- | --- |
| Part of the avatar is solid magenta | A Poiyomi material was not locked, so its shader was not included | Lock all materials and rebuild. The package's build hook stops the build in this case |
| Upload fails at the image step with `This file was already uploaded` | Byte-identical thumbnail | Take a new thumbnail |
| Strangers see a fallback avatar | Very Poor rank, hidden by their Performance Options | Expected with this pipeline; see [Performance Rank](04-unity-vrchat.md#performance-rank) |
| Avatar ignores world lighting (same colour in every world) | Poiyomi toon lighting defaults | Use the material presets; see [notes](notes.md#unity-and-vrchat) |
| Avatar looks flat compared to Unity | World has no post-processing, or the viewer turned it off | Out of the avatar's control |
| Shadowed side of the face or neck glows red | A skin scattering LUT on a Poiyomi Skin-mode material (my original build had this) | Remove `_SkinLUT` from the skin materials. Always check the look after locking, not before |

## Face tracking

| Symptom | Cause | Fix |
| --- | --- | --- |
| Nothing moves | One of the three links is down | Run `tools\tracking\check_ft_ports.ps1` |
| Port 25747 is not open | Module installed by copying the DLL, or FoxyFace started after the module's 60 s search window | Install from the Module Registry; start FoxyFace first, then restart VRCFaceTracking |
| VRCFaceTracking runs but has no window | Started from the exe | Start it through Steam |
| Port 9000 is not open | OSC is off in VRChat | Action Menu > Options > OSC > Enabled |
| Face moves in bursts and drops to neutral | Face leaves the camera view, bad light | Check with `osc_capture.ps1`: values dropping to 0 for seconds at a time mean lost tracking |

## General method

Two things saved me more time than anything else:

1. Decide whether something works by measuring, not by looking, and measure what ships. The pore normal first changed 0% of the pixels while I believed it was working. The skin LUT measured as harmless on the unlocked material and painted the cheek red once locked.
2. To decide whether an object renders at all, give it an unlit, saturated solid colour and count those pixels. While building a demo world I reached four wrong conclusions in a row by adjusting lighting on an object that was never being drawn.
