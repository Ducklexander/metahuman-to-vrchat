# Checks the webcam face-tracking chain without opening any GUI:
#
#   webcam -> FoxyFace --UDP 25747--> VRCFaceTracking module --OSC 9000--> VRChat
#                                     VRChat --OSC 9001--> VRCFaceTracking (avatar change notices)
#
# Usage (PowerShell 5.1 or 7):
#   powershell -ExecutionPolicy Bypass -File tools\tracking\check_ft_ports.ps1
#
# Each line says which link is up, and for a broken link, the most likely cause.

$ErrorActionPreference = 'SilentlyContinue'

function Get-Owner([int]$port) {
    $endpoint = Get-NetUDPEndpoint -LocalPort $port | Select-Object -First 1
    if (-not $endpoint) { return $null }
    $process = Get-Process -Id $endpoint.OwningProcess
    [PSCustomObject]@{ Port = $port; Pid = $endpoint.OwningProcess; Name = $process.ProcessName }
}

$checks = @(
    @{ Port = 25747; Expect = 'VRCFaceTracking.ModuleProcess'; Link = 'FoxyFace -> VRCFT module'
       Fix  = 'The FoxyFace module is not loaded. Install it from the VRCFaceTracking Module Registry (not by copying the DLL), start FoxyFace BEFORE VRCFaceTracking, and restart VRCFaceTracking if it was started first (the module only searches for FoxyFace for 60 s).' },
    @{ Port = 9000;  Expect = 'VRChat'; Link = 'VRCFT -> VRChat'
       Fix  = 'VRChat is not listening for OSC. In VRChat: Action Menu > Options > OSC > Enabled. Restart VRChat if the toggle is on but the port stays closed.' },
    @{ Port = 9001;  Expect = 'VRCFaceTracking'; Link = 'VRChat -> VRCFT'
       Fix  = 'VRCFaceTracking is not running or has no window. Start it through Steam (steam://rungameid/3329480); launching the exe directly started a process with no window and no ports in my tests.' }
)

"Processes"
"---------"
foreach ($name in 'FoxyFace', 'VRCFaceTracking', 'VRCFaceTracking.ModuleProcess', 'VRChat') {
    $p = Get-Process -Name $name
    if ($p) { "  running   {0,-32} pid {1}" -f $name, (($p | ForEach-Object Id) -join ', ') }
    else    { "  missing   {0}" -f $name }
}
""
"Ports"
"-----"
$broken = 0
foreach ($c in $checks) {
    $owner = Get-Owner $c.Port
    if ($owner -and $owner.Name -like "$($c.Expect)*") {
        "  OK      {0,-6} {1,-26} bound by {2} (pid {3})" -f $c.Port, $c.Link, $owner.Name, $owner.Pid
    } elseif ($owner) {
        $broken++
        "  CHECK   {0,-6} {1,-26} bound by {2} (pid {3}), expected {4}" -f $c.Port, $c.Link, $owner.Name, $owner.Pid, $c.Expect
    } else {
        $broken++
        "  DOWN    {0,-6} {1,-26} nobody is listening" -f $c.Port, $c.Link
        "          -> $($c.Fix)"
    }
}
""
if ($broken -eq 0) { "All three links are up. If the face still does not move, check that the avatar has the face-tracking template and that VRChat has loaded it (VRChat writes an OSC config for it under %USERPROFILE%\AppData\LocalLow\VRChat\VRChat\OSC\)." }
else { "$broken link(s) need attention. Start order that works: FoxyFace, then VRCFaceTracking, then enable OSC in VRChat." }
