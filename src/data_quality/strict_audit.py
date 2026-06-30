import json
import pyarrow.parquet as pq

# 1. Columnas de Power BI
with open(r'C:\Users\VVANEGASA\.gemini\antigravity\brain\65eed9fc-222d-477c-bfc6-611009f675bd\.system_generated\steps\87\output.txt', 'r', encoding='utf-8') as f:
    pbi_data = json.load(f)
pbi_cols = [col["name"] for col in pbi_data["data"][0]["columns"]]

# 2. Columnas del Parquet
pf = pq.ParquetFile(r'D:\VVANEGASA\My Documents\tmp_sisben_final_auditado.parquet')
pq_cols = [f.name for f in pf.schema]

print(f"PBI count: {len(pbi_cols)}")
print(f"PQ count: {len(pq_cols)}")

# Comparación exacta
missing_in_pq = [c for c in pbi_cols if c not in pq_cols]
extra_in_pq = [c for c in pq_cols if c not in pbi_cols]

print("\n--- FALTAN EN PARQUET (Exacto) ---")
for c in missing_in_pq:
    # Ver si es solo un tema de mayusculas
    match_case_insensitive = [p for p in pq_cols if p.lower() == c.lower()]
    if match_case_insensitive:
        print(f"CASE MISMATCH: '{c}' (PBI) vs '{match_case_insensitive[0]}' (PQ)")
    else:
        print(f"MISSING: '{c}'")

print("\n--- SOBRAN EN PARQUET (Exacto) ---")
for c in extra_in_pq:
    match_case_insensitive = [p for p in pbi_cols if p.lower() == c.lower()]
    if not match_case_insensitive:
        print(f"EXTRA: '{c}'")
