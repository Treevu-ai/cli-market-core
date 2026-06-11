"""
market_connectors/sunat_invoicing.py — SUNAT electronic invoice via PSE or SOL.

PSE (Nubefact / Facturalo / Efact / Digifact) is the recommended emission path.
SOL credentials (RUC + usuario + clave) authenticate against SUNAT for OSE/CPE APIs.
Consulta Integrada (client_id/secret) validates issued receipts.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

_DEFAULT_RUC = "20613045563"
_DEFAULT_COMPANY_NAME = "SINAPSIS INNOVADORA S.A.C."

SUNAT_SOL_TOKEN_URL = "https://api-seguridad.sunat.gob.pe/v1/clientessol"
SUNAT_CONSULTA_TOKEN_URL = "https://api-seguridad.sunat.gob.pe/v1/clientesextranet"
SUNAT_VALIDATE_URL = "https://api.sunat.gob.pe/v1/contribuyente/contribuyentes"
SUNAT_CPE_SCOPE = "https://api-cpe.sunat.gob.pe/"
NUBEFACT_API_BASE = "https://api.nubefact.com/api/v1"
# Nubefact demo/prod share the same host; demo vs prod is determined by route UUID + token.
NUBEFACT_DEMO_API_BASE = NUBEFACT_API_BASE


def _env_first(*keys: str, default: str = "") -> str:
    for key in keys:
        val = os.getenv(key, "").strip()
        if val:
            return val
    return default


def get_sunat_ruc() -> str:
    """Issuer RUC — Railway: SINAPSIS_RUC · canonical: SUNAT_RUC."""
    return _env_first("SUNAT_RUC", "SINAPSIS_RUC", default=_DEFAULT_RUC)


def get_sol_user() -> str:
    """SOL secondary user — Railway: CLAVE_SOL_TOKEN · canonical: SUNAT_SOL_USER."""
    return _env_first("SUNAT_SOL_USER", "CLAVE_SOL_TOKEN")


def get_sol_password() -> str:
    """SOL password — Railway: PASSWORD_SUNAT_SINAPSIS · canonical: SUNAT_SOL_PASS."""
    return _env_first("SUNAT_SOL_PASS", "PASSWORD_SUNAT_SINAPSIS")


def get_company() -> dict[str, str]:
    return {
        "razon_social": _env_first("SUNAT_RAZON_SOCIAL", default=_DEFAULT_COMPANY_NAME),
        "ruc": get_sunat_ruc(),
        "direccion": _env_first("SUNAT_DIRECCION", default="Lima, Perú"),
        "web": _env_first("SUNAT_WEB", default="https://cli-market.dev"),
    }


def sol_credentials_configured() -> bool:
    return bool(get_sunat_ruc() and get_sol_user() and get_sol_password())


def sunat_config_status() -> dict:
    """Non-secret config snapshot for ops / health checks."""
    return {
        "ruc": get_sunat_ruc(),
        "sol_user_configured": bool(get_sol_user()),
        "sol_pass_configured": bool(get_sol_password()),
        "sol_ready": sol_credentials_configured(),
        "pse_configured": pse_credentials_configured(),
        "pse_provider": get_pse_provider(),
        "pse_route_configured": bool(get_pse_route_id()),
        "pse_token_configured": bool(get_pse_token()),
        "consulta_configured": bool(get_consulta_client_id() and get_consulta_client_secret()),
    }


def get_pse_provider() -> str:
    return _env_first("SUNAT_PSE_PROVIDER", default="nubefact")


def get_pse_route_id() -> str:
    """Nubefact RUTA slug — Railway: PSE_SUNAT_ID · canonical: SUNAT_PSE_ROUTE_ID."""
    return _env_first("SUNAT_PSE_ROUTE_ID", "PSE_SUNAT_ID")


def get_pse_token() -> str:
    """Nubefact TOKEN — Railway: PSE_SUNAT_PASSWORD · canonical: SUNAT_PSE_API_KEY."""
    return _env_first("SUNAT_PSE_API_KEY", "SUNAT_NUBEFACT_TOKEN", "PSE_SUNAT_PASSWORD")


def get_pse_api_key() -> str:
    """Alias for generic Bearer PSE providers."""
    return get_pse_token()


def get_pse_api_url() -> str:
    """Full PSE endpoint. Builds Nubefact URL from route id when not set explicitly."""
    explicit = _env_first("SUNAT_PSE_API_URL")
    if explicit:
        return explicit
    route = get_pse_route_id()
    if not route:
        return ""
    if route.startswith("http://") or route.startswith("https://"):
        return route.rstrip("/")
    base = NUBEFACT_DEMO_API_BASE if get_sunat_mode() == "demo" else NUBEFACT_API_BASE
    return f"{base}/{route.strip('/')}"


def pse_credentials_configured() -> bool:
    return bool(get_pse_api_url() and get_pse_token())


def get_sunat_mode() -> str:
    """demo | production. Default production when Railway PSE/SOL env vars are set."""
    explicit = _env_first("SUNAT_MODE")
    if explicit:
        return explicit
    has_pse = bool(
        _env_first("PSE_SUNAT_ID", "SUNAT_PSE_ROUTE_ID", "SUNAT_PSE_API_URL")
        and _env_first("PSE_SUNAT_PASSWORD", "SUNAT_PSE_API_KEY", "SUNAT_NUBEFACT_TOKEN")
    )
    has_sol = bool(
        _env_first("SINAPSIS_RUC", "SUNAT_RUC")
        and _env_first("CLAVE_SOL_TOKEN", "SUNAT_SOL_USER")
        and _env_first("PASSWORD_SUNAT_SINAPSIS", "SUNAT_SOL_PASS")
    )
    if has_pse or has_sol:
        return "production"
    return "demo"


def get_consulta_client_id() -> str:
    return _env_first("SUNAT_CLIENT_ID")


def get_consulta_client_secret() -> str:
    return _env_first("SUNAT_CLIENT_SECRET")


def _sol_username() -> str:
    ruc = get_sunat_ruc()
    user = get_sol_user()
    if user.startswith(ruc):
        return user
    return f"{ruc}{user}"


async def _get_consulta_token() -> str:
    client_id = get_consulta_client_id()
    client_secret = get_consulta_client_secret()
    if not client_id or not client_secret:
        raise ValueError("SUNAT_CLIENT_ID and SUNAT_CLIENT_SECRET not configured")
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{SUNAT_CONSULTA_TOKEN_URL}/{client_id}/oauth2/token/",
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.sunat.gob.pe/v1/contribuyente/contribuyentes",
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        if resp.status_code == 200:
            return resp.json()["access_token"]
        raise RuntimeError(f"SUNAT consulta auth failed: {resp.text}")


async def _get_sol_token() -> str:
    if not sol_credentials_configured():
        raise ValueError("SUNAT SOL credentials not configured (RUC + user + password)")
    ruc = get_sunat_ruc()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{SUNAT_SOL_TOKEN_URL}/{ruc}/oauth2/token/",
            data={
                "grant_type": "password",
                "scope": SUNAT_CPE_SCOPE,
                "client_id": ruc,
                "client_secret": ruc,
                "username": _sol_username(),
                "password": get_sol_password(),
            },
        )
        if resp.status_code == 200:
            return resp.json()["access_token"]
        raise RuntimeError(f"SUNAT SOL auth failed: {resp.text}")


async def validate_receipt(
    num_ruc: str,
    cod_comp: str,
    serie: str,
    numero: int,
    fecha_emision: str,
    monto: float,
) -> dict:
    """
    Validate a receipt against SUNAT's database.

    cod_comp: 01=Factura, 03=Boleta de Venta
    fecha_emision: dd/mm/yyyy
    """
    if not num_ruc:
        num_ruc = get_sunat_ruc()
    if not get_consulta_client_id():
        return {
            "status": "sin_credenciales",
            "message": "SUNAT validation not configured. Set SUNAT_CLIENT_ID and SUNAT_CLIENT_SECRET.",
        }
    try:
        token = await _get_consulta_token()
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{SUNAT_VALIDATE_URL}/{num_ruc}/validarcomprobante",
                json={
                    "numRuc": num_ruc,
                    "codComp": cod_comp,
                    "numeroSerie": serie,
                    "numero": numero,
                    "fechaEmision": fecha_emision,
                    "monto": monto,
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                estado_map = {
                    "0": "NO EXISTE",
                    "1": "ACEPTADO",
                    "2": "ANULADO",
                    "3": "AUTORIZADO",
                    "4": "NO AUTORIZADO",
                }
                return {
                    "success": data.get("success", False),
                    "estado_comprobante": estado_map.get(
                        str(data.get("data", {}).get("estadoCp", "")), "DESCONOCIDO"
                    ),
                    "estado_contribuyente": data.get("data", {}).get("estadoRuc", ""),
                    "observaciones": data.get("data", {}).get("Observaciones", []),
                }
            return {"success": False, "error": resp.text}
    except ValueError as e:
        return {"status": "sin_credenciales", "message": str(e)}


def build_invoice_ubl(order: dict, items: list[dict]) -> dict:
    company = get_company()
    subtotal = round(sum(i["price"] * i["quantity"] for i in items), 2)
    igv = round(subtotal * 0.18, 2)
    return {
        "tipo_documento": "01",
        "serie": "F001",
        "numero": order.get("order_id", "").replace("ORD-", ""),
        "fecha_emision": datetime.now(timezone.utc).isoformat(),
        "moneda": "PEN",
        "emisor": company,
        "cliente": {
            "nombre": order.get("username", "Cliente"),
            "tipo_documento": "0",
            "numero_documento": "-",
        },
        "items": [
            {
                "codigo": i.get("product_id", ""),
                "descripcion": i.get("name", ""),
                "cantidad": i.get("quantity", 1),
                "precio_unitario": i.get("price", 0),
                "subtotal": round(i.get("price", 0) * i.get("quantity", 1), 2),
                "unidad": "NIU",
                "igv": round(i.get("price", 0) * i.get("quantity", 1) * 0.18, 2),
            }
            for i in items
        ],
        "subtotal": subtotal,
        "igv": igv,
        "total": round(subtotal + igv, 2),
    }


def _nubefact_auth_header() -> str:
    token = get_pse_token()
    if token.startswith('Token token="'):
        return token
    return f'Token token="{token}"'


def _parse_nubefact_response(data: dict) -> dict:
    if data.get("errors"):
        return {
            "ok": False,
            "codigo": data.get("codigo"),
            "errors": data.get("errors"),
        }
    return {
        "ok": True,
        "serie": data.get("serie"),
        "numero": data.get("numero"),
        "aceptada_por_sunat": data.get("aceptada_por_sunat"),
        "enlace_del_pdf": data.get("enlace_del_pdf"),
        "enlace_del_xml": data.get("enlace_del_xml"),
        "enlace_del_cdr": data.get("enlace_del_cdr"),
    }


def _order_numero(order: dict) -> int:
    raw = str(order.get("order_id", "")).replace("ORD-", "").replace("-", "")
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits:
        return int(digits[-8:]) or 1
    return 1


def build_nubefact_payload(order: dict, items: list[dict]) -> dict:
    """Nubefact JSON for generar_comprobante (boleta B2C default)."""
    total_gravada = 0.0
    total_igv = 0.0
    nubefact_items = []
    for i in items:
        qty = int(i.get("quantity", 1) or 1)
        precio_unitario = round(float(i.get("price", 0) or 0), 2)
        valor_unitario = round(precio_unitario / 1.18, 2)
        subtotal = round(valor_unitario * qty, 2)
        igv = round(subtotal * 0.18, 2)
        total_line = round(subtotal + igv, 2)
        total_gravada += subtotal
        total_igv += igv
        nubefact_items.append(
            {
                "unidad_de_medida": "NIU",
                "codigo": str(i.get("product_id", "") or "001"),
                "descripcion": str(i.get("name", "") or "Servicio CLI Market"),
                "cantidad": qty,
                "valor_unitario": valor_unitario,
                "precio_unitario": precio_unitario,
                "descuento": "",
                "subtotal": subtotal,
                "tipo_de_igv": 1,
                "igv": igv,
                "total": total_line,
                "anticipo_regularizacion": False,
                "anticipo_comprobante_serie": "",
                "anticipo_comprobante_numero": "",
            }
        )
    fecha = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    tipo = int(_env_first("SUNAT_COMPROBANTE_TIPO", default="2"))  # 2=boleta
    serie = _env_first("SUNAT_BOLETA_SERIE", "SUNAT_FACTURA_SERIE", default="BBB1")
    return {
        "operacion": "generar_comprobante",
        "tipo_de_comprobante": tipo,
        "serie": serie,
        "numero": _order_numero(order),
        "sunat_transaction": 1,
        "cliente_tipo_de_documento": 1,
        "cliente_numero_de_documento": str(order.get("cliente_documento", "00000000")),
        "cliente_denominacion": str(order.get("username", "Cliente CLI Market")),
        "cliente_direccion": "",
        "cliente_email": str(order.get("email", "")),
        "fecha_de_emision": fecha,
        "fecha_de_vencimiento": fecha,
        "moneda": 1,
        "porcentaje_de_igv": 18.0,
        "total_gravada": round(total_gravada, 2),
        "total_igv": round(total_igv, 2),
        "total": round(total_gravada + total_igv, 2),
        "enviar_automaticamente_a_la_sunat": True,
        "enviar_automaticamente_al_cliente": False,
        "items": nubefact_items,
    }


async def _post_nubefact(payload: dict) -> tuple[int, dict]:
    api_url = get_pse_api_url()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            api_url,
            json=payload,
            headers={
                "Authorization": _nubefact_auth_header(),
                "Content-Type": "application/json",
            },
        )
        try:
            body = resp.json()
        except Exception:
            body = {"errors": resp.text, "codigo": resp.status_code}
        return resp.status_code, body


async def verify_pse_connection() -> dict:
    """Ping Nubefact route+token without issuing a real comprobante."""
    if not pse_credentials_configured():
        return {
            "ok": False,
            "provider": get_pse_provider(),
            "reason": "missing_config",
            "config": sunat_config_status(),
        }
    payload = {
        "operacion": "consultar_comprobante",
        "tipo_de_comprobante": 2,
        "serie": "ZZZZ",
        "numero": 1,
    }
    status_code, data = await _post_nubefact(payload)
    parsed = _parse_nubefact_response(data)
    codigo = str(data.get("codigo", ""))
    # 10=token, 11=ruta, 24=documento no existe (auth OK)
    if parsed.get("ok"):
        return {"ok": True, "provider": "nubefact", "http_status": status_code, "response": parsed}
    if codigo in ("24", "21"):
        return {
            "ok": True,
            "provider": "nubefact",
            "http_status": status_code,
            "note": "Ruta y token válidos (consulta sin comprobante).",
            "codigo": codigo,
            "errors": data.get("errors"),
        }
    return {
        "ok": False,
        "provider": "nubefact",
        "http_status": status_code,
        "codigo": codigo,
        "errors": data.get("errors"),
        "hint": _nubefact_error_hint(codigo),
    }


def _nubefact_error_hint(codigo: str) -> str:
    hints = {
        "10": "Token incorrecto — revisa PSE_SUNAT_PASSWORD / SUNAT_NUBEFACT_TOKEN.",
        "11": "Ruta incorrecta — revisa PSE_SUNAT_ID o SUNAT_PSE_API_URL.",
        "50": "Cuenta Nubefact suspendida.",
        "51": "Cuenta Nubefact suspendida por falta de pago.",
    }
    return hints.get(codigo, "Ver manual Nubefact JSON.")


async def _emit_via_nubefact(order: dict, items: list[dict]) -> dict:
    company = get_company()
    payload = build_nubefact_payload(order, items)
    status_code, data = await _post_nubefact(payload)
    parsed = _parse_nubefact_response(data)
    if parsed.get("ok"):
        return {
            "status": "emitida",
            "channel": "nubefact",
            "serie_numero": f"{parsed.get('serie')}-{parsed.get('numero')}",
            "aceptada_por_sunat": parsed.get("aceptada_por_sunat"),
            "pdf_url": parsed.get("enlace_del_pdf", ""),
            "xml_url": parsed.get("enlace_del_xml", ""),
            "cdr_url": parsed.get("enlace_del_cdr", ""),
            "ruc": company["ruc"],
        }
    return {
        "status": "pse_error",
        "channel": "nubefact",
        "http_status": status_code,
        "codigo": data.get("codigo"),
        "errors": data.get("errors"),
        "hint": _nubefact_error_hint(str(data.get("codigo", ""))),
        "payload_serie": payload.get("serie"),
        "ruc": company["ruc"],
    }


async def _emit_via_pse_generic(order: dict, items: list[dict]) -> dict:
    invoice = build_invoice_ubl(order, items)
    company = get_company()
    api_url = get_pse_api_url().rstrip("/")
    if not api_url.endswith("/v1/invoices"):
        api_url = f"{api_url}/v1/invoices"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            api_url,
            json=invoice,
            headers={"Authorization": f"Bearer {get_pse_token()}"},
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            return {
                "status": "emitida",
                "channel": get_pse_provider(),
                "invoice_id": data.get("id", ""),
                "serie_numero": f"{invoice['serie']}-{invoice['numero']}",
                "cdr_status": data.get("cdr_status", "accepted"),
                "pdf_url": data.get("pdf_url", ""),
                "ruc": company["ruc"],
            }
        return {
            "status": "pse_error",
            "channel": get_pse_provider(),
            "invoice": invoice,
            "message": f"PSE {get_pse_provider()} responded {resp.status_code}.",
            "ruc": company["ruc"],
        }


async def _emit_via_pse(order: dict, items: list[dict]) -> dict | None:
    if not pse_credentials_configured():
        return None
    provider = get_pse_provider().lower()
    if provider in ("nubefact", "pse.pe", "pse"):
        return await _emit_via_nubefact(order, items)
    return await _emit_via_pse_generic(order, items)


async def _emit_via_sol(order: dict, items: list[dict]) -> dict | None:
    if not sol_credentials_configured():
        return None
    invoice = build_invoice_ubl(order, items)
    company = get_company()
    try:
        await _get_sol_token()
    except RuntimeError as exc:
        return {
            "status": "sol_error",
            "channel": "sol",
            "message": str(exc),
            "invoice": invoice,
            "ruc": company["ruc"],
            "razon_social": company["razon_social"],
        }
    return {
        "status": "sol_authenticated",
        "channel": "sol",
        "message": (
            "Credenciales SOL válidas. UBL generado; falta firma digital y envío CPE a OSE/SUNAT."
        ),
        "invoice": invoice,
        "ruc": company["ruc"],
        "razon_social": company["razon_social"],
    }


async def emit_invoice(order: dict, items: list[dict]) -> dict:
    company = get_company()
    invoice = build_invoice_ubl(order, items)

    pse_result = await _emit_via_pse(order, items)
    if pse_result is not None:
        return pse_result

    sol_result = await _emit_via_sol(order, items)
    if sol_result is not None:
        return sol_result

    hints = []
    if not pse_credentials_configured():
        hints.append("PSE_SUNAT_ID + PSE_SUNAT_PASSWORD (o SUNAT_PSE_API_URL + token)")
    if not sol_credentials_configured():
        hints.append(
            "SUNAT_RUC/SINAPSIS_RUC + SUNAT_SOL_USER/CLAVE_SOL_TOKEN + "
            "SUNAT_SOL_PASS/PASSWORD_SUNAT_SINAPSIS"
        )

    return {
        "status": "demo",
        "message": f"SUNAT no configurado ({get_pse_provider()}). Set: {', '.join(hints)}.",
        "invoice": invoice,
        "ruc": company["ruc"],
        "razon_social": company["razon_social"],
        "config": sunat_config_status(),
    }


# Backward compatibility for imports expecting module-level COMPANY dict.
COMPANY = get_company()
