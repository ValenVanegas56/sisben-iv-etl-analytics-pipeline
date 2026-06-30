param(
    [string]$Server = "localhost:59931",
    [string]$Database = "1d6c8188-dfef-4014-99d9-f53835697669"
)

# Cargar asambleas de Analysis Services
$assemblies = @(
    "Microsoft.AnalysisServices.Tabular.dll",
    "Microsoft.AnalysisServices.Server.dll",
    "Microsoft.AnalysisServices.Core.dll"
)
foreach ($assembly in $assemblies) {
    [System.Reflection.Assembly]::LoadWithPartialName($assembly.Replace(".dll", "")) | Out-Null
}

$svr = New-Object Microsoft.AnalysisServices.Tabular.Server
$svr.Connect($Server)
$db = $svr.Databases.GetByName($Database)
$model = $db.Model
$factTable = $model.Tables["1 Anonimizados (2)"]

Write-Host "1. Creando Tablas Dimensionales de Estado y Marca (DNP)..."

# ---- DIM ESTADO ----
if (-not $model.Tables.Contains("Dim_Estado_DNP")) {
    $dimEstado = New-Object Microsoft.AnalysisServices.Tabular.Table
    $dimEstado.Name = "Dim_Estado_DNP"
    
    $partition = New-Object Microsoft.AnalysisServices.Tabular.Partition
    $partition.Name = "Dim_Estado_DNP"
    $partition.Source = New-Object Microsoft.AnalysisServices.Tabular.CalculatedPartitionSource
    $partition.Source.Expression = @"
DATATABLE(
    ""Cod_Estado"", INTEGER,
    ""Descripcion_Estado"", STRING,
    ""Categoria_Calidad"", STRING,
    {
        {0, ""Registro Válido"", ""Válido""},
        {10, ""Excluido - Fallecido"", ""Excluido""},
        {30, ""Verif. Jefe Hogar (Denuncia)"", ""Verificación""},
        {31, ""Verif. Miembros (Denuncia)"", ""Verificación""},
        {32, ""Verif. Inconsistencias Proc."", ""Verificación""},
        {40, ""Verif. Desact. Salud (Embarazo)"", ""Verificación""},
        {41, ""Verif. Desact. Educación (Nivel)"", ""Verificación""},
        {42, ""Verif. Desact. Educación (Pensiones)"", ""Verificación""},
        {43, ""Verif. Desact. Ocupación e Ingresos"", ""Verificación""},
        {44, ""Verif. Desact. Actividad Mes"", ""Verificación""},
        {50, ""Verif. Movimiento atípico entre fichas"", ""Verificación""},
        {51, ""Verif. Inclusión atípica hogar"", ""Verificación""},
        {52, ""Verif. N° personas atípico discapacidad"", ""Verificación""},
        {53, ""Verif. N° personas atípico no parientes"", ""Verificación""},
        {54, ""Verif. N° personas atípico otro parentesco"", ""Verificación""},
        {55, ""Verif. Inclusión atípica no parientes"", ""Verificación""},
        {60, ""Datos no válidos (Encuesta/Fechas)"", ""Excluido / Inválido""},
        {61, ""Verif. Parentescos inconsistentes"", ""Verificación""},
        {62, ""Verif. Educación (Grado)"", ""Verificación""},
        {63, ""Verif. Antecedentes Sociodemográficos"", ""Verificación""},
        {64, ""Verif. Salud y fecundidad (Hijos)"", ""Verificación""},
        {65, ""Verif. Ocupación e ingresos"", ""Verificación""},
        {66, ""Verif. Vivienda"", ""Verificación""},
        {67, ""Verif. Hogares"", ""Verificación""},
        {68, ""Verif. Hogares (Cuartos)"", ""Verificación""},
        {69, ""Verif. Distancia vivienda-encuesta"", ""Verificación""},
        {70, ""Excluido - Documento no válido"", ""Excluido""},
        {71, ""Excluido - Documento duplicado"", ""Excluido""},
        {90, ""Verif. Desmejoramiento Vivienda"", ""Verificación""},
        {91, ""Verif. Desmejoramiento Educación"", ""Verificación""},
        {92, ""Verif. Desmejoramiento Ocupación"", ""Verificación""}
    }
)
"@
    $dimEstado.Partitions.Add($partition)
    $model.Tables.Add($dimEstado)
}

# ---- DIM MARCA ----
if (-not $model.Tables.Contains("Dim_Marca_DNP")) {
    $dimMarca = New-Object Microsoft.AnalysisServices.Tabular.Table
    $dimMarca.Name = "Dim_Marca_DNP"
    
    $partitionMarca = New-Object Microsoft.AnalysisServices.Tabular.Partition
    $partitionMarca.Name = "Dim_Marca_DNP"
    $partitionMarca.Source = New-Object Microsoft.AnalysisServices.Tabular.CalculatedPartitionSource
    $partitionMarca.Source.Expression = @"
DATATABLE(
    ""Cod_Marca"", INTEGER,
    ""Descripcion_Marca"", STRING,
    {
        {0, ""Registro válido""},
        {1, ""Excluido de publicación""},
        {10, ""Verificación persona""},
        {20, ""Verificación oficina""}
    }
)
"@
    $dimMarca.Partitions.Add($partitionMarca)
    $model.Tables.Add($dimMarca)
}

$model.SaveChanges() | Out-Null
Write-Host "Tablas dimensionales creadas y calculadas."


Write-Host "2. Creando Relaciones Ficticias -> Dim (Para filtros)..."
# Estado Rel
if (-not $model.Relationships.Contains("Rel_Estado")) {
    $rel = New-Object Microsoft.AnalysisServices.Tabular.SingleColumnRelationship
    $rel.Name = "Rel_Estado"
    $rel.ToColumn = $model.Tables["Dim_Estado_DNP"].Columns["Cod_Estado"]
    $rel.FromColumn = $factTable.Columns["estado"]
    $rel.ToCardinality = [Microsoft.AnalysisServices.Tabular.RelationshipEndCardinality]::One
    $rel.FromCardinality = [Microsoft.AnalysisServices.Tabular.RelationshipEndCardinality]::Many
    $rel.IsActive = $true
    $model.Relationships.Add($rel)
}

# Marca Rel
if (-not $model.Relationships.Contains("Rel_Marca")) {
    $relM = New-Object Microsoft.AnalysisServices.Tabular.SingleColumnRelationship
    $relM.Name = "Rel_Marca"
    $relM.ToColumn = $model.Tables["Dim_Marca_DNP"].Columns["Cod_Marca"]
    $relM.FromColumn = $factTable.Columns["marca"]
    $relM.ToCardinality = [Microsoft.AnalysisServices.Tabular.RelationshipEndCardinality]::One
    $relM.FromCardinality = [Microsoft.AnalysisServices.Tabular.RelationshipEndCardinality]::Many
    $relM.IsActive = $true
    $model.Relationships.Add($relM)
}
$model.SaveChanges() | Out-Null


Write-Host "3. Creando Medidas de Calidad de Datos (Eficientes)..."
function Add-Measure {
    param($Name, $Expr, $Format)
    if ($factTable.Measures.Contains($Name)) { $factTable.Measures.Remove($Name) }
    $m = New-Object Microsoft.AnalysisServices.Tabular.Measure
    $m.Name = $Name
    $m.Expression = $Expr
    if ($Format) { $m.FormatString = $Format }
    $factTable.Measures.Add($m)
}

# Medidas de Reporte Calidad DNP
Add-Measure -Name "Registros_DQ_Validos" -Expr "CALCULATE([Personas], 'Dim_Estado_DNP'[Categoria_Calidad] = `"Válido`")" -Format "#,##0"
Add-Measure -Name "Registros_DQ_Verificacion" -Expr "CALCULATE([Personas], 'Dim_Estado_DNP'[Categoria_Calidad] = `"Verificación`")" -Format "#,##0"
Add-Measure -Name "Registros_DQ_Excluidos" -Expr "CALCULATE([Personas], 'Dim_Estado_DNP'[Categoria_Calidad] IN {`"Excluido`", `"Excluido / Inválido`"})" -Format "#,##0"

# Medida para Titulo Dinamico UX
Add-Measure -Name "UX_Titulo_Tablero" -Expr @"
VAR vAno = IF(ISFILTERED('1 Anonimizados (2)'[anio]), CONCATENATEX(VALUES('1 Anonimizados (2)'[anio]), '1 Anonimizados (2)'[anio], "", ""), BLANK())
VAR vMpio = IF(ISFILTERED('dim_municipios'[Municipio]), CONCATENATEX(VALUES('dim_municipios'[Municipio]), 'dim_municipios'[Municipio], "", ""), BLANK())
VAR vGrupo = IF(ISFILTERED('1 Anonimizados (2)'[grupo_sisben]), CONCATENATEX(VALUES('1 Anonimizados (2)'[grupo_sisben]), '1 Anonimizados (2)'[grupo_sisben], "", ""), BLANK())
VAR unidos = CONCATENATEX(FILTER( {vAno, vMpio, vGrupo}, [Value] <> BLANK() ), [Value], "" • "")
RETURN IF(ISBLANK(unidos), ""Visión General Sisbén - Antioquia"", ""Filtros Activos: "" & unidos)
"@ -Format ""

# Medida para la Pirámide Invertida de Hombres
# Explicación rendimiento: O(1) Negar un escalar ya evaluado toma literal 0ms en VertiPaq. El formato oculta el negativo.
Add-Measure -Name "Personas_Hombres_Piramide" -Expr "-[Personas_Hombres]" -Format "#,##0;#,##0;0"

$model.SaveChanges() | Out-Null
Write-Host "Despliegue completo con éxito. Actualiza el modelo DAX (Model -> Recalculate) si es necesario."
