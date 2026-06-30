import os
import re

dax_folder = r"d:\VVANEGASA\Desktop\antigravity_sisben\tmdl_export"

measures = {}
def parse_tmdl(filepath):
    table_name = os.path.basename(filepath).replace(".tmdl","")
    with open(filepath, 'r', encoding='utf8') as f:
        content = f.read()
    
    # Simple regex to find measures
    # format in tmdl is usually:
    # measure 'Measure Name' = 
    #     <expression>
    #     formatString: ...
    measure_blocks = re.split(r'\n\s*measure\s+', content)
    
    for block in measure_blocks[1:]:
        lines = block.split('\n')
        if not lines: continue
        first_line = lines[0]
        # extract name, maybe wrapped in quotes or straight text until '=' or '\n'
        match = re.match(r"('([^']+)'|([^\s=]+))\s*=\s*", first_line)
        name = ""
        expression_lines = []
        if match:
            name = match.group(2) if match.group(2) else match.group(3)
            # The rest of first_line
            rest = first_line[match.end():]
            if rest.strip(): expression_lines.append(rest)
            
            for line in lines[1:]:
                if re.match(r'^\s*(formatString|isHidden|displayFolder|lineageTag|dataCategory|dataType)\s*:', line):
                    continue # properties, stop or skip
                if re.match(r'^\s*column\s+', line) or re.match(r'^\s*measure\s+', line) or re.match(r'^\s*hierarchy\s+', line) or re.match(r'^\s*partition\s+', line):
                    break
                expression_lines.append(line)
                
            expr = "\n".join(expression_lines).strip()
            measures[name] = {"table": table_name, "expr": expr}

for file in os.listdir(dax_folder):
    if file.endswith(".tmdl"):
        parse_tmdl(os.path.join(dax_folder, file))

# Audit Heuristics
inefficient_filters = []
complex_iterators = []

for m_name, info in measures.items():
    expr = info['expr'].upper()
    # Find FILTER(Table, Table[Col] = ...) which is bad instead of Kalkulate filters
    if "FILTER" in expr and "CALCULATE" in expr:
        inefficient_filters.append(m_name)
    if "SUMX" in expr or "AVERAGEX" in expr:
        complex_iterators.append(m_name)

print(f"Total Measures Analyzed: {len(measures)}")

print("\n--- MEASURES WITH POTENTIAL FILTER BOTTLENECKS (CALCULATE + FILTER on full tables) ---")
for m in inefficient_filters:
    print(f"- {m}")

print("\n--- MEASURES WITH DAX ITERATORS (SUMX/AVERAGEX potentials for Totals fix) ---")
for m in complex_iterators:
    print(f"- {m}")
    
# Let's save a clean dict of measures to a txt for deeper inspection if needed
with open("dax_dict_dump.txt", "w", encoding="utf8") as f:
    for k, v in measures.items():
        f.write(f"Measure: {k}\nExpression:\n{v['expr']}\n{'-'*40}\n")
