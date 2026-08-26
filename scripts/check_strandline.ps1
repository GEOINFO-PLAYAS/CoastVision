param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\")).Path,
    [string]$StrandlineBin = $env:STRANDLINE_BIN,
    [string]$Site = "cartagena",
    [string]$PythonPath,
    [switch]$SkipBenchmark
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$ParentRoot = Split-Path -Parent $ProjectRoot

function Invoke-PythonChecked([string[]]$Arguments) {
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Falló Python con código ${LASTEXITCODE}: python $($Arguments -join ' ')"
    }
}

$Python = $PythonPath
if (-not $Python) {
    $venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $Python = $venvPython
    }
}
if (-not $Python) {
    $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCommand) {
        $Python = $PythonCommand.Source
        if (-not $Python) {
            $Python = $PythonCommand.Definition
        }
    }
}
if (-not $Python) {
    throw "No se encontró Python. Prepara .venv antes de continuar."
}

if (-not $StrandlineBin) {
    $candidate = Join-Path $ParentRoot "strandline\target\release\strandline.exe"
    if (Test-Path $candidate) {
        $StrandlineBin = $candidate
    } else {
        $candidate = Join-Path $ParentRoot "strandline\target\release\strandline"
        if (Test-Path $candidate) {
            $StrandlineBin = $candidate
        }
    }
}
if (-not $StrandlineBin) {
    throw "No se encontró strandline. Ejecuta scripts\setup_strandline.ps1 primero."
}
$StrandlineBin = (Resolve-Path $StrandlineBin).Path

Write-Host "1/3 Pruebas del adaptador..." -ForegroundColor Cyan
Invoke-PythonChecked @("-m", "pytest", "-q", "tests\test_strandline.py")

Write-Host "2/3 Ejecución real de strandline ($Site)..." -ForegroundColor Cyan
Invoke-PythonChecked @("scripts\13_run_strandline.py", "--strandline-bin", $StrandlineBin, "--site", $Site, "--along-dist", "25", "--min-valid", "3")

if (-not $SkipBenchmark) {
    Write-Host "3/3 Benchmark..." -ForegroundColor Cyan
    Invoke-PythonChecked @("scripts\14_benchmark_strandline.py", "--strandline-bin", $StrandlineBin, "--site", $Site, "--runs", "3")
}

Write-Host "Verificación de strandline finalizada correctamente." -ForegroundColor Green
