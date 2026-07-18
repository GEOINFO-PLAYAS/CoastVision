# Eventos de marejadas

`marejadas_oficiales_armada.csv` es un catálogo **parcial y verificable** de
avisos oficiales que afectan el litoral central. Cada fila conserva el enlace
de la Armada/SERVIMET y el intervalo explícito del aviso.

No se presenta como una descarga completa SHOA/DMC: todavía falta revisar de
forma sistemática 2022, 2023 y 2025, además de obtener una serie tabular oficial
continua. La página de
[Datos Históricos de DIRECTEMAR](https://www.directemar.cl/directemar/cambio-climatico/datos-historicos)
identifica las fuentes institucionales SHOA, SERVIMET y cierres por marejadas;
la [DMC publica boletines anuales de eventos extremos](https://climatologia.meteochile.gob.cl/application/publicaciones/boletinEventosExtremos).

La revisión del índice DMC confirmó boletines oficiales para 2016–2025, pero
estos documentos son una selección de eventos atmosféricos y no un inventario
exhaustivo de marejadas. Por eso se usan como contexto y nunca para etiquetar
un año sin aviso como “sin marejada”. `catalog_metadata.json` deja esta
limitación legible por máquinas y no certifica como completo ningún año.

El pipeline puede unir este catálogo con la fecha UTC de cada escena y calcular
una correlación punto-biserial entre presencia de evento y anomalía de posición
costera. ERA5 puede añadirse como covariable continua, pero nunca se etiqueta
como sustituto de SHOA/DMC.

El archivo `oleaje_era5_cartagena.json` conserva seis valores de altura
significativa de ola que venían en el proyecto compañero. Se muestran en el
visor como contexto auxiliar y no cierran por sí solos la correlación oficial.
