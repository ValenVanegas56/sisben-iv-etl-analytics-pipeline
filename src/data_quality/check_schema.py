import pyarrow.parquet as pq

PARQUET_FILE = r"D:\VVANEGASA\My Documents\sisben_master.parquet"

try:
    schema = pq.read_schema(PARQUET_FILE)
    print("Columnas en el parquet:")
    print(schema.names[-20:])  # Las últimas 20 columnas

    # read 1M rows
    pf = pq.ParquetFile(PARQUET_FILE)
    df = next(pf.iter_batches(batch_size=2000000, columns=['anio', 'estado', 'marca'])).to_pandas()
    print("\nCrosstab Año x Estado:")
    print(df.groupby(['anio', 'estado'], dropna=False).size())
    print("\nCrosstab Año x Marca:")
    print(df.groupby(['anio', 'marca'], dropna=False).size())
except Exception as e:
    print(e)
