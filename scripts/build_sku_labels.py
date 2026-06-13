#!/usr/bin/env python3
"""Generate ZPL SKU barcode labels for the Zebra ZT411 (73 x 100 mm roll).

The Forage product master has no barcode numbers populated in CartonCloud
(units/cartons/pallets barcode fields are all empty). CartonCloud scans the
*product code* directly, so each label encodes the SKU `product_code` as a
Code128 barcode. One label per active SKU.

Label layout (portrait, 73 mm wide x 100 mm tall):

    +-----------------------+
    |       AE-BLA          |  <- SKU code, large
    |   AE - Dark Blackout  |  <- product name (wraps, <=2 lines)
    |                       |
    |   |||| ||| || ||||    |  <- Code128 of the SKU code
    |       AE-BLA          |  <- human-readable interpretation line
    +-----------------------+

Output: a single .zpl file (all labels concatenated, each ^XA..^XZ) that you
send straight to the printer, e.g.:

    lp -d ZT411 -o raw data/labels/sku-labels-YYYYMMDD.zpl
    # or over the network:
    cat data/labels/sku-labels-YYYYMMDD.zpl | nc <printer-ip> 9100

Read-only against the product master parquet. Writes nothing back to CC.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import unicodedata
from datetime import date

import pandas as pd

# --- label geometry (mm) -------------------------------------------------
# Landscape: 100 mm across the web, 73 mm down the feed.
LABEL_W_MM = 100.0
LABEL_H_MM = 73.0
MARGIN_MM = 4.0

SKU_FONT_MM = 11.0        # big SKU code at top
SKU_Y_MM = 4.0
NAME_FONT_MM = 4.6        # product name block
NAME_Y_MM = 16.0
NAME_MAX_LINES = 2
BARCODE_Y_MM = 28.0
BARCODE_H_MM = 33.0
MODULE_MM = 0.40          # Code128 narrow-element width


def transliterate(text: str) -> str:
    """Fold to printable ASCII so the default ZT411 font renders cleanly."""
    if text is None:
        return ""
    text = str(text).replace("–", "-").replace("—", "-")
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    # ^ and ~ are ZPL control prefixes; comma/colon are fine inside ^FD.
    return text.replace("^", "-").replace("~", "-").strip()


def code128_width_modules(data: str) -> int:
    """Conservative Code128 width in modules: start + data + checksum + stop.

    Each Code128 character is 11 modules; the stop pattern is 13. This assumes
    no subset-C pairing (worst case / widest), so centring never overflows.
    """
    return 11 * (len(data) + 2) + 13


def render_label(code: str, name: str, dpi: int) -> str:
    dpm = dpi / 25.4  # dots per mm
    mm = lambda x: round(x * dpm)

    pw = mm(LABEL_W_MM)
    ll = mm(LABEL_H_MM)
    margin = mm(MARGIN_MM)
    inner_w = pw - 2 * margin

    sku_h = mm(SKU_FONT_MM)
    name_h = mm(NAME_FONT_MM)
    module = max(2, mm(MODULE_MM))
    bc_h = mm(BARCODE_H_MM)

    code = transliterate(code)
    name = transliterate(name)

    # centre the barcode deterministically from its module width
    bc_dots = code128_width_modules(code) * module
    bc_x = max(margin, (pw - bc_dots) // 2)

    z = []
    z.append("^XA")
    z.append("^CI28")                       # UTF-8 input (data is ASCII anyway)
    z.append(f"^PW{pw}")                     # print width
    z.append(f"^LL{ll}")                     # label length
    z.append("^LH0,0")                       # label home / origin
    z.append("^LS0")
    # big SKU code, centred across the printable width
    z.append(f"^FO{margin},{mm(SKU_Y_MM)}^A0N,{sku_h},{sku_h}"
             f"^FB{inner_w},1,0,C,0^FD{code}^FS")
    # product name, wrapped, centred, max 2 lines
    z.append(f"^FO{margin},{mm(NAME_Y_MM)}^A0N,{name_h},{name_h}"
             f"^FB{inner_w},{NAME_MAX_LINES},0,C,0^FD{name}^FS")
    # Code128 barcode with human-readable interpretation line below
    z.append(f"^BY{module},2.0,{bc_h}")
    z.append(f"^FO{bc_x},{mm(BARCODE_Y_MM)}^BCN,{bc_h},Y,N,N^FD{code}^FS")
    z.append("^XZ")
    return "\n".join(z)


def latest_products_parquet(raw_dir: str) -> str:
    hits = sorted(glob.glob(os.path.join(raw_dir, "products_*.parquet")))
    if not hits:
        sys.exit(f"No products_*.parquet found in {raw_dir}")
    return hits[-1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--products", help="path to products parquet "
                    "(default: latest in data/raw/)")
    ap.add_argument("--raw-dir", default="data/raw")
    ap.add_argument("--out-dir", default="data/labels")
    ap.add_argument("--dpi", type=int, default=203, choices=[203, 300],
                    help="ZT411 head resolution (default 203)")
    ap.add_argument("--all", action="store_true",
                    help="include inactive products too (default: active only)")
    ap.add_argument("--only", metavar="CODES",
                    help="emit labels only for these product_code(s), "
                    "comma-separated. One code -> -test suffix; many -> "
                    "-subset suffix.")
    ap.add_argument("--customer-id", metavar="UUID",
                    help="filter to a single customer_id (e.g. The Forage "
                    "Company). Needed when the source parquet spans the whole "
                    "tenant.")
    ap.add_argument("--dry-run", action="store_true",
                    help="report counts, write nothing")
    args = ap.parse_args()

    products = args.products or latest_products_parquet(args.raw_dir)
    df = pd.read_parquet(products)

    total = len(df)
    if not args.all and "active" in df.columns:
        df = df[df["active"].astype(bool)]
    if args.customer_id and "customer_id" in df.columns:
        df = df[df["customer_id"].astype(str) == args.customer_id]
    df = df.dropna(subset=["product_code"])
    df = df[df["product_code"].astype(str).str.strip() != ""]
    df = df.drop_duplicates(subset=["product_code"]).sort_values("product_code")

    only_codes = None
    if args.only:
        only_codes = [c.strip() for c in args.only.split(",") if c.strip()]
        df = df[df["product_code"].astype(str).isin(only_codes)]
        missing = set(only_codes) - set(df["product_code"].astype(str))
        if missing:
            sys.exit(f"--only: codes not found (active/customer-filtered): "
                     f"{sorted(missing)}")

    print(f"source : {products}")
    print(f"products: {total} total -> {len(df)} labels "
          f"({'all' if args.all else 'active only'})")

    if args.dry_run:
        print("dry-run: no file written")
        return

    labels = [render_label(r.product_code, getattr(r, "name", ""), args.dpi)
              for r in df.itertuples(index=False)]
    payload = "\n".join(labels) + "\n"

    os.makedirs(args.out_dir, exist_ok=True)
    stamp = date.today().strftime("%Y%m%d")
    if only_codes and len(only_codes) == 1:
        suffix = f"-test-{only_codes[0]}"
    elif only_codes:
        suffix = "-subset"
    else:
        suffix = ""
    out = os.path.join(args.out_dir, f"sku-labels-{stamp}{suffix}.zpl")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(payload)

    print(f"wrote  : {out}  ({len(labels)} labels, {args.dpi} dpi, "
          f"{LABEL_W_MM:g}x{LABEL_H_MM:g} mm)")
    print("send   : lp -d ZT411 -o raw " + out)
    print("   or  : cat %s | nc <printer-ip> 9100" % out)


if __name__ == "__main__":
    main()
