# Changelog

## 0.1.0 (unreleased)

First public version of the tooling from my MetaHuman to VRChat build (August 2026).

- `blender/`: headless pipeline (`run.py` + TOML config) from `head.dna` / `body.dna` to a VRChat-ready FBX: 172 blendshapes, 55-bone Humanoid skeleton, 7 material slots. Reproduces my archived FBX bit for bit. `--from bake` resumes from the RigLogic checkpoint, `--qa` renders contact sheets, and every run ends with an independent re-import check and `bake_report.md`.
- Optional `vrc.blink` shape (`[bake] add_vrc_blink`), untested in VRChat.
- `tools/textures/`: texture build with green-channel flip, mask packing and thickness maps; procedural strand atlas for hair, lashes and brows; tear-line texture; tileable pore normal.
- Removed from my original build: the skin scattering LUT, which turns shadowed skin red once Poiyomi locks the material.
- `unity/com.ducklexander.metahuman-vrchat` 0.1.0: import settings, Poiyomi material presets, avatar setup (descriptor, visemes, eye look, Jerry's ARKit template without `VF_EyeRotation`), pre-upload check, and a build hook that stops a test or upload build when a Poiyomi material is unlocked.
- `tools/tracking/`: port check for the FoxyFace / VRCFaceTracking / VRChat chain, and an OSC recorder.
- Docs for every step, including what went wrong.
