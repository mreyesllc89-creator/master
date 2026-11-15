"""Read every `input` declaration of the EA and its include files into inputs_default.json.

usage: python -I extract_inputs.py <component_dir> <out_json>

The json keeps the declaration order, the MQL type, the default and the section (input group or the
"=== ... ===" separator strings), so presets can be written back in the tester's own order."""
import json
import re
import sys
from pathlib import Path

FILES = ["SpeedAlertContinuationFilter.mqh", "SpeedAlertFlashGoldPermission.mqh", "SpeedAlert_FlashGold_Micro.mq5"]
ENUMS = {"StopOnly": 0, "StopAndMarket": 1, "StopMarketLimit": 2, "FIXED": 0, "PERCENTILE": 1, "CP_OFF": 0, "CP_FILTER": 2,
         "FGF_NATIVE_TIMEFRAME": 0, "FGF_QUOTE_MILLISECONDS": 1, "FGF_LEVEL_ENTRY": 0, "FGF_LEVEL_CLOSE": 1,
         "FGF_LASTS_NEXT": 0, "FGF_LASTS_MINUTES": 1, "FGF_LASTS_CANDLES": 2, "FGF_LASTS_SECONDS": 3,
         "FGF_LASTS_MILLISECONDS": 4, "FGF_CHECK_TICK": 0, "FGF_CHECK_OPEN": 1, "FGF_CHECK_CLOSE": 2,
         "FGF_UNIT_ATR": 0, "FGF_UNIT_POINTS": 1, "PERIOD_CURRENT": 0, "PERIOD_M1": 1, "PERIOD_M2": 2, "PERIOD_M3": 3,
         "PERIOD_M4": 4, "PERIOD_M5": 5, "PERIOD_M6": 6, "PERIOD_M10": 10, "PERIOD_M12": 12, "PERIOD_M15": 15,
         "PERIOD_M20": 20, "PERIOD_M30": 30, "PERIOD_H1": 16385, "PERIOD_H2": 16386, "PERIOD_H3": 16387,
         "PERIOD_H4": 16388, "PERIOD_H6": 16390, "PERIOD_H8": 16392, "PERIOD_H12": 16396, "PERIOD_D1": 16408}


def main(root, out):
    rows = []
    section = ""
    for name in FILES:
        for line in (Path(root) / name).read_text(encoding="utf-8-sig").splitlines():
            g = re.match(r'\s*input\s+group\s+"(.*)"', line)
            if g:
                section = g.group(1)
                continue
            m = re.match(r"\s*input\s+([A-Za-z_0-9]+)\s+([A-Za-z_0-9]+)\s*=\s*(.*?);\s*(?://\s*(.*))?$", line)
            if not m:
                continue
            typ, key, default, comment = m.group(1), m.group(2), m.group(3).strip(), (m.group(4) or "").strip()
            if typ == "string":
                default = default.strip('"')
                if default.startswith("==="):
                    section = default.strip("= ")
                kind = "string"
            elif typ == "bool":
                kind, default = "bool", default == "true"
            elif typ in ("int", "long"):
                kind, default = "int", int(default)
            elif typ == "double":
                kind, default = "double", float(default)
            elif typ == "color":
                kind = "color"
            else:
                kind, default = "enum", ENUMS[default]
            rows.append(dict(name=key, type=typ, kind=kind, default=default, section=section, file=name, comment=comment))
    Path(out).write_text(json.dumps(rows, indent=1))
    print(len(rows), "inputs ->", out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
