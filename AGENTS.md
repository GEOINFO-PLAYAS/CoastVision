# Reglas de colaboración de CoastVision

## Propósito

Este repositorio entrega un MVP académico y una ruta de procesamiento científico. Toda contribución debe mantener separadas tres clases de evidencia:

- **real y reproducible**: tiene fuente, fecha, parámetros, recibo y artefactos reconstruibles;
- **demostrativa o sintética**: sirve para la interfaz, pero está rotulada como demo;
- **parcial**: existe un cálculo, pero falta cobertura, validación o revisión para usarlo en decisiones.

Nunca se debe presentar un archivo existente como prueba de una ejecución reciente ni transformar datos `dummy`, sintéticos o incompletos en resultados científicos mediante cambios de nombre o documentación.

## Propiedad y coordinación

| Área | Responsable principal | Límites de integración |
|---|---|---|
| Reglas, pruebas, procedencia, integración e informe | Nicolás (`xshift007`) | Integra después de recibir evidencia de los demás; no regenera resultados científicos ajenos sin coordinación. |
| Configuración de sitios y aplicación dinámica | Pablo | Mantiene `data/config/sites.json`, rutas relativas y compatibilidad del visor. |
| Datos, delimitación y Sentinel-2 de las playas | Emir | Entrega catálogos, recibos, escenas y QA; no usa `dummy_scene_*` como evidencia real. |
| FES2014, cambio costero y Strandline | Sebastián | Asume la validación de Strandline; compara ambos motores con las mismas entradas y documenta diferencias. |
| Marejadas, infraestructura y despliegue | Daniel | Conserva fuente oficial, alcance del inventario y configuración portable sin credenciales. |

Antes de modificar un archivo perteneciente a otra área, revisar `git status`, avisar al responsable y acordar el contrato de entrada/salida. No mezclar correcciones ajenas en el mismo commit.

## Orden de integración

1. Pablo valida configuración, AOI, CRS y rutas relativas.
2. Emir entrega las salidas Sentinel-2 con procedencia y QA.
3. Sebastián ejecuta FES2014, cambio costero y Strandline sobre esas entradas.
4. Daniel actualiza marejadas, infraestructura y despliegue con las salidas aceptadas.
5. Nicolás actualiza procedencia, preflight, pruebas, evidencias e informe y realiza la revisión final.

Las pruebas unitarias pueden desarrollarse en paralelo. Los hashes, el preflight persistido y las cifras del informe se cierran al final, porque dependen de los artefactos aceptados.

## Definición de terminado

Un cambio está **terminado** únicamente cuando cumple todo lo aplicable:

1. El alcance solicitado funciona y no rompe otro sitio, modo o plataforma compatible.
2. Las fuentes, fechas, parámetros, CRS, unidades, licencias y limitaciones quedan visibles en el artefacto o recibo correspondiente.
3. Las rutas versionadas son relativas al repositorio; no se aceptan rutas `C:\Users\...`, `file:///...` ni secretos.
4. Los datos reales, demostrativos y parciales están diferenciados explícitamente.
5. Las pruebas específicas pasan y la suite global termina con `58 passed` o con el total superior que resulte de agregar pruebas válidas.
6. `python scripts/12_demo_preflight.py` termina con código 0; el puerto local puede quedar como verificación opcional.
7. `git diff --check` no informa errores y `git status --short` contiene solo archivos del paquete de trabajo.
8. La documentación y el informe describen el resultado comprobado, no el comportamiento esperado.
9. Los artefactos generados necesarios se regeneran una sola vez al cierre y sus hashes coinciden con `data/provenance_manifest.json`.
10. El responsable entrega comandos ejecutados, resultados, limitaciones conocidas y archivos modificados para revisión.

No se considera terminado si solo compila, si las pruebas fueron ejecutadas parcialmente, si depende del computador de un integrante o si el resultado real fue reemplazado por un placeholder.

## Verificación mínima en PowerShell

Desde la raíz de `CoastVision`:

```powershell
python -m pytest -q -p no:cacheprovider
python scripts\12_demo_preflight.py
git diff --check
git status --short
```

Para Strandline, cuando el binario y sus dependencias ya estén preparados:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_strandline.ps1
```

Un resultado de Cargo con `0 tests` solo valida compilación; no cuenta como cobertura funcional del motor.

## Procedencia y archivos generados

- Los archivos textuales trazables usan LF mediante `.gitattributes`; no actualizar hashes con valores dependientes de CRLF.
- `data/raw/` conserva snapshots y recibos. No editar sus valores manualmente para hacer pasar una prueba.
- La regeneración base se realiza con `python scripts/00_refresh_source_data.py --offline` cuando se usan snapshots versionados, o sin `--offline` cuando existe autorización para renovar fuentes.
- Los modelos FES2014, repositorios externos, credenciales, entornos virtuales y resultados ignorados no se incorporan a Git.
- Si un output contiene una ruta absoluta histórica, debe regenerarse o documentarse como evidencia persistida no portable; no presentarlo como ejecución fresca.

## Flujo Git

- Antes de empezar: comprobar raíz, rama, remoto, estado y divergencia.
- Actualizar una rama limpia con avance lineal; no sobrescribir cambios locales de otro integrante.
- Mantener commits pequeños por responsabilidad y revisar el diff antes de publicar.
- No usar comandos destructivos para resolver conflictos. Ante un archivo compartido modificado por otra persona, detener la integración y coordinar.
- No publicar credenciales, tokens, sesiones, datos personales ni modelos externos.
