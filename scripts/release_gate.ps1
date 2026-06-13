param(
    [string]$Python = "python"
)

# Contract commands covered by this script:
# python -m build
# python -m compileall
# python -m flatten --help
# python -m flatten_polymorph --help
# python -m mypy --strict
# python -m flatten analyze
# python -m flatten trace
# python -m flatten plan
# python -m flatten rewrite
# python -m flatten verify
# python -m flatten benchmark

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $true
}

function Assert-LastExitCode {
    param([string]$Label)
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

& $Python -m pip install --upgrade build | Out-Host
Assert-LastExitCode "pip install build"
& $Python -m build | Out-Host
Assert-LastExitCode "build"

$repo = (Get-Location).Path
$venv = Join-Path ([System.IO.Path]::GetTempPath()) ("flatten-release-gate-" + [System.Guid]::NewGuid())
& $Python -m venv $venv
Assert-LastExitCode "venv"

$venvPython = Join-Path $venv "Scripts/python.exe"
if (-not (Test-Path $venvPython)) {
    $venvPython = Join-Path $venv "bin/python"
}

$wheel = Get-ChildItem -Path (Join-Path $repo "dist") -Filter "flatten_polymorph-*.whl" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if ($null -eq $wheel) {
    throw "No flatten_polymorph wheel found in dist/"
}

& $venvPython -m pip install --upgrade pip | Out-Host
Assert-LastExitCode "venv pip upgrade"
& $venvPython -m pip install $wheel.FullName "mypy>=1.8" | Out-Host
Assert-LastExitCode "venv wheel install"

$flattenPath = (& $venvPython -c "import pathlib, flatten; print(pathlib.Path(flatten.__file__).parent)").Trim()
$shimPath = (& $venvPython -c "import pathlib, flatten_polymorph; print(pathlib.Path(flatten_polymorph.__file__).parent)").Trim()

& $venvPython -m compileall $flattenPath $shimPath | Out-Host
Assert-LastExitCode "compileall"
& $venvPython -m flatten --help | Out-Host
Assert-LastExitCode "flatten help"
& $venvPython -m flatten_polymorph --help | Out-Host
Assert-LastExitCode "flatten_polymorph help"
& $venvPython -m mypy --strict -p flatten -p flatten_polymorph | Out-Host
Assert-LastExitCode "installed mypy strict"

$caseDir = Join-Path $venv "e2e"
New-Item -ItemType Directory -Force -Path $caseDir | Out-Null
$sample = Join-Path $caseDir "shapes.py"
$obs = Join-Path $caseDir "obs.json"
$plan = Join-Path $caseDir "plan.json"
$rewritten = Join-Path $caseDir "rewritten.py"
$cases = Join-Path $caseDir "cases.json"
$benchmarkJson = Join-Path $caseDir "benchmark_summary.json"
$benchmarkMd = Join-Path $caseDir "benchmark_summary.md"

$sampleSource = @'
from typing import final

@final
class Shape:
    def area(self):
        return 2

def entry():
    s = Shape()
    return s.area()
'@
[System.IO.File]::WriteAllText(
    $sample,
    $sampleSource,
    [System.Text.UTF8Encoding]::new($false)
)
[System.IO.File]::WriteAllText(
    $cases,
    '[{"args":[],"kwargs":{}}]',
    [System.Text.UTF8Encoding]::new($false)
)

& $venvPython -m flatten analyze $sample --json | Out-Host
Assert-LastExitCode "flatten analyze"
& $venvPython -m flatten trace $sample --entry shapes:entry --out $obs | Out-Host
Assert-LastExitCode "flatten trace"
& $venvPython -m flatten plan $sample --observations $obs --out $plan | Out-Host
Assert-LastExitCode "flatten plan"
& $venvPython -m flatten rewrite $sample --observations $obs --out $rewritten --apply --entry shapes:entry --cases $cases | Out-Host
Assert-LastExitCode "flatten rewrite"
& $venvPython -m flatten verify $sample $rewritten --entry shapes:entry --cases $cases | Out-Host
Assert-LastExitCode "flatten verify"
& $venvPython -m flatten benchmark --catalog (Join-Path $repo "benchmarks/projects.csv") --out-json $benchmarkJson --out-md $benchmarkMd | Out-Host
Assert-LastExitCode "flatten benchmark"

Write-Host "release gate passed"
