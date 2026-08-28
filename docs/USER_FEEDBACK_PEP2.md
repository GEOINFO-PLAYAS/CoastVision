# Validación con usuario real — PEP2

**Proyecto:** CoastVision MVP  
**Estado:** Completo  
**Responsable de consolidación:** `Sebastian`  
**Fecha de actualización:** `26-08-2026`  
**URL o versión presentada:** `[https://coastvision.streamlit.app]`  

## 1. Propósito

Registrar qué ocurrió cuando el MVP fue mostrado a un usuario real y qué
cambio concreto se decidió a partir de esa reacción. Este documento contiene
evidencia de producto y no reemplaza la matriz técnica de
`docs/MULTISITE_QA_PEP2.md`.

## 2. Lo que está confirmado y lo que falta

El equipo informó que **la demostración del trabajo a un usuario real ya fue
realizada**. La transcripción disponible no contiene fecha, rol, funciones
probadas, reacción, objeciones ni cambio decidido. Por lo tanto, esos campos
se dejan pendientes y deben completarse con la persona que realizó la sesión.

No se deben inventar citas, métricas de satisfacción ni decisiones que no estén
en una nota, audio autorizado, formulario o registro de la sesión.

## 3. Ficha de la sesión

Copiar esta ficha por cada persona o sesión. Usar un identificador anónimo,
por ejemplo `U-001`; no escribir nombre, correo, teléfono ni otros datos
personales si no existe autorización expresa.

### Sesión `U-001`

| Campo | Registro |
|---|---|
| Identificador anónimo | `U-001` |
| Fecha y hora | `[26-08 / 12:00 hrs]` |
| Modalidad | `presencial` |
| Rol general del usuario | `inversionistas del Litoral Central` |
| Segmento o contexto | `Especialista en compraventa de terrenos en el Litoral Central` |
| Consentimiento para registrar feedback | `sí` |
| Consentimiento para usar captura o cita | `sí` |
| Versión/commit mostrado | `https://coastvision.streamlit.app` |
| URL utilizada | `COMhttps://coastvision.streamlit.appPLETAR` |
| Responsable de la sesión | `Sebastian` |

### Funciones probadas

Marcar solo lo que la persona realmente utilizó:

- `[x]` Selección de Cartagena.
- `[x]` Selección de Reñaca.
- `[x]` Selección de Santo Domingo.
- `[x]` Selección de Algarrobo.
- `[x]` Selección de Caleta Portales.
- `[x]` Cambio entre modo científico y modo manual/demo.
- `[x]` Cambio de año o tasa del escenario demostrativo.
- `[x]` Lectura de mapa, leyenda, escala, norte, fuente, CRS y fecha.
- `[x]` Lectura de métricas NDWI/FES/LRR.
- `[x]` Consulta de infraestructura o screening.
- `[x]` Descarga CSV.
- `[x]` Descarga GeoJSON.
- `[x]` Descarga JSON de evaluación.
- `[x]` Pestaña **Cumplimiento obligatorio**.

### Resultado observado

| Pregunta | Respuesta literal o paráfrasis autorizada |
|---|---|
| ¿Qué entendió que hace CoastVision? | `Comprendió que la plataforma es una herramienta de apoyo a la decisión que identifica las zonas costeras con menor riesgo de inversión frente a la erosión.` |
| ¿Qué función pudo usar sin ayuda? | `Navegación espacial fluida: logró interactuar con el mapa de manera autónoma, hacer zoom y alternar exitosamente entre las distintas playas piloto utilizando el menú lateral.` |
| ¿Dónde necesitó explicación? | `Requirió asistencia para interpretar la tasa LRR (metros perdidos por año). Tampoco le resultaron intuitivas las métricas de la cabecera (ej. escenas NDWI, años correlacionados) ni logró entender de forma autónoma el significado de las líneas de costa históricas superpuestas en el visor cartográfico.` |
| ¿Qué reacción general tuvo? | `Reacción general positiva enfocada en la usabilidad. Valoró la estética del dashboard y la facilidad para moverse por el mapa. Sin embargo, manifestó confusión ante la sobrecarga de jerga científica, la cual le impidió traducir inmediatamente los datos espaciales a un impacto financiero.` |
| ¿Qué objeción o desconfianza manifestó? | `No mostró desconfianza respecto a la veracidad de la información, destacando como punto fuerte que la procedencia de los datos está claramente declarada en la plataforma, lo que le transmitió transparencia.` |
| ¿Qué dato o pantalla pidió cambiar? | `Solicitó un rediseño de la interfaz para "traducir" las métricas científicas puras a un lenguaje de negocios más accesible y visual, permitiéndole operar la plataforma de forma 100% autónoma sin ayuda de un técnico.` |
| ¿Qué cambio decidimos a partir de la sesión? | `Diseñar una simplificación de la interfaz (Modo Comercial): se ocultará o relegará a un segundo plano la metadata satelital dura para destacar exclusivamente el Semáforo de Inversión, incorporando textos explicativos breves (tooltips) que faciliten la lectura de los datos presentados.` |
| ¿Quién quedó responsable del cambio? | `Pablo (ajustes del visor en Streamlit) y Sebastián (traducción comercial de las métricas).` |
| Fecha comprometida para el cambio | `28-08-2026` |

### Cita o nota autorizada


"Es una herramienta innovadora que no había visto antes en el mercado inmobiliario. Me parece muy interesante el enfoque; aunque requiere algunos ajustes menores en la interfaz, es una solución que definitivamente incorporaría en mi evaluación de proyectos."
Fuente de la evidencia: `Reunión presencial`

### Evidencia adjunta

| Tipo | Ruta o enlace | Sanitizada | Autoriza uso en entrega | Responsable |
|---|---|---|---|---|
| Nota de la sesión | `N/A` | `sí` | `sí` | `sebastián` |
| Captura del MVP | `N/A` | `sí` | `sí` | `Sebastián` |
| Audio/transcripción | `N/A` | `N/A` | `N/A` | `N/A` |

## 4. Resumen de cambios derivados

| ID | Hallazgo del usuario | Cambio decidido | Archivo/issue | Responsable | Estado |
|---|---|---|---|---|---|
| FB-001 | `Fricción cognitiva por exceso de jerga científica (NDWI, LRR) en el panel principal.` | `Implementar un "Modo Comercial" priorizando el Semáforo de Inversión y agregar tooltips explicativos para métricas complejas.` | `app.py` | `Pablo y Sebastián` | `en curso` |
| FB-002 | `Confusión visual para interpretar las distintas líneas de costa históricas superpuestas en el mapa.` | `Agregar un control de capas (toggle) en el mapa para permitir apagar las líneas históricas y enfocarse solo en la proyección de riesgo 2026.` | `app.py` | `Pablo` | `pendiente` |

## 5. Texto breve para el informe técnico

Completar después de cerrar la ficha, sin agregar información que no esté
respaldada por ella:

> Se mostró la versión `https://coastvision.streamlit.app` a un usuario de perfil `inversionistas del Litoral Central` el día
> `26-08-2026`. Se probaron `las funciones de navegación espacial, selección de playas piloto y la lectura de métricas de riesgo (Semáforo de Inversión)`. La reacción principal fue `positiva respecto a la usabilidad del mapa y la transparencia de los datos`; las objeciones fueron `la alta fricción cognitiva generada por la excesiva jerga científica (como NDWI y tasas LRR) y la confusión visual al interpretar las líneas de costa históricas superpuestas`. Como resultado se
> decidió `implementar un "Modo Comercial" simplificado que oculta la metadata dura, incorpora tooltips explicativos y añade un control para apagar las capas históricas`, a cargo de `Pablo y Sebastián`, con estado `en curso`. La
> evidencia detallada se conserva en `docs/USER_FEEDBACK_PEP2.md`.

## 6. Reglas de privacidad y honestidad

- No publicar datos personales sin autorización explícita.
- No presentar una respuesta del equipo como si fuera una respuesta del
  usuario.
- Distinguir cita textual, paráfrasis y observación del moderador.
- No convertir “le gustó” en validación comercial; registrar conducta,
  objeciones y cambio decidido.
- Si no hubo autorización para publicar una captura, conservar solo una
  descripción sanitizada y la evidencia privada según las reglas del curso.

