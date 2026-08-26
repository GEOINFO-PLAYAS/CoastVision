param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\")).Path,
    [string]$StrandlineCommit = "fdd5a2fd1cb75389aa0579763d21f751205c30bb"
)

$ErrorActionPreference = "Stop"

function Require-Command([string]$Name, [string]$InstallHint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "No se encontró '$Name'. $InstallHint"
    }
}

function Invoke-Checked([string]$Command, [string[]]$Arguments, [string]$WorkingDirectory) {
    Push-Location $WorkingDirectory
    try {
        & $Command @Arguments
        $exitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($exitCode -ne 0) {
        throw "Falló '$Command $($Arguments -join ' ')'. Código: $exitCode"
    }
}

Require-Command "git" "Instala Git antes de continuar."
Require-Command "python" "Instala Python 3.11 o superior antes de continuar."
Require-Command "cargo" "Instala Rust desde https://rustup.rs/ y abre una nueva terminal."

$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$ParentRoot = Split-Path -Parent $ProjectRoot
$StrandlineRoot = Join-Path $ParentRoot "strandline"
$SurtgisRoot = Join-Path $ParentRoot "surtgis"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creando entorno Python de CoastVision..." -ForegroundColor Cyan
    Invoke-Checked "python" @("-m", "venv", ".venv") $ProjectRoot
    $VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        throw "Python creó el entorno, pero no apareció .venv\Scripts\python.exe."
    }
    Write-Host "Instalando dependencias Python..." -ForegroundColor Cyan
    Invoke-Checked $VenvPython @("-m", "pip", "install", "-r", "requirements.txt") $ProjectRoot
}

if (-not (Test-Path (Join-Path $StrandlineRoot ".git"))) {
    if (Test-Path $StrandlineRoot) {
        throw "Ya existe '$StrandlineRoot', pero no parece ser un repositorio Git de strandline."
    }
    Write-Host "Clonando strandline..." -ForegroundColor Cyan
    Invoke-Checked "git" @("clone", "https://github.com/franciscoparrao/strandline.git", $StrandlineRoot) $ParentRoot
}

if (-not (Test-Path (Join-Path $SurtgisRoot ".git"))) {
    if (Test-Path $SurtgisRoot) {
        throw "Ya existe '$SurtgisRoot', pero no parece ser un repositorio Git de surtgis."
    }
    Write-Host "Clonando surtgis (dependencia de strandline)..." -ForegroundColor Cyan
    Invoke-Checked "git" @("clone", "https://github.com/franciscoparrao/surtgis.git", $SurtgisRoot) $ParentRoot
}

if (-not (Test-Path (Join-Path $SurtgisRoot "crates\core\Cargo.toml"))) {
    throw "El repositorio surtgis no contiene crates\core\Cargo.toml en la ubicación esperada."
}
if (-not (Test-Path (Join-Path $SurtgisRoot "crates\cloud\Cargo.toml"))) {
    throw "El repositorio surtgis no contiene crates\cloud\Cargo.toml en la ubicación esperada."
}

$dirty = & git -C $StrandlineRoot status --porcelain
if ($dirty) {
    throw "strandline tiene cambios locales. Guárdalos o usa otra copia antes de cambiar al commit requerido."
}

Write-Host "Fijando strandline en el commit $StrandlineCommit..." -ForegroundColor Cyan
Invoke-Checked "git" @("-C", $StrandlineRoot, "checkout", $StrandlineCommit) $ParentRoot

Write-Host "Compilando strandline en modo release..." -ForegroundColor Cyan
Invoke-Checked "cargo" @("build", "--release", "--features", "cloud") $StrandlineRoot

$Binary = Join-Path $StrandlineRoot "target\release\strandline.exe"
if (-not (Test-Path $Binary)) {
    $Binary = Join-Path $StrandlineRoot "target\release\strandline"
}
if (-not (Test-Path $Binary)) {
    throw "La compilación terminó, pero no se encontró el ejecutable strandline."
}

Write-Host "strandline quedó instalado correctamente:" -ForegroundColor Green
Write-Host $Binary
Write-Host "En esta terminal puedes configurar la ruta con:"
Write-Host ('$env:STRANDLINE_BIN="' + $Binary + '"')
