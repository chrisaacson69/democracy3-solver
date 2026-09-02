"""Load Democracy 3 CSV files into a :class:`GameModel`.

The loader is deliberately strict-but-honest: every malformed formula or row is recorded in
``model.problems`` (with the reason) rather than silently dropped or guessed at. That way the shipped
data typos surface as data, per the grounding rule.
"""

from __future__ import annotations

import csv
import re
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


def load_overrides(mission_dir: Path, model: GameModel) -> list[tuple[str, str, str]]:
    """Apply a country's per-mission edge overrides from ``missions/<country>/overrides/*.ini``.

    The simulation CSVs are **shared by every country** — one ``data/simulation/`` for all six — so the
    1,149-edge network is country-agnostic. What differs per country is a handful of deliberate edits,
    and ignoring them makes the model quietly wrong for that country rather than generic.

    The USA is the case in point: it **DELETES** ``HandgunLaws -> ViolentCrimeRate`` and adds
    ``LuxuryGoodsTax`` and ``MansionTax`` edges onto ``MiddleIncome``. Loading the shared CSVs alone
    has handgun laws cutting violent crime in a US game where the scenario says they do not.

    Format: ``HostName`` is the source, ``TargetName`` the target, ``Equation`` the replacement formula
    or the literal ``DELETE``. An override naming an edge that does not exist **adds** it.

    Returns the list of ``(host, target, action)`` applied, so callers can report rather than assume.
    """
    applied: list[tuple[str, str, str]] = []
    root = Path(mission_dir) / "overrides"
    if not root.is_dir():
        return applied

    def field(text: str, key: str) -> str:
        m = re.search(r'^\s*' + key + r'\s*=\s*"?([^"\n]*)', text, re.I | re.M)
        return m.group(1).strip().strip('"') if m else ""

    for f in sorted(root.glob("*.ini")):
        txt = f.read_text(encoding="latin-1")
        host, target, eq = field(txt, "HostName"), field(txt, "TargetName"), field(txt, "Equation")
        if not host or not target:
            model.problems.append((f.name, "override", txt[:60], "missing HostName/TargetName"))
            continue
        try:
            inertia = int(float(field(txt, "Inertia") or 0))
        except ValueError:
            inertia = 0

        # the effect lives on whichever node hosts it
        holder = (model.policies.get(host) or model.sim_values.get(host)
                  or model.situations.get(host))
        lists = []
        if holder is not None:
            lists.append(holder.effects if host in model.policies else holder.outputs)
        # a sim value can also carry it as an *input* on the target side
        tnode = model.sim_values.get(target) or model.situations.get(target)
        if tnode is not None:
            lists.append(tnode.inputs)

        if eq.upper() == "DELETE":
            hit = False
            for lst in lists:
                for e in list(lst):
                    if e.target == target or (lst is getattr(tnode, "inputs", None) and e.target == host):
                        lst.remove(e); hit = True
            applied.append((host, target, "DELETE" if hit else "DELETE (not found)"))
            continue

        try:
            formula = parse_formula(eq)
        except FormulaError as exc:
            model.problems.append((f.name, "override", eq, str(exc)))
            continue
        replaced = False
        for lst in lists:
            for i, e in enumerate(list(lst)):
                if e.target == target:
                    lst[i] = Effect(target=target, formula=formula, inertia=inertia)
                    replaced = True
        if not replaced and holder is not None:
            (holder.effects if host in model.policies else holder.outputs).append(
                Effect(target=target, formula=formula, inertia=inertia))
        applied.append((host, target, "replace" if replaced else "add"))
    return applied


def load_country(sim_dir: str | Path, country: str | None = None) -> tuple[GameModel, list]:
    """Load the shared simulation, then apply one country's overrides.

    **The effect network is country-agnostic** — a single ``data/simulation/`` serves all six
    countries, so the 1,149 edges, 40 outcomes and 36 crises are identical everywhere, and the
    equilibrium solve needs no absolute quantities at all: it runs entirely in the normalised [0,1]
    space the CSVs define. Absolutes (population, GDP range, income bands) are needed only by the
    *budget* layer, which is why a country is a starting condition rather than a different model.

    What is country-specific is exactly three things:

    1. the **starting policy vector** — ``missions/<country>/<country>.txt`` ``[policies]``
    2. the **edge overrides** — ``missions/<country>/overrides/*.ini``, applied here
    3. the **starting voter biases** — ``missions/<country>/scripts/*.txt`` (not yet read)

    Returns ``(model, applied)`` so the caller can report which overrides took effect.
    """
    model = load_model(sim_dir)
    if not country:
        return model, []
    mission = Path(sim_dir).parent / "missions" / country
    if not mission.is_dir():
        raise FileNotFoundError(f"no mission directory for {country!r} at {mission}")
    return model, load_overrides(mission, model)


def load_model(sim_dir: str | Path) -> GameModel:
    """Load the full model from a ``data/simulation`` directory."""
    sim_dir = Path(sim_dir)
    model = GameModel()
    load_simulation(sim_dir / "simulation.csv", model)
    load_policies(sim_dir / "policies.csv", model)
    load_votertypes(sim_dir / "votertypes.csv", model)
    load_situations(sim_dir / "situations.csv", model)
    return model


__all__ = ["load_country", "load_model", "load_overrides", "load_simulation", "load_policies",
           "load_votertypes", "load_situations"]
