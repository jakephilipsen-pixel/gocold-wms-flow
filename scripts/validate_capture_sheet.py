#!/usr/bin/env python3
"""Pre-flight: confirm an edited carton-dim capture sheet PARSES before any bulk uses it.

Read-only. NO CartonCloud, NO network, NO writes — it loads the sheet through the SAME loader the
dims-write path uses (``analysis.dim_loader``) and reports the parse: the resolved column mapping,
SKU counts (total / fully measured / partial), header-drift errors surfaced plainly, and any value
that looks like a unit mix-up (a cm/metres number in the mm sheet). Exit 0 = clean, 1 = review
needed (doesn't load, or suspicious values), 2 = no such file.

    .venv/bin/python scripts/validate_capture_sheet.py --dims-path dims.ods
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# allow running without installing: src/ on path (same convention as the other scripts)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from analysis.capture_validate import validate_capture_sheet, format_validation  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a carton-dim capture sheet (read-only, no CartonCloud).",
    )
    parser.add_argument(
        "--dims-path", required=True, type=Path,
        help="path to the capture sheet to validate (.xlsx / .ods)",
    )
    args = parser.parse_args(argv)

    if not args.dims_path.exists():
        print(f"❌ no such file: {args.dims_path}", file=sys.stderr)
        return 2

    result = validate_capture_sheet(args.dims_path)
    print(format_validation(result))
    # non-zero so a wrapper script / CI can gate the bulk on a clean sheet
    return 0 if (result.loads and not result.flags) else 1


if __name__ == "__main__":
    raise SystemExit(main())
