"""Build the Policy Atlas: inject the efficiency matrix and the recipes into the template.

Companion to `build_explorer.py`. Kept as a build step for the same reason: re-run it and the page is
rebuilt from whatever the CSVs and the optimiser currently say, so the charts can never drift from the
model they describe.

Usage:  python scripts/build_atlas.py [-o atlas.html]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

TEMPLATE = Path("web/atlas.template.html")
EFF = Path("web/efficiency.json")
REC = Path("web/recipes.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="atlas.html")
    ap.add_argument("--refresh", action="store_true",
                    help="recompute the efficiency matrix before building")
    args = ap.parse_args()

    if args.refresh or not EFF.exists():
        subprocess.run([sys.executable, "scripts/export_efficiency.py", "-o", str(EFF)], check=True)

    eff = json.loads(EFF.read_text(encoding="utf-8"))
    rec = json.loads(REC.read_text(encoding="utf-8")) if REC.exists() else []
    if not rec:
        print("note: web/recipes.json missing — the page will build with an empty recipe list")

    def blob(o):
        # neutralise anything that could close the host <script> element
        return json.dumps(o, separators=(",", ":")).replace("<", "\\u003c")

    html = (TEMPLATE.read_text(encoding="utf-8")
            .replace("__EFFICIENCY_JSON__", blob(eff))
            .replace("__RECIPES_JSON__", blob(rec)))
    out = Path(args.out)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size/1024:.0f} KB; "
          f"{len(eff['policies'])} policies, {len(eff['outcomes'])} outcomes, {len(rec)} recipes)")


if __name__ == "__main__":
    main()
