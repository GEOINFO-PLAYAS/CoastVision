# Resultados

## CoastVision MVP activo

`outputs/coastvision_mvp/` se regenera con:

```powershell
python scripts/04_build_coastvision_mvp.py --year 2035 --retreat-rate 1.5
```

Contiene líneas de escenario, franjas, zona alcanzada, límites comparativos, corredor de estudio, estaciones, transectos, muestras DEM, perfil CSV, predios sintéticos, `resumen.json` y `provenance.json`.

`resumen.json` registra parámetros, fecha UTC, CRS, métricas y hashes del bundle fuente. `provenance.json` permite rastrear cada entrada a su snapshot y URL.

## Pipeline obligatorio unificado

- `requirement_status.json`: estado verificable de cada requisito obligatorio; se regenera con `python scripts/11_build_requirement_status.py`.
- `fes2014_validation.json`: inventario y validación estructural del modelo externo.
- `multitemporal/`: al completar los insumos contendrá NDWI, líneas crudas y corregidas, intersecciones, NSM/EPR/LRR y correlación con marejadas.
- `infrastructure_risk/`: edificios y caminos OSM clasificados a partir de distancia y LRR local.

Los directorios `multitemporal_validation*` son pruebas parciales de extracción
real 2017. No equivalen a la serie final 2016–2026 y no deben presentarse como
resultado científico cerrado.

## Resultados heredados

Los PNG, HTML y CSV directamente bajo `outputs/` provienen del laboratorio raster/vector anterior. No alimentan la app ni el semáforo del MVP.
