# CoastVision

Proyecto académico incremental de geoinformática costera para Playa Grande de Cartagena.

## Estado v09: Pruebas y documentación técnica

Se añaden 18 pruebas, evidencia JUnit y documentación coherente con el MVP demostrativo; la rama científica se incorpora recién en v10.

Este snapshot es acumulativo y contiene los hitos anteriores necesarios para reproducir el avance del proyecto.

## Verificación de este hito

`powershell
python -m pytest -q --junitxml=outputs/coastvision_mvp/pytest.xml
`

Resultado esperado: 18 pruebas aprobadas; 0 fallos.
