"""
ETL DEFINITIVO — Sisben Master Parquet v3 (CHUNK MODE) + CSV Export
===================================================================
Procesa 25M filas en lotes de 500.000 para no explotar la RAM.
El resultado final es IDENTICO al v2 — mismo esquema, mismo PARQUET.

Mejoras Integradas:
  - Logging centralizado para depuración de errores.
  - Generación automatizada de CSVs por municipio vía DuckDB (Rápido y eficiente).
  - Preparación de archivos para subida a SharePoint (Local Sync).
  - Generación de la tabla Dimensión de URLs para Power BI.
"""

import sys
import os
import gc
import time
import logging
import glob
import shutil
import tempfile
import ctypes

import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import duckdb

# ── Configuración de Logging ─────────────────────────────────────────────────
# Crea un archivo log y también imprime en consola
log_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), "etl_sisben.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

# ── Encoding seguro ──────────────────────────────────────────────────────────
sys.stdout.reconfigure(encoding="utf-8")

# ── Rutas Base ───────────────────────────────────────────────────────────────
PARQUET_IN  = r"D:\VVANEGASA\My Documents\sisben_master.parquet"
PARQUET_OUT = r"D:\VVANEGASA\My Documents\sisben_master_v3.parquet"  # temporal
PARQUET_FINAL = r"D:\VVANEGASA\My Documents\sisben_master.parquet"  # definitivo

# Rutas para generación de CSVs y SharePoint
OUTPUT_DIR_FULL = r"D:\VVANEGASA\My Documents\csvs_sisben_completos"
OUTPUT_DIR_ULTIMO_ANIO = r"D:\VVANEGASA\My Documents\csvs_sisben_ultimo_anio"

# Sincronización Local y URL Pública (Alineados a la subcarpeta Data_Municipios)
SHAREPOINT_LOCAL_SYNC_DIR = r"C:\Users\VVANEGASA\OneDrive - Gobernacion de Antioquia\SISBEN\Data_Municipios"
SHAREPOINT_WEB_BASE_URL = "https://gobantioquia-my.sharepoint.com/personal/hromeror_antioquia_gov_co/Documents/SISBEN/Data_Municipios/"
OUTPUT_DIM_CSV = r"D:\VVANEGASA\My Documents\dim_descargas_municipios.csv"

CHUNK_ROWS = 150_000

logging.info("=" * 70)
logging.info("ETL SISBEN DEFINITIVO v3 — Modo CHUNK + Exportación SharePoint")
logging.info(f"Chunk size: {CHUNK_ROWS:,} filas por lote")
logging.info("=" * 70)

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS — Reemplazo robusto de archivos en Windows
# ─────────────────────────────────────────────────────────────────────────────

def _archivo_bloqueado(ruta: str) -> bool:
    """Devuelve True si el archivo en `ruta` está siendo usado por otro proceso."""
    if not os.path.exists(ruta):
        return False
    try:
        # Intenta abrir el archivo para escritura exclusiva
        with open(ruta, "r+b") as fh:
            pass
        return False
    except (PermissionError, OSError):
        return True


def _reemplazar_parquet_robusto(
    origen: str,
    destino: str,
    reintentos: int = 8,
    espera_seg: float = 5.0,
) -> bool:
    """
    Reemplaza `destino` con `origen` de forma robusta en Windows.

    Estrategias (en orden):
      1. os.replace() atómico — falla si `destino` está bloqueado.
      2. Renombrar `destino` a un nombre de backup y luego mover `origen`.
      3. Copia byte a byte al destino (fallback final).

    Si el archivo sigue bloqueado, espera hasta `reintentos * espera_seg` segundos.
    """
    for intento in range(1, reintentos + 1):
        bloqueado = _archivo_bloqueado(destino)
        if bloqueado:
            logging.warning(
                f"    [WinError 32] '{os.path.basename(destino)}' está bloqueado por otro proceso. "
                f"Reintento {intento}/{reintentos} en {espera_seg:.0f}s... "
                f"(cierra Power BI / Excel si lo tienes abierto)"
            )
            time.sleep(espera_seg)
            continue

        # ── Estrategia 1: os.replace() atómico (recomendado en Windows) ──────
        try:
            os.replace(origen, destino)
            logging.info(f"    ✓ Reemplazo atómico exitoso → {destino}")
            return True
        except PermissionError as e:
            logging.warning(f"    os.replace() falló (intento {intento}): {e}")

        # ── Estrategia 2: rename del destino a backup + move del origen ──────
        backup = destino + ".bak"
        try:
            if os.path.exists(backup):
                os.remove(backup)
            os.rename(destino, backup)
            os.rename(origen, destino)
            # Si llegamos aquí, el reemplazo funcionó; borramos el backup
            try:
                os.remove(backup)
            except Exception:
                pass
            logging.info(f"    ✓ Reemplazo vía backup exitoso → {destino}")
            return True
        except PermissionError as e:
            logging.warning(f"    Estrategia backup falló (intento {intento}): {e}")
            # Revertir si el backup se creó pero el rename final falló
            if os.path.exists(backup) and not os.path.exists(destino):
                try:
                    os.rename(backup, destino)
                except Exception:
                    pass

        time.sleep(espera_seg)

    # ── Estrategia 3: Copia directa (fallback de último recurso) ─────────────
    logging.warning(
        f"    ⚠️  Fallback: copiando '{os.path.basename(origen)}' directamente sobre destino. "
        f"El archivo de destino podría no poder eliminarse ahora."
    )
    try:
        shutil.copy2(origen, destino)
        logging.info(f"    ✓ Copia directa exitosa → {destino}")
        # Intentar borrar el temporal
        try:
            os.remove(origen)
        except Exception:
            logging.warning(f"    ⚠️  No se pudo eliminar temporal: {origen}")
        return True
    except Exception as e:
        logging.error(f"    ❌ Fallback de copia también falló: {e}")
        return False


def to_int(series):
    """Int seguro desde cualquier dtype; NaN → pd.NA (Int64 nullable)."""
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def calcular_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica las 26 transformaciones DAX sobre un chunk de pandas."""
    rename_map = {}
    for col in df.columns:
        if col.lower().replace("?", "ñ").startswith("ind_discap_ba") and "arse" in col.lower():
            if col != "ind_discap_bañarse":
                rename_map[col] = "ind_discap_bañarse"
        if col.lower().startswith("tip_cuidado_ni") and "os" in col.lower():
            if col != "tip_cuidado_niños":
                rename_map[col] = "tip_cuidado_niños"
        if col.lower() == "num_evento_vendaval" and col != "Num_evento_vendaval":
            rename_map[col] = "Num_evento_vendaval"
    if rename_map:
        df.rename(columns=rename_map, inplace=True)

    COLS_INT64 = [
        "Cod_clase", "tip_vivienda", "tip_mat_paredes", "tip_mat_pisos",
        "ind_tiene_energia", "tip_estrato_energia", "ind_tiene_alcantarillado", "ind_tiene_gas",
        "ind_tiene_recoleccion", "ind_tiene_acueducto", "tip_estrato_acueducto",
        "num_cuartos_vivienda", "num_hogares_vivienda", "ide_hogar",
        "tip_ocupa_vivienda", "num_cuartos_exclusivos", "num_cuartos_dormir", "num_cuartos_unicos_dormir",
        "tip_sanitario", "tip_ubi_sanitario", "tip_uso_sanitario",
        "tip_origen_agua", "ind_agua_llega_7dias", "num_dias_llega",
        "ind_agua_llega_24horas", "num_horas_llega", "tip_uso_agua_beber", "tip_elimina_basura",
        "ind_tiene_cocina", "tip_prepara_alimentos", "tip_uso_cocina", "tip_energia_cocina",
        "ind_tiene_nevera", "ind_tiene_lavadora", "ind_tiene_pc", "ind_tiene_internet",
        "ind_tiene_moto", "ind_tiene_tractor", "ind_tiene_carro", "ind_tiene_bien_raiz",
        "ind_gasto_alimento", "vlr_gasto_alimento", "ind_gasto_transporte", "vlr_gasto_transporte",
        "ind_gasto_educacion", "vlr_gasto_educacion", "ind_gasto_salud", "vlr_gasto_salud",
        "ind_gasto_serv_publicos", "vlr_gasto_serv_publicos", "ind_gasto_celular", "vlr_gasto_celular",
        "ind_gasto_arriendo", "vlr_gasto_arriendo", "ind_gasto_otros", "vlr_gasto_otros",
        "vlr_total_gastos", "num_habita_vivienda",
        "ind_evento_inundacion", "num_evento_inundacion", "ind_evento_avalancha", "num_evento_avalancha",
        "ind_evento_terremoto", "num_evento_terremoto", "ind_evento_incendio", "num_evento_incendio",
        "ind_evento_vendaval", "Num_evento_vendaval", "ind_evento_hundimiento", "num_evento_hundimiento",
        "num_personas_hogar", "sexo_persona", "tip_parentesco", "tip_estado_civil", "ind_conyuge_vive_hogar", "ide_conyuge",
        "ind_padre_vive_hogar", "ide_padre", "ind_pariente_domestico", "ide_serv_domestico",
        "ind_discap_ver", "ind_discap_oir", "ind_discap_hablar", "ind_discap_moverse", "ind_discap_bañarse", "ind_discap_salir",
        "ind_discap_entender", "ind_discap_ninguna",
        "tip_seg_social", "ind_enfermo_30", "ind_acudio_salud", "ind_fue_atendido_salud",
        "ind_esta_embarazada", "ind_tuvo_hijos", "tip_cuidado_niños", "ind_recibe_comida",
        "ind_leer_escribir", "ind_estudia", "niv_educativo", "grado_alcanzado",
        "ind_fondo_pensiones", "tip_actividad_mes", "num_sem_buscando", "tip_empleado",
        "ind_ingr_salario", "vlr_ingr_salario", "ind_ingr_honorarios", "vlr_ingr_honorarios",
        "ind_ingr_cosecha", "vlr_ingr_cosecha", "ind_ingr_pension", "vlr_ingr_pension",
        "ind_ingr_remesa_pais", "vlr_ingr_remesa_pais", "ind_ingr_remesa_exterior", "vlr_ingr_remesa_exterior",
        "ind_ingr_arriendos", "vlr_ingr_arriendos", "ind_otros_ingresos", "vlr_otros_ingresos",
        "ind_ingr_estado", "vlr_ingr_fam_accion", "vlr_ingr_col_mayor", "vlr_ingr_otro_subsidio",
        "H_5", "I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8", "I9", "I10", "I11", "I12", "I13", "I14", "I15",
        "Edad", "anio",
    ]
    COLS_STR = [
        "NOM_BARRIO", "NOM_CORREGIMIENTO", "NOM_VEREDA", "Clasificacion", "grupo_sisben",
        "Fec_digitacion", "marca", "estado", "filename",
    ]

    for col in COLS_INT64:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    for col in COLS_STR:
        if col in df.columns:
            df[col] = df[col].astype(str).replace("nan", pd.NA)

    if "cod_mpio" in df.columns:
        df["cod_mpio"] = df["cod_mpio"].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(5).replace(["00nan", "000na", "nan"], pd.NA)

    grupo = df["Clasificacion"].astype(str).str[0].where(df["Clasificacion"].notna() & (df["Clasificacion"].astype(str) != "nan"), other="")
    df["orden_clasificacion"] = grupo.map({"A": 1, "B": 2, "C": 3, "D": 4}).fillna(99).astype("Int64")

    _tip_viv_map = {1: "Casa", 2: "Apartamento", 3: "Cuarto", 4: "Otro tipo de unidad de vivienda", 5: "Vivienda indígena"}
    df["Tipo_Vivienda_txt"] = to_int(df["tip_vivienda"]).map(_tip_viv_map).fillna("Sin información")

    _paredes_map = {
        0: "Sin paredes", 1: "Bloque, ladrillo, piedra, madera pulida", 2: "Tapia pisada o adobe", 3: "Bahareque",
        4: "Material prefabricado", 5: "Madera burda, tabla o tablón", 6: "Guadua, caña u otro vegetal", 7: "Zinc, tela, lona, cartón, desechos",
    }
    df["Material de las Paredes"] = to_int(df["tip_mat_paredes"]).map(_paredes_map).fillna("Sin información")

    _srv_map = {1: "Sí tiene servicio", 2: "No tiene servicio"}
    df["Energia_txt"]        = to_int(df["ind_tiene_energia"]).map(_srv_map).fillna("Sin información")
    df["Acueducto_txt"]      = to_int(df["ind_tiene_acueducto"]).map(_srv_map).fillna("Sin información")
    df["Alcantarillado_txt"] = to_int(df["ind_tiene_alcantarillado"]).map(_srv_map).fillna("Sin información")
    df["Gas_txt"]            = to_int(df["ind_tiene_gas"]).map(_srv_map).fillna("Sin información")
    df["Recoleccion_txt"]    = to_int(df["ind_tiene_recoleccion"]).map(_srv_map).fillna("Sin información")

    _clase_map = {1: "Urbano", 2: "Urbano", 3: "Rural"}
    df["Clase_txt"] = to_int(df["Cod_clase"]).map(_clase_map).fillna("Sin información")

    _sanitario_map = {
        1: "Con conexión a alcantarillado", 2: "Con conexión a pozo séptico",
        3: "Sin conexión a alcantarillado ni pozo", 4: "Letrina o bajamar", 5: "No tiene",
    }
    df["Sanitario_txt"] = to_int(df["tip_sanitario"]).map(_sanitario_map).fillna("Sin información")

    for _c in ["I11", "I12", "I13", "I14", "I15"]:
        df[_c] = to_int(df[_c])
    df["Privaciones_Vivienda"] = (df["I11"].fillna(0) + df["I12"].fillna(0) + df["I13"].fillna(0) + df["I14"].fillna(0) + df["I15"].fillna(0)).astype("Int64")

    _pv = df["Privaciones_Vivienda"]
    df["Nivel_Calidad_Vivienda"] = np.where(_pv == 0, "Sin privaciones", np.where(_pv <= 2, "Privación moderada", np.where(_pv >= 3, "Privación alta", "Sin información")))

    df["Zona"] = to_int(df["Cod_clase"]).map(_clase_map).fillna("Sin información")
    df["Es_Jefe"] = (to_int(df["tip_parentesco"]) == 1).astype("Int64")

    _jefe_mask = (to_int(df["tip_parentesco"]) == 1)
    df["Sexo_Jefe"] = pd.array([pd.NA] * len(df), dtype="Int64")
    df.loc[_jefe_mask, "Sexo_Jefe"] = to_int(df.loc[_jefe_mask, "sexo_persona"])

    _sexo_jefe_map = {1: "Hombre jefe", 2: "Mujer jefe"}
    df["Sexo_Jefe_Label"] = df["Sexo_Jefe"].map(_sexo_jefe_map)

    _personas = pd.to_numeric(df["num_personas_hogar"], errors="coerce")
    _cuartos  = pd.to_numeric(df["num_cuartos_vivienda"], errors="coerce").replace(0, np.nan)
    df["Personas_por_Cuarto"] = (_personas / _cuartos).astype("Float64")

    _ppc = df["Personas_por_Cuarto"]
    df["Cat_Hacinamiento"] = np.where(_ppc.isna(), "Sin información", np.where(_ppc > 3, "Hacinado", "No hacinado"))

    _piso_map = {
        1: "Alfombra o tapete, mármol, parqué, madera pulida y lacada", 2: "Baldosa, vinilo, tableta, ladrillo",
        3: "Cemento, gravilla", 4: "Madera burda, madera en mal estado, tabla, tablón",
        5: "Tierra o arena", 6: "Otro",
    }
    df["Material del Piso"] = to_int(df["tip_mat_pisos"]).map(_piso_map).fillna("Sin información")

    df["Orden_Paredes"] = to_int(df["tip_mat_paredes"])

    _ocupa_map = {
        1: "Arriendo o subarriendo", 2: "Propia pagando", 3: "Propia pagada",
        4: "Con permiso", 5: "Posesión sin título",
    }
    df["Tipo_Ocupacion_txt"] = to_int(df["tip_ocupa_vivienda"]).map(_ocupa_map).fillna("Sin información")

    _edad = pd.to_numeric(df["Edad"], errors="coerce")
    _rango_cond = [
        _edad <= 4,  _edad <= 9,  _edad <= 14, _edad <= 19, _edad <= 24, _edad <= 29, _edad <= 34, _edad <= 39, _edad <= 44, _edad <= 49,
        _edad <= 54, _edad <= 59, _edad <= 64, _edad <= 69, _edad <= 74, _edad <= 79, _edad >= 80,
    ]
    _rango_labels = [
        "00-04", "05-09", "10-14", "15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49",
        "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80+",
    ]
    df["Rango_Edad"] = np.select(_rango_cond, _rango_labels, default=pd.NA)

    _orden_edad_map = {
        "00-04": 1, "05-09": 2, "10-14": 3, "15-19": 4, "20-24": 5, "25-29": 6, "30-34": 7, "35-39": 8,
        "40-44": 9, "45-49": 10, "50-54": 11, "55-59": 12, "60-64": 13, "65-69": 14, "70-74": 15, "75-79": 16, "80+": 17,
    }
    df["Orden_Edad"] = df["Rango_Edad"].map(_orden_edad_map).astype("Int64")

    _regimen_map = {0: "Ninguno", 1: "Contributivo", 2: "Especial", 3: "Subsidiado", 9: "No sabe"}
    df["Regimen_Salud_Limpio"] = to_int(df["tip_seg_social"]).map(_regimen_map).fillna("Sin información")

    return df

COLS_CALCULADAS = [
    "orden_clasificacion", "Tipo_Vivienda_txt", "Material de las Paredes",
    "Energia_txt", "Acueducto_txt", "Alcantarillado_txt", "Gas_txt", "Recoleccion_txt",
    "Clase_txt", "Sanitario_txt", "Privaciones_Vivienda", "Nivel_Calidad_Vivienda", "Zona",
    "Es_Jefe", "Sexo_Jefe", "Sexo_Jefe_Label", "Personas_por_Cuarto", "Cat_Hacinamiento",
    "Material del Piso", "Orden_Paredes", "Tipo_Ocupacion_txt", "Rango_Edad", "Orden_Edad", "Regimen_Salud_Limpio",
]

# ─────────────────────────────────────────────────────────────────────────────
# BLOQUE 1: PROCESAMIENTO POR CHUNKS (ETL PARQUET)
# ─────────────────────────────────────────────────────────────────────────────
def generar_parquet():
    try:
        logging.info(f"[1] Abriendo Parquet fuente: {PARQUET_IN}")

        # ── Leer metadata ANTES de abrir el writer (así cerramos el handle de lectura
        #    lo antes posible y evitamos bloqueos cruzados en Windows) ──────────
        with open(PARQUET_IN, "rb") as f_in:
            pf_meta = pq.ParquetFile(f_in)
            total_rows = pf_meta.metadata.num_rows
            num_row_groups = pf_meta.metadata.num_row_groups
        logging.info(f"    Filas totales : {total_rows:,}")
        logging.info(f"    Row groups    : {num_row_groups}")

        writer = None
        filas_procesadas = 0
        chunk_num = 0
        t_inicio = time.time()

        logging.info(f"\n[2] Procesando en chunks de {CHUNK_ROWS:,} filas...")

        # ── Abrir el archivo fuente SOLO para leer; usamos un handle explícito
        #    para poder cerrarlo con precisión antes del rename. ─────────────────
        f_source = open(PARQUET_IN, "rb")
        try:
            pf = pq.ParquetFile(f_source)
            for batch in pf.iter_batches(batch_size=CHUNK_ROWS):
                chunk_num += 1
                t_chunk = time.time()

                df_chunk = batch.to_pandas()
                df_chunk = calcular_columnas(df_chunk)

                cols_base = [c for c in df_chunk.columns if c not in COLS_CALCULADAS]
                cols_finales = cols_base + [c for c in COLS_CALCULADAS if c in df_chunk.columns]
                df_chunk = df_chunk[cols_finales]

                table = pa.Table.from_pandas(df_chunk, preserve_index=False)

                if writer is None:
                    schema = table.schema
                    writer = pq.ParquetWriter(PARQUET_OUT, schema, compression="snappy")
                    logging.info(f"    Schema definido: {len(schema)} columnas")

                writer.write_table(table)

                filas_procesadas += len(df_chunk)
                elapsed = time.time() - t_chunk
                velocidad = len(df_chunk) / elapsed if elapsed > 0 else 0
                eta = (total_rows - filas_procesadas) / velocidad if velocidad > 0 else 0

                logging.info(f"    Chunk {chunk_num:>3} | {filas_procesadas:>12,} / {total_rows:,} filas | {elapsed:.1f}s | ETA: {eta/60:.1f} min")

                del df_chunk, table, batch
                gc.collect()

            if writer:
                writer.close()
                writer = None
        finally:
            # ── Cerrar el handle de LECTURA explícitamente ANTES del rename ──
            f_source.close()
            gc.collect()  # forzar liberación de referencias PyArrow
            time.sleep(0.5)  # pequeña pausa para que el SO libere el handle

        logging.info(f"\n[3] Chunks completados: {chunk_num} | Filas procesadas: {filas_procesadas:,}")

        # ── Reemplazo robusto con múltiples estrategias ───────────────────────
        logging.info("\n[4] Reemplazando archivo original (modo robusto)...")
        if PARQUET_OUT != PARQUET_FINAL:
            exito_reemplazo = _reemplazar_parquet_robusto(
                origen=PARQUET_OUT,
                destino=PARQUET_FINAL,
                reintentos=8,
                espera_seg=5.0,
            )
            if not exito_reemplazo:
                logging.error(
                    "❌ No se pudo reemplazar el Parquet final después de todos los reintentos. "
                    f"El resultado transformado está en: {PARQUET_OUT}"
                )
                return False
        else:
            logging.info(f"    ✓ Parquet escrito directamente en destino final: {PARQUET_FINAL}")

        size_mb = os.path.getsize(PARQUET_FINAL) / (1024 * 1024)
        tiempo_total = (time.time() - t_inicio) / 60

        logging.info(f"\n{'=' * 70}")
        logging.info(f"✅  PARQUET DEFINITIVO GUARDADO")
        logging.info(f"    Filas    : {filas_procesadas:,}")
        logging.info(f"    Tamaño   : {size_mb:.1f} MB")
        logging.info(f"    Tiempo   : {tiempo_total:.1f} minutos")
        logging.info(f"{'=' * 70}")

        logging.info("\n✅ ETL PARQUET completado exitosamente.")
        return True

    except Exception as e:
        logging.error(f"❌ Error crítico en generación de Parquet: {str(e)}", exc_info=True)
        if writer:
            try:
                writer.close()
            except Exception:
                pass
        return False

# ─────────────────────────────────────────────────────────────────────────────
# BLOQUE 2: POST-PROCESAMIENTO CSVs Y SHAREPOINT
# ─────────────────────────────────────────────────────────────────────────────

# ── Carga DIVIPOLA desde el archivo fuente (mismo origen que Power BI) ────────
# Archivo: Divpola_antioquia_PB.xlsx | Tabla: tblMpiosAntio
# Columnas usadas: cod_mpio (clave, 5 dígitos con padding) y NomMunicipio
DIVIPOLA_XLSX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DIVIPOLA_EAT_GOBANT.xlsx")

def _cargar_divipola() -> dict:
    """
    Lee el Excel DIVIPOLA local del proyecto y devuelve un dict {cod_mpio_5dig: nombre}.
    Usa hoja 'DIVIPOLA_EAT', columnas Cod_DANE_Mun y Nom_Mun.
    Si el archivo no existe o falla, devuelve dict vacío y loguea advertencia.
    """
    try:
        df_div = pd.read_excel(DIVIPOLA_XLSX, sheet_name="DIVIPOLA_EAT")
        # Normalizar cod_mpio a string de 5 dígitos
        df_div["cod_mpio"] = (
            df_div["Cod_DANE_Mun"].astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.zfill(5)
        )
        mapping = dict(zip(df_div["cod_mpio"], df_div["Nom_Mun"].astype(str)))
        logging.info(f"    ✓ DIVIPOLA cargado: {len(mapping)} municipios desde '{DIVIPOLA_XLSX}'")
        return mapping
    except FileNotFoundError:
        logging.warning(f"    ⚠️  Archivo DIVIPOLA no encontrado: '{DIVIPOLA_XLSX}'. NOM_MUNICIPIO usará solo el código.")
        return {}
    except Exception as e:
        logging.warning(f"    ⚠️  Error al leer DIVIPOLA: {e}. NOM_MUNICIPIO usará solo el código.")
        return {}

# Se carga una sola vez al inicio del bloque de post-procesamiento
DIVIPOLA_MUNICIPIOS: dict = {}  # se inicializa en generar_csvs_y_preparar_sharepoint()




def obtener_mpio(ruta):
    basename = os.path.basename(ruta)
    if "cod_mpio=" in basename:
        return basename.split("=")[1]
    return "00000"

def generar_csvs_y_preparar_sharepoint():
    global DIVIPOLA_MUNICIPIOS
    try:
        logging.info("\n" + "="*70)
        logging.info("INICIANDO POST-PROCESAMIENTO: GENERACIÓN DE CSVS Y CATÁLOGO DE SHAREPOINT")
        logging.info("="*70)

        # Cargar tabla DIVIPOLA desde el archivo fuente (mismo que Power BI)
        DIVIPOLA_MUNICIPIOS = _cargar_divipola()

        os.makedirs(OUTPUT_DIR_FULL, exist_ok=True)
        os.makedirs(OUTPUT_DIR_ULTIMO_ANIO, exist_ok=True)

        logging.info("[1] Consultando el último año disponible en la base de datos...")
        max_anio = duckdb.query(f"SELECT MAX(anio) as max_anio FROM '{PARQUET_FINAL}'").fetchone()[0]
        logging.info(f"    Último año detectado: {max_anio}")

        # Se omite el particionado de la base completa por instrucción del usuario.

        # ── Columnas excluidas del CSV: todas las calculadas + columnas técnicas ────
        # Columnas a EXCLUIR del CSV de descarga:
        #   - COLS_CALCULADAS:  columnas generadas por el ETL (Material de las Paredes, etc.)
        #   - "Source.Name":    columna técnica del origen del archivo Excel, sin valor para el usuario final
        #   - "Fec_digitacion": columna de fecha/hora de digitación, no hace parte del diccionario de variables SISBEN
        #   - "Material de las Paredes" / "Material del Piso" (cat_paredes/cat_pisos): ya incluidas en COLS_CALCULADAS
        # Adicionalmente se reordena: Clasificacion, grupo_sisben, anio quedan justo después de NOM_BARRIO.
        # Se agrega columna NOM_MUNICIPIO = cod_mpio + ' - ' + nombre DIVIPOLA.
        COLS_EXCLUIR_CSV = set(COLS_CALCULADAS) | {"Source.Name", "Fec_digitacion"}

        # Orden deseado en el CSV:
        # 1. cod_mpio
        # 2. NOM_MUNICIPIO (nueva columna calculada inline)
        # 3. Cod_clase
        # 4. NOM_BARRIO
        # 5. Clasificacion, grupo_sisben, anio   ← movidas aquí
        # 6. Resto de columnas base en orden natural (excluyendo las ya colocadas y las excluidas)
        COLS_PRIORIDAD = ["cod_mpio", "Cod_clase", "NOM_BARRIO", "Clasificacion", "grupo_sisben", "anio"]

        # Obtener columnas disponibles en el parquet (excluyendo las no deseadas)
        all_cols_raw = duckdb.query(f"DESCRIBE SELECT * FROM '{PARQUET_FINAL}' LIMIT 0").fetchall()
        all_cols = [row[0] for row in all_cols_raw]
        cols_base_disponibles = [
            c for c in all_cols
            if c not in COLS_EXCLUIR_CSV and c not in COLS_PRIORIDAD
        ]

        # Lista final de columnas en el CSV (sin incluir NOM_MUNICIPIO aún — se agrega como expresión SQL)
        # Orden: cod_mpio, Cod_clase, NOM_BARRIO, Clasificacion, grupo_sisben, anio, [resto]
        cols_prioridad_validas = [c for c in COLS_PRIORIDAD if c in all_cols]
        cols_csv_finales = cols_prioridad_validas + cols_base_disponibles

        # Construir el SELECT con NOM_MUNICIPIO en segunda posición
        def col_quoted(c):
            return f'"{c}"'

        # La columna NOM_MUNICIPIO se genera inline con un CASE WHEN en DuckDB
        # Si el diccionario está vacío (DIVIPOLA no cargó), se usa solo el código
        if DIVIPOLA_MUNICIPIOS:
            case_parts = " ".join([
                f"WHEN cod_mpio = '{k}' THEN '{k} - {v}'"
                for k, v in DIVIPOLA_MUNICIPIOS.items()
            ])
            nom_municipio_expr = f"(CASE {case_parts} ELSE cod_mpio || ' - Sin nombre' END) AS \"NOM_MUNICIPIO\""
        else:
            nom_municipio_expr = "(cod_mpio || ' - Sin nombre') AS \"NOM_MUNICIPIO\""

        # SELECT final: cod_mpio, NOM_MUNICIPIO, Cod_clase, NOM_BARRIO, Clasificacion, grupo_sisben, anio, [resto]
        select_cols = [
            col_quoted("cod_mpio"),
            nom_municipio_expr,
        ]
        # Agregar el resto en orden (sin cod_mpio que ya está primero)
        for c in cols_csv_finales:
            if c != "cod_mpio":
                select_cols.append(col_quoted(c))

        select_sql = ", ".join(select_cols)
        logging.info(f"    Columnas en el CSV: {len(select_cols)} (incluyendo NOM_MUNICIPIO)")

        logging.info(f"[2] Particionando base ÚLTIMO AÑO ({max_anio}) por municipio con columnas y orden configurados...")
        query_csv = (
            f"COPY ("
            f"  SELECT {select_sql} "
            f"  FROM '{PARQUET_FINAL}' "
            f"  WHERE anio = {max_anio}"
            f") TO '{OUTPUT_DIR_ULTIMO_ANIO}' "
            f"(FORMAT CSV, PARTITION_BY (cod_mpio), OVERWRITE_OR_IGNORE 1, HEADER 1);"
        )
        duckdb.query(query_csv)
        logging.info(f"    ✓ CSVs del último año generados exitosamente.")

        # --- Copia a SharePoint ---
        def concatenar_csvs(mpio_dir, output_file):
            archivos = sorted(glob.glob(os.path.join(mpio_dir, "data*.csv")))
            if not archivos:
                return False
            with open(output_file, 'wb') as outfile:
                outfile.write(b'\xef\xbb\xbf')
                for i, fname in enumerate(archivos):
                    with open(fname, 'rb') as infile:
                        if i != 0:
                            infile.readline() # Saltar header
                        shutil.copyfileobj(infile, outfile)
            return True

        carpetas_ultimo = glob.glob(os.path.join(OUTPUT_DIR_ULTIMO_ANIO, "cod_mpio=*"))
        
        logging.info(f"[3] Encontradas {len(carpetas_ultimo)} carpetas de último año.")
        logging.info(f"[4] Concatenando y copiando archivos a carpeta sincronizada local de SharePoint...")
        
        os.makedirs(os.path.join(SHAREPOINT_LOCAL_SYNC_DIR, "Ultimo_Anio"), exist_ok=True)
        
        datos_dim = []
        
        for c_dir in carpetas_ultimo:
            mpio = obtener_mpio(c_dir)
            outfile = os.path.join(SHAREPOINT_LOCAL_SYNC_DIR, "Ultimo_Anio", f"mpio_{mpio}_ultimo_anio.csv")
            if concatenar_csvs(c_dir, outfile):
                datos_dim.append({
                    "cod_mpio": mpio,
                    "Url_Descarga": f"{SHAREPOINT_WEB_BASE_URL}Ultimo_Anio/mpio_{mpio}_ultimo_anio.csv?download=1"
                })
            
        logging.info(f"    ✓ Archivos concatenados y copiados a SharePoint local: {SHAREPOINT_LOCAL_SYNC_DIR}")

        # --- Generar Catálogo Dimensión ---
        logging.info(f"[5] Generando tabla de URLs para Power BI...")
        if datos_dim:
            pd.DataFrame(datos_dim).to_csv(OUTPUT_DIM_CSV, index=False)
            logging.info(f"    ✓ Dimensión creada exitosamente: {OUTPUT_DIM_CSV}")
        else:
            logging.warning("    ⚠️ No se encontraron datos para generar la dimensión.")

        logging.info("\n✅ PIPELINE COMPLETO FINALIZADO EXITOSAMENTE.")

    except Exception as e:
        logging.error(f"❌ Error en la generación de CSVs o subida a SharePoint: {str(e)}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# EJECUCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    exito_parquet = generar_parquet()
    if exito_parquet:
        generar_csvs_y_preparar_sharepoint()
    else:
        logging.warning("⚠️ No se ejecutó la generación de CSVs debido a un error previo en el Parquet.")
