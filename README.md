# CoastVision MVP

Sistema geoinformático para evaluar erosión y exposición costera en **Playa Grande de Cartagena**. La unificación conserva la aplicación Streamlit estable del proyecto original e incorpora, como módulos separados, el trabajo satelital y mareográfico rescatable de la versión del compañero.

> **Estado real:** el visor usa por defecto el pipeline científico: 31 escenas catalogadas, 28 escenas NDWI aceptadas, once líneas anuales 2016–2026 corregidas con FES2014, 38 LRR válidas y 290 elementos OSM evaluados. El escenario manual anterior permanece aislado como modo didáctico. La correlación de marejadas fue calculada, pero sigue exploratoria porque el inventario oficial SHOA/DMC no es exhaustivo.

La matriz detallada y la arquitectura unificada están en [`docs/UNIFICACION_Y_CUMPLIMIENTO.md`](docs/UNIFICACION_Y_CUMPLIMIENTO.md).

## Estado resumido

| Componente | Estado verificable |
|---|---|
| Streamlit, estaciones, elevación y consulta por clic | **Conectado al pipeline**; el clic devuelve la infraestructura OSM evaluada más cercana |
| Catálogo Sentinel-2 2016–2026 | **Validado**; 31 escenas catalogadas y ningún año ausente |
| NDWI y línea de agua | **Completo 2016–2026**; 28 escenas aceptadas y consenso anual cuando hay dos o tres escenas válidas |
| Corrección FES2014 | **Completa para la serie**; 34/34 constituyentes, 28 predicciones por fecha y once líneas MSL |
| Tasas tipo DSAS en Python | **Completo**; 39 transectos, 336 intersecciones y 38 LRR válidas con IC95 |
| Marejadas SHOA/DMC | **Correlación ejecutada, catálogo parcial**; n=11, r=-0,405 y p=0,216; no concluyente |
| Edificaciones y caminos OSM | **Screening conectado**; 38 edificios y 252 tramos, todos bajos con los datos actuales |
| Siete elementos cartográficos | **Implementados y verificados visualmente** en la aplicación local |

## Qué funciona hoy

- Delimitación completa de 1,87 km de Playa Grande mediante el arco marino del polígono OSM `natural=beach`.
- Área de estudio satelital definida como la envolvente de un buffer de 500 m en UTM 19S alrededor de toda la playa.
- Once estaciones E01–E11 y transectos de 310 m, con latitud, longitud y progresiva costera.
- Cotas Copernicus DEM GLO-90 a 50, 150 y 250 m tierra adentro.
- Semáforo científico de infraestructura conectado a costa FES2014 2026 y LRR local; el modo demostrativo queda separado.
- Catálogo estival Sentinel-2 para todos los años 2016–2026.
- Pipeline integrado para NDWI, FES2014, cambio tipo DSAS y correlación con marejadas, más un pipeline separado para infraestructura OSM.
- La extracción multiescena puede combinar hasta tres escenas por año mediante mayoría estricta en UTM 19S; si solo hay una escena válida, el resultado queda marcado como fallback de una sola escena.
- Con el modelo FES2014 disponible, cada escena se corrige individualmente antes de calcular la mediana métrica anual; esto evita ocultar diferencias de marea usando una sola fecha representativa.
- Estado obligatorio regenerable desde artefactos mediante `scripts/11_build_requirement_status.py`.
- Preflight de demo mediante `scripts/12_demo_preflight.py`.
- Título, leyenda, escala, norte, fuente/autor, CRS/proyección y fecha dentro del mapa.
- Interfaz concentrada en el mapa, las mediciones y los cinco resultados obligatorios del pipeline.
- Comparación de las once líneas costeras anuales reales; el selector destaca un año sin alterar las clases del screening a 30 años.
- Controles explícitos para líneas, transectos, muestras DEM, edificaciones y capas OSM reales cuando sus artefactos estén disponibles.
- Exportación desde la interfaz de perfil CSV, transectos GeoJSON y evaluación puntual JSON.

## Arquitectura unificada

```text
Línea OSM + DEM GLO-90 ──> geometry.py ──> app.py (mediciones complementarias)
          │
          └─> AOI 500 m ──> catálogo Sentinel-2 2016–2026
                                  │
                                  └─> NDWI + SCL ──> línea por fecha
                                                        │
FES2014 externo ────────────────────────────────────────┤
                                                        └─> costa corregida a MSL
                                                                  │
                                                                  └─> NSM/EPR/LRR por 39 transectos
                                                                          │
OSM edificios/caminos ──> screening a 30 años ──> semáforo científico en app.py
Avisos Armada parciales ──> unión temporal/correlación exploratoria ───────┘
```

El ramal científico es el modo predeterminado de la aplicación. Las franjas de `geometry.py` solo aparecen al seleccionar **Escenario exploratorio manual** y nunca alimentan el semáforo científico.

## Instalación y MVP reproducible

```powershell
python -m venv .venv --system-site-packages
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\00_refresh_source_data.py --offline
.\.venv\Scripts\python.exe scripts\04_build_coastvision_mvp.py
.\.venv\Scripts\python.exe scripts\run_mvp.py
```

La aplicación abre en `http://localhost:8501`.

### Si aparece `ModuleNotFoundError: coastvision.scientific`

Ese mensaje significa que se copió `app.py` sin el paquete `src`. Hay que extraer
el ZIP completo manteniendo esta estructura:

```text
CoastVision/
  app.py
  src/coastvision/scientific.py
  outputs/infrastructure_risk/
```

Desde la raíz correcta, ejecutar `python scripts/run_mvp.py`. Las copias antiguas
ahora arrancan en modo demo y muestran una advertencia, pero no pueden activar el
semáforo científico hasta incorporar `src/coastvision/scientific.py` y las salidas
del pipeline.

## Pipeline multitemporal

### 1. Reconstruir el catálogo Sentinel-2

Requiere internet. Conserva ID, fecha UTC, nubosidad, cobertura y URL de cada asset.

```powershell
.\.venv\Scripts\python.exe scripts\06_build_sentinel_catalog.py `
  --buffer-m 500 --max-cloud 20 --scenes-per-year 3
```

Salida: `data/sentinel/catalog_2016_2026.json`.

### 2. Reproducir la serie científica actual

```powershell
.\.venv\Scripts\python.exe scripts\07_process_multitemporal.py `
  --years 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026 `
  --resume-cache `
  --tide-model-dir "$env:TIDE_MODEL_DIR" `
  --output outputs\multitemporal
```

Esta ejecución procesa hasta tres escenas por año, aplica consenso NDWI, corrige cada escena con FES2014 antes de la mediana anual y recalcula NSM/EPR/LRR sobre los once años. El estado global permanece `PARTIAL_DO_NOT_USE_FOR_DECISIONS` únicamente por la cobertura incompleta del catálogo oficial de marejadas, no por falta de años satelitales.

### 3. Configurar y validar FES2014

FES2014b es un recurso **externo**. Sus 34 NetCDF pesan aproximadamente 4,5 GB y no deben entrar en Git ni en los ZIP.

```powershell
$env:TIDE_MODEL_DIR="C:\ruta\segura\tide_models"
.\.venv\Scripts\python.exe scripts\09_validate_fes2014.py `
  --model-dir "$env:TIDE_MODEL_DIR"

# Validación numérica real; la primera apertura puede tardar varios minutos.
.\.venv\Scripts\python.exe scripts\09_validate_fes2014.py `
  --model-dir "$env:TIDE_MODEL_DIR" --predict
```

La raíz indicada debe contener `fes2014/ocean_tide/*.nc`.

### 4. Ejecutar la serie completa desde cero

El producto 2016 se obtiene como L1C público desde Earth Search/AWS; no tiene SCL y la escena disponible supera el umbral nominal de nubosidad, por lo que queda marcada como fallback sujeto a QA visual. Los años 2017–2026 usan COG L2A públicos con SCL.

```powershell
.\.venv\Scripts\python.exe scripts\07_process_multitemporal.py `
  --years 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026 `
  --tide-model-dir "$env:TIDE_MODEL_DIR" `
  --output outputs\multitemporal
```

El resultado solo se considera completo si `pipeline_summary.json` declara los
once años en `fes2014_corrected_years` y
`satellite_tide_change_complete_2016_2026: true`. `pipeline_complete_2016_2026`
seguirá falso mientras `storm_requirement_complete` sea falso por cobertura
oficial incompleta.

### 5. Descargar y evaluar infraestructura OSM

```powershell
.\.venv\Scripts\python.exe scripts\08_refresh_osm_infrastructure.py
```

La consulta incluye `building=*` y `highway=*` dentro del AOI de Playa Grande.
Cuando existan las líneas FES2014 y las tasas LRR reales, el cruce completo se
ejecuta con:

```powershell
.\.venv\Scripts\python.exe scripts\10_assess_infrastructure.py
```

El script 10 valida sus cuatro insumos, combina distancia a la costa más
reciente con la LRR local y exporta edificios, caminos y un resumen con hashes.
La ejecución actual publicó 38 edificios y 252 tramos. El screening usa las LRR
2016–2026 y exige validar cobertura OSM, topografía y terreno antes de decidir.

### 6. Regenerar el estado obligatorio

```powershell
.\.venv\Scripts\python.exe scripts\11_build_requirement_status.py
```

Salida: `outputs/requirement_status.json`. Este script no sustituye los
procesamientos: lee los artefactos existentes y mantiene cada requisito como
parcial o pendiente mientras falte su evidencia real.

### 7. Verificar la demo antes de presentar

```powershell
.\.venv\Scripts\python.exe scripts\12_demo_preflight.py
```

El preflight comprueba datos base, siete elementos, Sentinel/NDWI, FES, tasas,
correlación de marejadas, infraestructura y disponibilidad local de Streamlit. `demo_ready: true`
no equivale a `strict_completion: true`.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

La suite cubre geometría, adquisición,
NDWI/consenso, FES2014, cambio tipo DSAS, marejadas, infraestructura y
funciones visuales, además de verificar que el semáforo solo se habilite con la
cadena científica completa.

## Seguridad y datos externos

- Nunca versionar `.env`, credenciales, tokens ni contraseñas.
- La versión recibida del compañero contenía una credencial incrustada en un script auxiliar. El archivo no se integró y esa credencial debe **rotarse en el proveedor**.
- No copiar `tide_models/`, `node_modules/` ni cachés opacos a los ZIP incrementales.
- ERA5 puede utilizarse como covariable continua, pero no se presenta como sustituto de los avisos SHOA/DMC.
- El DEM GLO-90 tiene 90 m de resolución y no sirve para decisiones prediales ni niveles finos de inundación.

## Documentación

- [`docs/UNIFICACION_Y_CUMPLIMIENTO.md`](docs/UNIFICACION_Y_CUMPLIMIENTO.md): arquitectura y matriz honesta de requisitos.
- [`docs/PIPELINE_Y_DATOS.md`](docs/PIPELINE_Y_DATOS.md): fuentes, descargas y delimitación.
- [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md): arquitectura original del MVP.
- [`docs/EVIDENCIAS_RUBRICA.md`](docs/EVIDENCIAS_RUBRICA.md): evidencia de la entrega.
- [`docs/DEMO_5_MIN.md`](docs/DEMO_5_MIN.md): guion de demostración.
- [`docs/PRODUCT_BACKLOG_SRS.md`](docs/PRODUCT_BACKLOG_SRS.md): backlog, SRS y trazabilidad.
- [`docs/MATRIZ_RUBRICA_E2.md`](docs/MATRIZ_RUBRICA_E2.md): cruce directo con la rúbrica de avance.
- [`docs/INFORME_TECNICO_MVP.md`](docs/INFORME_TECNICO_MVP.md): informe complementario.
- [`docs/MVP_SCOPE.md`](docs/MVP_SCOPE.md): alcance y riesgos.

## Alcance responsable

El borde OSM es una referencia para delimitar la playa, no una observación satelital de 2026. El semáforo científico clasifica infraestructura, no polígonos continuos de terreno; las franjas y proyecciones manuales son demostrativas. CoastVision no sustituye un estudio costero, topográfico, hidrográfico, catastral ni financiero.
