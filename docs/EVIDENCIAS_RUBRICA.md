# Evidencias para la rúbrica

## Estado verificable al corte

- Visor Streamlit/Folium operativo para Playa Grande: 1,8689 km, 11 estaciones, 11 transectos y 33 cotas DEM.
- Escenario exportado de referencia: 2035, 1,5 m/año y 13,5 m acumulados; **demostrativo**.
- Catálogo Sentinel-2: 31 escenas, años 2016–2026 presentes.
- NDWI real: 28 escenas aceptadas y once líneas anuales 2016–2026; 2016 L1C queda sujeto a QA visual reforzado.
- FES2014: 34/34 NetCDF, predicción numérica validada y 28 correcciones por fecha UTC.
- DSAS equivalente: 39 transectos, 336 intersecciones y 38 LRR válidas sobre 2016–2026.
- Marejadas: correlación ejecutada con n=11, r=-0,405 y p=0,216; catálogo oficial parcial y resultado no concluyente.
- Infraestructura: 38 edificios y 252 tramos OSM; screening de la serie completa conectado al semáforo del mapa.
- Mapa: siete elementos obligatorios implementados.
- Estado derivado: `MVP_UNIFICADO_CON_PENDIENTES_DE_DATOS`, `strict_completion: false`.

## Matriz criterio → evidencia

| Criterio de avance | Qué se demuestra | Evidencia directa | Verificación |
|---|---|---|---|
| Evidencias de avance (35 %) | Visor funcional, artefactos base y pipeline científico modular | `app.py`, `outputs/coastvision_mvp/`, scripts 06–11, `outputs/requirement_status.json` | Abrir app, revisar salidas y ejecutar auditoría |
| Diseño arquitectural (20 %) | Separación entre demo, datos, procesamiento científico, auditoría e interfaz | [Arquitectura](ARQUITECTURA.md) | Seguir diagrama, entradas y contratos |
| Uso de tecnologías (15 %) | Streamlit, Folium, GeoPandas, Rasterio, Shapely, PyProj, STAC, pyTMD/FES2014, SciPy/scikit-learn | `requirements.txt`, `src/` y scripts | Inspeccionar módulos y pruebas específicas |
| Demo funcional (30 %) | Cobertura, medición, escenario, clic, elevación, siete elementos y estado obligatorio | [Guion de 5 minutos](DEMO_5_MIN.md), app y captura | Seguir el guion cronometrado |

## Cumplimiento de requisitos obligatorios

| # | Requisito | Evidencia | Estado | Pendiente para cerrar |
|---|---|---|---|---|
| 1 | Extraer línea costera Sentinel-2 2016–2026 | catálogo, 28 recibos y 11 líneas NDWI | Completo | QA visual reforzado de 2016 |
| 2 | Aplicar NDWI o MNDWI | `src/coastvision/sentinel.py` y `outputs/multitemporal/` | Completo 2016–2026 | Documentar incertidumbre L1C/L2A |
| 3 | Calcular tasas con DSAS o equivalente Python | `transect_rates.csv/.geojson` | Completo, 38 LRR | Revisar transectos con baja completitud |
| 4 | Correlacionar con marejadas SHOA/DMC | `storm_correlation.json`, unión CSV y metadatos | Ejecutado, parcial | Certificar inventario oficial exhaustivo |
| 5 | Identificar edificaciones y caminos en riesgo | `data/infrastructure/` y `outputs/infrastructure_risk/` | Completo como screening | Validar cobertura OSM y terreno |
| 6 | Corrección de marea FES2014 | validación, 28 correcciones y once líneas anuales | Completo 2016–2026 | Mantener modelo externo fuera del ZIP |
| 7 | Siete elementos obligatorios del mapa | `app.py` | Completo | Verificación visual final antes de presentar |

## Evidencia por comando

### 1. Reconstrucción base sin red

```powershell
python scripts/00_refresh_source_data.py --offline
```

Evidencia histórica del bundle:

```text
mode: offline
osm_way: 300607261
osm_version: 12
shoreline_vertices: 69
elevation_samples: 33
manifest: data/provenance_manifest.json
```

### 2. Exportación del escenario demo

```powershell
python scripts/04_build_coastvision_mvp.py --year 2035 --retreat-rate 1.5
```

Produce capas, perfil, resumen y procedencia en `outputs/coastvision_mvp/`. Los hashes vinculan el escenario con el bundle base. No produce observaciones Sentinel ni tasas reales.

### 3. Catálogo Sentinel-2

```powershell
python scripts/06_build_sentinel_catalog.py
```

Resultado persistente: 31 escenas, un candidato L1C público en 2016 y tres candidatos L2A por año entre 2017 y 2026; ningún año ausente del catálogo.

### 4. Extracción NDWI multitemporal

```powershell
python scripts/07_process_multitemporal.py --years 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 2026 --resume-cache --tide-model-dir "RUTA_EXTERNA_AL_MODELO"
```

Artefactos presentes:

- raster NDWI;
- polígono de agua;
- línea bruta;
- gráfico de control;
- resumen con once años NDWI/FES2014, 336 intersecciones, 38 LRR y correlación exploratoria de marejadas.

### 5. FES2014 externo

```powershell
python scripts/09_validate_fes2014.py --model-dir "RUTA_EXTERNA_AL_MODELO"
python scripts/09_validate_fes2014.py --model-dir "RUTA_EXTERNA_AL_MODELO" --predict
```

La validación registra 34/34 constituyentes, aproximadamente 4,5 GB y una predicción numérica de control. `tide_corrections.csv` contiene 28 correcciones y sensibilidad para pendientes 0,03/0,05/0,08.

### 6. Infraestructura

```powershell
python scripts/08_refresh_osm_infrastructure.py
python scripts/10_assess_infrastructure.py
```

El primer comando creó el snapshot real; el segundo publicó el screening para 38 edificios y 252 tramos usando LRR 2016–2026. El resultado exige validación de campo.

### 7. Estado obligatorio

```powershell
python scripts/11_build_requirement_status.py
```

`outputs/requirement_status.json` deriva el estado desde archivos reales. Resultado actual: seis requisitos completos y marejadas parcial por catálogo oficial incompleto.

### 8. App

```powershell
python scripts/run_mvp.py
```

Verificaciones realizadas en la unificación:

- sintaxis de `app.py` correcta;
- auditoría cartográfica devuelve siete filas;
- estado de artefactos sin error;
- endpoint de salud de Streamlit responde HTTP 200.

La comprobación visual final de posición, contraste y legibilidad de los siete elementos debe hacerse en el navegador antes de entregar.

### 9. Pruebas

La evidencia consolidada registra:

```text
53 passed in 8.04s
```

en `outputs/coastvision_mvp/pytest.xml`, ejecutada después de las integraciones científicas y de interfaz.

## Correspondencia con el informe

| Criterio del informe | Evidencia disponible |
|---|---|
| Profundidad | [Pipeline y datos](PIPELINE_Y_DATOS.md) explica delimitación, fuentes, NDWI, FES, cambio, marejadas e infraestructura |
| Evidencia de implementación | Código modular, catálogo, NDWI 2017, validaciones y estado derivado |
| Estructura | [Informe técnico](INFORME_TECNICO_MVP.md) separa método, resultados, limitaciones y próximos pasos |
| Fuentes | Manifiesto OSM/DEM, recibos Sentinel, metadatos de marejadas y validación FES |
| Claridad | Se distinguen observaciones, escenarios, datos externos y resultados pendientes |
| Distribución de tareas e IA | Sección específica del informe; responsables reales aún deben completarse |

## Contingencia de presentación

- Si fallan tiles o enlaces externos, usar `docs/evidence/coastvision_mvp_2035.png` y artefactos locales.
- Si no hay clave LLM, usar TF-IDF local; el LLM no interviene en el cálculo.
- No ejecutar descargas, FES2014 ni procesamiento multitemporal durante la demo.
- Mostrar la pestaña **Cumplimiento obligatorio** para evitar sobreafirmaciones.

## Declaración honesta de alcance

Sentinel/NDWI, FES2014, DSAS equivalente e infraestructura tienen resultados 2016–2026 persistidos y el mapa los consume por defecto. El semáforo es un screening de elementos OSM, no una zonificación oficial. Marejadas sigue parcial: la correlación existe, pero el catálogo oficial no permite una conclusión robusta.
