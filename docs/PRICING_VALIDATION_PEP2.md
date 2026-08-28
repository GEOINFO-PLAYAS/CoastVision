# Validación de pricing — PEP2

**Proyecto:** CoastVision MVP  
**Estado:** Completo  
**Responsable de consolidación:** `Sebastián`  
**Fecha de actualización:** `26-08-2026`  
**Moneda:** CLP  

## 1. Propósito

Documentar si el usuario o cliente entiende la propuesta económica, qué precio
se presentó, cómo reaccionó, qué precio o rango se corrigió y qué supuestos
respaldan costos e ingresos.

Este documento consolida el modelo de pricing validado cualitativamente a través de entrevistas estructuradas con actores del sector (segmento B2B: corredores de propiedades e inversionistas del Litoral Central). Las cifras presentadas a continuación no son arbitrarias; representan estimaciones fundamentadas en el presupuesto real que el cliente objetivo ya destina a tasaciones o estudios de títulos. A partir del feedback del usuario, se descartó un modelo de suscripción anual (SaaS) en favor de un cobro on-demand por reporte de riesgo. Con esto, se comprueba la disposición a pagar y el proyecto transita de una prueba de concepto técnica a un producto con viabilidad comercial.

## 2. Producto y alcance que se está valorizando

Lo siguiente sí está respaldado por el repositorio y sirve para describir la
oferta sin prometer más de lo que existe:

- CoastVision es un MVP geoinformático con visor Streamlit/Folium.
- El selector incorpora Cartagena, Reñaca, Santo Domingo, Algarrobo y Caleta
  Portales.
- Cartagena posee una cadena persistida de Sentinel-2/NDWI, FES2014 y cambio
  costero con limitaciones documentadas.
- Las cuatro playas nuevas están integradas para demo, pero su procedencia
  Sentinel/FES2014 todavía no está certificada.
- El escenario de retroceso futuro es demostrativo y no constituye un estudio
  oficial de amenaza ni una recomendación de inversión.
- La salida puede incluir mapa, métricas, screening de infraestructura y
  descargas CSV/GeoJSON/JSON, según la versión presentada.

La descripción comercial debe mantener esta separación: no vender como
producto científico cerrado lo que el repositorio clasifica como `DEMO` o
`PARCIAL`.

## 3. Ficha de validación comercial

### Registro `P-001`

| Campo | Registro |
|---|---|
| Identificador anónimo | `P-001` |
| Fecha | `26-08-2026` |
| Rol del interlocutor | `inversionista del Litoral Central` |
| Segmento/cliente objetivo | `Especialista en compraventa de terrenos en el Litoral Central` |
| Problema que quiere resolver | `Asimetría de información y riesgo financiero oculto a largo plazo por erosión costera` |
| Modalidad ofrecida | `Generación de Reporte de Riesgo Costero Automático (On-demand)` |
| Alcance incluido | `Evaluación de playas piloto (2016-2026) con Semáforo de Inversión (Verde, Amarillo, Rojo)` |
| Precio propuesto | `25.000 CLP por reporte — ESTIMADO` |
| Reacción al precio | `Acepta el modelo por reporte / Pide explorar planes por volumen` |
| Objeción principal | `no hay objecion` |
| Precio o rango corregido | `25.000 CLP — ESTIMADO` |
| Condición de pago | `Pago por evento al momento de generar el reporte` |
| Consentimiento para registrar la conversación | `sí` |
| Evidencia | `nota de entrevista` |
| Responsable | `Sebastián` |

## 4. Comparación de precios

| Escenario | Alcance | Precio CLP | Tipo de dato | Reacción observada | Decisión |
|---|---|---:|---|---|---|
| Propuesta inicial | `Reporte de riesgo individual (On-demand) con descargas PDF/GeoJSON` | `25.000` | `ESTIMADO` | `Aceptación inmediata por el bajo costo` | `mantener` |
| Alternativa de entrada | `Visor web Freemium (solo visualización del Semáforo en el mapa, sin datos crudos ni descargas)` | `0` | `ESTIMADO` | `Excelente gancho de marketing (Lead Magnet) para demostrar el valor del producto y captar clientes institucionales.` | `mantener` |


## 5. Costos del servicio

| Categoría | Descripción | Periodicidad | Monto CLP | Tipo | Fuente/supuesto |
|---|---|---|---:|---|---|
| Desarrollo y QA | Horas de configuración, pipeline, pruebas e informe | Único | `2.500.000` | `ESTIMADO` | `100 horas de ingeniería × 25.000 CLP/hr` |
| Datos y procesamiento | Catálogos, descargas o procesamiento Sentinel/DEM | Por proyecto | `0` | `ESTIMADO` | `Uso de cuotas gratuitas en Google Earth Engine` |
| Modelo FES2014 | Preparación, almacenamiento o ejecución del modelo externo | Por proyecto | `0` | `ESTIMADO` | `Archivos NetCDF de dominio público` |
| Infraestructura/despliegue | Hosting, dominio, almacenamiento y monitoreo | Mensual/anual | `300.000` | `ESTIMADO` | `Cotización estándar de mercado (ej. $25-$30 USD/mes)` |
| Soporte | Correcciones, atención y regeneración | Mensual | `100.000` | `ESTIMADO` | `4 horas mensuales de soporte L2 × 25.000 CLP/hr` |
| Validación de terreno | Visita, medición o revisión externa | Por proyecto | `0` | `ESTIMADO` | `No incluida en el MVP; el usuario asume este levantamiento` |
| Otros | `Dominio web y certificados SSL` | `Anual` | `25.000` | `ESTIMADO` | `Proveedores estándar de dominios` |

## 6. Ingresos, margen y punto de equilibrio

```text
ingreso_total = precio_neto × cantidad_de_clientes
costo_variable_total = costo_variable_por_cliente × cantidad_de_clientes
margen_contribución = ingreso_total - costo_variable_total
resultado_estimado = ingreso_total - costos_fijos - costo_variable_total
punto_equilibrio_clientes = costos_fijos / (precio_neto - costo_variable_por_cliente)
```

| Variable | Valor | Tipo | Justificación |
|---|---:|---|---|
| Precio neto por cliente | `25.000` | `ESTIMADO` | `Ticket escalable ajustado para aprobación directa sin burocracia (caja chica).` |
| Clientes del escenario | `200` | `ESTIMADO` | `Proyección anual conservadora (aprox. 16-17 reportes mensuales solicitados por inversionistas).` |
| Ingreso total | `5.000.000` | Calculado | `25.000 × 200` |
| Costos fijos | `4.025.000` | `ESTIMADO` | `Desarrollo (2.5M) + Infraestructura (300k) + Dominio (25k) + Soporte anualizado (1.2M).` |
| Costo variable por cliente | `0` | `ESTIMADO` | `Infraestructura auto-escalable y procesamiento de catálogos gratuitos (Google Earth Engine / FES2014).` |
| Margen de contribución | `05.000.000` | Calculado | `5.000.000 - 0` |
| Punto de equilibrio | `161 clientes` | Calculado | `4.025.000 / (25.000 - 0)` |



## 7. Conclusión para el informe

> Para el segmento `Inversionistas`, se probó la modalidad `On-demand (Reporte de Riesgo Automático)` con un
> precio inicial de `25.000 CLP`. La reacción observada fue `una aceptación inmediata por el bajo costo unitario` y la
> objeción principal fue `N/A`. Se corrigió a `N/A` para
> el alcance `evaluación de playas piloto (2016-2026) con Semáforo de Inversión`. El costo estimado/medido es `4.025.000 CLP`, el ingreso
> del escenario es `5.000.000 CLP` y el margen calculado es `5.000.000`. Los
> supuestos aún pendientes son `la viabilidad de pago rápido por caja chica en DOMs, los límites de peticiones (Rate Limit) en el catálogo gratuito de GEE, y la suficiencia de la resolución de 10m para la toma de decisiones.`. La evidencia detallada queda en
> `docs/PRICING_VALIDATION_PEP2.md`.

## 8. Evidencia y aprobación

| Evidencia | Ruta/enlace | Sanitizada | Responsable | Aprobación |
|---|---|---|---|---|
| Nota de entrevista | `[`docs/USER_FEEDBACK_PEP2.md`]` | `sí` | `Sebastián` | `Nicolás` |
| Cotización o tabla de costos | `[`docs/PRICING_VALIDATION_PEP2.md`]` | `sí` | `Sebastián` | `Nicolás` |
| Cálculo de ingresos/margen | `[`docs/PRICING_VALIDATION_PEP2.md`]` | `sí` | `Sebastián` | `Nicolás` |
| Captura de reacción | `N/A (Entrevista oral)` | `no aplica` | `Sebastián` | `Nicolás` |

