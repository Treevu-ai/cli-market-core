#!/usr/bin/env python3
"""Export canonical MCP tool registry as CSV for docs and landing sync."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_core.mcp_registry_export import REGISTRY_CSV_HEADERS, registry_export_rows, write_registry_csv
from market_core.market_mcp_registry import public_tool_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Export MCP registry CSV from market_mcp_registry.py")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=ROOT / "ops" / "mcp-tools-registry.csv",
        help="Output CSV path (default: ops/mcp-tools-registry.csv)",
    )
    parser.add_argument(
        "--profile",
        default="default",
        help="Profile used for default_visible column (default: default)",
    )
    parser.add_argument("--stdout", action="store_true", help="Print CSV to stdout instead of writing a file")
    args = parser.parse_args()

    rows = registry_export_rows(args.profile)
    if args.stdout:
        from market_core.mcp_registry_export import registry_csv_text

        sys.stdout.write(registry_csv_text(args.profile))
        return

    out = write_registry_csv(args.output, profile=args.profile)
    legacy = public_tool_count("legacy")
    default = public_tool_count("default")
    print(
        f"Wrote {out} ({len(rows)} tools · default={default} · legacy={legacy} · "
        f"columns={','.join(REGISTRY_CSV_HEADERS)})"
    )


if __name__ == "__main__":
    main()
