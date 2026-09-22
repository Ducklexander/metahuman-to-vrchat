# 4. Unity and VRChat upload

## Steps

1. **Create the project.** In VCC, create a VRChat Avatar project with Unity **2022.3.22f1** and add VRCFury, Jerry's VRCFT Templates and Poiyomi Toon ([versions and repos](01-prerequisites.md#software-and-tested-versions)).

2. **Add this repo's Unity package.** Window > Package Manager > `+` > Add package from git URL:

   ```
   https://github.com/Ducklexander/metahuman-to-vrchat.git?path=/unity/com.ducklexander.metahuman-vrchat#v0.1.0
   ```

   Needs Git on the PATH. When it worked, the menu **Tools > MetaHuman to VRChat** exists.

3. **Copy your files in.** Make a folder such as `Assets/Avatar/`, put `Avatar.fbx` in it, and put the `Textures` folder from `work/` next to it:

   ```
   Assets/Avatar/Avatar.fbx
   Assets/Avatar/Textures/*.png
   ```

4. **Set up.** Open a scene, select `Avatar.fbx` in the Project window, and run **Tools > MetaHuman to VRChat > Set Up Avatar**. It:
   - applies the import settings to the FBX and textures, then reimports the FBX (about 8 minutes; Unity is busy, not frozen)
   - creates 7 Poiyomi materials in `Assets/Avatar/Materials/`
   - places the avatar in the scene with a VRC Avatar Descriptor (view point, 15 visemes, eye look) and Jerry's ARKit face-tracking template
   - opens the check window

5. **Check.** The check window should list no errors. Info lines about unlocked materials and the triangle count are expected. You can rerun it any time: select the avatar root and use **Check Before Upload**.

6. **Build and upload.** VRChat SDK > Show Control Panel > Builder > sign in > **Build and Test** (optional), then **Build and Upload**. On the first build, Poiyomi asks about an "Automatic Lighting Fix": answer **Yes**.

## Check after upload

In VRChat, switch to the avatar in front of a mirror. The avatar should be the right height, fully textured, and nothing should be magenta. Without face tracking the eyes look around on their own; the face does not move yet ([chapter 5](05-face-tracking.md)).

## What the setup does, for reference

| Setting | Value | Why |
| --- | --- | --- |
| Convert Units (`useFileScale`) | On | Without it the avatar is about 100x too large |
| Rig | Humanoid | 54 bones map automatically |
| Blend Shape Normals | Import | Keeps the normals baked in Blender |
| Read/Write | On | SDK error when off |
| Textures: Streaming Mip Maps | On | SDK error when off |
| Normal maps | BC5, no extra green flip | Already flipped by `build.py` |
| Materials | Poiyomi presets | Tuned values from my avatar, including four lighting fixes so the avatar picks up world light |
| Template | `VF_ARKit_VRCFT`, with `VF_EyeRotation` removed | Otherwise eye movement is doubled while tracking |

The three steps are also available one by one under **Advanced**.

## Performance Rank

My avatar is **Very Poor** on PC, and yours will be too unless you reduce the head before the bake.

| Stat | Value | Rank |
| --- | --- | --- |
| Triangles | 110,836 (including the template's 220-triangle debug display) | **Very Poor** (Poor ends at 70,000) |
| Texture memory | about 61 MB | Good |
| Material slots | 8 (7 + the debug display) | Good |
| Bones | 55 | Excellent |
| PhysBones, contacts, constraints | 0 | Excellent |
| Download size | about 83 MB | within the 200 MB limit |

Only the triangle count is bad. The meshes that carry the blendshapes need 61,534 triangles on their own; the only way down is decimating the head in Blender, which costs facial detail. Many players hide Very Poor avatars by default, so strangers may see a fallback until they choose to show yours. Quest / Android is not supported.

## If it fails

| Symptom | Fix |
| --- | --- |
| No Tools > MetaHuman to VRChat menu | Git missing, or the package URL is wrong. Check the Package Manager and the Console |
| Avatar is huge | Convert Units was turned off. Run Advanced > 1 again |
| Build error about Read/Write or Streaming Mip Maps | Run Advanced > 1 again |
| Build stopped with `[MH2VRC] Build stopped: ... not locked` | Run **Lock Poiyomi Materials**, then build again |
| Part of the avatar is magenta in VRChat | A material was uploaded unlocked. Lock, check, re-upload |
| Build hangs with no log output | A hidden dialog is waiting (Poiyomi's lighting fix, "Unlocked Shader", or Save Scene). Find it and answer it |
| Dialog "Shader Optimizer: Unlocked Shader" | You built without testing or uploading, so nothing locked the materials. Run **Lock Poiyomi Materials** first, or use Build and Test |
| Re-upload fails with `This file was already uploaded` | Take a new thumbnail |
| Eyes move twice as far while tracking | `VF_EyeRotation` is back under the template. Delete it |

## Known issues

| Issue | Status |
| --- | --- |
| No blink without face tracking | Rebuild with `add_vrc_blink = true`; setup then wires it. Untested in VRChat |
| No PhysBones | No hair bones in the skeleton. If you add some, divide radii by 100 |
| SDK warning about the pelvis/thigh angle | Affects full-body IK only; harmless on desktop |
| 55 Unified Expressions shapes unused | The ARKit template uses the ARKit 52. The Unified template would need renamed shapes; untested |
