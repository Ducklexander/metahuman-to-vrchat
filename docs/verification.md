# Verification record

How I checked that the generalised tools in this repo reproduce the avatar I actually built and uploaded. Run on 2026-09-21 on the machine listed in [prerequisites](01-prerequisites.md#what-i-tested-on).

## Blender pipeline, end to end

Input: my archived `head.dna` / `body.dna` (UE 5.6.1 export), my hair and eyebrow LOD1 card FBX files. Output went to a temporary folder outside the repo.

```
blender -b --python blender/run.py -- --config <tmp>/config.toml --qa
```

Later, after `build.py` existed, I repeated the whole thing from scratch with `python build.py <tmp>/config.toml` (import, bake, export, verification, then all textures): 58 s for Blender, 123 s for textures, and again 0.0 difference in every geometry comparison below and 0 differing pixels in all 18 textures.

Blender 5.1.0, Character DNA 0.12.4, headless. The first run stopped in the QA stage on a missing import in my code; after the fix I resumed with `--from bake` from the saved checkpoint, which also exercised the resume path.

| Stage | Time |
| --- | --- |
| Import (DNA, correctives, pose library) | 12.7 s |
| Bake, 172 shapes | 25.2 s (26.7 s in the first run) |
| QA contact sheets | 16.6 s |
| Cleanup through export | 8.6 s |
| Total from checkpoint, including clean-process verification | 54.1 s |

### Numbers against the original bake report

| Item | Original report | Generalised pipeline | Match |
| --- | --- | --- | --- |
| Shape keys (incl. Basis) | 173 | 173 | yes |
| ARKit 52 | 52/52 | 52/52 | yes |
| VRChat visemes | 15/15 | 15/15 | yes |
| Unified Expressions extras | 55 | 55 | yes |
| MetaHuman extras / emotions | 38 / 12 | 38 / 12 | yes |
| Triangles | 110,616 | 110,616 | yes |
| Vertices (Blender) | 71,554 | 71,554 | yes |
| Material slots | 7 | 7 | yes |
| Triangles per slot | 48,004 / 28,000 / 1,536 / 1,536 / 8,350 / 386 / 22,804 | same | yes |
| Bones | 55 | 55 | yes |
| Max bone influences | 4 | 4 | yes |
| Zero-delta shapes | `vrc.v_sil` only | `vrc.v_sil` only | yes |
| Height | 1.702 m | 1.702 m | yes |
| FBX size | 50.7 MB | 50.7 MB | yes |

Note on counts: the archived report's summary says "Basis + 169" in places, but its own mapping tables list 52 + 55 + 38 + 15 + 12 = 172 shapes, and the archived FBX has 172 plus Basis. I did not find where 169 came from; the files agree on 172.

Every field of the archived `fbx_verification.json` (except the file path) is identical to the new one.

### Geometry diff against the archived FBX

Both FBX files imported into a clean Blender and compared array by array:

| Compared | Max absolute difference |
| --- | --- |
| Basis vertex positions (71,554 vertices) | 0.0 |
| All 172 shape deltas | 0.0 |
| UVs (270,670 loops) | 0.0 |
| Skin weights | 0.0 |
| Bone rest matrices | 0.0 |
| Material index per polygon | 0 mismatches |
| Shape key order, slot order, bone names | identical |

The output is bit-identical to the archived FBX.

## Texture tools

All 19 PNG files of my original texture set regenerated from the archived UE exports and compared pixel by pixel with the archived textures: 0 differing pixels in every file. That includes `Skin_Head_Thickness` and `Skin_Body_Thickness`, which I originally made by hand inside Unity and which `build_textures.py` now generates. (One of the 19, `Skin_ScatterLUT`, was removed from the repo afterwards; see below.)

The hair atlas matched only after one fix: the first version picked the shared parent material instance `MI_Hair_Cards` (no melanin values) instead of the character's own `MID_MI_Hair_Cards_209`.

## Unity package

A new project, not my original one: Unity 2022.3.22f1, created with `vpm` and pinned to VRChat SDK 3.10.4, VRCFury 1.1408.0, Jerry's VRCFT Templates 7.0.5 and Poiyomi Toon 9.3.64. The package was installed from a git URL (a local `git+file://` URL to this repo, because the GitHub repo did not exist yet). Inputs were the FBX and textures produced by the steps above.

| Step | Result |
| --- | --- |
| Package install and compile | Clean, no compiler errors |
| Texture import settings | 19 textures configured (that run still included the LUT) |
| FBX reimport with the package settings | 467 s (my original: 478 s) |
| Mesh in Unity | 73,466 vertices, 110,616 triangles, 172 blendshapes, 7 submeshes (same as the original) |
| Humanoid | Valid, 54 bones mapped; head at y = 1.5227 (same as the original) |
| Materials from presets | 7 Poiyomi Toon materials |
| Avatar setup | Descriptor view position (0, 1.5757, 0.0926) and eye-look rotations identical to my original descriptor; 15 visemes; `VF_ARKit_VRCFT` added, `VF_EyeRotation` removed |
| Pre-upload check | 0 errors, 0 warnings |
| Poiyomi lock through the package | All 7 materials locked into `Assets/.../OptimizedShaders/`; `_DetailNormalMap` survived the lock |
| VRCSDK build (build only, no upload) | Succeeded, 0 errors. Bundle 83.05 MB (my original upload: 82.98 MB) |
| SDK performance stats | 110,836 triangles (Very Poor), 61.4 MB textures (Good), 8 materials, 2 skinned meshes, 55 bones. Overall Very Poor, from triangles only |

Problems this test found, all fixed before the numbers above:

1. **The skin LUT turns shadowed skin red after locking.** See [notes](notes.md#unity-and-vrchat). The avatar I uploaded has this artefact; the presets no longer use my LUT.
2. **My build hook blocked a legitimate build.** For a build-only run, VRCFury deliberately stops Poiyomi from locking, so the hook saw unlocked materials and failed the build. It now reads the SDK's `VRC_SdkBuilder.ActiveBuildType` and only blocks test and upload builds. The blocking path for a real upload is not exercised here (that needs an upload).
3. **The view position was 12 mm too far back** compared with my original descriptor. The setup now adds that offset.
4. **Scripted builds stop at dialogs.** The build waited on a Save Scene dialog (the test scene had never been saved) and then on Thry's "Automatic Lighting Fix" dialog, both with no log output. This is the behaviour documented in chapter 4 and the notes; it is not a package bug.

Not tested: Build and Test, Build and Upload (no upload was made from the new project), and the package in any Unity version other than 2022.3.22f1.
