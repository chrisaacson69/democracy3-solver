"""Load Democracy 3 CSV files into a :class:`GameModel`.

The loader is deliberately strict-but-honest: every malformed formula or row is recorded in
``model.problems`` (with the reason) rather than silently dropped or guessed at. That way the shipped
data typos surface as data, per the grounding rule.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .formula import FormulaError, parse_formula
from .model import Effect, GameModel, Policy, Situation, SimValue, VoterType


def _is_number(cell: str) -> bool:
    try:
        float(cell.strip())
        return True
    except ValueError:
        return False


def _data_rows(path: Path) -> list[list[str]]:
    """Return only the ``#``-marked data rows, with the leading ``#`` stripped."""
    with path.open(newline="", encoding="latin-1") as fh:
        rows = list(csv.reader(fh))
    return [r[1:] for r in rows if r and r[0].strip() == "#"]


def _parse_effect(token_fields: list[str], owner: str, section: str,
                  problems: list) -> Effect | None:
    """Parse a ``Target, formula [, inertia]`` triple that spans consecutive CSV columns.

    Effects are stored as adjacent columns (target, formula, optional inertia), so the caller passes
    the already-grouped slice. Returns None and records a problem on any failure.
    """
    target = token_fields[0].strip()
    formula_src = token_fields[1].strip() if len(token_fields) > 1 else ""
    inertia = 0
    if len(token_fields) > 2 and token_fields[2].strip():
        try:
            inertia = int(float(token_fields[2].strip()))
        except ValueError:
            problems.append((owner, section, ",".join(token_fields), "bad inertia"))
    try:
        formula = parse_formula(formula_src)
    except FormulaError as exc:
        problems.append((owner, section, f"{target},{formula_src}", str(exc)))
        return None
    return Effect(target=target, formula=formula, inertia=inertia)


def _group_effects(cells: list[str], owner: str, section: str, problems: list) -> list[Effect]:
    """Walk a flat list of cells, grouping them into ``target,formula[,inertia]`` effects.

    The CSV stores each effect as a single *quoted* cell like ``"GDP,0.98*(x^4),4"`` — so csv already
    hands us one cell per effect. We split on commas ourselves to separate target/formula/inertia,
    being careful that the formula itself may contain commas only inside ``()`` — which the shipped
    data does not do, so a plain split is faithful here.
    """
    effects: list[Effect] = []
    for cell in cells:
        cell = cell.strip()
        if not cell or cell == "#":
            continue
        parts = cell.split(",")
        eff = _parse_effect(parts, owner, section, problems)
        if eff is not None:
            effects.append(eff)
    return effects


def _split_sections(cells: list[str]) -> list[list[str]]:
    """Split a row's trailing cells on the literal ``#`` section markers."""
    sections: list[list[str]] = [[]]
    for c in cells:
        if c.strip() == "#":
            sections.append([])
        else:
            sections[-1].append(c)
    return sections


def load_simulation(path: Path, model: GameModel) -> None:
    for row in _data_rows(path):
        # name, guiname, desc, zone, def, min, max, emotion, icon, [#, inputs, #, outputs]
        if len(row) < 9:
            model.problems.append((row[0] if row else "?", "simrow", ",".join(row), "too short"))
            continue
        name = row[0].strip()
        try:
            default, mn, mx = float(row[4]), float(row[5]), float(row[6])
        except ValueError:
            model.problems.append((name, "simrow", ",".join(row[4:7]), "bad def/min/max"))
            continue
        rest = row[9:]
        sections = _split_sections(rest)
        # sections[0] is the gap before the first '#'; inputs then outputs follow.
        after_markers = sections[1:]
        inputs = _group_effects(after_markers[0], name, "input", model.problems) \
            if len(after_markers) > 0 else []
        outputs = _group_effects(after_markers[1], name, "output", model.problems) \
            if len(after_markers) > 1 else []
        model.sim_values[name] = SimValue(
            name=name, guiname=row[1].strip(), description=row[2], zone=row[3].strip(),
            default=default, min=mn, max=mx, emotion=row[7].strip(),
            inputs=inputs, outputs=outputs,
        )


def load_policies(path: Path, model: GameModel) -> None:
    for row in _data_rows(path):
        if len(row) < 18:
            model.problems.append((row[0] if row else "?", "polrow", ",".join(row), "too short"))
            continue
        name = row[0].strip()

        def num(idx: int, default: float = 0.0) -> float:
            try:
                return float(row[idx]) if row[idx].strip() else default
            except (ValueError, IndexError):
                model.problems.append((name, "polnum", row[idx] if idx < len(row) else "", f"col {idx}"))
                return default

        # Effects begin after the '#Effects' marker.
        try:
            eff_start = next(i for i, c in enumerate(row) if c.strip().lower() == "#effects") + 1
        except StopIteration:
            eff_start = 18
        effects = _group_effects(row[eff_start:], name, "policy", model.problems)
        model.policies[name] = Policy(
            name=name, guiname=row[1].strip(), slider=row[2].strip(), description=row[3],
            flags=[f.strip() for f in row[4].split(",") if f.strip()],
            department=row[9].strip(),
            mincost=num(10), maxcost=num(11), cost_multiplier=row[12].strip(),
            implementation=int(num(13)),
            minincome=num(14), maxincome=num(15), income_multiplier=row[16].strip(),
            effects=effects,
        )


def load_votertypes(path: Path, model: GameModel) -> None:
    for row in _data_rows(path):
        if len(row) < 10:
            model.problems.append((row[0] if row else "?", "voterrow", ",".join(row), "too short"))
            continue
        name = row[0].strip()
        try:
            default, pct = float(row[5]), float(row[6])
        except ValueError:
            model.problems.append((name, "voterrow", f"{row[5]},{row[6]}", "bad default/pct"))
            continue
        influences: dict[str, float] = {}
        # influences start after the '#' marker (col 10 onward), as "Group,weight" cells.
        for cell in row[10:]:
            cell = cell.strip()
            if not cell or cell == "#":
                continue
            parts = [p.strip() for p in cell.split(",")]
            if len(parts) >= 2:
                try:
                    influences[parts[0]] = float(parts[1])
                except ValueError:
                    model.problems.append((name, "influence", cell, "bad weight"))
        model.voter_types[name] = VoterType(
            name=name, guiname=row[1].strip(), plural=row[2].strip(),
            default=default, percentage=pct, description=row[7], influences=influences,
        )


def load_situations(path: Path, model: GameModel) -> None:
    # cols (after '#'): 0 name,1 gui,2 desc,3 zone,4 icon,5 starttxt,6 stoptxt,7 positive,
    #                   8 start_trigger,9 stop_trigger, then flags + inputs, '#', outputs
    for row in _data_rows(path):
        if len(row) < 10:
            model.problems.append((row[0] if row else "?", "sitrow", ",".join(row), "too short"))
            continue
        name = row[0].strip()
        try:
            positive = float(row[7]) > 0.5
            start, stop = float(row[8]), float(row[9])
        except ValueError:
            model.problems.append((name, "sitrow", f"{row[7:10]}", "bad triggers"))
            continue
        sections = _split_sections(row[10:])
        raw_in = [c for c in (sections[0] if sections else []) if c.strip() and not _is_number(c)]
        raw_out = [c for c in (sections[1] if len(sections) > 1 else []) if c.strip() and not _is_number(c)]
        inputs = _group_effects(raw_in, name, "sit_in", model.problems)
        outputs = _group_effects(raw_out, name, "sit_out", model.problems)
        model.situations[name] = Situation(
            name=name, guiname=row[1].strip(), start_trigger=start, stop_trigger=stop,
            positive=positive, inputs=inputs, outputs=outputs,
        )


def load_model(sim_dir: str | Path) -> GameModel:
    """Load the full model from a ``data/simulation`` directory."""
    sim_dir = Path(sim_dir)
    model = GameModel()
    load_simulation(sim_dir / "simulation.csv", model)
    load_policies(sim_dir / "policies.csv", model)
    load_votertypes(sim_dir / "votertypes.csv", model)
    load_situations(sim_dir / "situations.csv", model)
    return model


__all__ = ["load_model", "load_simulation", "load_policies", "load_votertypes", "load_situations"]
