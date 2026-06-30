# Pipeline de Datos — Sistema de Identificación de Potenciales Beneficiarios (Sisbén IV)

Implementación de un pipeline de datos de extremo a extremo para el procesamiento, validación y análisis del Sisbén IV en Antioquia. El proyecto integra fuentes de datos del DNP, DANE y la Gobernación de Antioquia, y expone los resultados a través de un modelo semántico tabular en Power BI.

---

## Contexto

El Sisbén IV es el instrumento de focalización del Estado colombiano. Este repositorio contiene el código desarrollado para automatizar la ingesta, limpieza, validación de calidad y modelado analítico de los microdatos del Sisbén IV para los **125 municipios del departamento de Antioquia**, cubriendo más de **4 millones de registros** individuales y **26 columnas calculadas** derivadas de las variables originales del DNP.

El pipeline alimenta un tablero de Power BI que permite a la Gobernación consultar coberturas, índices de privación (IPM), composición de hogares, calidad de vivienda y caracterización socioeconómica por municipio, zona y año de encuesta.

---

## Stack Tecnológico

| Capa | Herramientas |
|---|---|
| Ingesta y transformación | Python · Pandas · PyArrow · DuckDB |
| Almacenamiento intermedio | Parquet (columnar) |
| Calidad de datos | Scripts de auditoría propios |
| Modelo analítico | Power BI · TMDL · DAX |
| Distribución | OneDrive / SharePoint · CSV por municipio |
| Automatización | PowerShell · Python scripts |

---

## Estructura del Repositorio

```
portfolio_sisben/
│
├── src/
│   ├── etl/                       # Pipelines de extracción y transformación
│   │   ├── etl_sisben_definitivo.py       # Pipeline principal (Sisbén IV)
│   │   ├── etl_dane_viviendas_hogares.py  # Proyecciones DANE (hogares y viviendas)
│   │   ├── etl_poblacion_cobertura.py     # Cobertura poblacional por municipio
│   │   └── upload_recursos.py             # Distribución de archivos a SharePoint
│   │
│   ├── data_quality/              # Auditoría y validación de esquemas
│   │   ├── audit_cols.py                  # Validación columnas Parquet vs Power BI
│   │   ├── check_schema.py                # Verificación de tipos de datos
│   │   ├── deep_pq_check.py               # Inspección profunda de Parquet
│   │   ├── dax_audit.py                   # Validación de medidas DAX
│   │   └── strict_audit.py                # Auditoría estricta de integridad
│   │
│   └── utils/                     # Utilidades y post-procesamiento
│       ├── fix_csv_columns.py             # Normalización de columnas en CSV
│       ├── fix_sharepoint.py              # Corrección de rutas SharePoint
│       ├── post_process_municipios.py     # Renombrado y enriquecimiento de CSVs
│       └── tmdl_reorganize.py             # Reorganización del modelo TMDL
│
├── model/                         # Definición del modelo semántico (Power BI)
│   ├── tmdl_sisben/               # Modelo tabular en formato TMDL
│   │   ├── model.tmdl
│   │   ├── relationships.tmdl
│   │   ├── expressions.tmdl
│   │   └── tables/                # 19 tablas: dimensiones, hechos y calculadas
│   ├── deploy_dq_model.ps1        # Script de despliegue del modelo
│   └── master_audit_fixed.ps1     # Auditoría completa del modelo
│
├── docs/                          # Documentación técnica y metodológica
│   ├── Documento_Metodologico_Sisben_Actualizado.tex
│   ├── presentacion_modelo_sisben.tex
│   └── informes/                  # Informes PDF por municipio (125 municipios)
│
├── data/                          # Diccionarios y datos de referencia (públicos)
│   ├── Variables.xlsx             # Diccionario de variables del Sisbén IV
│   └── DIVIPOLA_EAT_GOBANT.xlsx   # Codificación DIVIPOLA — Gobernación Antioquia
│
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Módulos Principales

### `etl_sisben_definitivo.py`

El núcleo del pipeline. Procesa el archivo maestro de microdatos en modo **chunk** (lotes de 150.000 filas) para operar dentro de límites de memoria con conjuntos de datos de varios millones de registros.

Principales responsabilidades:
- Normalización de tipos (Int64 nullable, strings, fechas).
- Cálculo de **26 columnas derivadas**: clasificación socioeconómica, rango de edad, régimen de salud, categorías de hacinamiento, privaciones de vivienda (IPM), entre otras.
- Exportación del Parquet final consolidado.
- Generación de CSVs individuales por municipio vía **DuckDB** (procesamiento SQL sobre Parquet).
- Generación de la tabla dimensión `dim_descargas_municipios` con URLs de descarga directa desde SharePoint.

```python
# Ejemplo: cálculo de hacinamiento sobre el chunk
_personas = pd.to_numeric(df["num_personas_hogar"], errors="coerce")
_cuartos  = pd.to_numeric(df["num_cuartos_vivienda"], errors="coerce").replace(0, np.nan)
df["Personas_por_Cuarto"] = (_personas / _cuartos).astype("Float64")
df["Cat_Hacinamiento"] = np.where(_ppc > 3, "Hacinado", "No hacinado")
```

### `etl_dane_viviendas_hogares.py`

Procesa las proyecciones oficiales del DANE (hogares y viviendas) para municipios de Antioquia, 2018–2042. Realiza un **melt** de formato ancho a largo, alinea los códigos DANE con DIVIPOLA y genera los Parquet de referencia para los indicadores de cobertura.

### `post_process_municipios.py`

Post-procesa los CSVs por municipio depositados en OneDrive: estandariza nombres de archivo usando codificación DIVIPOLA, agrega la columna `nom_mpio`, y regenera el CSV de dimensión de descargas con las URLs públicas de SharePoint.

### `upload_recursos.py`

Automatiza la distribución de recursos estáticos (diccionario de variables e informes municipales en PDF) desde el entorno local hacia las carpetas de OneDrive sincronizadas con SharePoint, actualizando las URLs en el CSV dimensión.

---

## Modelo Semántico (TMDL)

El directorio `model/tmdl_sisben/` contiene la definición completa del modelo tabular de Power BI en formato **TMDL** (Tabular Model Definition Language), lo que permite versionarlo en Git y desplegarlo programáticamente.

El modelo incluye:

| Tipo | Tablas |
|---|---|
| Tabla de hechos | `fct_Sisben` (microdatos individuales) |
| Dimensiones | `dim_municipios`, `Dim_Anios`, `Dim_Rango_Edad`, `Dim_Estado_DNP`, `Dim_Marca_DNP`, `Nivel_Sisben`, `Dim_Privacion`, `Dim_IPM_Dimension` |
| Dimensiones de vivienda | `Dim_Categoria_Vivienda`, `Dim_Bloque_Sanitario`, `Dim_Tipo_Evento`, `Dim_Evento`, `Tabla_Indicadores_Vivienda` |
| Tablas DANE | `Poblacion_DANE`, `Hogares_DANE`, `Viviendas_DANE` |
| Auxiliares | `Selector_Vivienda`, `Dim_Indicador_Hogar` |

---

## Informes Municipales

La carpeta `docs/informes/` contiene **125 informes en PDF**, uno por cada municipio de Antioquia, generados automáticamente a partir del modelo de datos. Los PDFs incluyen indicadores de cobertura, distribución por clasificación Sisbén y comparativos con las proyecciones DANE.

---

## Datos de Referencia

Los archivos en `data/` son de uso público y no contienen microdatos personales:

- **`Variables.xlsx`**: Diccionario oficial de las variables del Sisbén IV (DNP).
- **`DIVIPOLA_EAT_GOBANT.xlsx`**: Tabla de códigos geográficos DIVIPOLA adaptada para la Gobernación de Antioquia, con correspondencia entre municipios, subregiones y entidades territoriales.

> **Nota sobre datos sensibles:** Los microdatos del Sisbén IV son información personal protegida bajo la Ley 1581 de 2012 (Habeas Data). Los archivos Parquet y CSV con registros individuales no hacen parte de este repositorio.

---

## Cómo ejecutar

### Requisitos

```bash
pip install -r requirements.txt
```

### Variables de entorno

Antes de ejecutar los scripts ETL, define las rutas de entrada y salida en cada archivo o configura las siguientes variables de entorno:

```bash
SISBEN_PARQUET_IN   # Ruta al Parquet de entrada con microdatos
SISBEN_PARQUET_OUT  # Ruta de salida del Parquet procesado
SISBEN_CSV_DIR      # Directorio de salida para CSVs por municipio
ONEDRIVE_SYNC_DIR   # Carpeta local sincronizada con SharePoint
```

### Ejecución del pipeline principal

```bash
python src/etl/etl_sisben_definitivo.py
```

### Ejecución de la auditoría de calidad

```bash
python src/data_quality/strict_audit.py
python src/data_quality/audit_cols.py
```

---

## Autor

Valentina Vanegas — Analista de Datos  
Proyecto desarrollado en el contexto del análisis de datos del Sisbén IV para la Gobernación de Antioquia.
