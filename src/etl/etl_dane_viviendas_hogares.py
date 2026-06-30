import pandas as pd
import os

# Archivos de entrada
FILE_HOGARES = r"D:\VVANEGASA\Desktop\antigravity_sisben\anexo-proyecciones-hogares-dptal-mpal-2018-2042.xlsx"
FILE_VIVIENDAS = r"D:\VVANEGASA\Desktop\antigravity_sisben\anexo-proyecciones-viviendas-dptal-mpal-2018-2042.xlsx"

# Archivos de salida
OUT_HOGARES = r"D:\VVANEGASA\My Documents\hogares_dane.parquet"
OUT_VIVIENDAS = r"D:\VVANEGASA\My Documents\viviendas_dane.parquet"

def process_dane_file(file_path, sheet_name, value_col_name):
    print(f"Procesando {file_path}...")
    # Leer sin encabezado desde la fila 10 (donde empieza la data real)
    df = pd.read_excel(file_path, sheet_name=sheet_name, skiprows=10, header=None)
    
    # Hay 5 columnas iniciales + 25 años (2018 a 2042) = 30 columnas
    # Las columnas son: cod_dpto, nom_dpto, cod_mpio, nom_mpio, Area, 2018, 2019... 2042
    years = list(range(2018, 2043))
    cols = ['cod_dpto', 'nom_dpto', 'cod_mpio', 'nom_mpio', 'Area'] + years
    
    # Asignar a las primeras 30 columnas, si hay más las ignoramos
    df = df.iloc[:, :len(cols)]
    df.columns = cols
    
    # Filtrar solo Antioquia (Código 05 o '05')
    df = df[df['cod_dpto'].astype(str).str.zfill(2) == '05']
    
    # Asegurar que cod_mpio tenga 5 caracteres (ej: '05001')
    # A veces viene como número, a veces como string. Si es nulo lo ignoramos
    df = df.dropna(subset=['cod_mpio'])
    # Convertir float a int para evitar '5001.0' -> '05001'
    df['cod_mpio'] = df['cod_mpio'].apply(lambda x: str(int(x)).zfill(5) if pd.notnull(x) and str(x).replace('.0','').isdigit() else str(x))
    
    # Mapear Área a Cod_clase
    def map_area(x):
        x_str = str(x).lower().strip()
        if 'cabecera' in x_str: return 1
        elif 'rural' in x_str or 'centro' in x_str: return 2
        elif 'total' in x_str: return 0
        return -1
        
    df['Cod_clase'] = df['Area'].apply(map_area)
    
    # Hacer Melt (Unpivot)
    df_melted = df.melt(
        id_vars=['cod_mpio', 'Cod_clase'],
        value_vars=years,
        var_name='anio',
        value_name=value_col_name
    )
    
    # Convertir tipos
    df_melted['anio'] = df_melted['anio'].astype(int)
    df_melted = df_melted.dropna(subset=[value_col_name])
    df_melted[value_col_name] = df_melted[value_col_name].round().astype(int)
    
    return df_melted[['cod_mpio', 'anio', 'Cod_clase', value_col_name]]

if __name__ == "__main__":
    anios_cobertura = [2021, 2022, 2023, 2024, 2025, 2026]
    print(f"Filtrando proyecciones para los años: {anios_cobertura}")

    df_hogares = process_dane_file(FILE_HOGARES, 'Proyecciones Hogares mpio', 'Hogares_Proyectados')
    df_hogares = df_hogares[df_hogares['anio'].isin(anios_cobertura)]
    df_hogares.to_parquet(OUT_HOGARES, index=False)
    print(f"Guardado exitosamente: {OUT_HOGARES} con {len(df_hogares)} registros.")
    
    df_viviendas = process_dane_file(FILE_VIVIENDAS, 'Proye total viviendas mpio', 'Viviendas_Proyectadas')
    df_viviendas = df_viviendas[df_viviendas['anio'].isin(anios_cobertura)]
    df_viviendas.to_parquet(OUT_VIVIENDAS, index=False)
    print(f"Guardado exitosamente: {OUT_VIVIENDAS} con {len(df_viviendas)} registros.")
