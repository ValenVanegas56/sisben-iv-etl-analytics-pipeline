import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import sys
import os

# --- Configuración ---
sys.stdout.reconfigure(encoding="utf-8")

CSV_IN = r"D:\VVANEGASA\My Documents\Input Tablero Sisbén 2021-2026\POB_ANT_2006-2035_Act08-2025-AjustMed.csv"
PARQUET_OUT = r"D:\VVANEGASA\My Documents\poblacion_proyectada.parquet"

print("Iniciando ETL de Población Proyectada (Robust Mode)...")

# --- Lectura ---
# El DANE suele usar ISO-8859-1 para la Ñ, pero a veces viene corrupto
try:
    df = pd.read_csv(CSV_IN, encoding="ISO-8859-1")
except:
    df = pd.read_csv(CSV_IN, encoding="utf-8")

# --- Normalización de Columnas ---
# Buscamos las columnas por aproximación para evitar errores de codificación
map_cols = {}
for c in df.columns:
    c_upper = str(c).upper()
    if "DPMP" in c_upper: map_cols[c] = "DPMP"
    if "AO" in c_upper or "A" in c_upper and "O" in c_upper and len(c) < 5: map_cols[c] = "AÑO"
    if "GENERO" in c_upper: map_cols[c] = "Genero"
    if "REA" in c_upper and "GEOGR" in c_upper: map_cols[c] = "AREA_TXT"
    if "EDAD_NUM" in c_upper: map_cols[c] = "Edad_Num"
    if "POB" in c_upper and len(c) < 5: map_cols[c] = "Pob"

df.rename(columns=map_cols, inplace=True)
print(f"Columnas mapeadas: {list(df.columns)}")

# --- Filtros ---
print("Filtrando años 2021-2026...")
df = df[df["AÑO"].isin([2021, 2022, 2023, 2024, 2025, 2026])]

# --- Mapeos Geográficos y Demográficos ---

# 1. Municipio (DPMP a cod_mpio de 5 dígitos)
df["cod_mpio"] = df["DPMP"].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(5)

# 2. Género (Hombres=1, Mujeres=2)
df["sexo_persona"] = df["Genero"].map({"Hombres": 1, "Mujeres": 2}).fillna(0).astype(int)

# 3. Área (Filtramos y mapeamos a IDs de Sisben)
# CSV: "Cabecera Municipal" -> 1, "Centro Poblado y Rural Disperso" -> 3
df["Cod_clase"] = df["AREA_TXT"].map({
    "Cabecera Municipal": 1, 
    "Centro Poblado y Rural Disperso": 3
}).fillna(3).astype(int)

# 4. Rango de Edad (Mismo que Sisben para comparabilidad)
def get_rango_edad(edad):
    try:
        e = float(edad)
        if e <= 4: return "00-04"
        if e <= 9: return "05-09"
        if e <= 14: return "10-14"
        if e <= 19: return "15-19"
        if e <= 24: return "20-24"
        if e <= 29: return "25-29"
        if e <= 34: return "30-34"
        if e <= 39: return "35-39"
        if e <= 44: return "40-44"
        if e <= 49: return "45-49"
        if e <= 54: return "50-54"
        if e <= 59: return "55-59"
        if e <= 64: return "60-64"
        if e <= 69: return "65-69"
        if e <= 74: return "70-74"
        if e <= 79: return "75-79"
        return "80+"
    except:
        return "Sin información"

df["Rango_Edad"] = df["Edad_Num"].apply(get_rango_edad)

# --- Agregación ---
print("Agregando datos por grupo poblacional...")
df_agg = df.groupby(["cod_mpio", "AÑO", "Cod_clase", "sexo_persona", "Rango_Edad"], as_index=False)["Pob"].sum()

# Renombrar para claridad en Power BI
df_agg.rename(columns={"AÑO": "anio", "Pob": "Poblacion_Proyectada"}, inplace=True)

# --- Exportación ---
print(f"Exportando a Parquet: {PARQUET_OUT}")
table = pa.Table.from_pandas(df_agg, preserve_index=False)
pq.write_table(table, PARQUET_OUT, compression="snappy")

print("="*50)
print(f"ETL COMPLETADO EXITOSAMENTE")
print(f"Filas resultantes: {len(df_agg):,}")
print("="*50)
