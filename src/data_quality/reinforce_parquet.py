import pyarrow.parquet as pq
import pyarrow as pa
import os
import gc

input_file = r"D:\VVANEGASA\My Documents\tmp_sisben_mpio.parquet"
output_file = r"D:\VVANEGASA\My Documents\tmp_sisben_final_auditado.parquet"

print(f"Reforzando Parquet: {input_file}")

pf = pq.ParquetFile(input_file)
schema = pf.schema.to_arrow_schema()

# Determinar cambios en el schema
# Queremos: Num_evento_vendaval -> num_evento_vendaval
# Añadir filename (como Source.Name)

new_fields = []
for field in schema:
    if field.name == "Num_evento_vendaval":
        new_fields.append(pa.field("num_evento_vendaval", field.type))
    else:
        new_fields.append(field)

# Añadir filename si no existe
if "filename" not in [f.name for f in new_fields]:
    # Encontrar el tipo de Source.Name
    source_name_type = next(f.type for f in schema if f.name == "Source.Name")
    new_fields.append(pa.field("filename", source_name_type))

new_schema = pa.schema(new_fields)

writer = pq.ParquetWriter(output_file, new_schema, compression='snappy')

total_rows = pf.metadata.num_rows
processed = 0

print("Procesando chunks...")
for batch in pf.iter_batches(batch_size=500000):
    # Convertir a dict para manipular columnas facilmente
    print(f"      - Leyendo batch {processed//500000 + 1}...")
    data = batch.to_pydict()
    
    # Renombrar columna
    if "Num_evento_vendaval" in data:
        data["num_evento_vendaval"] = data.pop("Num_evento_vendaval")
    
    # Agregar filename
    if "filename" not in data:
        data["filename"] = data["Source.Name"]
        
    # Crear nueva tabla con el nuevo schema (el orden de las columnas debe coincidir con el schema)
    # Sin embargo, el writer espera que el orden de las columnas coincida con el schema definido.
    # Reordenamos las keys segun el new_schema
    ordered_data = {name: data[name] for name in new_schema.names}
    
    out_table = pa.Table.from_pydict(ordered_data, schema=new_schema)
    writer.write_table(out_table)
    
    processed += len(out_table)
    if processed % 1000000 == 0 or processed == total_rows:
        print(f"Progreso: {processed:,} / {total_rows:,}")
        
    del data, ordered_data, out_table, batch
    gc.collect()

writer.close()
print(f"\nFinalizado! Archivo creado en: {output_file}")
