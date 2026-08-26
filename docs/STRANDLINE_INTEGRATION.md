# Integración técnica de strandline

## Alcance

CoastVision mantiene su análisis Python como referencia y puede ejecutar el
motor Rust oficial `strandline` sobre el mismo caso. La integración usa dos
operaciones reales del pipeline:

1. `strandline intersect` calcula las intersecciones costa-transecto.
2. `strandline rates` calcula NSM, EPR, LRR, WLR, SCE y sus incertidumbres.

El adaptador `src/coastvision/strandline.py` convierte los GeoJSON WGS84 de
CoastVision a CSV UTM 19S, ejecuta ambos comandos, lee sus CSV y escribe una
versión normalizada con la convención del proyecto. La salida de Rust es, por
tanto, consumida por Python y queda acompañada por `manifest.json`, comandos,
versiones, hashes y tiempos.

## Contrato de coordenadas y signos

`strandline` espera `origin_e,origin_n` hacia tierra y `end_e,end_n` hacia el
mar; su `chainage_m` crece desde el origen terrestre. CoastVision mide desde la
línea base, con positivo hacia tierra. Para no invertir silenciosamente una
tasa, el adaptador aplica:

```text
position_coastvision_m = baseline_offset_m - chainage_strandline_m
rate_coastvision = -rate_strandline
```

Las fechas se toman de `acquired_at` de cada shoreline, no del año entero.
Esto evita el desfase temporal identificado en el Laboratorio 3.

## Compilar el motor oficial

El repositorio publicado de `strandline` usa una dependencia local hermana
llamada `surtgis`. Una copia limpia necesita mantener ambos repositorios al
mismo nivel:

```powershell
git clone https://github.com/franciscoparrao/strandline.git
git clone https://github.com/franciscoparrao/surtgis.git
cd strandline
git checkout fdd5a2fd1cb75389aa0579763d21f751205c30bb
cargo build --release --features cloud
```

El hash anterior es el motor revisado para esta integración. El binario queda
en `strandline/target/release/strandline` (en Windows, agrega `.exe`). El
`rust/Cargo.toml` local es un runner sin dependencias que permite invocarlo de
forma estable desde Cargo; el motor de dominio sigue siendo el repositorio
oficial y no se copia al repositorio de CoastVision.

## Ejecutar sobre Playa Grande

Con los outputs multitemporales ya generados:

```powershell
$env:STRANDLINE_BIN="C:\ruta\strandline\target\release\strandline.exe"
python scripts/13_run_strandline.py --site cartagena
```

También se puede indicar la ruta directamente:

```powershell
python scripts/13_run_strandline.py `
  --strandline-bin "C:\ruta\strandline\target\release\strandline.exe" `
  --site cartagena --along-dist 25 --min-valid 3
```

Para un sitio que todavía no tenga el archivo de transectos materializado, se
pueden entregar explícitamente los tres artefactos de entrada con
`--transects`, `--shorelines` y `--native-rates`.

Los artefactos quedan en `outputs/multitemporal/strandline/`:

- `inputs/transects.csv`, `inputs/shorelines.csv` y `inputs/dates.csv`;
- `intersections_strandline_raw.csv` y `rates_strandline_raw.csv`;
- `transect_intersections_strandline.csv` y `transect_rates_strandline.csv`;
- `manifest.json` con comandos, hashes, versión y comparación contra Python.

## Ejecutar dentro del pipeline multitemporal

La misma integración puede activarse al cerrar una corrida de `07_process`:

```powershell
python scripts/07_process_multitemporal.py `
  --site cartagena `
  --tide-model-dir "$env:TIDE_MODEL_DIR" `
  --strandline-bin "$env:STRANDLINE_BIN"
```

El archivo `pipeline_summary.json` incluye `strandline_integration`. Si el
binario falla, el estado queda explícitamente `FAILED`; no se presenta una
salida nativa como si fuera Rust.

## Benchmark reproducible

El benchmark usa los mismos `transects.geojson` y
`shorelines_2016_2026_fes2014.geojson` para ambos caminos:

```powershell
python scripts/14_benchmark_strandline.py `
  --site cartagena `
  --strandline-bin "$env:STRANDLINE_BIN" `
  --runs 3
```

Publica medianas de tiempo y la comparación de LRR en
`outputs/multitemporal/strandline/benchmark.json`. Los tiempos incluyen la
conversión CSV del adaptador, para que la cifra represente la integración de
extremo a extremo y no solo una llamada aislada al binario.

## Limitaciones y decisión de uso

- `--along-dist` cambia cuántas observaciones encuentra el motor; 25 m es el
  valor usado en la validación del laboratorio y debe mantenerse al comparar.
- La salida normalizada permite comparar con Python, pero no reemplaza
  automáticamente las capas científicas visibles. Primero debe revisarse el
  RMSE, la cobertura de transectos y las diferencias de signos.
- El motor oficial tiene una dependencia de compilación no incluida en su
  README. Por eso se fija el commit y se documenta el layout de los repositorios.
- El modo `profile` no se conecta al pipeline: el laboratorio detectó que puede
  emitir filas sin muestras o fuera del largo del transecto con datos cortos.
- La máscara SCL tampoco se activa desde este adaptador; el laboratorio observó
  que la configuración publicada podía borrar el océano. CoastVision conserva
  su extracción NDWI validada y usa strandline aquí en el tramo vectorial, donde
  el contrato y la comparación son controlables.
