import json
from collections import defaultdict

with open(r"C:\Projects\Assistant\_pbix_extract\Report\Layout", encoding="utf-16-le") as f:
    raw = f.read()

outer = json.loads(raw)

table_cols = defaultdict(set)

def walk(obj):
    """Recursively parse all embedded JSON strings and extract Entity/Property pairs."""
    if isinstance(obj, str):
        s = obj.strip()
        if s.startswith(('{', '[')):
            try:
                walk(json.loads(s))
            except Exception:
                pass
    elif isinstance(obj, list):
        for v in obj:
            walk(v)
    elif isinstance(obj, dict):
        # Check for a prototypeQuery with From + Select
        if "From" in obj and "Select" in obj:
            alias_map = {f["Name"]: f["Entity"] for f in obj["From"] if "Entity" in f}
            for sel in obj["Select"]:
                for kind in ("Column", "Measure"):
                    if kind in sel:
                        entry = sel[kind]
                        prop = entry.get("Property", "")
                        source = (entry.get("Expression", {})
                                       .get("SourceRef", {})
                                       .get("Source", ""))
                        entity = alias_map.get(source, source)
                        if entity and prop:
                            table_cols[entity].add(prop)
        for v in obj.values():
            walk(v)

walk(outer)

print("=== Tables and Columns in Power BI report ===\n")
for table in sorted(table_cols):
    print(f"[{table}]")
    for col in sorted(table_cols[table]):
        print(f"  {col}")
    print()
