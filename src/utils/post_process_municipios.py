# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
"""
post_process_municipios.py
==========================
1. Agrega columna nom_mpio a cada CSV de municipio en OneDrive.
2. Renombra archivos: mpio_05001_MEDELLIN_ultimo_anio.csv
3. Regenera dim_descargas_municipios.csv con cod_mpio, nom_mpio, Url_Descarga.
"""

import os
import glob
import shutil
import pandas as pd
import unicodedata
import csv

# ── Rutas ─────────────────────────────────────────────────────────────────────
ONEDRIVE_DIR    = r"C:\Users\VVANEGASA\OneDrive - Universidad de Medellin\SISBEN_Data\Data_Municipios\Ultimo_Anio"
OUTPUT_DIM_CSV  = r"D:\VVANEGASA\My Documents\dim_descargas_municipios.csv"
SP_BASE_URL     = "https://udemedellin-my.sharepoint.com/personal/vvanegas409_soyudemedellin_edu_co/Documents/SISBEN_Data/Data_Municipios/Ultimo_Anio/"

# ── Diccionario DANE: 125 municipios de Antioquia ────────────────────────────
MUNICIPIOS = {
    "05001": "MEDELLIN",         "05002": "ABEJORRAL",        "05004": "ABRIAQUI",
    "05021": "ALEJANDRIA",       "05030": "AMAGA",            "05031": "AMALFI",
    "05034": "ANDES",            "05036": "ANGELOPOLIS",      "05038": "ANGOSTURA",
    "05040": "ANORI",            "05042": "SANTAFE DE ANTIOQUIA", "05044": "ANZA",
    "05045": "APARTADO",         "05051": "ARBOLETES",        "05055": "ARGELIA",
    "05059": "ARMENIA",          "05079": "BARBOSA",          "05086": "BELLO",
    "05088": "BELMIRA",          "05091": "BETANIA",          "05093": "BETULIA",
    "05101": "CIUDAD BOLIVAR",   "05107": "BRICENO",          "05113": "BURITICA",
    "05120": "CACERES",          "05125": "CAICEDO",          "05129": "CALDAS",
    "05134": "CAMPAMENTO",       "05138": "CANASGORDAS",      "05142": "CARACOLI",
    "05145": "CARAMANTA",        "05147": "CAREPA",           "05148": "EL CARMEN DE VIBORAL",
    "05150": "CAROLINA",         "05154": "CAUCASIA",         "05172": "CHIGORODO",
    "05190": "CISNEROS",         "05197": "COCORNA",          "05206": "CONCEPCION",
    "05209": "CONCORDIA",        "05212": "COPACABANA",       "05234": "DABEIBA",
    "05237": "DON MATIAS",       "05240": "EBEJICO",          "05250": "EL BAGRE",
    "05264": "ENTRERRIOS",       "05266": "ENVIGADO",         "05282": "FREDONIA",
    "05284": "FRONTINO",         "05306": "GIRALDO",          "05308": "GIRARDOTA",
    "05310": "GOMEZ PLATA",      "05313": "GRANADA",          "05315": "GUADALUPE",
    "05318": "GUARNE",           "05321": "GUATAPE",          "05347": "HELICONIA",
    "05353": "HISPANIA",         "05360": "ITAGUI",           "05361": "ITUANGO",
    "05364": "JARDIN",           "05368": "JERICO",           "05376": "LA CEJA",
    "05380": "LA ESTRELLA",      "05390": "LA PINTADA",       "05400": "LA UNION",
    "05411": "LIBORINA",         "05425": "MACEO",            "05440": "MARINILLA",
    "05467": "MONTEBELLO",       "05475": "MURINDO",          "05480": "MUTATA",
    "05483": "NARINO",           "05490": "NECOCLI",          "05495": "NECHI",
    "05501": "OLAYA",            "05541": "PENOL",            "05543": "PEQUE",
    "05576": "PUEBLORRICO",      "05579": "PUERTO BERRIO",    "05585": "PUERTO NARE",
    "05591": "PUERTO TRIUNFO",   "05604": "REMEDIOS",         "05607": "RETIRO",
    "05615": "RIONEGRO",         "05628": "SABANALARGA",      "05631": "SABANETA",
    "05642": "SALGAR",           "05647": "SAN ANDRES DE CUERQUIA", "05649": "SAN CARLOS",
    "05652": "SAN FRANCISCO",    "05656": "SAN JERONIMO",     "05658": "SAN JOSE DE LA MONTANA",
    "05659": "SAN JUAN DE URABA","05660": "SAN LUIS",         "05664": "SAN PEDRO DE LOS MILAGROS",
    "05665": "SAN PEDRO DE URABA","05667": "SAN RAFAEL",      "05670": "SAN ROQUE",
    "05674": "SAN VICENTE FERRER","05679": "SANTA BARBARA",   "05686": "SANTA ROSA DE OSOS",
    "05690": "SANTO DOMINGO",    "05697": "EL SANTUARIO",     "05736": "SEGOVIA",
    "05756": "SONSON",           "05761": "SOPETRAN",         "05789": "TAMESIS",
    "05790": "TARAZA",           "05792": "TARSO",            "05809": "TITIRIBÍ",
    "05819": "TOLEDO",           "05837": "TURBO",            "05842": "URAMITA",
    "05847": "URRAO",            "05854": "VALDIVIA",         "05856": "VALPARAISO",
    "05858": "VEGACHI",          "05861": "VENECIA",          "05873": "VIGIA DEL FUERTE",
    "05885": "YALI",             "05887": "YARUMAL",          "05890": "YOLOMBO",
    "05893": "YONDO",            "05895": "ZARAGOZA",
}

def normalizar(nombre):
    """Elimina tildes y caracteres especiales para uso en nombre de archivo."""
    nfkd = unicodedata.normalize("NFKD", nombre)
    sin_tilde = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sin_tilde.upper().replace(" ", "_")

def procesar():
    archivos = glob.glob(os.path.join(ONEDRIVE_DIR, "mpio_*.csv"))
    print(f"Encontrados {len(archivos)} archivos CSV en OneDrive.")

    datos_dim = []
    procesados = 0
    sin_nombre = []

    for ruta_vieja in sorted(archivos):
        nombre_archivo = os.path.basename(ruta_vieja)

        # Extraer cod_mpio del nombre actual (mpio_05001_... o mpio_05001_NOMBRE_...)
        partes = nombre_archivo.replace("mpio_", "").replace("_ultimo_anio.csv", "").split("_")
        cod = partes[0].zfill(5)

        nom = MUNICIPIOS.get(cod)
        if not nom:
            sin_nombre.append(cod)
            nom = f"COD{cod}"  # fallback

        nom_safe = normalizar(nom)

        # Nombre nuevo del archivo
        nuevo_nombre = f"mpio_{cod}_{nom_safe}_ultimo_anio.csv"
        ruta_nueva = os.path.join(ONEDRIVE_DIR, nuevo_nombre)

        # Leer CSV actual
        try:
            df = pd.read_csv(ruta_vieja, dtype=str, encoding="utf-8-sig")
        except Exception as e:
            print(f"  ERROR leyendo {nombre_archivo}: {e}")
            continue

        # Asegurar que cod_mpio tenga cero al inicio
        if "cod_mpio" in df.columns:
            df["cod_mpio"] = df["cod_mpio"].str.zfill(5)

        # Agregar nom_mpio como segunda columna si no existe
        if "nom_mpio" not in df.columns:
            df.insert(1, "nom_mpio", nom)

        # Guardar en nuevo nombre con BOM (para que Excel lea tildes bien)
        with open(ruta_nueva, "w", newline="", encoding="utf-8-sig") as f:
            df.to_csv(f, index=False)

        # Borrar archivo viejo solo si el nombre cambió
        if ruta_vieja != ruta_nueva and os.path.exists(ruta_vieja):
            os.remove(ruta_vieja)

        # Registro para dim
        url = f"{SP_BASE_URL}{nuevo_nombre}?download=1"
        datos_dim.append({"cod_mpio": cod, "nom_mpio": nom, "Url_Descarga": url})
        procesados += 1
        print(f"  ✓ {nuevo_nombre}")

    # Generar dim CSV
    df_dim = pd.DataFrame(datos_dim).sort_values("cod_mpio")
    df_dim.to_csv(OUTPUT_DIM_CSV, index=False, quoting=csv.QUOTE_ALL)

    print(f"\n{'='*60}")
    print(f"✅ Procesados: {procesados} municipios")
    print(f"✅ dim_descargas_municipios.csv regenerado con {len(df_dim)} filas")
    if sin_nombre:
        print(f"⚠️  Sin nombre DANE: {sin_nombre}")
    print(f"{'='*60}")
    print(df_dim.head(3).to_string())

if __name__ == "__main__":
    procesar()
