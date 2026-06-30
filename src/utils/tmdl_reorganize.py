#!/usr/bin/env python3
"""
tmdl_reorganize.py — Reorganiza modelo SISBEN 1604
1. Agrega displayFolder a todas las medidas
2. Corrige medidas rotas (Pct_Pisos, Pct_Paredes)
3. Renombra tabla '1 Anonimizados (2)' → fct_Sisben
4. Renombra relaciones
5. Elimina Tabla.tmdl (tabla basura)
"""

import os, re, shutil

TMDL      = r"D:\VVANEGASA\Desktop\antigravity_sisben\tmdl_sisben"
TABLES    = os.path.join(TMDL, "tables")

# ── 1. MAPA DE CARPETAS ──────────────────────────────────────────────────────
F = {
    # IPM
    "Hogares Pobres":"IPM","Personas IPM":"IPM","Porcentaje_IPM":"IPM",
    "Incidencia":"IPM","Incidencia_Departamental":"IPM","Incidencia_SISBEN":"IPM",
    "IPM_Max":"IPM","Año_Maximo":"IPM","IPM_Año_Actual":"IPM","IPM_Año_Anterior":"IPM",
    "Variacion_IPM":"IPM","Variacion_Max":"IPM","Variacion_Min":"IPM",
    "Ranking_IPM":"IPM","Ranking_Variacion":"IPM","Ranking_Reduccion":"IPM",
    "Ranking_Personas_IPM":"IPM","Ranking_Volumen":"IPM",
    "Municipio_Max_IPM":"IPM","Municipio_Max_Personas":"IPM",
    "Municipio_Mayor_Aumento":"IPM","Municipio_Mayor_Reduccion":"IPM","Municipio_Mayor_Volumen":"IPM",
    "Subregion_Mayor_Incidencia":"IPM","Personas_Max_IPM":"IPM",
    "Personas_Pobreza":"IPM","Pct_Personas_Pobreza":"IPM",
    "Participacion_IPM":"IPM","Participacion_IPM_Grupo":"IPM",
    "Participacion_IPM_Subregion2":"IPM","Participacion_IPM_Subregion3":"IPM",
    "Participacion_Max":"IPM","Participacion_Lider":"IPM",
    "IPM_Acumulado":"IPM","IPM_Acumulado_%":"IPM",
    "IPM_Subtexto":"IPM","SISBEN_Subtexto":"IPM",
    "Texto_Max_IPM":"IPM","Texto_Aumento":"IPM","Texto_Reduccion":"IPM",
    "Pct_PersonasIPM_Municipio":"IPM","Tarjeta_IPM_Combinada":"IPM",
    # IPM\Dimensiones IPM
    "Pct_I1_BajoLogroEducativo":"IPM\\Dimensiones IPM",
    "Pct_I2_Analfabetismo":"IPM\\Dimensiones IPM",
    "Pct_I3_InasistenciaEscolar":"IPM\\Dimensiones IPM",
    "Pct_I4_RezagoEscolar":"IPM\\Dimensiones IPM",
    "Pct_I5_BarrerasCuidadoInfancia":"IPM\\Dimensiones IPM",
    "Pct_I6_TrabajoInfantil":"IPM\\Dimensiones IPM",
    "Pct_I7_DesempleoLargaDuracion":"IPM\\Dimensiones IPM",
    "Pct_I8_TrabajoInformal":"IPM\\Dimensiones IPM",
    "Pct_I9_SinAseguramientoSalud":"IPM\\Dimensiones IPM",
    "Pct_I10_BarreraAccesoServiciosSalud":"IPM\\Dimensiones IPM",
    "Pct_I11_SinAccesoFuentesAguaMejorada":"IPM\\Dimensiones IPM",
    "Pct_I12_InadecuadaEliminacionExcretas":"IPM\\Dimensiones IPM",
    "Pct_I13_MaterialInadecuadoPisos":"IPM\\Dimensiones IPM",
    "Pct_I14_MaterialInadecuadoParedes":"IPM\\Dimensiones IPM",
    "Pct_I15_HacinamientoCritico":"IPM\\Dimensiones IPM",
    "Titulo_Heatmap_IPM":"IPM",
    # Vivienda
    "Total_Viviendas":"Vivienda","tViviendas_Con_Privacion":"Vivienda",
    "Pct_Viv_Con_Privacion":"Vivienda","Pct_Viviendas_Rurales":"Vivienda",
    "Prom_Privaciones_Vivienda":"Vivienda","Prom_Priv_Rural":"Vivienda",
    "Prom_Priv_Cabecera":"Vivienda","Prom_Priv_Hombre":"Vivienda","Prom_Priv_Mujer":"Vivienda",
    "Brecha_Privaciones":"Vivienda","Score_Vivienda_Hogar":"Vivienda",
    "Prom_Calidad_Municipio":"Vivienda","Prom_Cuartos_Vivienda":"Vivienda",
    "Prom_Hogares_Vivienda":"Vivienda","Pct_Viviendas_Multiples_Hogares":"Vivienda",
    "Pct_Hacinamiento_Observable":"Vivienda","Pct_Pared_Material":"Vivienda",
    "Pct_Piso_Material":"Vivienda","Viviendas_Jefe_Hombre":"Vivienda",
    "Viviendas_Jefa_Mujer":"Vivienda","Pct_Jefe_Hombre":"Vivienda","Pct_Jefa_Mujer":"Vivienda",
    "Hogares_Jefe_Hombre":"Vivienda","Hogares_Jefa_Mujer":"Vivienda",
    "Pct_Viviendas_Energia":"Vivienda","Pct_Viviendas_Acueducto":"Vivienda",
    "Pct_Viviendas_Gas":"Vivienda","Max_Problema_Vivienda":"Vivienda",
    "Problema_Dominante":"Vivienda",
    # Vivienda\Privaciones
    "Pct_Sin_Energia":"Vivienda\\Privaciones","Pct_Sin_Acueducto":"Vivienda\\Privaciones",
    "Pct_Sin_Alcantarillado":"Vivienda\\Privaciones","Pct_Sin_Gas":"Vivienda\\Privaciones",
    "Pct_Sin_Recoleccion":"Vivienda\\Privaciones","Pct_Sin_Agua":"Vivienda\\Privaciones",
    "Pct_Hacinamiento":"Vivienda\\Privaciones","Pct_Saneamiento_Inadecuado":"Vivienda\\Privaciones",
    "Pct_Pisos_Inadecuados":"Vivienda\\Privaciones","Pct_Paredes_Inadecuadas":"Vivienda\\Privaciones",
    # Vivienda\Eventos Naturales
    "Pct_Viv_Afectadas_Inundacion":"Vivienda\\Eventos Naturales",
    "Pct_Viv_Afectadas_Avalancha":"Vivienda\\Eventos Naturales",
    "Pct_Viv_Afectadas_Terremoto":"Vivienda\\Eventos Naturales",
    "Pct_Viv_Afectadas_Incendio":"Vivienda\\Eventos Naturales",
    "Pct_Viv_Afectadas_Vendaval":"Vivienda\\Eventos Naturales",
    "Pct_Viv_Afectadas_Hundimiento":"Vivienda\\Eventos Naturales",
    "Prom_Inundaciones":"Vivienda\\Eventos Naturales","Prom_Avalancha":"Vivienda\\Eventos Naturales",
    "Prom_Hundimiento":"Vivienda\\Eventos Naturales","Prom_Incendio":"Vivienda\\Eventos Naturales",
    "Prom_Terremoto":"Vivienda\\Eventos Naturales",
    # Hogares
    "Hogares":"Hogares","Prom_Personas_Hogar":"Hogares",
    "Tamano_Promedio_Hogar":"Hogares","Personas_por_Cuarto_Dormir":"Hogares",
    "Pct_Hogares_Agua7Dias":"Hogares","Pct_Hogares_Agua24H":"Hogares",
    "Pct_Hogares_Cocina":"Hogares","Pct_Hogares_Combustible_Solido":"Hogares",
    "Pct_Hogares_Internet":"Hogares","Pct_Hogares_Nevera":"Hogares",
    "Pct_Hogares_Lavadora":"Hogares","Pct_Hogares_Pc":"Hogares",
    "Pct_Hogares_Moto":"Hogares","Pct_Hogares_Tractor":"Hogares",
    "Pct_Hogares_Carro":"Hogares","Pct_Hogares_Bien_Raiz":"Hogares",
    "Titulo_Heatmap_Hogares":"Hogares",
    # Hogares\Gasto
    "Pct_Hogares_Gasto_Alimento":"Hogares\\Gasto","Pct_Hogares_Gasto_Transporte":"Hogares\\Gasto",
    "Pct_Hogares_Gasto_Educacion":"Hogares\\Gasto","Pct_Hogares_Gasto_Salud":"Hogares\\Gasto",
    "Pct_Hogares_Gasto_Serv_Publi":"Hogares\\Gasto","Pct_Hogares_Gasto_Celular":"Hogares\\Gasto",
    "Pct_Hogares_Gasto_Arriendo":"Hogares\\Gasto","Pct_Hogares_Gasto_Otros":"Hogares\\Gasto",
    "Gasto_Promedio_Alimento":"Hogares\\Gasto","Gasto_Promedio_Transporte":"Hogares\\Gasto",
    "Gasto_Promedio_Educacion":"Hogares\\Gasto","Gasto_Promedio_Salud":"Hogares\\Gasto",
    "Gasto_Promedio_Serv_Publicos":"Hogares\\Gasto","Gasto_Promedio_Celular":"Hogares\\Gasto",
    "Gasto_Promedio_Arriendo":"Hogares\\Gasto","Gasto_Promedio_Otros":"Hogares\\Gasto",
    "Gasto_Promedio_Total":"Hogares\\Gasto",
    "Valor_Indicador_Hogar":"Hogares",
    # Demografia
    "Personas":"Demografia","Total Filas":"Demografia","Total Únicos":"Demografia",
    "Personas_Hombres":"Demografia","Personas_Mujeres":"Demografia",
    "Hombre_%":"Demografia","Mujeres_%":"Demografia",
    "personas_A":"Demografia","personas_B":"Demografia",
    "personas_C":"Demografia","personas_D":"Demografia",
    "percen_A":"Demografia","percen_B":"Demografia",
    "percen_C":"Demografia","percen_D":"Demografia",
    "Grupo_A":"Demografia","Grupo_B":"Demografia",
    "Grupo_C":"Demografia","Grupo_D":"Demografia",
    "Total_Personas_Filtro":"Demografia","Proporcion_Municipio":"Demografia",
    "Pct_Personas_Municipio":"Demografia","Pct_Grupo":"Demografia",
    "Etiqueta_Grupo_A":"Demografia","Etiqueta_Grupo_B":"Demografia",
    "Etiqueta_Grupo_C":"Demografia","Etiqueta_Grupo_D":"Demografia",
    "Personas_Hommbres_Piramide":"Demografia","Subregiones todas":"Demografia",
    "Tasa de Cobertura Sisb\u00c3\u00a9n":"Demografia","% Cobertura Sisben":"Demografia",
    "anio_Seleccionado":"Demografia",
    # Selectores (en sus propias tablas)
    "Eje_Sisben":"Selectores","Pct_Privacion_Dinamica":"Selectores",
    "Valor_Heatmap_Viv":"Selectores","Pct_Evento_Vivienda":"Selectores",
    "Prom_Eventos_Vivienda":"Selectores","Pct_Privacion_Seleccionada":"Selectores",
    "Valor_Hogar_Pct":"Selectores","Valor_Hogar_Gasto":"Selectores",
    "Variable_Sanitaria_Activa":"Selectores","Valor_Matriz_Vivienda":"Selectores",
    "Filtro_Tipo_Vivienda":"Selectores",
    # Calidad Datos
    "Personas_Verificacion":"Calidad Datos","Personas_Excluidas":"Calidad Datos",
    "Calidad_Integridad_Porcentaje":"Calidad Datos",
    "-- Indicador Clave de Desempe\u00f1o (KPI)%_Salud_Base_Datos":"Calidad Datos",
    "Matriz1_PorcentajeValido":"Calidad Datos","Matriz1_Validados":"Calidad Datos",
    "Matriz1_Ranking_Mpio":"Calidad Datos","Matriz2_VerificacionOficina":"Calidad Datos",
    "Matriz2_PorcentajeOficina":"Calidad Datos","Matriz2_Ranking_Mpio":"Calidad Datos",
    "Matriz3_SeleccionCoord":"Calidad Datos","Matriz3_PorcentajeCoord":"Calidad Datos",
    "Matriz3_Ranking_Mpio":"Calidad Datos",
    # UX
    "UX_Titulo_Tablero":"UX","Color_Tarjeta":"UX",
    "Etiqueta_Barra":"UX","Etiqueta_Barra_Por_Grupo":"UX",
}

# ── 2. PROCESA UN ARCHIVO TMDL ───────────────────────────────────────────────
def process_file(path):
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    # Reemplaza referencias a tabla vieja
    lines = [l.replace("'1 Anonimizados (2)'", "fct_Sisben") for l in lines]

    result = []
    current_measure = None
    display_folder_written = False
    MEASURE_RE = re.compile(r'^\tmeasure\s+(.+?)(?:\s*=.*)?$')

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip("\r\n")

        # Detectar inicio de medida
        m = MEASURE_RE.match(stripped)
        if m:
            raw = m.group(1).strip()
            current_measure = raw.strip("'")
            display_folder_written = False

        # Antes de lineageTag, insertar displayFolder si corresponde
        if re.match(r'\t\tlineageTag:', stripped) and current_measure in F:
            if not display_folder_written:
                folder = F[current_measure]
                result.append(f'\t\tdisplayFolder: "{folder}"\r\n')
                display_folder_written = True

        # Saltar displayFolder existente (para sobreescribir)
        if re.match(r'\t\tdisplayFolder:', stripped):
            i += 1
            continue

        result.append(line)
        i += 1

    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(result)

    return len([l for l in result if "displayFolder:" in l])

# ── 3. FIX MEDIDAS ROTAS ─────────────────────────────────────────────────────
def fix_broken_measures(path):
    with open(path, "r", encoding="utf-8") as fh:
        content = fh.read()

    # Fix Pct_Pisos_Inadecuados: reemplaza filtro por columna inexistente
    content = content.replace(
        "fct_Sisben[Cat_Piso_Calidad] = \"Inadecuado\"",
        "fct_Sisben[tip_mat_pisos] IN {4, 5, 6}"
    )
    # Fix Pct_Paredes_Inadecuadas
    content = content.replace(
        "fct_Sisben[Cat_Paredes_Calidad] = \"Inadecuado\"",
        "fct_Sisben[tip_mat_paredes] IN {3, 4, 5, 6, 7}"
    )

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print("  [OK] Medidas rotas corregidas")

# ── 4. RENOMBRA RELACIONES ───────────────────────────────────────────────────
def fix_relationships(path):
    with open(path, "r", encoding="utf-8") as fh:
        content = fh.read()

    replacements = {
        "relationship AutoDetected_140220da-8674-4d47-a730-1fa21669f3ed":
            "relationship fct_Sisben_dim_municipios",
        "relationship Relationship\r\n": "relationship Poblacion_dim_municipios\r\n",
        "relationship 'Relationship 1'": "relationship Poblacion_Dim_Anios",
        "relationship 'Relationship 2'": "relationship Poblacion_Dim_Rango_Edad",
        "relationship 4a723bcc-9e66-81e5-e318-cc1b7858dba8":
            "relationship fct_Sisben_Dim_Estado_DNP",
        "relationship 'Relationship 3'": "relationship fct_Sisben_Dim_Anios",
        # tabla en fromColumn
        "'1 Anonimizados (2)'.": "fct_Sisben.",
    }
    for old, new in replacements.items():
        content = content.replace(old, new)

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print("  [OK] Relaciones renombradas")

# ── 5. RENOMBRA ARCHIVO DE TABLA ─────────────────────────────────────────────
def rename_table_file():
    old = os.path.join(TABLES, "1 Anonimizados (2).tmdl")
    new = os.path.join(TABLES, "fct_Sisben.tmdl")
    if os.path.exists(old):
        os.rename(old, new)
        print(f"  [OK] Archivo renombrado -> fct_Sisben.tmdl")
        # Actualiza la declaración de tabla dentro del archivo
        with open(new, "r", encoding="utf-8") as fh:
            content = fh.read()
        content = content.replace("table '1 Anonimizados (2)'", "table fct_Sisben", 1)
        with open(new, "w", encoding="utf-8") as fh:
            fh.write(content)
    else:
        print(f"  [!] Ya renombrado o no encontrado: {old}")
    return new

# ── 6. ELIMINA TABLA BASURA ──────────────────────────────────────────────────
def delete_tabla():
    p = os.path.join(TABLES, "Tabla.tmdl")
    if os.path.exists(p):
        os.remove(p)
        print("  [OK] Tabla.tmdl eliminado")
    else:
        print("  [!] Tabla.tmdl no encontrado")

# ── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("TMDL REORGANIZE — SISBEN 1604")
    print("=" * 60)

    # Primero renombramos el archivo de tabla (antes de procesar)
    print("\n[P3] Renombrando tabla principal...")
    main_tmdl = rename_table_file()

    # Procesamos TODOS los archivos tmdl
    print("\n[P4] Aplicando displayFolders y referencias...")
    total_folders = 0
    for root, dirs, files in os.walk(TMDL):
        for fname in files:
            if fname.endswith(".tmdl"):
                fpath = os.path.join(root, fname)
                n = process_file(fpath)
                if n:
                    print(f"  {fname}: {n} displayFolder(s) insertados")
                else:
                    # igual se procesaron las referencias de tabla
                    print(f"  {fname}: referencias actualizadas")
                total_folders += n

    print(f"\n  Total displayFolders insertados: {total_folders}")

    # Fix medidas rotas
    print("\n[P1] Corrigiendo medidas rotas...")
    fix_broken_measures(main_tmdl)

    # Relaciones
    print("\n[P8] Renombrando relaciones...")
    fix_relationships(os.path.join(TMDL, "relationships.tmdl"))

    # Tabla basura
    print("\n[P2] Eliminando tabla basura...")
    delete_tabla()

    print("\n" + "=" * 60)
    print("LISTO. Importa el TMDL en Power BI con ImportFromTmdlFolder.")
    print("=" * 60)
