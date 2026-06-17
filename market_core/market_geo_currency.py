"""Business lines, country/store directory, and currency helpers.

Pure data + side-effect-free helpers extracted from market_core.py: no DB
or network coupling, only depends on the static STORES directory.
"""

from __future__ import annotations

from .market_stores import STORES

LINES = {
    "supermercados":   {"name": "Supermercados",          "emoji": "🛒", "description": "Alimentos, bebidas y consumo diario"},
    "farmacias":       {"name": "Farmacias y Salud",      "emoji": "💊", "description": "Medicamentos, bienestar y cuidado personal"},
    "electro":         {"name": "Electro y Tecnología",   "emoji": "📱", "description": "Electrónicos, electrodomésticos y gadgets"},
    "hogar":           {"name": "Hogar y Construcción",   "emoji": "🏠", "description": "Mejoramiento del hogar, muebles, ferretería"},
    "departamentales": {"name": "Tiendas Departamentales", "emoji": "🏬", "description": "Ropa, hogar, electrónicos y más"},
    "moda":            {"name": "Moda y Vestimenta",      "emoji": "👕", "description": "Ropa, calzado y accesorios"},
    "automotriz":      {"name": "Automotriz",             "emoji": "🚗", "description": "Repuestos, accesorios y servicios automotrices"},
    "industrial":      {"name": "Industrial y Mayorista",  "emoji": "🏭", "description": "Insumos, herramientas y materiales industriales"},
}


def canonical_line_name(line_id: str | None) -> str:
    """Display name for a business line — ignores legacy line_name in snapshots."""
    key = (line_id or "").strip()
    if not key:
        return "Sin categoría"
    meta = LINES.get(key)
    if meta:
        return str(meta.get("name") or key)
    return key.replace("_", " ").title()


COUNTRIES: dict[str, dict] = {}
for _sk, _sv in STORES.items():
    _cc = _sv["country"]
    if _cc not in COUNTRIES:
        COUNTRIES[_cc] = {"name": _cc, "stores": []}
    COUNTRIES[_cc]["stores"].append(_sk)
# Human-readable country names
_country_names: dict[str, str] = {
    "PE": "Perú", "AR": "Argentina", "BR": "Brasil", "MX": "México", "CO": "Colombia",
    "CL": "Chile", "ES": "España", "FR": "Francia", "IT": "Italia", "DE": "Alemania",
    "GB": "Reino Unido", "PT": "Portugal", "NL": "Países Bajos", "BE": "Bélgica",
    "PL": "Polonia", "SE": "Suecia", "DK": "Dinamarca", "FI": "Finlandia",
    "NO": "Noruega", "AT": "Austria", "CH": "Suiza", "IE": "Irlanda",
    "GR": "Grecia", "CZ": "República Checa", "RO": "Rumania", "HU": "Hungría",
    "SK": "Eslovaquia", "BG": "Bulgaria", "HR": "Croacia", "SI": "Eslovenia",
    "LU": "Luxemburgo", "EE": "Estonia", "LV": "Letonia", "LT": "Lituania",
    "UY": "Uruguay", "EC": "Ecuador", "BO": "Bolivia", "PY": "Paraguay",
    "VE": "Venezuela", "CR": "Costa Rica", "GT": "Guatemala", "SV": "El Salvador",
    "PA": "Panamá", "DO": "República Dominicana", "HN": "Honduras", "NI": "Nicaragua",
    "US": "Estados Unidos", "CA": "Canadá", "AU": "Australia", "NZ": "Nueva Zelanda",
    "JP": "Japón", "KR": "Corea del Sur", "CN": "China", "TW": "Taiwán",
    "HK": "Hong Kong", "SG": "Singapur", "IN": "India", "MY": "Malasia",
    "TH": "Tailandia", "ID": "Indonesia", "PH": "Filipinas", "VN": "Vietnam",
    "TR": "Turquía", "RU": "Rusia", "AE": "Emiratos Árabes Unidos",
    "ZA": "Sudáfrica", "NG": "Nigeria",
}
for _cc in COUNTRIES:
    COUNTRIES[_cc]["name"] = _country_names.get(_cc, _cc)

# ── Currency ──────────────────────────────────────────────────────────────────

CURRENCY_SYMBOLS: dict[str, str] = {
    "PEN": "S/", "ARS": "ARS", "BRL": "R$", "MXN": "MXN", "COP": "COP",
    "CLP": "CLP", "EUR": "€", "GBP": "£",
}

# PEN value of 1 unit of each currency (static; live rates: /checkout/rates).
FX_PEN_PER_UNIT: dict[str, float] = {
    "PEN": 1.0,
    "ARS": 0.0027,
    "BRL": 1.02,
    "MXN": 0.29,
    "COP": 0.0013,
    "CLP": 0.0053,
    "EUR": 4.05,
    "USD": 3.70,
}


def convert_currency(amount: float, frm: str, to: str) -> float:
    """Convert amount using static PEN-equivalent rates."""
    src = (frm or "PEN").upper()
    dst = (to or "PEN").upper()
    r_src = FX_PEN_PER_UNIT.get(src)
    r_dst = FX_PEN_PER_UNIT.get(dst)
    if r_src is None or r_dst is None:
        raise ValueError(f"Unsupported currency. Supported: {list(FX_PEN_PER_UNIT)}")
    return round(amount * r_src / r_dst, 6)


def price_to_usd(price: float, currency: str) -> float | None:
    if not price or price <= 0:
        return None
    cur = (currency or "").upper()
    if cur not in FX_PEN_PER_UNIT:
        return None
    return round(convert_currency(price, cur, "USD"), 4)


def fmt_price(price: float, currency: str = "PEN") -> str:
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    return f"{symbol} {price:,.2f}"

def store_color(store: str) -> str:
    colors: dict[str, str] = {
        "wong": "#3cffd0", "metro": "#5200ff", "plazavea": "#ffe600",
        "carrefour": "#3cffd0", "jumbo_ar": "#00FF88", "carrefour_br": "#3cffd0",
        "chedraui": "#FF6B35", "heb": "#FF6B35",
        "olimpica": "#60A5FA", "exito": "#60A5FA",
        "drogaraia": "#FF6B35", "drogasil": "#FF6B35",
        "magazineluiza": "#A78BFA", "motorola_br": "#A78BFA",
        "renner": "#FFD600", "centauro": "#4ADE80", "homecenter": "#F5F5F0",
        "carrefour_es": "#FFD600", "decathlon_fr": "#4ADE80",
    }
    return colors.get(store, "#e9e9e9")

def store_emoji(store: str) -> str:
    return STORES.get(store, {}).get("emoji", "📦")
