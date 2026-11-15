"""Write calibrated presets and MT5 optimizer range files from a JSON of overrides.

usage: python -I make_presets.py <overrides.json> <out_dir>

overrides.json = {"<preset file stem>": {"base": "<shipped preset stem>", "set": {input: value, ...},
                                         "ranges": {input: [start, step, stop], ...}, "note": "..."}}
Presets keep the package convention: TradingEnabled=false and a _DISABLED suffix. Files with ranges are
for the Strategy Tester optimizer and have TradingEnabled=true (the development build refuses to start
outside the tester anyway).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # scripts are run with python -I

import params

HERE = os.path.dirname(os.path.abspath(__file__))


def main(spec_path, out_dir):
    spec = json.load(open(spec_path))
    os.makedirs(out_dir, exist_ok=True)
    for stem, item in spec.items():
        p = params.from_set(os.path.join(HERE, "..", "shipped_presets", item["base"] + "_DISABLED.set"))
        for k, v in item.get("set", {}).items():
            if k not in params.BY_NAME:
                raise KeyError(k)
            p[k] = v
        ranges = {k: tuple(v) for k, v in item.get("ranges", {}).items()}
        p["TradingEnabled"] = bool(ranges)
        name = f"{stem}_TESTER_OPT.set" if ranges else f"{stem}_DISABLED.set"
        header = [item.get("note", ""), f"base preset: {item['base']}",
                  "changed: " + ", ".join(f"{k}={params.fmt(params.BY_NAME[k], v)}" for k, v in item.get("set", {}).items())]
        params.write_set(os.path.join(out_dir, name), p, ranges, [h for h in header if h])
        print(name, len(item.get("set", {})), "changes", len(ranges), "ranges")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
