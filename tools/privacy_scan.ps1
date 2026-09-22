# Scans the repository for things that must not be published: VRChat IDs, local paths, e-mail
# addresses, and MetaHuman asset files. Run before every push:
#
#   powershell -ExecutionPolicy Bypass -File tools\privacy_scan.ps1
#
# Exits 1 if anything is found.

$root = Split-Path -Parent $PSScriptRoot
$patterns = [ordered]@{
    'VRChat user ID'       = 'usr_[0-9a-f]{8}-'
    'VRChat avatar ID'     = 'avtr_[0-9a-f]{8}-'
    'VRChat world ID'      = 'wrld_[0-9a-f]{8}-'
    'Windows user path'    = '[A-Za-z]:[\\/]Users[\\/](?!<)[^\\/\s"]+'
    # Any absolute drive path except the placeholders the docs use on purpose.
    'Local drive path'     = '\b[A-Z]:[\\/](?!path[\\/]to|Unity\b|Program Files)[A-Za-z]'
    'E-mail address'       = '[A-Za-z0-9._%+-]+@(gmail|outlook|hotmail|yahoo|icloud)\.com'
}
$assetExtensions = '.dna', '.fbx', '.blend', '.blend1', '.uasset', '.vrca'

$files = git -C $root ls-files --cached --others --exclude-standard
$hits = 0
foreach ($rel in $files) {
    $path = Join-Path $root $rel
    if ($assetExtensions -contains [IO.Path]::GetExtension($rel).ToLower()) {
        "ASSET    $rel"; $hits++; continue
    }
    if ($rel -like 'tools/privacy_scan.ps1') { continue }
    if ('.png', '.jpg', '.gif', '.mp4', '.webm' -contains [IO.Path]::GetExtension($rel).ToLower()) { continue }
    if ((Get-Item $path).Length -gt 5MB) { continue }
    $text = [IO.File]::ReadAllText($path)
    foreach ($name in $patterns.Keys) {
        foreach ($m in [regex]::Matches($text, $patterns[$name])) {
            "{0,-20} {1}: {2}" -f $name, $rel, $m.Value; $hits++
        }
    }
}
if ($hits -eq 0) { "privacy scan: clean ($($files.Count) files)"; exit 0 }
"privacy scan: $hits finding(s)"; exit 1
