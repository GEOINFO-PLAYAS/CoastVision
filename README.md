# CoastVision

Proyecto académico incremental de geoinformática costera para Playa Grande de Cartagena.

## Estado v05: Playa Grande y fuentes reproducibles

Se define el alcance del MVP y se incorporan el polígono OSM de Playa Grande, elevaciones Open-Meteo, snapshots originales y hashes.

Este snapshot es acumulativo y contiene los hitos anteriores necesarios para reproducir el avance del proyecto.

## Verificación de este hito

`powershell
python scripts/00_refresh_source_data.py --offline
`

Resultado esperado: 69 vértices del arco marino; 33 cotas DEM; manifiesto reproducible.
