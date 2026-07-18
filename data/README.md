# Datos

## Entradas activas del MVP

- `playa_grande_shoreline_osm.geojson`: borde marino derivado del polígono OpenStreetMap `way 300607261`, ODbL.
- `elevation_profile_open_meteo.json`: 33 cotas Copernicus DEM GLO-90 consultadas mediante Open-Meteo, resolución 90 m.
- `knowledge_base.json`: fragmentos locales del asistente RAG.
- `provenance_manifest.json`: URLs, versión OSM, fecha UTC, roles y hashes SHA-256 del bundle activo.
- `sentinel/catalog_2016_2026.json`: 31 escenas candidatas STAC para 2016–2026, con proveedor, fecha, nubosidad, tesela, cobertura y estado de acceso.
- `events/marejadas_oficiales_armada.csv`: avisos oficiales verificados ya recopilados; el inventario todavía es parcial.
- `events/catalog_metadata.json`: declara explícitamente la cobertura incompleta del catálogo de marejadas.
- `config/analysis_config.json`: AOI, ventana estacional, índice NDWI, pendiente de playa asumida, métricas DSAS y parámetros de infraestructura.

Los snapshots que permiten reconstruir el bundle sin internet están en `data/raw/`. La actualización online usa `python scripts/00_refresh_source_data.py`; el modo offline usa `--offline`.

El borde OSM deriva de un polígono `natural=beach`: es una referencia espacial, no una línea de agua observada en 2026. Las cotas DEM son indicativas y no equivalen a altura de marea ni a levantamiento topográfico. Los offsets de 50/150/250 m se miden sobre cada transecto.

## Datos heredados del laboratorio

Los siguientes archivos son sintéticos y solo alimentan los ejercicios raster/vector anteriores:

- `green.tif`
- `nir.tif`
- `dem.tif`
- `linea_costa.geojson`
- `zonas_costeras.gpkg`

No se usan para el semáforo ni para la red de medición de CoastVision.

## Datos externos que no entran en Git

FES2014b contiene 34 NetCDF y pesa aproximadamente 4,5 GB. Se configura con
`TIDE_MODEL_DIR`; consulte `data/external/fes2014/README.md`. Los archivos COG
o GeoTIFF descargados de Sentinel-2 también se regeneran y no se versionan.
