[CmdletBinding()]
param(
    [string]$OutputDirectory,
    [string]$SourceDirectory
)

# Mantener este archivo en UTF-8 con BOM: Windows PowerShell 5.1 interpreta
# incorrectamente los literales en español cuando un .ps1 UTF-8 no tiene BOM.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $ProjectRoot "versiones_incrementales"
}
if (-not $SourceDirectory) {
    $SourceDirectory = $ProjectRoot
}
$SourceRoot = (Resolve-Path -LiteralPath $SourceDirectory).Path

$projectRootFull = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd("\")
$sourceRootFull = [System.IO.Path]::GetFullPath($SourceRoot).TrimEnd("\")
$outputFull = [System.IO.Path]::GetFullPath($OutputDirectory).TrimEnd("\")
$projectPrefix = $projectRootFull + "\"

if (
    $outputFull -eq $projectRootFull -or
    -not $outputFull.StartsWith($projectPrefix, [System.StringComparison]::OrdinalIgnoreCase)
) {
    throw "La salida debe permanecer dentro del proyecto y no puede ser la raíz: $outputFull"
}
if (-not $sourceRootFull.StartsWith($projectPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "La fuente debe permanecer dentro del proyecto: $sourceRootFull"
}

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )

    $parent = Split-Path -Parent $Path
    if ($parent) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $normalized = $Content.Replace("`r`n", "`n").Replace("`r", "`n")
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $normalized, $encoding)
}

function Get-RelativePathPosix {
    param(
        [Parameter(Mandatory = $true)][string]$BaseDirectory,
        [Parameter(Mandatory = $true)][string]$FilePath
    )

    $basePath = [System.IO.Path]::GetFullPath($BaseDirectory).TrimEnd("\") + "\"
    $absolutePath = [System.IO.Path]::GetFullPath($FilePath)
    $baseUri = New-Object System.Uri($basePath)
    $fileUri = New-Object System.Uri($absolutePath)
    return [System.Uri]::UnescapeDataString($baseUri.MakeRelativeUri($fileUri).ToString())
}

function Get-ProjectHashMap {
    param([Parameter(Mandatory = $true)][string]$ProjectDirectory)

    $map = @{}
    $files = Get-ChildItem -LiteralPath $ProjectDirectory -Recurse -File |
        Sort-Object FullName
    foreach ($file in $files) {
        $relative = Get-RelativePathPosix -BaseDirectory $ProjectDirectory -FilePath $file.FullName
        if ($relative.StartsWith(".commit-bundle/", [System.StringComparison]::OrdinalIgnoreCase)) {
            continue
        }
        $map[$relative] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    return $map
}

function New-DeterministicZip {
    param(
        [Parameter(Mandatory = $true)][string]$SourceDirectory,
        [Parameter(Mandatory = $true)][string]$ZipPath,
        [Parameter(Mandatory = $true)][datetimeoffset]$Timestamp
    )

    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }

    $fileStream = [System.IO.File]::Open(
        $ZipPath,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None
    )
    $archive = New-Object System.IO.Compression.ZipArchive(
        $fileStream,
        [System.IO.Compression.ZipArchiveMode]::Create,
        $false
    )

    try {
        $files = Get-ChildItem -LiteralPath $SourceDirectory -Recurse -File |
            Sort-Object { Get-RelativePathPosix -BaseDirectory $SourceDirectory -FilePath $_.FullName }
        foreach ($file in $files) {
            $relative = Get-RelativePathPosix -BaseDirectory $SourceDirectory -FilePath $file.FullName
            $entryName = "CoastVision/$relative"
            $entry = $archive.CreateEntry(
                $entryName,
                [System.IO.Compression.CompressionLevel]::Optimal
            )
            $entry.LastWriteTime = $Timestamp

            $source = [System.IO.File]::OpenRead($file.FullName)
            $destination = $entry.Open()
            try {
                $source.CopyTo($destination)
            }
            finally {
                $destination.Dispose()
                $source.Dispose()
            }
        }
    }
    finally {
        $archive.Dispose()
        $fileStream.Dispose()
    }
}

function Get-StreamSha256 {
    param([Parameter(Mandatory = $true)][System.IO.Stream]$Stream)

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = $sha.ComputeHash($Stream)
        return ([System.BitConverter]::ToString($bytes)).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Read-ZipEntryText {
    param([Parameter(Mandatory = $true)]$Entry)

    $stream = $Entry.Open()
    $reader = New-Object System.IO.StreamReader(
        $stream,
        (New-Object System.Text.UTF8Encoding($false)),
        $true
    )
    try {
        return $reader.ReadToEnd()
    }
    finally {
        $reader.Dispose()
        $stream.Dispose()
    }
}

function Test-ZipPackage {
    param(
        [Parameter(Mandatory = $true)][string]$ZipPath,
        [Parameter(Mandatory = $true)][hashtable]$ExpectedProjectHashes
    )

    $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        $entries = @($archive.Entries | Where-Object { $_.Name })
        if ($entries.Count -eq 0) {
            throw "ZIP vacío: $ZipPath"
        }

        $seen = @{}
        foreach ($entry in $entries) {
            $name = $entry.FullName.Replace("\", "/")
            if (-not $name.StartsWith("CoastVision/")) {
                throw "Entrada fuera de la raíz CoastVision/: $name"
            }
            if ($name -match '(^/)|(^[A-Za-z]:)|(^|/)\.\.(/|$)') {
                throw "Ruta insegura en ZIP: $name"
            }
            $key = $name.ToLowerInvariant()
            if ($seen.ContainsKey($key)) {
                throw "Entrada duplicada sin distinguir mayúsculas: $name"
            }
            $seen[$key] = $true

            $relative = $name.Substring("CoastVision/".Length)
            if (
                $relative -match '(^|/)(\.git|\.agents|\.codex|\.venv|__pycache__|\.pytest_cache|node_modules|tide_models|logs|tmp)(/|$)' -or
                $relative -match '(^|/)[^/]+\.safe(/|$)' -or
                $relative -match '\.pyc$|\.tiff?$|\.jp2$|\.nc$|\.gpkg$|\.zip$|\.streamlit-.*\.log$' -or
                $relative -match '(^|/)\.env$|(^|/)\.streamlit/secrets\.toml$'
            ) {
                throw "Archivo excluido encontrado en ZIP: $relative"
            }

            if ($relative -match '\.(py|ps1|md|json|csv|txt|toml|ya?ml|ipynb|example)$') {
                $text = Read-ZipEntryText -Entry $entry
                $secretPattern = '(?i)(sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----|(password|passwd|api[_-]?key|secret|token)\s*[:=]\s*["''][^"''`${<\s][^"'']{11,}["''])'
                if ($text -match $secretPattern) {
                    throw "Posible secreto incrustado en ZIP: $relative"
                }
            }
        }

        $hashEntry = $entries | Where-Object {
            $_.FullName -eq "CoastVision/.commit-bundle/FILES.sha256"
        }
        if (@($hashEntry).Count -ne 1) {
            throw "Falta FILES.sha256 único en $ZipPath"
        }

        $declared = @{}
        $hashText = Read-ZipEntryText -Entry $hashEntry
        foreach ($line in ($hashText -split "`n")) {
            $trimmed = $line.TrimEnd("`r")
            if (-not $trimmed) {
                continue
            }
            if ($trimmed -notmatch '^([0-9a-f]{64})  (.+)$') {
                throw "Línea inválida en FILES.sha256: $trimmed"
            }
            $declared[$Matches[2]] = $Matches[1]
        }

        if ($declared.Count -ne $ExpectedProjectHashes.Count) {
            throw "Cantidad de hashes internos distinta en $ZipPath"
        }

        foreach ($relative in ($ExpectedProjectHashes.Keys | Sort-Object)) {
            if (-not $declared.ContainsKey($relative)) {
                throw "Hash no declarado: $relative"
            }
            if ($declared[$relative] -ne $ExpectedProjectHashes[$relative]) {
                throw "Hash declarado incorrecto: $relative"
            }
            $entryName = "CoastVision/$relative"
            $entry = $archive.GetEntry($entryName)
            if (-not $entry) {
                throw "Archivo faltante en ZIP: $entryName"
            }
            $stream = $entry.Open()
            try {
                $actualHash = Get-StreamSha256 -Stream $stream
            }
            finally {
                $stream.Dispose()
            }
            if ($actualHash -ne $ExpectedProjectHashes[$relative]) {
                throw "Contenido corrupto o distinto: $relative"
            }
        }

        foreach ($required in @(
            "CoastVision/.commit-bundle/manifest.json",
            "CoastVision/.commit-bundle/FILES.sha256",
            "CoastVision/.commit-bundle/COMMIT_MESSAGE.txt"
        )) {
            if (-not $archive.GetEntry($required)) {
                throw "Metadato faltante: $required"
            }
        }
    }
    finally {
        $archive.Dispose()
    }
}

function New-StageReadme {
    param([Parameter(Mandatory = $true)]$Version)

    $commands = ($Version.Commands | ForEach-Object { $_ }) -join "`n"
    return @"
# CoastVision

Proyecto académico incremental de geoinformática costera para Playa Grande de Cartagena.

## Estado v$($Version.Number.ToString("00")): $($Version.Title)

$($Version.Summary)

Este snapshot es acumulativo y contiene los hitos anteriores necesarios para reproducir el avance del proyecto.

## Verificación de este hito

```powershell
$commands
```

Resultado esperado: $($Version.Expected -join "; ").

"@
}

try {
    Add-Type -AssemblyName System.IO.Compression -ErrorAction Stop
} catch {
    # El tipo puede estar cargado previamente.
}
try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction Stop
} catch {
    # El tipo puede estar cargado previamente.
}

$versions = @(
    [pscustomobject]@{
        Number = 1
        Slug = "inicializacion"
        Title = "Inicialización del repositorio"
        Commit = "chore: inicializar proyecto CoastVision"
        Summary = "Se crea la base mínima del repositorio, con identidad del proyecto y exclusiones seguras para Git."
        Commands = @("git init", "git status --short")
        Expected = @("repositorio vacío listo para recibir el entorno")
    },
    [pscustomobject]@{
        Number = 2
        Slug = "entorno_geoinformatico"
        Title = "Entorno Python y notebook inicial"
        Commit = "chore: configurar entorno geoinformático y notebook"
        Summary = "Se documentan las dependencias, el laboratorio Jupyter y el chequeo reproducible del entorno geoespacial."
        Commands = @(
            "python -m pip install -r requirements.txt",
            "python scripts/00_check_setup.py"
        )
        Expected = @("dependencias declaradas", "chequeo del entorno ejecutable")
    },
    [pscustomobject]@{
        Number = 3
        Slug = "datos_sinteticos"
        Title = "Datos raster y vector de laboratorio"
        Commit = "feat: generar datos raster y vector de laboratorio"
        Summary = "Se incorpora un generador controlado de bandas verde/NIR, DEM, zonas costeras y una línea de costa ficticia."
        Commands = @("python scripts/01_create_sample_data.py")
        Expected = @("rasters y capas sintéticas regenerables localmente")
    },
    [pscustomobject]@{
        Number = 4
        Slug = "laboratorio_ndwi"
        Title = "Análisis NDWI y cartografía"
        Commit = "feat: calcular NDWI y publicar cartografía"
        Summary = "Se completa el flujo raster/vector con NDWI, estadísticas zonales, mapa estático y mapa Folium."
        Commands = @(
            "python scripts/01_create_sample_data.py",
            "python scripts/02_ndwi_zonal_stats.py",
            "python scripts/03_visualize_results.py"
        )
        Expected = @("CSV de estadísticas", "PNG y HTML cartográficos")
    },
    [pscustomobject]@{
        Number = 5
        Slug = "fuentes_reproducibles"
        Title = "Playa Grande y fuentes reproducibles"
        Commit = "feat: incorporar fuentes reales y procedencia reproducible"
        Summary = "Se define el alcance del MVP y se incorporan el polígono OSM de Playa Grande, elevaciones Open-Meteo, snapshots originales y hashes."
        Commands = @("python scripts/00_refresh_source_data.py --offline")
        Expected = @("69 vértices del arco marino", "33 cotas DEM", "manifiesto reproducible")
    },
    [pscustomobject]@{
        Number = 6
        Slug = "motor_geoespacial"
        Title = "Motor geoespacial y exportación"
        Commit = "feat: implementar motor geoespacial y exportación"
        Summary = "Se implementan CRS, arco marino, estaciones, transectos, elevación, escenarios temporales, franjas y doce artefactos exportables."
        Commands = @("python scripts/04_build_coastvision_mvp.py --year 2035 --retreat-rate 1.5")
        Expected = @("1,87 km cubiertos", "11 estaciones", "12 artefactos del escenario")
    },
    [pscustomobject]@{
        Number = 7
        Slug = "asistente_rag"
        Title = "Asistente local con evidencia"
        Commit = "feat: agregar asistente local con recuperación TF-IDF"
        Summary = "Se añade recuperación TF-IDF sobre una base local y una síntesis LLM opcional, manteniendo un fallback sin API."
        Commands = @(
            "python -c `"import sys; sys.path.insert(0, 'src'); from coastvision.rag import retrieve; print(retrieve('marea y elevación', 1))`""
        )
        Expected = @("respuesta recuperada sin OPENAI_API_KEY")
    },
    [pscustomobject]@{
        Number = 8
        Slug = "app_interactiva"
        Title = "Aplicación Streamlit interactiva"
        Commit = "feat: construir demo interactiva Streamlit"
        Summary = "Se integra el mapa completo, el cambio temporal, la evaluación por clic, elevaciones, enlaces externos, el asistente y un tablero que todavía funciona como hoja de ruta científica."
        Commands = @("python scripts/run_mvp.py")
        Expected = @("aplicación disponible en http://localhost:8501")
    },
    [pscustomobject]@{
        Number = 9
        Slug = "pruebas_documentacion"
        Title = "Pruebas y documentación técnica"
        Commit = "test: validar geometría procedencia y escenarios"
        Summary = "Se añaden 18 pruebas, evidencia JUnit y documentación coherente con el MVP demostrativo; la rama científica se incorpora recién en v10."
        Commands = @("python -m pytest -q --junitxml=outputs/coastvision_mvp/pytest.xml")
        Expected = @("18 pruebas aprobadas", "0 fallos")
    },
    [pscustomobject]@{
        Number = 10
        Slug = "unificacion_requisitos"
        Title = "Unificación y requisitos obligatorios"
        Commit = "feat: unificar pipeline científico y evidencias obligatorias"
        Summary = "Se integran el pipeline multitemporal 2016-2026, las correcciones FES2014, las tasas LRR, el análisis de marejadas, la infraestructura OSM y un semáforo Streamlit conectado al pipeline."
        Commands = @(
            "python scripts/00_refresh_source_data.py --offline",
            "python scripts/04_build_coastvision_mvp.py --year 2035 --retreat-rate 1.5",
            "python scripts/11_build_requirement_status.py",
            "python scripts/12_demo_preflight.py",
            "python -m pytest -q"
        )
        Expected = @("pipeline 2016-2026 reproducible", "semáforo conectado", "7 requisitos auditados", "53 pruebas aprobadas")
    }
)

$minimumVersion = [ordered]@{
    ".gitignore" = 1
    "requirements.txt" = 2
    "notebooks\00_inicio_geoinformatica.ipynb" = 2
    "scripts\00_check_setup.py" = 2
    "scripts\01_create_sample_data.py" = 3
    "scripts\02_ndwi_zonal_stats.py" = 4
    "scripts\03_visualize_results.py" = 4
    "data\linea_costa.geojson" = 4
    "outputs\mapa_interactivo.html" = 4
    "outputs\mapa_ndwi_zonas.png" = 4
    "outputs\zonas_contextily.png" = 4
    "outputs\zonas_ndwi_stats.csv" = 4
    "docs\MVP_SCOPE.md" = 5
    "data\playa_grande_shoreline_osm.geojson" = 5
    "data\elevation_profile_open_meteo.json" = 5
    "data\knowledge_base.json" = 5
    "data\provenance_manifest.json" = 5
    "data\raw\osm_way_300607261.xml" = 5
    "data\raw\open_meteo_elevation_response.json" = 5
    "data\raw\source_receipt.json" = 5
    "data\README.md" = 5
    "src\coastvision\acquisition.py" = 5
    "scripts\00_refresh_source_data.py" = 5
    "src\coastvision\geometry.py" = 6
    "scripts\04_build_coastvision_mvp.py" = 6
    "outputs\README.md" = 6
    "outputs\coastvision_mvp\area_estudio.geojson" = 6
    "outputs\coastvision_mvp\estaciones_medicion.geojson" = 6
    "outputs\coastvision_mvp\franjas_riesgo.geojson" = 6
    "outputs\coastvision_mvp\limites_comparacion.geojson" = 6
    "outputs\coastvision_mvp\lineas_costa.geojson" = 6
    "outputs\coastvision_mvp\muestras_elevacion.geojson" = 6
    "outputs\coastvision_mvp\perfil_elevacion.csv" = 6
    "outputs\coastvision_mvp\predios_demo.geojson" = 6
    "outputs\coastvision_mvp\provenance.json" = 6
    "outputs\coastvision_mvp\resumen.json" = 6
    "outputs\coastvision_mvp\transectos.geojson" = 6
    "outputs\coastvision_mvp\zona_alcanzada.geojson" = 6
    "src\coastvision\rag.py" = 7
    "app.py" = 8
    "scripts\run_mvp.py" = 8
    "docs\DEMO_5_MIN.md" = 8
    "tests\test_mvp.py" = 9
    "outputs\coastvision_mvp\pytest.xml" = 9
    "docs\ARQUITECTURA.md" = 9
    "docs\PIPELINE_Y_DATOS.md" = 9
    "docs\EVIDENCIAS_RUBRICA.md" = 10
    "docs\INFORME_TECNICO_MVP.md" = 10
    "docs\evidence\coastvision_mvp_2035.png" = 10
    ".env.example" = 10
    "data\config\analysis_config.json" = 10
    "data\events\marejadas_oficiales_armada.csv" = 10
    "data\events\catalog_metadata.json" = 10
    "data\events\README.md" = 10
    "data\events\oleaje_era5_cartagena.json" = 10
    "data\external\fes2014\README.md" = 10
    "data\infrastructure\buildings_osm.geojson" = 10
    "data\infrastructure\roads_osm.geojson" = 10
    "data\infrastructure\source_receipt.json" = 10
    "data\raw\osm_infrastructure_playa_grande.json" = 10
    "data\sentinel\catalog_2016_2026.json" = 10
    "data\sentinel\local_assets.example.json" = 10
    "docs\MATRIZ_RUBRICA_E2.md" = 10
    "docs\PRODUCT_BACKLOG_SRS.md" = 10
    "docs\UNIFICACION_Y_CUMPLIMIENTO.md" = 10
    "outputs\demo_preflight.json" = 10
    "outputs\fes2014_validation.json" = 10
    "outputs\infrastructure_risk\buildings_risk.geojson" = 10
    "outputs\infrastructure_risk\roads_risk.geojson" = 10
    "outputs\infrastructure_risk\summary.json" = 10
    "outputs\multitemporal\pipeline_summary.json" = 10
    "outputs\multitemporal\shorelines_2016_2026_fes2014.geojson" = 10
    "outputs\multitemporal\shorelines_raw_ndwi.geojson" = 10
    "outputs\multitemporal\storm_correlation.json" = 10
    "outputs\multitemporal\storm_scene_join.csv" = 10
    "outputs\multitemporal\tide_corrections.csv" = 10
    "outputs\multitemporal\transect_intersections.csv" = 10
    "outputs\multitemporal\transect_intersections.geojson" = 10
    "outputs\multitemporal\transect_rates.csv" = 10
    "outputs\multitemporal\transect_rates.geojson" = 10
    "outputs\multitemporal\transects.geojson" = 10
    "outputs\multitemporal\water_2017.geojson" = 10
    "outputs\multitemporal\water_2016.geojson" = 10
    "outputs\multitemporal\water_2018.geojson" = 10
    "outputs\multitemporal\water_2019.geojson" = 10
    "outputs\multitemporal\water_2020.geojson" = 10
    "outputs\multitemporal\water_2021.geojson" = 10
    "outputs\multitemporal\water_2022.geojson" = 10
    "outputs\multitemporal\water_2023.geojson" = 10
    "outputs\multitemporal\water_2024.geojson" = 10
    "outputs\multitemporal\water_2025.geojson" = 10
    "outputs\multitemporal\water_2026.geojson" = 10
    "outputs\requirement_status.json" = 10
    "outputs\multitemporal_validation_v2\pipeline_summary.json" = 10
    "outputs\multitemporal_validation_v2\shoreline_2017_check.png" = 10
    "outputs\multitemporal_validation_v2\shorelines_raw_ndwi.geojson" = 10
    "outputs\multitemporal_validation_v2\water_2017.geojson" = 10
    "scripts\06_build_sentinel_catalog.py" = 10
    "scripts\07_process_multitemporal.py" = 10
    "scripts\08_refresh_osm_infrastructure.py" = 10
    "scripts\09_validate_fes2014.py" = 10
    "scripts\10_assess_infrastructure.py" = 10
    "scripts\11_build_requirement_status.py" = 10
    "scripts\12_demo_preflight.py" = 10
    "src\coastvision\change_analysis.py" = 10
    "src\coastvision\infrastructure.py" = 10
    "src\coastvision\sentinel.py" = 10
    "src\coastvision\scientific.py" = 10
    "src\coastvision\storms.py" = 10
    "src\coastvision\tides.py" = 10
    "src\coastvision\visual_features.py" = 10
    "src\coastvision\waves.py" = 10
    "tests\test_change_analysis.py" = 10
    "tests\test_infrastructure.py" = 10
    "tests\test_sentinel.py" = 10
    "tests\test_scientific.py" = 10
    "tests\test_storms.py" = 10
    "tests\test_tides.py" = 10
    "tests\test_visual_features.py" = 10
    "tests\test_waves.py" = 10
    "scripts\05_build_incremental_versions.ps1" = 10
}

foreach ($sourceRelative in $minimumVersion.Keys) {
    $sourcePath = Join-Path $SourceRoot $sourceRelative
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        throw "Falta archivo fuente requerido: $sourceRelative"
    }
}

if (Test-Path -LiteralPath $outputFull) {
    # outputFull fue resuelto y validado como descendiente de ProjectRoot antes de borrar.
    Remove-Item -LiteralPath $outputFull -Recurse -Force
}
New-Item -ItemType Directory -Path $outputFull -Force | Out-Null
$stagingRoot = Join-Path $outputFull "_staging"
New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null

$previousHashes = @{}
$zipHashes = @{}
$packageSummaries = @()

foreach ($version in $versions) {
    $versionId = "v{0:D2}" -f $version.Number
    $stageRoot = Join-Path $stagingRoot $versionId
    $projectStage = Join-Path $stageRoot "CoastVision"
    New-Item -ItemType Directory -Path $projectStage -Force | Out-Null

    foreach ($item in $minimumVersion.GetEnumerator()) {
        if ([int]$item.Value -gt $version.Number) {
            continue
        }
        $source = Join-Path $SourceRoot $item.Key
        $destination = Join-Path $projectStage $item.Key
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Force
    }

    $initPath = Join-Path $projectStage "src\coastvision\__init__.py"
    if ($version.Number -eq 5) {
        Write-Utf8NoBom -Path $initPath -Content '"""Adquisición y procedencia de datos para CoastVision."""'
        $minimalGeometryPath = Join-Path $projectStage "src\coastvision\geometry.py"
        $minimalGeometry = @'
"""Geometría mínima para ubicar las consultas de elevación del hito v05."""

from __future__ import annotations

import math

from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.ops import transform


WGS84 = "EPSG:4326"
UTM_19S = "EPSG:32719"
STATION_COUNT = 11
ELEVATION_OFFSETS_M = (50, 150, 250)

_TO_UTM = Transformer.from_crs(WGS84, UTM_19S, always_xy=True)
_TO_WGS84 = Transformer.from_crs(UTM_19S, WGS84, always_xy=True)


def _to_utm(geometry):
    return transform(_TO_UTM.transform, geometry)


def _to_wgs84(geometry):
    return transform(_TO_WGS84.transform, geometry)


def _local_frame(line: LineString, distance_m: float) -> tuple[Point, float, float]:
    distance_m = min(max(distance_m, 0.0), line.length)
    window = min(8.0, max(2.0, line.length / 500.0))
    start = line.interpolate(max(0.0, distance_m - window))
    end = line.interpolate(min(line.length, distance_m + window))
    dx = end.x - start.x
    dy = end.y - start.y
    norm = math.hypot(dx, dy)
    if norm == 0:
        raise ValueError("No se pudo calcular la orientación local de la costa.")
    tx, ty = dx / norm, dy / norm
    return line.interpolate(distance_m), -ty, tx


def elevation_query_points_for_shoreline(
    shoreline_wgs84: LineString,
) -> list[dict[str, float | int | str]]:
    """Genera E01-E11 y offsets 50/150/250 m para consultar el DEM."""
    shoreline = _to_utm(shoreline_wgs84)
    records: list[dict[str, float | int | str]] = []
    spacing = shoreline.length / (STATION_COUNT - 1)
    for index in range(STATION_COUNT):
        station_id = f"E{index + 1:02d}"
        coast, nx, ny = _local_frame(shoreline, spacing * index)
        for offset_m in ELEVATION_OFFSETS_M:
            sample_utm = Point(coast.x + nx * offset_m, coast.y + ny * offset_m)
            sample_wgs84 = _to_wgs84(sample_utm)
            records.append(
                {
                    "station_id": station_id,
                    "offset_m": offset_m,
                    "latitude": round(sample_wgs84.y, 7),
                    "longitude": round(sample_wgs84.x, 7),
                }
            )
    return records
'@
        Write-Utf8NoBom -Path $minimalGeometryPath -Content $minimalGeometry
    }
    elseif ($version.Number -ge 6) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $initPath) -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $SourceRoot "src\coastvision\__init__.py") -Destination $initPath -Force
    }

    # Los archivos que aparecen antes de v10 reciben contenido coherente con
    # ese hito. Así los commits antiguos no describen módulos o artefactos que
    # todavía no existen en su snapshot.
    if ($version.Number -ge 5 -and $version.Number -lt 10) {
        $stageKnowledge = @'
[
  {
    "title": "Alcance del piloto",
    "content": "El MVP se limita a Playa Grande de Cartagena y usa una referencia OSM y cotas Copernicus GLO-90 para explorar un escenario demostrativo.",
    "source": "Informe PEP 1 y alcance MVP",
    "url": ""
  },
  {
    "title": "CoastSat",
    "content": "CoastSat es la referencia metodológica prevista para extraer líneas de costa desde imágenes Sentinel. En este hito todavía no se implementa la rama satelital.",
    "source": "Repositorio oficial CoastSat",
    "url": "https://github.com/kvos/CoastSat"
  },
  {
    "title": "Modelo de riesgo demostrativo",
    "content": "La tasa y los umbrales del visor son parámetros transparentes para explorar escenarios; no son una predicción oficial ni una clasificación regulatoria.",
    "source": "Reglas transparentes del prototipo",
    "url": ""
  },
  {
    "title": "Limitaciones",
    "content": "El borde OSM no es una línea de agua observada y el DEM de 90 m no sustituye topografía, mareas ni trabajo de terreno.",
    "source": "Ficha metodológica CoastVision",
    "url": ""
  },
  {
    "title": "Recomendaciones del profesor",
    "content": "El proyecto debe mantener un problema acotado, documentar fuentes, avanzar por iteraciones y ejecutar el pipeline fuera del notebook.",
    "source": "Clases de Geoinformática",
    "url": ""
  }
]
'@
        $stageKnowledgePath = Join-Path $projectStage "data\knowledge_base.json"
        Write-Utf8NoBom -Path $stageKnowledgePath -Content $stageKnowledge

        $stageDataReadme = @'
# Datos del MVP demostrativo

Entradas activas de este hito:

- `playa_grande_shoreline_osm.geojson`: arco marino de Playa Grande derivado de OpenStreetMap.
- `elevation_profile_open_meteo.json`: 33 cotas Copernicus DEM GLO-90.
- `knowledge_base.json`: evidencia local del asistente.
- `provenance_manifest.json` y `raw/`: URLs, snapshots y hashes reproducibles.

El borde OSM es una referencia espacial, no una línea de agua observada. Las cotas de 90 m son indicativas. Los raster y vectores del laboratorio inicial son sintéticos y no alimentan el semáforo del MVP.
'@
        Write-Utf8NoBom -Path (Join-Path $projectStage "data\README.md") -Content $stageDataReadme

        $stageScope = @'
# CoastVision MVP — alcance del piloto

El piloto se concentra en Playa Grande de Cartagena. Usa el arco marino OSM completo, 11 estaciones E01–E11, transectos de 310 m y 33 cotas GLO-90 a 50, 150 y 250 m tierra adentro.

El producto de esta etapa es demostrativo: permite comunicar dónde se mide, explorar un desplazamiento lineal configurable y evaluar puntos con reglas transparentes. OSM no es una observación satelital; GLO-90 no equivale a marea ni topografía de detalle; los predios son sintéticos.

Los cálculos métricos se realizan en UTM 19S (`EPSG:32719`), los GeoJSON usan WGS84 (`EPSG:4326`) y el lienzo Leaflet se representa en Web Mercator (`EPSG:3857`). La integración Sentinel-2, corrección de marea y tasas observadas queda para un hito científico posterior.
'@
        Write-Utf8NoBom -Path (Join-Path $projectStage "docs\MVP_SCOPE.md") -Content $stageScope

        $stageProvenancePath = Join-Path $projectStage "data\provenance_manifest.json"
        $stageProvenance = Get-Content -LiteralPath $stageProvenancePath -Raw -Encoding UTF8 | ConvertFrom-Json
        $knowledgeInput = $stageProvenance.active_inputs | Where-Object { $_.path -eq "data/knowledge_base.json" }
        $knowledgeInput.sha256 = (Get-FileHash -LiteralPath $stageKnowledgePath -Algorithm SHA256).Hash.ToLowerInvariant()
        Write-Utf8NoBom -Path $stageProvenancePath -Content (($stageProvenance | ConvertTo-Json -Depth 12) + "`n")
    }

    if ($version.Number -ge 6 -and $version.Number -lt 10) {
        $stageOutputProvenance = Join-Path $projectStage "outputs\coastvision_mvp\provenance.json"
        Copy-Item -LiteralPath (Join-Path $projectStage "data\provenance_manifest.json") -Destination $stageOutputProvenance -Force

        $stageSummaryPath = Join-Path $projectStage "outputs\coastvision_mvp\resumen.json"
        $stageSummary = Get-Content -LiteralPath $stageSummaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $stageKnowledgeHash = (Get-FileHash -LiteralPath (Join-Path $projectStage "data\knowledge_base.json") -Algorithm SHA256).Hash.ToLowerInvariant()
        $stageSummary.source_hashes.'data/knowledge_base.json' = $stageKnowledgeHash
        $stageSummary.provenance_manifest_sha256 = (Get-FileHash -LiteralPath $stageOutputProvenance -Algorithm SHA256).Hash.ToLowerInvariant()
        Write-Utf8NoBom -Path $stageSummaryPath -Content (($stageSummary | ConvertTo-Json -Depth 12) + "`n")

        $stageOutputsReadme = @'
# Resultados del MVP demostrativo

`outputs/coastvision_mvp/` se regenera con:

```powershell
python scripts/04_build_coastvision_mvp.py --year 2035 --retreat-rate 1.5
```

Contiene líneas y franjas de escenario, zona alcanzada, área de estudio, estaciones, transectos, muestras DEM, perfil CSV, predios sintéticos, resumen y procedencia. Los PNG, HTML y CSV directamente bajo `outputs/` pertenecen al laboratorio raster/vector inicial.
'@
        Write-Utf8NoBom -Path (Join-Path $projectStage "outputs\README.md") -Content $stageOutputsReadme
    }

    if ($version.Number -ge 8 -and $version.Number -lt 10) {
        $stageAppPath = Join-Path $projectStage "app.py"
        $stageAppText = [System.IO.File]::ReadAllText($stageAppPath, (New-Object System.Text.UTF8Encoding($false)))
        $stageAppText = $stageAppText.Replace(
            "FES2014 está integrado y su estructura 34/34 fue ",
            "La corrección FES2014 se incorporará en v10; todavía no está "
        ).Replace(
            "validada; aún falta aplicarlo a la serie completa 2016-2026.",
            "disponible en este hito."
        ).Replace(
            "el módulo FES2014 está implementado; la serie corregida final aún no existe.",
            "la corrección FES2014 se incorpora en v10 y no existe en este hito."
        ).Replace(
            "Este tablero lee el catálogo Sentinel, las salidas multitemporales, la validación FES2014, ",
            "Este tablero funciona como hoja de ruta hasta v10 y, cuando existan, leerá el catálogo Sentinel, las salidas multitemporales y la validación FES2014, "
        )
        Write-Utf8NoBom -Path $stageAppPath -Content $stageAppText

        $stageDemo = @'
# Guion de demo — MVP demostrativo

1. Mostrar los 1,87 km de Playa Grande, E01–E11 y sus transectos.
2. Revisar latitud, longitud y cotas GLO-90 a 50, 150 y 250 m.
3. Cambiar el año y la tasa para explicar el escenario lineal, sin presentarlo como predicción.
4. Evaluar un punto y abrir los enlaces externos de contexto.
5. Consultar el asistente local y cerrar con las limitaciones: OSM no es una línea observada, el DEM no es marea y las franjas no son regulatorias.

El tablero de requisitos científicos de la interfaz actúa en esta versión como hoja de ruta; sus datos y módulos se incorporan en el hito de unificación v10.
'@
        Write-Utf8NoBom -Path (Join-Path $projectStage "docs\DEMO_5_MIN.md") -Content $stageDemo
    }

    if ($version.Number -eq 9) {
        $stageArchitecture = @'
# Arquitectura del MVP demostrativo

```text
OSM + Copernicus GLO-90 -> adquisición y procedencia -> geometry.py
geometry.py -> capas GeoJSON/CSV -> app.py (Streamlit + Folium)
knowledge_base.json -> rag.py -> asistente local TF-IDF
tests/test_mvp.py -> geometría, procedencia y escenarios
```

WGS84 se usa en APIs y GeoJSON, Web Mercator en el lienzo y UTM 19S en distancias. La rama científica multitemporal se integra recién en v10.
'@
        Write-Utf8NoBom -Path (Join-Path $projectStage "docs\ARQUITECTURA.md") -Content $stageArchitecture

        $stagePipeline = @'
# Pipeline y datos del MVP demostrativo

1. `scripts/00_refresh_source_data.py --offline` reconstruye OSM, DEM y procedencia desde snapshots.
2. `scripts/04_build_coastvision_mvp.py` genera estaciones, transectos, escenarios y exportaciones.
3. `scripts/run_mvp.py` inicia la aplicación interactiva.
4. `python -m pytest -q` valida el núcleo del MVP.

Entradas reales: arco marino OSM y 33 cotas Copernicus GLO-90. Escenarios, franjas y predios son demostrativos. Sentinel-2, FES2014, cambio tipo DSAS, marejadas e infraestructura quedan documentados como siguiente hito y no se declaran presentes en v09.
'@
        Write-Utf8NoBom -Path (Join-Path $projectStage "docs\PIPELINE_Y_DATOS.md") -Content $stagePipeline
    }

    $readmePath = Join-Path $projectStage "README.md"
    if ($version.Number -eq 10) {
        Copy-Item -LiteralPath (Join-Path $SourceRoot "README.md") -Destination $readmePath -Force
    }
    else {
        Write-Utf8NoBom -Path $readmePath -Content (New-StageReadme -Version $version)
    }

    $currentHashes = Get-ProjectHashMap -ProjectDirectory $projectStage
    $added = @($currentHashes.Keys | Where-Object { -not $previousHashes.ContainsKey($_) } | Sort-Object)
    $removed = @($previousHashes.Keys | Where-Object { -not $currentHashes.ContainsKey($_) } | Sort-Object)
    $changed = @(
        $currentHashes.Keys |
            Where-Object {
                $previousHashes.ContainsKey($_) -and $previousHashes[$_] -ne $currentHashes[$_]
            } |
            Sort-Object
    )

    if ($removed.Count -gt 0) {
        throw "$versionId no es acumulativa; eliminó: $($removed -join ', ')"
    }
    if (($added.Count + $changed.Count) -eq 0) {
        throw "$versionId no contiene cambios respecto de la anterior."
    }

    $projectBytes = (
        Get-ChildItem -LiteralPath $projectStage -Recurse -File |
            Where-Object {
                (Get-RelativePathPosix -BaseDirectory $projectStage -FilePath $_.FullName) -notlike ".commit-bundle/*"
            } |
            Measure-Object -Property Length -Sum
    ).Sum
    if ($null -eq $projectBytes) {
        $projectBytes = 0
    }

    $bundleDirectory = Join-Path $projectStage ".commit-bundle"
    New-Item -ItemType Directory -Path $bundleDirectory -Force | Out-Null
    $parentVersion = if ($version.Number -eq 1) { $null } else { "v{0:D2}" -f ($version.Number - 1) }
    $manifest = [ordered]@{
        schema_version = 1
        version = $versionId
        slug = $version.Slug
        title = $version.Title
        parent = $parentVersion
        cumulative = $true
        commit_message = $version.Commit
        summary = $version.Summary
        verification_commands = @($version.Commands)
        expected_results = @($version.Expected)
        files = [ordered]@{
            count = $currentHashes.Count
            bytes = [long]$projectBytes
            added = @($added)
            changed = @($changed)
            removed = @($removed)
        }
    }
    $manifestJson = $manifest | ConvertTo-Json -Depth 8
    Write-Utf8NoBom -Path (Join-Path $bundleDirectory "manifest.json") -Content ($manifestJson + "`n")
    Write-Utf8NoBom -Path (Join-Path $bundleDirectory "COMMIT_MESSAGE.txt") -Content ($version.Commit + "`n")

    $hashLines = @(
        $currentHashes.Keys | Sort-Object | ForEach-Object {
            "$($currentHashes[$_])  $_"
        }
    )
    Write-Utf8NoBom -Path (Join-Path $bundleDirectory "FILES.sha256") -Content (($hashLines -join "`n") + "`n")

    $zipName = "CoastVision_{0}_{1}.zip" -f $versionId, $version.Slug
    $zipPath = Join-Path $outputFull $zipName
    $timestamp = New-Object System.DateTimeOffset(
        2026,
        7,
        16,
        12,
        $version.Number,
        0,
        [System.TimeSpan]::Zero
    )
    New-DeterministicZip -SourceDirectory $projectStage -ZipPath $zipPath -Timestamp $timestamp
    Test-ZipPackage -ZipPath $zipPath -ExpectedProjectHashes $currentHashes

    $zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($zipHashes.ContainsKey($zipHash)) {
        throw "ZIP duplicado: $zipName y $($zipHashes[$zipHash])"
    }
    $zipHashes[$zipHash] = $zipName

    $packageSummaries += [pscustomobject]@{
        version = $versionId
        slug = $version.Slug
        zip = $zipName
        commit_message = $version.Commit
        project_files = $currentHashes.Count
        added = $added.Count
        changed = $changed.Count
        bytes = (Get-Item -LiteralPath $zipPath).Length
        sha256 = $zipHash
    }

    $previousHashes = $currentHashes
}

$shaLines = @(
    $packageSummaries | ForEach-Object { "$($_.sha256)  $($_.zip)" }
)
Write-Utf8NoBom -Path (Join-Path $outputFull "SHA256SUMS.txt") -Content (($shaLines -join "`n") + "`n")

$summaryJson = $packageSummaries | ConvertTo-Json -Depth 5
Write-Utf8NoBom -Path (Join-Path $outputFull "versiones.json") -Content ($summaryJson + "`n")

$guideRows = @(
    $packageSummaries | ForEach-Object {
        "| $($_.version) | ``$($_.zip)`` | ``$($_.commit_message)`` | $($_.project_files) |"
    }
)
$guide = @'
# Guía de commits incrementales de CoastVision

Los diez ZIP son **snapshots completos y acumulativos**. Cada paquete contiene el estado del proyecto correspondiente a su hito y puede incorporarse como un commit independiente.

## Flujo recomendado

1. Extraer `v01`; la única raíz del ZIP es `CoastVision/`.
2. Entrar a esa carpeta y ejecutar `git init`.
3. Ejecutar `git add .` y crear el commit con el mensaje indicado.
4. Para `v02` a `v10`, extraer el ZIP temporalmente y copiar **el contenido de su carpeta `CoastVision/`** sobre el mismo repositorio.
5. Revisar `git status`, ejecutar la verificación indicada en `.commit-bundle/manifest.json`, y crear el siguiente commit.

`.commit-bundle/` contiene el mensaje, el manifiesto y los hashes, pero está ignorada por `.gitignore`, por lo que `git add .` no la incorpora al proyecto.

## Secuencia

| Versión | ZIP | Mensaje sugerido | Archivos del proyecto |
|---|---|---|---:|
__GUIDE_ROWS__

## Integridad

- `SHA256SUMS.txt` valida los contenedores ZIP.
- Cada ZIP contiene `.commit-bundle/FILES.sha256` para validar los archivos del proyecto.
- No se incluyen `.git`, `.venv`, `node_modules`, caches, logs, secretos, SAFE, TIFF, JP2, NetCDF, GPKG ni ZIP anidados.
- Cada paquete se inspecciona además para detectar firmas comunes de credenciales incrustadas.
- Los TIFF/GPKG del laboratorio se regeneran con los scripts 01 y 02 y por eso no se versionan.
- No hay eliminaciones de archivos entre una versión y la siguiente.
'@
$guide = $guide.Replace("__GUIDE_ROWS__", ($guideRows -join "`n"))
Write-Utf8NoBom -Path (Join-Path $outputFull "GUIA_COMMITS.md") -Content $guide

$stagingFull = [System.IO.Path]::GetFullPath($stagingRoot)
if (-not $stagingFull.StartsWith($outputFull + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "No se eliminará staging fuera de la salida validada."
}
Remove-Item -LiteralPath $stagingRoot -Recurse -Force

$packageSummaries | Format-Table version, zip, project_files, added, changed, bytes -AutoSize
Write-Host "`nPaquetes creados y validados en: $outputFull"
