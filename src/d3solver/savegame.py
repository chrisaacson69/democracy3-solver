"""Parse a Democracy 3 savegame (autosave.xml) — the ground-truth oracle.

The save is the game's post-turn **fixed point**: every simulation value, policy setting, and voter
state at equilibrium. We use it to validate the simulator (does our combination rule reproduce these
values?) rather than trusting our own math.

The file is not clean XML: it's a concatenation of fragments (no single root), it uses numeric element
names like ``<0>``, and may contain unescaped ``&``. We sanitize minimally and wrap before parsing.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SaveState:
    sim_values: dict[str, float] = field(default_factory=dict)      # simvalue name -> equilibrium value
    policies: dict[str, dict] = field(default_factory=dict)          # policy name -> {targ,val,active,...}
    situations: dict[str, dict] = field(default_factory=dict)        # situation name -> {val, active}
    voter_values: dict[str, float] = field(default_factory=dict)     # voter group -> aggregate value (if found)
    globals: dict[str, float] = field(default_factory=dict)          # socialism, liberalism, apathy, ...
    mission: str = ""
    _root: ET.Element | None = None

    def active_situations(self) -> dict[str, float]:
        """name -> value for situations currently active."""
        return {n: d["val"] for n, d in self.situations.items() if d.get("active")}


def _sanitize(text: str) -> str:
    # the save ends with a stray </xml> that was never opened — drop it before wrapping
    text = text.replace("</xml>", "")
    # element names starting with a digit (<0>, </1>, <0_hist>) are invalid XML → prefix with 'n'
    text = re.sub(r"<(/?)(\d[\w.\-]*)>", r"<\1n\2>", text)
    # unescaped ampersands
    text = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9A-Fa-f]+;)", "&amp;", text)
    return text


def _parse_group_index(root: ET.Element) -> dict[int, str]:
    """First <hashtable><hashes> maps voter-group name -> index (name,idx,name,idx,...)."""
    ht = root.find("hashtable")
    if ht is None:
        return {}
    hashes = ht.findtext("hashes") or ""
    toks = [t for t in hashes.split(",") if t != ""]
    idx_to_name: dict[int, str] = {}
    for i in range(0, len(toks) - 1, 2):
        name, num = toks[i], toks[i + 1]
        try:
            idx_to_name[int(num)] = name
        except ValueError:
            pass
    return idx_to_name


def _parse_root(path: Path) -> ET.Element:
    text = path.read_text(encoding="latin-1")
    return ET.fromstring("<root>\n" + _sanitize(text) + "\n</root>")


def load_savegame(path: str | Path) -> SaveState:
    path = Path(path)
    root = _parse_root(path)
    s = SaveState(_root=root)

    for sv in root.iter("simvalue"):
        name = sv.findtext("name")
        val = sv.findtext("value")
        if name is not None and val is not None:
            s.sim_values[name] = float(val)

    for p in root.iter("policy"):
        name = p.findtext("name")
        if name is None:
            continue
        def num(tag, default=0.0):
            t = p.findtext(tag)
            try:
                return float(t)
            except (TypeError, ValueError):
                return default
        def first_hist(tag):
            t = p.findtext(tag)
            if not t:
                return 0.0
            head = t.split(",")[0].strip()
            try:
                return float(head)
            except ValueError:
                return 0.0
        s.policies[name] = {
            "targ": num("targ"), "val": num("val"), "active": int(num("active")),
            "cost_scalar": num("cost_scalar", 1.0), "earn_scalar": num("earn_scalar", 1.0),
            "cost": first_hist("costhistory"),     # current actual cost (~$M)
            "income": first_hist("incomehistory"),  # current actual income (~$M)
        }

    # Voter-group aggregate values live in the <simulation> array, indexed per the group hashtable.
    idx_to_name = _parse_group_index(root)
    sim_arr = root.find("simulation")
    if sim_arr is not None and idx_to_name:
        for idx, gname in idx_to_name.items():
            cell = sim_arr.findtext(f"n{idx}")
            if cell is not None:
                s.voter_values[gname] = float(cell)

    for st in root.iter("situation"):
        nm = st.findtext("name")
        if nm is None:
            continue
        def snum(tag, default=0.0):
            t = st.findtext(tag)
            try:
                return float(t)
            except (TypeError, ValueError):
                return default
        s.situations[nm] = {"val": snum("val"), "active": int(snum("active"))}

    m = root.find("mission")
    if m is not None:
        s.mission = m.findtext("name") or ""
        for tag in ("socialism", "liberalism", "apathy", "difficulty"):
            t = m.findtext(tag)
            if t is not None:
                s.globals[tag] = float(t)

    ge = root.find("globaleconomy")
    if ge is not None:
        for tag in ("pos", "years", "intens"):
            t = ge.findtext(tag)
            if t is not None:
                s.globals[f"globaleconomy_{tag}"] = float(t)

    return s


if __name__ == "__main__":
    import sys
    from collections import Counter

    s = load_savegame(sys.argv[1])
    root = s._root
    print("mission:", s.mission, "| globals:", s.globals)
    print(f"simvalues: {len(s.sim_values)} | policies: {len(s.policies)} "
          f"(active: {sum(1 for p in s.policies.values() if p['active'])})"
          f" | voter groups: {len(s.voter_values)}")
    print("simvalue names starting with '_':",
          [n for n in s.sim_values if n.startswith("_")])
    print("\nvoter-group values:")
    for g, v in s.voter_values.items():
        print(f"   {g:18s} {v:.4f}")
    print("\nGDP =", s.sim_values.get("GDP"), "| size of <simulation> array:",
          len(list(root.find("simulation"))) if root.find("simulation") is not None else "n/a")
