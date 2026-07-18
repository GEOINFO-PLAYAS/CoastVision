# Pipeline y datos del MVP demostrativo

1. `scripts/00_refresh_source_data.py --offline` reconstruye OSM, DEM y procedencia desde snapshots.
2. `scripts/04_build_coastvision_mvp.py` genera estaciones, transectos, escenarios y exportaciones.
3. `scripts/run_mvp.py` inicia la aplicación interactiva.
4. `python -m pytest -q` valida el núcleo del MVP.

Entradas reales: arco marino OSM y 33 cotas Copernicus GLO-90. Escenarios, franjas y predios son demostrativos. Sentinel-2, FES2014, cambio tipo DSAS, marejadas e infraestructura quedan documentados como siguiente hito y no se declaran presentes en v09.