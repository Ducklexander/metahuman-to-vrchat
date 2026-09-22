# 6. Webcam face tracking

The avatar side is finished once the ARKit template is on it. This chapter connects a webcam to it:

```
webcam -> FoxyFace -> UDP 25747 -> FoxyFaceVRCFTInterface (VRCFT module)
       -> VRCFaceTracking -> OSC UDP 9000 -> VRChat -> Jerry's ARKit template -> 52 blendshapes
```

FoxyFace runs MediaPipe face landmarks plus Project Babble's mouth model on the webcam image. It needs to see your whole face, so this only works in **desktop mode**. With a headset on, the upper face is covered. See [VR mode](#vr-mode) for what that needs instead.

No code is involved. `tools/tracking` has two PowerShell scripts for diagnosing the chain.

Time: about 30 minutes to connect, plus calibration.

## Install

1. **FoxyFace**: download the full release (with GPU models) from [the FoxyFace releases page](https://github.com/Jeka8833/FoxyFace/releases) and unzip it anywhere. I used 1.0.5.1.
2. **VRCFaceTracking**: install from Steam (app 3329480) and start it once so it creates its settings folder.
3. **FoxyFace module**: in VRCFaceTracking, open the Module Registry, search for FoxyFace and install **FoxyFaceVRCFTInterface**.

Install the module from the registry, not by copying the DLL. I first copied `FoxyFaceVRCFTInterface.dll` and `module.json` into `%APPDATA%\VRCFaceTracking\CustomLibs\` by hand. VRCFaceTracking did not treat it as installed, and its module process never started. A registry install creates a subfolder named after the module ID and works. If you already copied the DLL by hand, move that copy out of `CustomLibs\` so the module is not loaded twice.

## Start order

The order matters:

1. Start **FoxyFace** and check that it shows your face with landmarks.
2. Start **VRCFaceTracking** through Steam, or with `start steam://rungameid/3329480`. Launching `VRCFaceTracking.exe` directly gave me a running process with no window and no open ports.
3. In **VRChat**, switch to your avatar, then Action Menu > Options > OSC > **Enabled**.

When the module loads, it searches for FoxyFace for 60 seconds (`SearchFoxyFaceTimeoutSeconds` in `%APPDATA%\VRCFaceTracking\Configs\FoxyFace\FoxyFace.json`). If VRCFaceTracking started first and FoxyFace was not found in time, restart VRCFaceTracking.

## Check the chain

```bat
powershell -ExecutionPolicy Bypass -File tools\tracking\check_ft_ports.ps1
```

It shows which process holds each port and what to do about a missing one:

| Port | Should be held by | If nobody holds it |
| --- | --- | --- |
| 25747 | `VRCFaceTracking.ModuleProcess` | The FoxyFace module did not load |
| 9000 | `VRChat` | OSC is off in VRChat |
| 9001 | `VRCFaceTracking` | VRCFaceTracking is not running properly |

When I first tried, all three links were down for three different reasons (OSC off, module installed by hand, FoxyFace not running). The port check found all three in a few seconds. Looking at the GUIs had not.

When all three are up, VRChat writes an OSC config file for the avatar under `%USERPROFILE%\AppData\LocalLow\VRChat\VRChat\OSC\usr_<your-user-id>\Avatars\`. For my avatar it registered 152 parameters.

In VRChat, the template adds a Face Tracking menu with Eye Tracking, Lip Tracking, Visemes and Settings (including smoothing and a debug display that shows each FT parameter live). Use the debug display to confirm parameters are arriving before tuning anything.

## Calibration

**Not done yet.** This section will be replaced with a tested procedure and before/after numbers.

What I know so far, from my first connection:

- Out of the box the face moves, but the eyes look half closed.
- In Jerry's ARKit template, `FT/v2/EyeLidLeft` / `EyeLidRight` go through a blend tree where 0 is fully closed, **0.75 is relaxed open** (the controller's default value) and 1.0 is wide. So "eyes half closed" means the value arriving is below 0.75.
- I recorded 60 seconds and got a median of 0.18 (left) and 0.13 (right). I have not acted on it, because the measurement has two problems: my OSC parser mis-read some packets at the time (fixed since), and all four recorded parameters ended at exactly 0.000, which looks like my face left the camera, not like closed eyes.
- FoxyFace's `config.json` holds a partial neutral calibration from that evening: neutral offsets for 11 values (eye gaze X/Y, head Y/Z, cheek puff and suck, tongue out), no eyelid entries, and every max range still at the default of -1 / +1. `HeadZ`'s neutral is stored as a string (`"-30.737677"`) while the others are numbers, which looks like a FoxyFace quirk worth watching. In the same file, `CheekPuff` and `HeadX` are set to `Disabled`; I have not checked whether that is FoxyFace's default.

The plan, in order:

1. Record a clean baseline with `osc_capture.ps1` while holding a neutral face for the full minute, looking at the screen.
2. If the eyelid median is near 0.75, tracking is fine and the avatar's 0.75 pose is too droopy; tune `OSCm/Sensitivity/EyeLid` in the template (default 0.8) or adjust the shape.
3. If it is well below 0.75, FoxyFace is reading open eyes as half closed; run FoxyFace's neutral calibration. That fixes the cause instead of the symptom.
4. If the values jump around, tune smoothing (FoxyFace's One Euro filter settings, and the template's Local Smoothing).
5. Score each expression group (brows, eyes, smile, pucker, jaw, cheeks, tongue) and sort any problems into "baked shape", "binding strength" or "tracker".

## Measuring instead of guessing

`osc_capture.ps1` records what VRChat sends out on UDP 9001 and prints n / min / median / max per parameter, plus a 5-second time series for one parameter:

```bat
powershell -ExecutionPolicy Bypass -File tools\tracking\osc_capture.ps1 -Seconds 60 -Series "FT/v2/EyeLidLeft"
```

Two lessons from using it:

- My first version of the parser occasionally misread packets and let partial values into the statistics. The current one drops a packet entirely if any part fails to parse and reports how many it dropped.
- A median over a whole minute can hide the fact that your face was not in view. Read the time series: if values drop to 0 for several seconds, tracking was lost, not your eyes closed.

Do not start by moving sensitivity sliders. If a value is low because the tracker reads it low, a higher sensitivity also exaggerates everything else on that parameter (for eyelids, blinks become extreme).

## VR mode

The avatar does not care where the tracking comes from; VR only changes the VRCFaceTracking module. A webcam cannot see your face under a headset, so VR needs face or eye tracking hardware. Options I looked at but have not bought or tested:

- Project Babble mouth tracker (lower face)
- EyeTrackVR (eyes, DIY)
- A headset with built-in face and eye tracking that VRCFaceTracking supports

## Known limitations

| Limitation | Status |
| --- | --- |
| Eyes look half closed with default settings | Open; see Calibration |
| Calibration, per-expression scoring, smoothing | Not done yet |
| Desktop mode only | By design of webcam tracking |
| Needs your whole face in good, even light | FoxyFace is a camera-based tracker; a dark room or a strong backlight degrades it |
| Windows only | FoxyFace and VRCFaceTracking are Windows programs |
| Tested with FoxyFace 1.0.5.1 and a 720p laptop webcam only | Other cameras and newer FoxyFace versions untested |
