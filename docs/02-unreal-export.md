# 2. Unreal Engine: make and export your MetaHuman

Since UE 5.6, MetaHuman Creator runs inside the Unreal Editor, and the [MetaHuman license](https://www.metahuman.com/license) allows MetaHumans in other engines and platforms. Keep your exported files private: the license allows using them in an avatar, not publishing the raw files.

You need four things out of Unreal:

| Output | Used by | Required |
| --- | --- | --- |
| `head.dna` and `body.dna`, in one folder | Blender bake | Yes |
| Face textures folder (with the `*_Cavity.png`) | Texture build | Yes |
| The character's baked textures (`T_Head_*`, `T_Body_*`, `T_Eye*`, `T_Teeth_*`) as PNG | Texture build | Yes |
| Hair and eyebrow card meshes (LOD1) as FBX, and the hair colour values | Blender bake, hair atlas | Optional, but without them the avatar is bald with no eyebrows |

Time: about 30 minutes once your MetaHuman exists. Creating the MetaHuman is the only creative step in the whole pipeline and is not covered here; Epic's MetaHuman documentation covers it.

## 1. Create the MetaHuman

1. Create or open a UE 5.6 project. The MetaHuman plugins ship with the engine; make sure `MetaHuman Creator` is enabled under Edit > Plugins.
2. In the Content Browser: right-click > MetaHuman > MetaHuman Character. Open it and design the face, body and hair.
3. Assemble the character (the Assembly step in MetaHuman Creator) so that the body, grooms and hair card meshes exist in your project. In my project the assembled assets ended up in `/Game/MetaHumans/<CharacterName>/` with shared assets in `/Game/MetaHumans/Common/`.

## 2. DNA and face textures

The Epic documentation I read describes an Export > DCC Export button in the MetaHuman Creator palette. In UE 5.6.1 that button was not there. The same functions are in the main menu bar of the MetaHuman Creator window, under **MetaHuman Character**, section *MetaHuman Character Data*:

- **Save Face DNA** -> save as `head.dna`
- **Save Body DNA** -> save as `body.dna` in the **same folder**. The Blender importer only looks for `body.dna` next to `head.dna`.
- **Save Face Textures** -> any folder, for example `DCC/FaceTextures`. You need the file ending in `_Cavity.png` from it.

How to tell it worked: both DNA files start with the bytes `DNA`. Mine were 52.7 MB (head) and 4.4 MB (body).

There is no Python API for DNA export in UE 5.6. The only exporter in Python, `MetaHumanIdentity.export_dna_data_to_files`, is for Mesh to MetaHuman identities, not for Creator characters. So this step is manual.

## 3. Baked textures

The build script needs these PNG files from the assembled character:

```
T_Head_BC  T_Head_N  T_Head_SRMF  T_Head_Scatter
T_Body_BC  T_Body_N  T_Body_SRMF  T_Body_Scatter
T_EyeIrisL_BC  T_EyeIrisL_N  T_EyeScleraL_BC  T_EyeScleraL_N
T_EyeIrisR_BC  T_EyeIrisR_N  T_EyeScleraR_BC  T_EyeScleraR_N
T_Teeth_BC  T_Teeth_N  T_Teeth_SRM
```

Search for each name in the Content Browser, select them all, then right-click > Asset Actions > Export, choose PNG, and save them into one folder (for example `Textures/`). Keep the original file names.

Expect large files: the head and body normal and SRMF maps were 8192 x 8192 in my project. The build script downsizes them.

## 4. Hair and eyebrow cards

UE's MetaHuman hair is a strand groom plus generated card meshes for lower LODs. VRChat can only use the cards.

1. Find the static meshes named like `Hair_<Style>_CardsMesh_Group0_LOD1` and `Eyebrows_<Style>_CardMesh_Group0_LOD1` (mine were `Hair_M_BobMessy_...` and `Eyebrows_M_Dense_...`).
2. Right-click > Asset Actions > Export > FBX. Default FBX options are fine.

Use LOD1, not LOD0. My LOD0 hair was 34,093 triangles; LOD1 was 18,738 and looks the same at avatar viewing distance. The head alone is already over 60k triangles and cannot be reduced, because it carries the blendshapes.

What does not work, so you do not spend time on it: the groom itself cannot be exported (the Groom plugin only registers an importer), and the hair cards have no texture atlas to export. UE's hair shader (`M_hair_v4`) is procedural. The texture step paints a strand atlas instead.

### Hair colour

MetaHuman describes hair colour with melanin, redness and dye parameters, not a colour. The atlas script reads them from a small JSON file. Open the character's hair-card material instance (mine was `/Game/MetaHumans/<CharacterName>/Grooms/MID_MI_Hair_Cards_209`), note the values, and write them in this format:

```json
{
  "instances": [
    {
      "asset": "/Game/MetaHumans/MyCharacter/Grooms/MID_MI_Hair_Cards_209",
      "scalars": {
        "hairMelanin": 0.8, "hairRedness": 0.15,
        "HighlightsMelanin": 0.15, "OmbreMelanin": 0.25, "OmbreRedness": 0.3
      },
      "vectors": {
        "hairDye": [0, 0, 0, 1],
        "HighlightshairDye": [0.0956, 0.199, 0.5538, 1],
        "OmbrehairDye": [0.0538, 0.2841, 1.0, 1]
      }
    }
  ]
}
```

Guessing is a bad idea here. I almost picked a "reasonable brown" and would have missed that my character has dark hair with blue highlights and a blue ombre. If you leave the file out, the atlas uses a neutral brown.

The same values can be read with a short UE Python script (`MaterialInstanceConstant.get_editor_property("scalar_parameter_values")`); I read mine that way through a headless commandlet. That script is not in this repo yet.

## Folder layout I used

```
my_metahuman/
  config.toml            (copied from config.example.toml)
  DCC/
    head.dna
    body.dna
    FaceTextures/        (Save Face Textures output)
  Textures/              (T_*.png exported from the Content Browser)
  Hair/
    Hair_..._CardsMesh_Group0_LOD1.fbx
    Eyebrows_..._CardMesh_Group0_LOD1.fbx
    hair_params.json
  work/                  (created by build.py)
```

Everything in this folder is your MetaHuman. Do not commit it to a public repository.
