# Records the avatar parameters VRChat sends out over OSC and prints n / min / median / max per
# parameter, plus a 5-second time series for one parameter so you can tell whether the person
# actually held each pose (a single median over a whole minute can hide a lost face).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File tools\tracking\osc_capture.ps1 -Seconds 60 -Series 'FT/v2/EyeLidLeft'
#
# VRChat sends to UDP 9001. If another program already holds 9001 (VRCFaceTracking can), the
# script says so and exits; nothing is changed on the system.
#
# Each packet is parsed on its own: a packet that fails to parse is dropped whole and counted as
# "unparseable", so one malformed datagram cannot skew the numbers. (An earlier version without
# this isolation produced values I could not trust.)

param(
    [int]$Port = 9001,
    [int]$Seconds = 60,
    [string]$Filter = 'EyeLid|EyeSquint|JawOpen|BrowInnerUp',
    [string]$Series = 'FT/v2/EyeLidLeft'
)


function Read-OscString {
    param([byte[]]$Buf, [ref]$Idx, [int]$End)
    $start = $Idx.Value
    while ($Idx.Value -lt $End -and $Buf[$Idx.Value] -ne 0) { $Idx.Value++ }
    if ($Idx.Value -ge $End) { throw 'unterminated string' }
    $len = $Idx.Value - $start
    $s = [Text.Encoding]::ASCII.GetString($Buf, $start, $len)
    $Idx.Value = $start + [int]([Math]::Ceiling(($len + 1) / 4.0) * 4)
    return $s
}

function Read-OscInt32 {
    param([byte[]]$Buf, [ref]$Idx, [int]$End)
    if (($Idx.Value + 4) -gt $End) { throw 'truncated int32' }
    $b = @($Buf[$Idx.Value], $Buf[$Idx.Value + 1], $Buf[$Idx.Value + 2], $Buf[$Idx.Value + 3])
    [Array]::Reverse($b)
    $Idx.Value += 4
    return [BitConverter]::ToInt32([byte[]]$b, 0)
}

function Read-OscFloat32 {
    param([byte[]]$Buf, [ref]$Idx, [int]$End)
    if (($Idx.Value + 4) -gt $End) { throw 'truncated float32' }
    $b = @($Buf[$Idx.Value], $Buf[$Idx.Value + 1], $Buf[$Idx.Value + 2], $Buf[$Idx.Value + 3])
    [Array]::Reverse($b)
    $Idx.Value += 4
    return [BitConverter]::ToSingle([byte[]]$b, 0)
}

function Parse-OscPacket {
    param([byte[]]$Buf, [int]$Offset, [int]$End, [System.Collections.ArrayList]$Out)
    $i = $Offset
    $addr = Read-OscString $Buf ([ref]$i) $End

    if ($addr -eq '#bundle') {
        if (($i + 8) -gt $End) { throw 'truncated bundle timetag' }
        $i += 8
        while ($i -lt $End) {
            $size = Read-OscInt32 $Buf ([ref]$i) $End
            if ($size -le 0 -or ($i + $size) -gt $End) { throw 'bad bundle element size' }
            Parse-OscPacket $Buf $i ($i + $size) $Out
            $i += $size
        }
        return
    }

    $tags = Read-OscString $Buf ([ref]$i) $End
    if (-not $tags.StartsWith(',')) { throw 'missing type tag string' }

    foreach ($t in $tags.Substring(1).ToCharArray()) {
        switch ($t) {
            'f' { [void]$Out.Add(@($addr, [double](Read-OscFloat32 $Buf ([ref]$i) $End))) }
            'i' { [void]$Out.Add(@($addr, [double](Read-OscInt32   $Buf ([ref]$i) $End))) }
            'T' { [void]$Out.Add(@($addr, 1.0)) }
            'F' { [void]$Out.Add(@($addr, 0.0)) }
            'N' { [void]$Out.Add(@($addr, 0.0)) }
            'd' { if (($i + 8) -gt $End) { throw 'truncated double' }; $i += 8 }
            's' { [void](Read-OscString $Buf ([ref]$i) $End) }
            'b' { $n = Read-OscInt32 $Buf ([ref]$i) $End
                  $i += [int]([Math]::Ceiling($n / 4.0) * 4) }
            default { throw "unsupported type tag '$t'" }
        }
    }
}

try {
    $udp = New-Object System.Net.Sockets.UdpClient($Port)
} catch {
    "ERROR: cannot bind UDP $Port -- $($_.Exception.Message)"
    exit 1
}
$udp.Client.ReceiveTimeout = 500
$ep = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any, 0)

$samples = @{}                                   # name -> List[double]
$series  = [System.Collections.Generic.List[object]]::new()
$t0      = Get-Date
$deadline = $t0.AddSeconds($Seconds)
$packets = 0
$failed  = 0

"Listening on UDP $Port for $Seconds s ..."
while ((Get-Date) -lt $deadline) {
    try { $data = $udp.Receive([ref]$ep) }
    catch [System.Net.Sockets.SocketException] { continue }

    $packets++
    $pending = New-Object System.Collections.ArrayList
    try { Parse-OscPacket $data 0 $data.Length $pending }
    catch { $failed++; continue }

    $elapsed = ((Get-Date) - $t0).TotalSeconds
    foreach ($rec in $pending) {
        $name = $rec[0] -replace '^/avatar/parameters/', ''
        if ($name -notmatch $Filter) { continue }
        if (-not $samples.ContainsKey($name)) {
            $samples[$name] = [System.Collections.Generic.List[double]]::new()
        }
        $samples[$name].Add($rec[1])
        if ($name -eq $Series) { $series.Add([PSCustomObject]@{ T = $elapsed; V = $rec[1] }) }
    }
}
$udp.Close()

"packets: $packets   unparseable: $failed"
""
"{0,-28} {1,6} {2,8} {3,8} {4,8}" -f 'parameter', 'n', 'min', 'median', 'max'
"-" * 64
foreach ($k in ($samples.Keys | Sort-Object)) {
    $v = $samples[$k]
    $sorted = @($v | Sort-Object)
    "{0,-28} {1,6} {2,8:N3} {3,8:N3} {4,8:N3}" -f `
        $k, $v.Count, ($v | Measure-Object -Minimum).Minimum,
        $sorted[[int]($sorted.Count / 2)], ($v | Measure-Object -Maximum).Maximum
}

if ($series.Count -gt 0) {
    ""
    "=== $Series per 5-second bucket ==="
    "{0,-10} {1,6} {2,8} {3,8} {4,8}" -f 'window', 'n', 'min', 'median', 'max'
    "-" * 46
    foreach ($g in ($series | Group-Object { [int]([Math]::Floor($_.T / 5)) * 5 } | Sort-Object { [int]$_.Name })) {
        $vals = @($g.Group.V | Sort-Object)
        "{0,-10} {1,6} {2,8:N3} {3,8:N3} {4,8:N3}" -f `
            "$($g.Name)-$([int]$g.Name + 5)s", $vals.Count, $vals[0],
            $vals[[int]($vals.Count / 2)], $vals[$vals.Count - 1]
    }
}
