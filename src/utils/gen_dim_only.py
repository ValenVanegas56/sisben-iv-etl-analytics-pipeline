import os
import glob
import pandas as pd
import csv

# ─── NUEVAS RUTAS LOCALES ──────────────────────────────────────────
ONEDRIVE_DIR_CSVS = r"C:\Users\VVANEGASA\OneDrive - Gobernacion de Antioquia\SISBEN\Data_Municipios\Ultimo_Anio"
ONEDRIVE_DIR_INFORMES = r"C:\Users\VVANEGASA\OneDrive - Gobernacion de Antioquia\SISBEN\Informes_Municipales"

OUTPUT_DIM_CSV  = r"D:\VVANEGASA\My Documents\dim_descargas_municipios.csv"

# ─── NUEVAS RUTAS WEB (SHAREPOINT GOBERNACIÓN) ─────────────────────
SP_BASE_CSV = "https://gobantioquia-my.sharepoint.com/personal/hromeror_antioquia_gov_co/Documents/SISBEN/Data_Municipios/Ultimo_Anio/"
SP_BASE_INFORME = "https://gobantioquia-my.sharepoint.com/personal/hromeror_antioquia_gov_co/Documents/SISBEN/Informes_Municipales/"
URL_VARIABLES = "https://gobantioquia-my.sharepoint.com/personal/hromeror_antioquia_gov_co/Documents/SISBEN/Variables/Variables.xlsx?download=1"

def generar_dim():
    archivos = glob.glob(os.path.join(ONEDRIVE_DIR_CSVS, "mpio_*.csv"))
    datos_dim = []
    
    for ruta in archivos:
        nombre_archivo = os.path.basename(ruta)
        # Expected format: mpio_05001_MEDELLIN_ultimo_anio.csv
        partes = nombre_archivo.replace("mpio_", "").replace("_ultimo_anio.csv", "").split("_", 1)
        if len(partes) == 2:
            cod = partes[0]
            nom = partes[1]
        else:
            # Ignorar los archivos viejos que no tienen el nombre del municipio (ej. mpio_05001_ultimo_anio.csv)
            continue
            
        nombre_informe = f"informe_{cod}_{nom}.pdf"
            
        url_csv = f"{SP_BASE_CSV}{nombre_archivo}?download=1"
        url_informe = f"{SP_BASE_INFORME}{nombre_informe}?download=1"
        url_bandera_escudo = f"https://github.com/HmRomeror/BandsMpios_Antio/blob/main/{cod}.png?raw=true"
        
        datos_dim.append({
            "cod_mpio": cod, 
            "nom_mpio": nom.replace("_", " "), 
            "Url_Descarga": url_csv,
            "Url_Informe": url_informe,
            "Url_Descarga_Variables": URL_VARIABLES,
            "Bandera_escudo": url_bandera_escudo
        })
        
    df_dim = pd.DataFrame(datos_dim).sort_values("cod_mpio")
    
    try:
        df_dim.to_csv(OUTPUT_DIM_CSV, index=False, quoting=csv.QUOTE_ALL)
        print(f"[EXITO] {OUTPUT_DIM_CSV} regenerado con {len(df_dim)} filas")
    except PermissionError:
        print(f"[ERROR] El archivo {OUTPUT_DIM_CSV} esta abierto en otro programa (Power BI o Excel). Por favor cierralo e intenta de nuevo.")

if __name__ == "__main__":
    generar_dim()
