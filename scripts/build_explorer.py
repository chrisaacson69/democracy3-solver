"""Build the browser explorer: inject the exported model into the HTML template.

Kept as a build step rather than a hand-edited page so the data in the explorer can never drift from
the CSVs -- re-run it and the page is rebuilt from whatever the game currently ships.

Usage:  python scripts/build_explorer.py [-o explorer.html]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

TEMPLATE = Path("web/explorer.template.html")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="explorer.html")
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as td:
        blob = Path(td) / "model.json"
        subprocess.run([sys.executable, "scripts/export_web_model.py", "-o", str(blob)], check=True)
        data = json.loads(blob.read_text(encoding="utf-8"))

    # Re-dump compactly and neutralise anything that could close the host <script> element.
    payload = json.dumps(data, separators=(",", ":")).replace("<", "\u003c")
    html = TEMPLATE.read_text(encoding="utf-8").replace("__MODEL_JSON__", payload)
    out = Path(args.out)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
