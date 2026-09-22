# 1. Prerequisites

## What I tested on

Everything in this repo ran on one machine. I have not tested other hardware or operating systems.

| | |
| --- | --- |
| OS | Windows 11 Home (26200) |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU (8 GB) |
| CPU / RAM | AMD Ryzen 5 7535HS / 32 GB |
| Webcam | The laptop's built-in 720p USB webcam |

macOS and Linux are untested. The Blender and texture steps are plain Python and may work there; Unity 2022.3.22f1 exists for both, but FoxyFace and VRCFaceTracking are Windows programs, so the face tracking part is Windows only.

## Accounts

| Account | Why | Notes |
| --- | --- | --- |
| Epic Games | Unreal Engine 5.6 and MetaHuman Creator | MetaHuman is free under USD 1M annual revenue. See [the license notes](../LICENSE-AUDIT.md). |
| Poly Hammer (free) | Downloads the Character DNA Blender extension | The free edition is only on Poly Hammer's own extension server, which needs an API token from your account dashboard. GitHub releases have source only. |
| VRChat | Uploading the avatar | Must be a VRChat account, not a Steam, Meta or Viveport login, and at least **New User** trust rank. VRChat raises your rank from time spent in the game; a brand new account cannot upload. |
| Steam | VRCFaceTracking | Free on Steam (app 3329480). |

## Software and tested versions

Versions matter in this pipeline. The Unity version is not negotiable: VRChat only accepts content built with the version listed on [creators.vrchat.com](https://creators.vrchat.com/sdk/upgrade/current-unity-version/), which was 2022.3.22f1 when I checked on 2026-09-21. Unity 6 uploads do not load.

| Software | Version I used | Where to get it |
| --- | --- | --- |
| Unreal Engine | 5.6.1 | Epic Games Launcher. MetaHuman Creator and the MetaHuman plugins ship with the engine from 5.6. |
| Blender | 5.1.0 | [blender.org](https://www.blender.org/download/) |
| Poly Hammer Character DNA | 0.12.4 | Poly Hammer extension server (below). 0.13.7 is current as of 2026-09-21 and untested with this pipeline. |
| Python | 3.10 or newer, with numpy, Pillow, scipy | For `build.py`: `pip install -r requirements.txt` |
| Unity | 2022.3.22f1 | Unity Hub. Install exactly this version. |
| VRChat Creator Companion (VCC) | 2.4.5 | [vrchat.com/home/download](https://vrchat.com/home/download) |
| VRChat SDK - Avatars | 3.10.4 | VCC |
| VRCFury | 1.1408.0 | VCC, repo `https://vcc.vrcfury.com` |
| Jerry's VRCFT Templates | 7.0.5 | VCC, repo `https://adjerry91.github.io/VRCFaceTracking-Templates/index.json` |
| Poiyomi Toon | 9.3.64 | VCC, repo `https://poiyomi.github.io/vpm/index.json` |
| FoxyFace | 1.0.5.1 (full build with GPU models) | [github.com/Jeka8833/FoxyFace/releases](https://github.com/Jeka8833/FoxyFace/releases). 1.0.6.1 is current and untested. |
| FoxyFaceVRCFTInterface | 1.0.4.3 | VRCFaceTracking's Module Registry (search "FoxyFace") |
| VRCFaceTracking | Steam build 23033521 | Steam |

None of these packages are bundled in this repo, and several of their licenses forbid it. Install them from the sources above.

### Poly Hammer Character DNA

1. Sign up at the Poly Hammer portal and open your dashboard.
2. Copy the Blender extension repository URL and your access token from the dashboard. When I set it up the repository URL was `https://api.portal.polyhammer.com/v1/blender-extensions/`.
3. In Blender: Edit > Preferences > Get Extensions > Repositories (top right) > `+` > Add Remote Repository. Paste the URL, enable authentication, paste the token.
4. Back in Get Extensions, search for `Character DNA`, install it, and make sure it is enabled.

To confirm, run this in Blender's Python console. It should print a version tuple such as `(0, 12, 4)`:

```python
import addon_utils; [m.bl_info["version"] for m in addon_utils.modules() if m.__name__.endswith("character_dna")]
```

### VPM repositories

In VCC: Settings > Packages > Add Repository, once for each of the three URLs in the table. Then create a new Avatar project (it must use Unity 2022.3.22f1) and add the four packages from the Manage Project screen. If you prefer the command line, `vpm` does the same:

```bat
vpm new MyAvatar Avatar -p D:\Unity
vpm add package com.vrchat.avatars@3.10.4 -p D:\Unity\MyAvatar
vpm add package com.vrcfury.vrcfury@1.1408.0 -p D:\Unity\MyAvatar
vpm add package adjerry91.vrcft.templates@7.0.5 -p D:\Unity\MyAvatar
vpm add package com.poiyomi.toon@9.3.64 -p D:\Unity\MyAvatar
```

`vpm new` picks the newest SDK. On the day I wrote this, GitHub was returning 504 for the 3.10.5 download and `vpm new` failed; adding 3.10.4 explicitly worked from the local VCC cache.

## Disk space and time

| Step | Time on my machine | Notes |
| --- | --- | --- |
| Unreal install + MetaHuman Creator | an evening | UE 5.6 is a large download (tens of GB). Sculpting the face is the only creative step and takes as long as you want. |
| Unreal export | 30 minutes | Mostly finding the right assets the first time |
| Build (`build.py`: Blender bake and textures) | about 2 minutes | Headless |
| Unity setup | about 20 minutes | Of which about 8 minutes is one FBX reimport |
| First upload | 10 minutes | |
| Face tracking setup | 30 minutes | Calibration is extra; see [chapter 5](05-face-tracking.md) |

Keep your MetaHuman export, the `work/` folder and your Unity project out of any public repository. They contain your MetaHuman.
