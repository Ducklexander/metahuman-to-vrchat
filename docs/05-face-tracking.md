# 5. Webcam face tracking

```
webcam -> FoxyFace -> VRCFaceTracking (FoxyFace module) -> OSC -> VRChat -> ARKit template -> blendshapes
```

FoxyFace needs to see your whole face, so this works in desktop mode only. Windows only.

## Install

1. **FoxyFace**: download the full release (with GPU models) from [github.com/Jeka8833/FoxyFace/releases](https://github.com/Jeka8833/FoxyFace/releases) and unzip it.
2. **VRCFaceTracking**: install it from Steam and start it once.
3. **FoxyFace module**: in VRCFaceTracking, open the Module Registry, search for FoxyFace and install **FoxyFaceVRCFTInterface**. Install it from the registry; copying the DLL into the folder by hand does not register it.

## Start, in this order

1. **FoxyFace**, and check that it shows your face.
2. **VRCFaceTracking**, through Steam. Started directly from the exe, it ran without a window for me.
3. **VRChat**: switch to your avatar, then Action Menu > Options > OSC > **Enabled**.

The module looks for FoxyFace for 60 seconds after it loads. If you started VRCFaceTracking first, restart it.

## Check

```bat
powershell -ExecutionPolicy Bypass -File tools\tracking\check_ft_ports.ps1
```

It shows which of the three links is down and what to do:

| Port | Should be held by | If not |
| --- | --- | --- |
| 25747 | `VRCFaceTracking.ModuleProcess` | The FoxyFace module did not load |
| 9000 | `VRChat` | OSC is off in VRChat |
| 9001 | `VRCFaceTracking` | VRCFaceTracking is not running properly |

In VRChat, the template adds a Face Tracking menu with a debug display that shows each parameter live.

## Calibration

Not finished in my setup: with the defaults the eyes look a bit too closed. In Jerry's ARKit template, the eyelid parameter treats 0.75 as relaxed open, so the value coming in is too low. To see what your avatar receives, record it (close VRCFaceTracking first if it holds port 9001):

```bat
powershell -ExecutionPolicy Bypass -File tools\tracking\osc_capture.ps1 -Seconds 60 -Series "FT/v2/EyeLidLeft"
```

If the eyelid median sits well below 0.75 while your eyes are relaxed, calibrate FoxyFace's neutral pose; if it is near 0.75, lower the template's eyelid sensitivity instead. Values dropping to 0 for seconds at a time mean the camera lost your face.

## VR

The avatar does not change for VR; only the VRCFaceTracking module does. A webcam cannot see your face under a headset, so VR needs face or eye tracking hardware that VRCFaceTracking supports. I have not tried any.
