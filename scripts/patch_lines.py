from pathlib import Path

p = Path(__file__).resolve().parent.parent / "market_core" / "market_core.py"
text = p.read_text(encoding="utf-8")
if '"automotriz"' in text:
    print("already patched")
    raise SystemExit(0)
old = '"moda":            {"name": "Moda y Vestimenta",      "emoji": "👕", "description": "Ropa, calzado y accesorios"},\n}'
new = (
    '"moda":            {"name": "Moda y Vestimenta",      "emoji": "👕", "description": "Ropa, calzado y accesorios"},\n'
    '    "automotriz":      {"name": "Automotriz",           "emoji": "🚗", "description": "Repuestos, accesorios y servicios automotrices"},\n}'
)
if old not in text:
    raise SystemExit("pattern not found")
p.write_text(text.replace(old, new), encoding="utf-8")
print("patched automotriz line")