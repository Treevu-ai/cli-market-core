#!/usr/bin/env python3
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "market_connectors" / "vtex.py"
t = p.read_text(encoding="utf-8")

if "_vtex_json_list" not in t:
    t = t.replace(
        '_VTEX_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"\n',
        '_VTEX_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"\n'
        "_VTEX_OK_STATUSES = frozenset({200, 206})\n\n\n"
        "def _vtex_json_list(resp: httpx.Response) -> list[dict] | None:\n"
        '    """Parse VTEX catalog search response; 206 Partial Content is valid."""\n'
        "    if resp.status_code not in _VTEX_OK_STATUSES:\n"
        "        return None\n"
        '    ct = resp.headers.get("content-type", "")\n'
        '    if "json" not in ct:\n'
        "        return None\n"
        "    data = resp.json()\n"
        "    return data if isinstance(data, list) else None\n",
        1,
    )

old_cache = """                        resp = await client.get(url, params=params, headers=headers)
                        if resp.status_code == 200:
                            ct = resp.headers.get("content-type", "")
                            if "json" in ct:
                                data = resp.json()
                                if isinstance(data, list) and len(data) > 0:
                                    logger.debug(f"Cache-assisted search succeeded for {store_key}")
                                    return data"""

new_cache = """                        resp = await client.get(url, params=params, headers=headers)
                        data = _vtex_json_list(resp)
                        if data:
                            logger.debug(f"Cache-assisted search succeeded for {store_key}")
                            return data"""

old_direct = """                    # Check for success
                    if resp.status_code == 200:
                        ct = resp.headers.get("content-type", "")
                        if "json" in ct:
                            data = resp.json()
                            if isinstance(data, list):
                                logger.debug(f"Direct search succeeded for {store_key}")
                                return data"""

new_direct = """                    data = _vtex_json_list(resp)
                    if data is not None:
                        logger.debug(f"Direct search succeeded for {store_key}")
                        return data"""

if old_cache in t:
    t = t.replace(old_cache, new_cache, 1)
if old_direct in t:
    t = t.replace(old_direct, new_direct, 1)

p.write_text(t, encoding="utf-8")
print("patched vtex.py for HTTP 206")