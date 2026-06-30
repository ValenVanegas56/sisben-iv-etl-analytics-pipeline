$port = 50312
$conn = "Data Source=localhost:$port"
[Reflection.Assembly]::LoadWithPartialName("Microsoft.AnalysisServices.Tabular") | Out-Null
$server = New-Object Microsoft.AnalysisServices.Tabular.Server
$server.Connect($conn)
$m = $server.Databases[0].Model

Write-Host "--- Iniciando Auditoria y Ejecucion ---"

# 1. CREACION DE LA TABLA Y PARTICION DE POBLACION DANE
if ($m.Tables.Contains("Poblacion_DANE")) { $m.Tables.Remove("Poblacion_DANE") }

$t = New-Object Microsoft.AnalysisServices.Tabular.Table
$t.Name = "Poblacion_DANE"

$cols = @(
    @("cod_mpio", [Microsoft.AnalysisServices.Tabular.DataType]::String),
    @("anio", [Microsoft.AnalysisServices.Tabular.DataType]::Int64),
    @("Cod_clase", [Microsoft.AnalysisServices.Tabular.DataType]::Int64),
    @("sexo_persona", [Microsoft.AnalysisServices.Tabular.DataType]::Int64),
    @("Rango_Edad", [Microsoft.AnalysisServices.Tabular.DataType]::String),
    @("Poblacion_Proyectada", [Microsoft.AnalysisServices.Tabular.DataType]::Int64)
)

foreach ($col in $cols) {
    $c = New-Object Microsoft.AnalysisServices.Tabular.DataColumn
    $c.Name = $col[0]
    $c.DataType = $col[1]
    $c.SourceColumn = $col[0]
    $t.Columns.Add($c)
}

$p = New-Object Microsoft.AnalysisServices.Tabular.Partition
$p.Name = "Partition_Pob_DANE"
$src = New-Object Microsoft.AnalysisServices.Tabular.MPartitionSource
$src.Expression = 'let Source = Parquet.Document(File.Contents("D:\VVANEGASA\My Documents\poblacion_proyectada.parquet")),#"Changed Type" = Table.TransformColumnTypes(Source,{{"cod_mpio", type text}, {"anio", Int64.Type}, {"Cod_clase", Int64.Type}, {"sexo_persona", Int64.Type}, {"Rango_Edad", type text}, {"Poblacion_Proyectada", Int64.Type}}) in #"Changed Type"'
$p.Source = $src
$t.Partitions.Add($p)
$m.Tables.Add($t)

# 1.1 Crear las relaciones
function Add-Rel($fromTable, $fromCol, $toTable, $toCol) {
    $r = New-Object Microsoft.AnalysisServices.Tabular.SingleColumnRelationship
    $r.FromColumn = $m.Tables[$fromTable].Columns[$fromCol]
    $r.ToColumn = $m.Tables[$toTable].Columns[$toCol]
    $r.FromCardinality = [Microsoft.AnalysisServices.Tabular.RelationshipEndCardinality]::Many
    $r.ToCardinality = [Microsoft.AnalysisServices.Tabular.RelationshipEndCardinality]::One
    $r.CrossFilteringBehavior = [Microsoft.AnalysisServices.Tabular.CrossFilteringBehavior]::OneDirection
    $r.IsActive = $true
    $m.Relationships.Add($r)
}

# Borrar viejas relaciones si hubieran
$rels = @()
foreach ($rx in $m.Relationships) { 
    if ($rx.FromTable.Name -eq "Poblacion_DANE") { $rels += $rx }
}
foreach ($rx in $rels) { $m.Relationships.Remove($rx) }

# Add relationships (if target dimensions exist)
if ($m.Tables.Contains("dim_municipios")) { Add-Rel "Poblacion_DANE" "cod_mpio" "dim_municipios" "cod_mpio" }
if ($m.Tables.Contains("Dim_Anios")) { Add-Rel "Poblacion_DANE" "anio" "Dim_Anios" "anio" }
if ($m.Tables.Contains("Dim_Rango_Edad")) { Add-Rel "Poblacion_DANE" "Rango_Edad" "Dim_Rango_Edad" "Rango_Edad" }

# 2. CREACION DE LA MEDIDA % COBERTURA SISBEN (El Fix del "70% vs 10%")
$factTable = $m.Tables.Find("1 Anonimizados (2)")
if ($factTable.Measures.Contains("Tasa de Cobertura Sisbén")) { $factTable.Measures.Remove("Tasa de Cobertura Sisbén") }

$m_cov = New-Object Microsoft.AnalysisServices.Tabular.Measure
$m_cov.Name = "Tasa de Cobertura Sisbén"
$m_cov.Expression = @"
VAR max_year = MAX(Dim_Anios[anio])
RETURN
DIVIDE(
    CALCULATE(COUNTROWS('1 Anonimizados (2)'), Dim_Anios[anio] = max_year),
    CALCULATE(SUM('Poblacion_DANE'[Poblacion_Proyectada]), Dim_Anios[anio] = max_year),
    BLANK()
)
"@
$m_cov.FormatString = "0.00%"
$factTable.Measures.Add($m_cov)


# 3. REFACTORIZAR MEDIDA FILTER() ineficiente en Dim_Tipo_Evento
$te = $m.Tables.Find("Dim_Tipo_Evento")
if ($te -and $te.Measures.Contains("Prom_Eventos_Vivienda")) {
    $te.Measures["Prom_Eventos_Vivienda"].Expression = @"
VAR _evento = SELECTEDVALUE(Dim_Tipo_Evento[TipoEvento])
RETURN
SWITCH(
    _evento,
    "Inundación",   CALCULATE(AVERAGE('1 Anonimizados (2)'[num_evento_inundacion]), '1 Anonimizados (2)'[ind_evento_inundacion] = 1),
    "Avalancha",    CALCULATE(AVERAGE('1 Anonimizados (2)'[num_evento_avalancha]),  '1 Anonimizados (2)'[ind_evento_avalancha] = 1),
    "Terremoto",    CALCULATE(AVERAGE('1 Anonimizados (2)'[num_evento_terremoto]),  '1 Anonimizados (2)'[ind_evento_terremoto] = 1),
    "Incendio",     CALCULATE(AVERAGE('1 Anonimizados (2)'[num_evento_incendio]),   '1 Anonimizados (2)'[ind_evento_incendio] = 1),
    "Vendaval",     CALCULATE(AVERAGE('1 Anonimizados (2)'[Num_evento_vendaval]),   '1 Anonimizados (2)'[ind_evento_vendaval] = 1),
    "Hundimiento",  CALCULATE(AVERAGE('1 Anonimizados (2)'[num_evento_hundimiento]),'1 Anonimizados (2)'[ind_evento_hundimiento] = 1)
)
"@
}


# 4. REFACTORIZAR MEDIDAS DE GRAND TOTAL (ISINSCOPE Fix para promedios departamentales)

$cat_viv = $m.Tables.Find("Dim_Categoria_Vivienda")
if ($cat_viv -and $cat_viv.Measures.Contains("Valor_Matriz_Vivienda")) {
    $current_expr = $cat_viv.Measures["Valor_Matriz_Vivienda"].Expression
    # El Valor_Matriz_Vivienda ya tenia AVERAGEX(VALUES(...)), calcularemos si esta bien
    $cat_viv.Measures["Valor_Matriz_Vivienda"].Expression = $current_expr -replace "IF\(\s*ISINSCOPE\(Dim_Categoria_Vivienda\[Categoria\]\)", "IF(HASONEVALUE(Dim_Categoria_Vivienda[Categoria])"
}

$ind_hog = $m.Tables.Find("Dim_Indicador_Hogar")
if ($ind_hog -and $ind_hog.Measures.Contains("Valor_Hogar_Pct")) {
    $ind_hog.Measures["Valor_Hogar_Pct"].Expression = @"
IF(
    HASONEVALUE(Dim_Indicador_Hogar[Tipo]),
    IF(SELECTEDVALUE(Dim_Indicador_Hogar[Tipo]) = "Condiciones", [Valor_Indicador_Hogar], BLANK()),
    AVERAGEX(
        FILTER(VALUES(Dim_Indicador_Hogar[Tipo]), Dim_Indicador_Hogar[Tipo] = "Condiciones"),
        [Valor_Indicador_Hogar]
    )
)
"@
}

$ipm_dim = $m.Tables.Find("Dim_IPM_Dimension")
if ($ipm_dim -and $ipm_dim.Measures.Contains("Pct_Privacion_Seleccionada")) {
    $ipm_dim.Measures["Pct_Privacion_Seleccionada"].Expression = @"
VAR Val = SWITCH(
    SELECTEDVALUE(Dim_IPM_Dimension[Dimension_IPM]),
    "Bajo logro educativo", [Pct_I1_BajoLogroEducativo],
    "Analfabetismo", [Pct_I2_Analfabetismo],
    "Inasistencia escolar", [Pct_I3_InasistenciaEscolar],
    "Rezago escolar", [Pct_I4_RezagoEscolar],
    "Barreras primera infancia", [Pct_I5_BarrerasCuidadoInfancia],
    "Trabajo infantil", [Pct_I6_TrabajoInfantil],
    "Desempleo larga duración", [Pct_I7_DesempleoLargaDuracion],
    "Trabajo informal", [Pct_I8_TrabajoInformal],
    "Sin aseguramiento en salud", [Pct_I9_SinAseguramientoSalud],
    "Barreras acceso salud", [Pct_I10_BarreraAccesoServiciosSalud],
    "Sin acceso a agua", [Pct_I11_SinAccesoFuentesAguaMejorada],
    "Eliminación inadecuada de excretas", [Pct_I12_InadecuadaEliminacionExcretas],
    "Material inadecuado de pisos", [Pct_I13_MaterialInadecuadoPisos],
    "Material inadecuado de paredes", [Pct_I14_MaterialInadecuadoParedes],
    "Hacinamiento crítico", [Pct_I15_HacinamientoCritico],
    BLANK()
)
RETURN
IF(
    HASONEVALUE(Dim_IPM_Dimension[Dimension_IPM]),
    Val,
    AVERAGEX(
        VALUES(Dim_IPM_Dimension[Dimension_IPM]),
        SWITCH(
            Dim_IPM_Dimension[Dimension_IPM],
            "Bajo logro educativo", [Pct_I1_BajoLogroEducativo],
            "Analfabetismo", [Pct_I2_Analfabetismo],
            "Inasistencia escolar", [Pct_I3_InasistenciaEscolar],
            "Rezago escolar", [Pct_I4_RezagoEscolar],
            "Barreras primera infancia", [Pct_I5_BarrerasCuidadoInfancia],
            "Trabajo infantil", [Pct_I6_TrabajoInfantil],
            "Desempleo larga duración", [Pct_I7_DesempleoLargaDuracion],
            "Trabajo informal", [Pct_I8_TrabajoInformal],
            "Sin aseguramiento en salud", [Pct_I9_SinAseguramientoSalud],
            "Barreras acceso salud", [Pct_I10_BarreraAccesoServiciosSalud],
            "Sin acceso a agua", [Pct_I11_SinAccesoFuentesAguaMejorada],
            "Eliminación inadecuada de excretas", [Pct_I12_InadecuadaEliminacionExcretas],
            "Material inadecuado de pisos", [Pct_I13_MaterialInadecuadoPisos],
            "Material inadecuado de paredes", [Pct_I14_MaterialInadecuadoParedes],
            "Hacinamiento crítico", [Pct_I15_HacinamientoCritico],
            BLANK()
        )
    )
)
"@
}


$m.SaveChanges()
$server.Disconnect()

Write-Host "¡Auditoria y reestructuracion finalizada exitosamente!"
