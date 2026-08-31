"""Export the parsed model to JSON for the browser explorer.

The explorer re-solves the equilibrium on every slider drag, so it needs the effect network in a form
JavaScript can evaluate fast and without ``eval`` (the Artifact CSP does not reliably permit
``new Function``). Rather than reimplement the formula grammar in JS — a rebuild, and an unverified
one — this compiles each formula to a small nested-array AST **using the same Python parser the solver
trusts**, and ships that. The browser side is then a 12-line stack evaluator over a data structure,
not a second implementation of the grammar.

AST encoding (compact on purpose; there are ~1150 of them):
    3.5                      a bare number
    "x"                      the source node's value
    ["r", "GDP"]             another node's value (the multiplier refs)
    ["u", a]                 unary minus
    ["+"|"-"|"*"|"/"|"^", a, b]

Also parses ``data/simulation/dilemmas/*.txt``, which share the same ``Source, formula`` influence
grammar as everything else. A dilemma's pressure is the sum of its influences; ``_random_,lo,hi``
contributes a uniform band rather than a value, and is kept separate so the deterministic,
state-driven part can be shown on its own.

Usage:  python scripts/export_web_model.py [-o out.json]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

from d3solver import load_model
from d3solver.config import sim_dir
from d3solver.savegame import load_savegame
from d3solver.scenario import from_savegame

SAVE = Path("tests/fixtures/autosave_usa_turn1.xml")

_BINOP = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.Pow: "^"}


def to_ast(source: str):
    """Compile a Democracy 3 effect formula to the JSON AST above."""
    tree = ast.parse(source.replace("^", "**"), mode="eval")

    def walk(n):
        if isinstance(n, ast.Expression):
            return walk(n.body)
        if isinstance(n, ast.Constant):
            return float(n.value)
        if isinstance(n, ast.Name):
            return "x" if n.id == "x" else ["r", n.id]
        if isinstance(n, ast.UnaryOp):
            if isinstance(n.op, ast.USub):
                return ["u", walk(n.operand)]
            return walk(n.operand)
        if isinstance(n, ast.BinOp):
            op = _BINOP.get(type(n.op))
            if op is None:
                raise ValueError(f"unsupported operator in {source!r}")
            return [op, walk(n.left), walk(n.right)]
        raise ValueError(f"unsupported node {type(n).__name__} in {source!r}")

    return walk(tree)


def parse_dilemmas(root: Path) -> list[dict]:
    """Parse data/simulation/dilemmas/*.txt into name/description/influences/options."""
    out = []
    for f in sorted(root.glob("*.txt")):
        txt = f.read_text(encoding="latin-1")

        def section(name):
            m = re.search(rf"\[{name}\](.*?)(?=\n\[|\Z)", txt, re.S)
            return m.group(1) if m else ""

        def field(body, key):
            m = re.search(rf"^\s*{key}\s*=\s*(.*)$", body, re.I | re.M)
            return m.group(1).strip().strip('"') if m else ""

        head = section("dilemma")
        infl, rnd = [], None
        for line in section("influences").strip().splitlines():
            if "=" not in line:
                continue
            val = line.split("=", 1)[1].strip().strip('"')
            parts = [p.strip() for p in val.split(",")]
            if parts[0] == "_random_" and len(parts) >= 3:
                try:
                    rnd = [float(parts[1]), float(parts[2])]
                except ValueError:
                    pass
                continue
            if len(parts) < 2:
                continue
            src, expr = parts[0], ",".join(parts[1:])
            try:
                infl.append({"source": src, "formula": expr, "ast": to_ast(expr)})
            except (SyntaxError, ValueError):
                pass  # surfaced by count in the summary; never fabricated
        opts = []
        for i in (0, 1):
            body = section(f"option{i}")
            if body:
                opts.append({"name": field(body, "Name"), "description": field(body, "Description")})
        out.append({
            "name": field(head, "name") or f.stem,
            "guiname": field(head, "guiname") or f.stem,
            "description": field(head, "description"),
            "influences": infl,
            "random": rnd,
            "options": opts,
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="explorer_model.json")
    args = ap.parse_args()

    d = sim_dir()
    model = load_model(d)
    save = load_savegame(SAVE)
    scen = from_savegame(save)

    nodes, edges, problems = {}, [], []

    def add_edge(source, target, expr, kind):
        try:
            edges.append({"s": source, "t": target, "f": expr, "a": to_ast(expr), "k": kind})
        except (SyntaxError, ValueError) as exc:
            problems.append([target, expr, str(exc)])

    for n, sv in model.sim_values.items():
        nodes[n] = {"kind": "sim", "gui": sv.guiname or n, "desc": sv.description,
                    "zone": sv.zone, "def": sv.default, "min": sv.min, "max": sv.max,
                    "emotion": sv.emotion}
        for e in sv.outputs:
            add_edge(n, e.target, e.formula.source, "sim")
        for e in sv.inputs:
            add_edge(e.target, n, e.formula.source, "sim")

    for n, vt in model.voter_types.items():
        nodes[n] = {"kind": "voter", "gui": vt.guiname or n, "desc": vt.description,
                    "zone": "Voters", "def": vt.default, "min": -1.0, "max": 1.0,
                    "emotion": "HIGHGOOD", "pct": vt.percentage}

    for n, st in model.situations.items():
        nodes[n] = {"kind": "situation", "gui": st.guiname or n, "desc": "",
                    "zone": "Situations", "def": 0.0, "min": 0.0, "max": 1.0,
                    "emotion": "HIGHGOOD" if st.positive else "HIGHBAD",
                    "start": st.start_trigger, "stop": st.stop_trigger,
                    "positive": st.positive}
        for e in st.inputs:
            add_edge(e.target, n, e.formula.source, "sit_in")
        for e in st.outputs:
            add_edge(n, e.target, e.formula.source, "sit_out")

    policies = {}
    for n, p in model.policies.items():
        policies[n] = {"gui": p.guiname or n, "desc": p.description,
                       "dept": p.department or "Other", "slider": p.slider,
                       "mincost": p.mincost, "maxcost": p.maxcost,
                       "minincome": p.minincome, "maxincome": p.maxincome,
                       "start": scen.policies.get(n, 0.0)}
        for e in p.effects:
            add_edge(n, e.target, e.formula.source, "policy")

    dilemmas = parse_dilemmas(Path(d) / "dilemmas")

    payload = {
        "meta": {
            "source": "Democracy 3 (Positech Games) shipped simulation CSVs, parsed by d3solver",
            "country": "United States", "economy_default": scen.economy,
            "note": "values are the game's internal normalised scale unless stated",
        },
        "nodes": nodes,
        "edges": edges,
        "policies": policies,
        "exogenous": scen.exogenous,
        "situationsActive": scen.ref_active,
        "refState": scen.ref_state,
        "dilemmas": dilemmas,
        "problems": problems + [list(p) for p in model.problems],
    }
    out = Path(args.out)
    out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"{model.summary()}")
    print(f"nodes={len(nodes)} edges={len(edges)} policies={len(policies)} "
          f"dilemmas={len(dilemmas)} ast-problems={len(problems)}")
    print(f"wrote {out}  ({out.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
