# Build Korean satellite assembly for Devolutions.Resources
# Prerequisites:
#   - .NET 8 SDK (dotnet on PATH, or set $env:DOTNET_ROOT)
#   - translated JSON in _extract/ko/*.ko.json
#   - (optional) Python venv with dnfile for post-build verify

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

function Resolve-DotNet {
    if ($env:DOTNET_ROOT -and (Test-Path (Join-Path $env:DOTNET_ROOT "dotnet.exe"))) {
        return (Join-Path $env:DOTNET_ROOT "dotnet.exe")
    }
    foreach ($candidate in @(
        "C:\dotnet-sdk-full\dotnet.exe",
        "$env:ProgramFiles\dotnet\dotnet.exe",
        "${env:ProgramFiles(x86)}\dotnet\dotnet.exe"
    )) {
        if ($candidate -and (Test-Path $candidate)) {
            $env:DOTNET_ROOT = Split-Path -Parent $candidate
            return $candidate
        }
    }
    $cmd = Get-Command dotnet -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "dotnet (.NET 8 SDK) not found. Install SDK or set DOTNET_ROOT."
}

$dotnet = Resolve-DotNet
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"
Write-Host "Using dotnet: $dotnet"

$koJson = Join-Path $Root "_extract\ko"
$resDir = Join-Path $Root "_tools\KoSatellite\Resources"
$outKo = Join-Path $Root "ko"
New-Item -ItemType Directory -Force -Path $resDir, $outKo | Out-Null

# Ensure ResWriter
$rwProj = Join-Path $Root "_tools\ResWriter\ResWriter.csproj"
$rwOut = Join-Path $Root "_tools\ResWriter\bin"
& $dotnet build $rwProj -c Release -o $rwOut | Out-Host
$rwDll = Join-Path $rwOut "ResWriter.dll"

$map = @(
  @{ Json = "LogResources.ko.json"; Res = "Devolutions.Resources.Properties.LogResources.ko.resources" },
  @{ Json = "MsgResources.ko.json"; Res = "Devolutions.Resources.Properties.MsgResources.ko.resources" },
  @{ Json = "UIResources.ko.json"; Res = "Devolutions.Resources.Properties.UIResources.ko.resources" }
)

foreach ($m in $map) {
  $src = Join-Path $koJson $m.Json
  if (-not (Test-Path -LiteralPath $src)) { throw "Missing $src" }
  $dst = Join-Path $resDir $m.Res
  Write-Host "Writing $($m.Res) ..."
  & $dotnet exec $rwDll $src $dst
  if ($LASTEXITCODE -ne 0) { throw "ResWriter failed for $($m.Json)" }
}

$satProj = Join-Path $Root "_tools\KoSatellite\KoSatellite.csproj"
$satOut = Join-Path $Root "_tools\KoSatellite\bin"
& $dotnet build $satProj -c Release -o $satOut | Out-Host
if ($LASTEXITCODE -ne 0) { throw "Satellite build failed" }

# SDK emits the real satellite under <out>/ko/Devolutions.Resources.resources.dll
$built = Get-ChildItem -Path (Join-Path $satOut "ko") -Filter "Devolutions.Resources.resources.dll" -ErrorAction SilentlyContinue |
  Select-Object -First 1
if (-not $built) {
  $built = Get-ChildItem -Path $satOut -Recurse -Filter "Devolutions.Resources.resources.dll" |
    Where-Object { $_.Directory.Name -eq "ko" } | Select-Object -First 1
}
if (-not $built) {
  Write-Host "Outputs:"
  Get-ChildItem -Path $satOut -Recurse | ForEach-Object { $_.FullName }
  throw "Built satellite DLL not found"
}

$dest = Join-Path $outKo "Devolutions.Resources.resources.dll"
Copy-Item -LiteralPath $built.FullName -Destination $dest -Force
Write-Host "OK -> $dest ($((Get-Item -LiteralPath $dest).Length) bytes)"

# Also refresh deploy package
$deployDll = Join-Path $Root "deploy\ko\Devolutions.Resources.resources.dll"
New-Item -ItemType Directory -Force -Path (Split-Path $deployDll) | Out-Null
Copy-Item -LiteralPath $dest -Destination $deployDll -Force
Write-Host "OK -> $deployDll"

# Verify culture via dnfile (optional)
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
try {
  & $py -c @"
import dnfile
pe = dnfile.dnPE(r'$dest')
for row in pe.net.mdtables.Assembly:
    print('Assembly', row.Name, 'Culture=', repr(str(row.Culture)), 'Ver=', f'{row.MajorVersion}.{row.MinorVersion}.{row.BuildNumber}.{row.RevisionNumber}')
for row in pe.net.mdtables.ManifestResource:
    print('MR', row.Name)
"@
} catch {
  Write-Host "Skip dnfile verify (install: pip install dnfile)"
}
