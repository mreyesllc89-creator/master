"""EA inputs: defaults from the source, .set files in and out, and the engine's parameter vector."""
import json
import os

import numpy as np

import engine

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = json.load(open(os.path.join(HERE, "inputs_default.json")))
BY_NAME = {r["name"]: r for r in SPEC}

# replay-only switches (prefix X_), not EA inputs
EXTRA = {"X_ExitGatePips": 6.8, "X_SlipPts": 0.0, "X_CommissionPts": 0.0, "X_StopsLevelPts": 0.0,
         "X_MicroRestart": 1.0, "X_TradeBuys": 1.0, "X_TradeSells": 1.0, "X_FillSnapPts": 0.0, "X_LimitAtMarket": 1.0, "X_LatencyMs": 0.0,
         "X_StopLossSlipMult": 1.0}


def defaults():
    """Source-code defaults (not the shipped presets)."""
    p = {r["name"]: r["default"] for r in SPEC}
    p.update(EXTRA)
    return p


def read_set(path):
    raw = open(path, "rb").read()
    txt = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
    out = {}
    for line in txt.splitlines():
        if not line or line.startswith(";") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.split("||")[0].strip()
    return out


def from_set(path):
    """Inputs of a preset, typed; anything the file does not mention keeps the source default."""
    p = defaults()
    for k, v in read_set(path).items():
        r = BY_NAME.get(k)
        if r is None:
            continue
        if r["kind"] == "bool":
            p[k] = v.lower() == "true"
        elif r["kind"] in ("int", "enum"):
            p[k] = int(float(v))
        elif r["kind"] == "double":
            p[k] = float(v)
        else:
            p[k] = v
    return p


def fmt(r, v):
    if r["kind"] == "bool":
        return "true" if v else "false"
    if r["kind"] in ("int", "enum"):
        return str(int(v))
    if r["kind"] == "double":
        s = repr(float(v))
        return s
    return str(v)


def write_set(path, p, ranges=None, header=()):
    """Write a tester .set (every input, source order). `ranges` = {name: (start, step, stop)} adds
    optimizer ranges: name=value||start||step||stop||Y."""
    ranges = ranges or {}
    lines = [f"; {h}" for h in header]
    for r in SPEC:
        k = r["name"]
        v = fmt(r, p[k])
        if k in ranges:
            a, s, b = ranges[k]
            v = f"{v}||{fmt(r, a)}||{fmt(r, s)}||{fmt(r, b)}||Y"
        lines.append(f"{k}={v}")
    with open(path, "w", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")


def vector(p):
    """Parameter vector in engine.NAMES order."""
    v = np.zeros(engine.NP)
    for k, name in enumerate(engine.NAMES):
        v[k] = float(p[name])
    return v


def diff(a, b):
    """Inputs that differ between two parameter sets (numeric and bool only)."""
    out = {}
    for k in a:
        if k in b and a[k] != b[k] and not isinstance(a[k], str):
            out[k] = (a[k], b[k])
    return out
