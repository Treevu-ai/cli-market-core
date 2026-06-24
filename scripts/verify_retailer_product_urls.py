#!/usr/bin/env python3
"""Smoke-verify product URLs for all active retailers."""

from __future__ import annotations

import argparse
import json
import os
import sys

# Keep offline import deterministic unless explicitly probing live API health.
os.environ.setdefault("MARKET_SKIP_LIVE", "1")

from market_core.market_action_links import verify_active_retailer_urls


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", action="append", help="Limit to store key(s)")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    report = verify_active_retailer_urls(args.store)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"Checked {report['stores_checked']} retailers — "
            f"ok={report['stores_ok']} failed={report['stores_failed']} "
            f"({report['coverage_pct']}%)"
        )
        for row in report["stores"]:
            status = "OK" if row["ok"] else "FAIL"
            print(
                f"[{status}] {row['store']:16} {row.get('status_code') or '-':>4} "
                f"{row.get('link_mode') or '-':10} {row.get('url') or '-'}"
            )
    return 0 if report["stores_failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
