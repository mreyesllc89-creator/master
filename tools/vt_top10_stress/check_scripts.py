"""Independent mechanical check of the generated scripts (separate implementation from the generator). Exit 1 on any problem."""
import json, re, os, sys, difflib
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"); man = json.load(open(f"{OUT}/manifest.json", encoding="utf-8"))
SHORT = {"FlashGold v5":"FG5","ShapeMap v0.9.2":"SM92","Orientation v2.8 (partial ladder)":"OTDI28"}
bases = {k: open(f"{OUT}/_diffs/base_{v}.pine", encoding="utf-8").read().splitlines() for k, v in SHORT.items()}
problems = []
def pine_val(v):
    if isinstance(v, bool): return "true" if v else "false"
    if isinstance(v, str): return f'"{v}"'
    return repr(float(v)) if isinstance(v, float) else str(v)
FIRST = re.compile(r"\(\s*(\"[^\"]*\"|[^,]+?)\s*,")
for m in man:
    f = f"{OUT}/{m['file']}"; src = open(f, encoding="utf-8").read(); lines = src.splitlines(); base = bases[m["strategy"]]
    vi = next(i for i, l in enumerate(lines) if re.match(r"^//@version=\d+$", l))
    if any(not (l.startswith("//") or l.strip() == "") for l in lines[:vi]): problems.append((m["file"], "code before //@version"))
    for name, val in m["inputs"].items():
        hits = [l for l in lines if re.match(r"^" + re.escape(name) + r"\s*=\s*input\.", l)]
        if len(hits) != 1: problems.append((m["file"], f"{name}: {len(hits)} definitions")); continue
        mm = re.match(r"^" + re.escape(name) + r"\s*=\s*input\.(\w+)\(\s*(\"[^\"]*\"|[^,]+?)\s*,", hits[0])
        if not mm: problems.append((m["file"], f"{name}: cannot parse")); continue
        kind, got = mm.groups(); exp = pine_val(val)
        if kind in ("float", "int"):
            if float(got) != float(val): problems.append((m["file"], f"{name}: {got} != {exp}"))
        elif got != exp: problems.append((m["file"], f"{name}: {got} != {exp}"))
        if kind == "string":
            om = re.search(r"options\s*=\s*\[([^\]]*)\]", hits[0])
            if om and exp not in re.findall(r'"[^"]*"', om.group(1)): problems.append((m["file"], f"{name}: {exp} not in options"))
    i0 = next(i for i, l in enumerate(lines) if l.startswith("strategy(")); call = ""; depth = 0
    for l in lines[i0:]:
        call += l + "\n"; depth += l.count("(") - l.count(")")
        if depth == 0: break
    callc = re.sub(r"//[^\n]*", "", call)
    pats = [r"default_qty_value\s*=\s*0\.1\b", r"commission_type\s*=\s*strategy\.commission\.cash_per_contract", r"commission_value\s*=\s*0\.30?\b", r"slippage\s*=\s*10\b", r"default_qty_type\s*=\s*strategy\.fixed"]
    if m["strategy"].startswith("Orientation"): pats += [r"margin_long\s*=\s*1\b", r"margin_short\s*=\s*1\b"]
    for pat in pats:
        if not re.search(pat, callc): problems.append((m["file"], f"strategy(): missing {pat}"))
    if callc.count("(") != callc.count(")"): problems.append((m["file"], "strategy(): unbalanced parens"))
    if f'"{m["title"]}"' not in callc or f'"{m["shorttitle"]}"' not in callc: problems.append((m["file"], "strategy(): title/shorttitle"))
    if re.search(r",\s*,", callc) or re.search(r",\s*\)", callc): problems.append((m["file"], "strategy(): stray comma"))
    sm = difflib.SequenceMatcher(None, base, lines, autojunk=False); allowed = set(m["inputs"])
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal": continue
        old = base[i1:i2]; new = lines[j1:j2]
        if tag == "insert" and all(l.startswith("//") for l in new): continue
        if tag == "replace":
            ok = True
            if len(old) == len(new):
                for o, n in zip(old, new):
                    nm = re.match(r"^(\w+)\s*=\s*input\.", o)
                    if nm and nm.group(1) in allowed and FIRST.sub("(X,", o, count=1) == FIRST.sub("(X,", n, count=1): continue
                    if o.startswith("strategy(") or o.strip().startswith(("default_qty_type", "commission_type", "slippage")): continue
                    ok = False
            else:
                ok = all(l.startswith("//") for l in new[:-1]) and new[-1].startswith("strategy(") and len(old) == 1 and old[0].startswith("strategy(")
            if ok: continue
        problems.append((m["file"], f"unexpected diff {tag} base[{i1}:{i2}] -> gen[{j1}:{j2}]: {old[:1]} -> {new[:1]}"))
    if "__FGF_OVERLAY__" in src: problems.append((m["file"], "placeholder left"))
    ov = re.search(r"^FGF_FORCE_OVERLAY = (true|false)$", src, re.M).group(1)
    if ov != ("false" if m["strategy"] == "FlashGold v5" else "true"): problems.append((m["file"], f"overlay flag {ov}"))
    for name, val in m["inputs"].items():
        if f"//   {name} = {pine_val(val)}" not in src: problems.append((m["file"], f"header missing {name}"))
    if f"trades {m['screen']['trades']} " not in src: problems.append((m["file"], "header trades"))
    if "TICK SIZE" not in src or "Stress re-run" not in src: problems.append((m["file"], "header warnings missing"))
    if m["inputs"].get("exitUnit") == "Points" and "POINTS-MODE EXITS" not in src: problems.append((m["file"], "points marker missing"))
    if m["strategy"] == "ShapeMap v0.9.2" and m["inputs"].get("enterTick") is not False: problems.append((m["file"], "enterTick not false"))
print(len(man), "files checked;", len(problems), "problems")
for p in problems[:40]: print(p)
sys.exit(1 if problems else 0)
