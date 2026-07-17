# CoastVision

Proyecto académico incremental de geoinformática costera para Playa Grande de Cartagena.

## Estado v06: Motor geoespacial y exportación

Se implementan CRS, arco marino, estaciones, transectos, elevación, escenarios temporales, franjas y doce artefactos exportables.

Este snapshot es acumulativo y contiene los hitos anteriores necesarios para reproducir el avance del proyecto.

## Verificación de este hito

`powershell
python scripts/04_build_coastvision_mvp.py --year 2035 --retreat-rate 1.5
`

Resultado esperado: 1,87 km cubiertos; 11 estaciones; 12 artefactos del escenario.
