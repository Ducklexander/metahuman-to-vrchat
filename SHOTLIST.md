# Shot list

Footage that needs a person in front of the webcam or a logged-in VRChat client. Everything else (Blender sheets, Unity renders, the expression loop) is already generated from the tools and lives in `media/` or in the blog's media folder.

Full-size recordings go to the website's R2 or a GitHub Release, not into git. The repo keeps only small JPG/GIF previews.

## Recording settings (all shots)

| Setting | Value |
| --- | --- |
| Recorder | OBS Studio |
| Resolution / frame rate | 1920x1080, 60 fps (30 fps is fine for UI captures) |
| Encoder | NVENC H.264, CQP 18 (or x264 CRF 18), keyframe interval 2 s |
| Audio | Off, or a separate track; the blog videos play muted |
| VRChat | Desktop mode, Graphics set to High, post-processing on, nameplates hidden (Action Menu > Options > Nameplates), own avatar shown to self |
| World | My private studio world, standing on the spawn point facing the mirror. Any world with a mirror and good light works |
| Light on your face | A lamp in front of you, no strong backlight. FoxyFace tracks much worse in a dark room |

## Shots

| # | Shot | Length | Used in | Notes |
| --- | --- | --- | --- | --- |
| 1 | **Hero: mirror and webcam side by side.** VRChat window on the left (me looking at the mirror), FoxyFace preview window on the right, both in one OBS scene. Neutral, talk a sentence, big smile, raised brows with open mouth, pucker, wink left, wink right, tongue out, back to neutral. | 20-30 s | Blog top, README GIF (a 6-8 s cut) | Most important shot. Hold each expression about 1.5 s. Crop OBS canvas so the avatar face fills at least half the height |
| 2 | **Calibration before/after.** Same framing as shot 1, the same sequence once before calibration and once after. | 2 x 15 s | Face tracking chapter | Recorded during the calibration session, see gate 4 |
| 3 | **Eyes only.** Mirror close-up: look left, right, up, down, blink, slow close and open, squint. | 10-15 s | Face tracking chapter (eyelid issue) | Needed to show whether the eyelid neutral value is fixed |
| 4 | **Tracking off.** VRCFaceTracking closed, avatar idling at the mirror: shows bone-based eye look and no blinking (known issue). | 8 s | Chapter 5 known issues | Optional |
| 5 | **MetaHuman Creator.** A few seconds of sculpting in UE 5.6, then the MetaHuman Character menu with Save Face DNA / Save Body DNA visible. | 10-15 s | Blog "how it works", chapter 2 | Screen capture of the UE window only. A screenshot of the open menu is enough if video is a hassle |
| 6 | **The existing 20 s demo** (Unity scene + VRChat first-person at the mirror). | 20 s | Blog | I need the file path |
| 7 | **World lighting walk.** Walk from a warm light to a cold light in the studio world while facing the mirror. | 10 s | Chapter 5 (lighting presets) | Optional; the Unity before/after images already make the point |

## After recording

Put the raw files in one folder and tell me the path. I will cut, crop and encode:

- web video: MP4 (H.264, CRF 23, `+faststart`) and WebM (VP9), 1280 px wide
- README GIF: 480 px wide, 12-15 fps, under 3 MB
- poster frames as JPG for each video
