# License and redistribution audit

Checked on 2026-09-21. This is a working note for deciding what goes into the public repository. It is not legal advice. Where a term is ambiguous I took the conservative reading.

Short version: the repo ships the method and the tools. It does not ship my avatar, any MetaHuman asset, or any third-party package. Each user brings their own MetaHuman and installs the third-party tools from the official sources.

## 1. MetaHuman assets

### What the current terms say

Sources, read on 2026-09-21. Epic geo-redirected me to the Simplified Chinese reference translations (`/eula-reference/unreal-zh-cn`, `/eula-reference/content-zh-cn`); Epic states that the English text is the binding version. Quotes below are my English renderings of those pages, so treat them as paraphrase and check the English originals before relying on the wording.

- MetaHuman licensing FAQ, https://www.metahuman.com/license
  - MetaHuman is included in the standard Unreal Engine license. Free under USD 1M annual revenue; above that the standard UE terms apply.
  - "Can I use MetaHuman characters and animations outside Unreal Engine?" Yes. The UE EULA allows MetaHuman characters and animations to be used in any engine and creative software, under the applicable terms.
  - Used outside UE, MetaHuman characters and animations are classed as non-engine products, so no royalty applies for linear media or for runtime use in games or interactive apps that do not use UE.
  - Above USD 1M revenue, rendering MetaHumans outside UE requires a UE seat license.
  - MetaHuman assets may be packaged in UE for sale on Fab and third-party marketplaces.
  - MetaHuman characters or animation curves may not be used to build or enhance datasets or to train or test AI/ML systems.
- Unreal Engine EULA, https://www.unrealengine.com/eula/unreal
  - Section 4: products may be distributed only as Section 4 allows. Section 4(a)(i) "Non-engine products": asset files developed with the engine code, such as character models and animations, are non-engine products even when they are included in a product that uses another game engine. The same clause adds that some assets provided under separate agreements may be used only with Unreal Engine.
  - Section 6(e): you may not use or let others use MetaHuman digital humans and animation curves to build or enhance databases or to train or test AI/ML systems.
  - Section 7(a): no license is granted to Epic trademarks, which explicitly include the Unreal Engine and MetaHuman names and logos.
  - Section 8(b): the UE EULA supersedes the old MetaHuman Creator EULA.
- Epic Content License Agreement, https://www.unrealengine.com/eula/content
  - Section 3: Licensed Content may be distributed to end users only incorporated in object-code form as an integral part of a project. Rendered linear media (videos, images) may be distributed freely.
  - Section 4: unless service-specific terms say otherwise, Licensed Content may not be distributed to third parties in source format, except to employees and contractors working on your project.
  - Section 6: no selling or transferring Licensed Content on a standalone basis; no letting third parties access it to create their own content for public distribution.
  - MetaHuman Content Appendix: Epic owns and retains all IP in MetaHuman Creator and RigLogic, "including those rights embodied in MetaHuman Content". (The Chinese reference copy I could load still says MetaHuman Content is UE-only content. That line predates the June 2025 change and is contradicted by the FAQ and the UE EULA; the UE EULA is the controlling document for MetaHumans made in UE 5.6+.)

### How that applies to each file type

| File | Where it came from | Can it go in a public repo? | Reason |
| --- | --- | --- | --- |
| `head.dna`, `body.dna` | MetaHuman Creator export (UE 5.6.1) | No | Raw source asset. It embeds the RigLogic rig definition, whose IP Epic retains. A loose DNA file in a git repo is not "an integral part of a product" and is exactly the kind of standalone, source-format distribution the Content License restricts. There is no benefit to users either: they must export their own. |
| UE-exported textures (`T_Head_*`, `T_Body_*`, eyes, teeth, FaceTextures) | UE export | No | Same reasoning: source-format assets. |
| Hair and eyebrow card FBX (`Hair_M_BobMessy_*`, `Eyebrows_M_Dense_*`) | Epic-authored MetaHuman grooms in `MetaHumans/Common` | No | Epic-created content, not mine. |
| `Avatar.fbx` | Output of my pipeline | No | A derivative containing the full MetaHuman mesh, skin weights and 172 baked RigLogic expressions. It would let anyone extract the character. |
| `.blend` files (`v02_baked.blend`, `v04_merged.blend`) | My pipeline | No | Contain the full MetaHuman mesh and rig. |
| Baked blendshapes, `bake_result.json`, `corrective_shape_keys.json`, `addon_poses_raw.json` | Pipeline intermediates | No | The first two are per-character data; the third is derived from Poly Hammer's GPL pose library and is regenerated on each machine anyway. |
| Textures my scripts generate (skin LUT, detail normal, hair strand atlas) | Procedural, my code | Only the procedural ones are safe | `Skin_ScatterLUT.png` and `Skin_DetailNormal.png` are pure math. The hair atlas uses hair colour values read from my MetaHuman's material instance, so I leave it out; users regenerate it from their own values. |
| The uploaded VRChat avatar (`.vrca` on VRChat's servers) | Build output | Allowed | MetaHuman content compiled into a product for end users, which Section 4(a)(i) of the UE EULA covers. |
| Renders, screenshots and videos of the avatar | My captures | Allowed | Rendered linear media, freely distributable under Content License Section 3. Fine for the blog and for small images in the repo. |

### Trademark note

"MetaHuman" and "Unreal Engine" are Epic trademarks (UE EULA Section 7(a)). Using the name descriptively (a repo that converts MetaHumans to VRChat avatars) is normal nominative use. I add a one-line "not affiliated with or endorsed by Epic Games or VRChat" notice to the README and do not use Epic or VRChat logos.

## 2. Unity packages (install by VPM, never vendored)

| Package | Version tested | License | Redistributable in this repo? | How users install it |
| --- | --- | --- | --- | --- |
| VRChat SDK (`com.vrchat.base`, `com.vrchat.avatars`) | 3.10.4 | VRChat SDK License, https://hello.vrchat.com/legal/sdk (last updated 2021-11-05). Section 4.3(d) prohibits distributing or making VRChat Materials available to third parties. | No | VRChat Creator Companion |
| VRCFury (`com.vrcfury.vrcfury`) | 1.1408.0 | Custom dual license (`LICENSE.md` in VRCFury/VRCFury). The commercial option requires that VRCFury "must be downloaded directly by the end user from an official distribution channel" and "must not be redistributed with your product". | No | VPM repo `https://vcc.vrcfury.com` |
| Jerry's VRCFT Templates (`adjerry91.vrcft.templates`) | 7.0.5 | MIT (Adjerry91/VRCFaceTracking-Templates) | Legally yes, but not needed | VPM repo `https://adjerry91.github.io/VRCFaceTracking-Templates/index.json` |
| Poiyomi Toon (`com.poiyomi.toon`) | 9.3.64 | MIT (poiyomi/PoiyomiToonShader) for the free version | Legally yes, but not needed | VPM repo `https://poiyomi.github.io/vpm/index.json` |

Vendoring would pin users to stale copies and, for the SDK and VRCFury, break the license. The repo lists repo URLs and tested versions only.

## 3. Blender side

| Item | License | Decision |
| --- | --- | --- |
| Poly Hammer Character DNA addon (tested 0.12.4; GitHub repo `poly-hammer/character-dna-addon`) | GPL-3.0 | Not bundled. Users install it from Poly Hammer's extension server, which needs a free account and an API token. GitHub releases carry no packaged zip (checked: 0.10.3 through 0.13.7 have zero assets). Current release is 0.13.7 (2026-09-16); I only tested 0.12.4, and the docs say so. |
| Epic's DNA bindings (bundled inside the addon) | Epic | Not bundled; used through the addon at runtime. |
| Blender itself | GPL | Not bundled. |

GPL consequence for my own code: the Blender scripts import the GPL addon at runtime (`bl_ext.api_portal_polyhammer_com.character_dna`) and run inside Blender. Blender's position is that add-ons using the Python API are covered by the GPL when distributed. MIT is GPL-compatible, so MIT on my scripts is fine as long as I do not ship the addon. If the tool is ever submitted to extensions.blender.org it must be GPL-3.0-or-later. Decision needed (see the confirmation gate): MIT for everything, or GPL-3.0-or-later for `blender/` and MIT for the rest.

## 4. Face tracking software (link only)

| Item | Version tested | License | Decision |
| --- | --- | --- | --- |
| FoxyFace (Jeka8833/FoxyFace) | 1.0.5.1 | No license file in the repo (all rights reserved by default) | Link to the official GitHub releases only. Current release is 1.0.6.1 (2026-09-05), untested. |
| FoxyFaceVRCFTInterface | 1.0.4.3 | Distributed with FoxyFace releases | Install through the VRCFaceTracking Module Registry, which is also the only install method that worked (see docs). |
| VRCFaceTracking (benaclejames/VRCFaceTracking) | Steam build 23033521 | Apache-2.0 | Link to Steam (app 3329480). |

## 5. My own scripts and docs

Everything in `blender/`, `tools/`, `unity/` and `docs/` is my work, adapted from the archive's 43 pipeline scripts. Proposed license: MIT (see gate). The docs quote no third-party text beyond short phrases with attribution.

## 6. Privacy clean-up

Removed or generalised before anything is committed:

| Item | Where it appeared | Action |
| --- | --- | --- |
| VRChat user ID (`usr_...`) | Session 5 report (OSC config path) | Replaced with `usr_<your-user-id>` |
| Avatar and world blueprint IDs (`avtr_...`, `wrld_...`) | Archive README, Session 4/5 and studio world reports | Removed |
| Local absolute paths (project, tool and user-profile folders on my drives) | Every archived script and report | Replaced by config values or placeholders like `<blender.exe>` |
| Machine name and Windows user name | Session 1 report | Not copied |
| Email addresses | Git identity | Commits use the GitHub noreply address, not the global git email |
| `.mcp.json`, `.env` | Archive root | Not copied |
| Unity `Library/`, `Logs/`, `unity-editor.log`, `UserSettings/` | Archive Unity projects | Not copied |

`tools/privacy_scan.ps1` greps the tree for these patterns and runs before every push.
