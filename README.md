# CoastVision

Proyecto académico incremental de geoinformática costera para Playa Grande de Cartagena.

## Estado v04: Análisis NDWI y cartografía

Se completa el flujo raster/vector con NDWI, estadísticas zonales, mapa estático y mapa Folium.

Este snapshot es acumulativo y contiene los hitos anteriores necesarios para reproducir el avance del proyecto.

## Verificación de este hito

`powershell
python scripts/01_create_sample_data.py
python scripts/02_ndwi_zonal_stats.py
python scripts/03_visualize_results.py
`

Resultado esperado: CSV de estadísticas; PNG y HTML cartográficos.
