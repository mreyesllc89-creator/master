import re, sys
src = open(sys.argv[1]).read()
overrides = dict(kv.split("=") for kv in sys.argv[3:])
out = []
for line in src.split("\n"):
    if re.match(r"\s*#property", line): continue
    if re.match(r"\s*input group", line): continue
    m = re.match(r"^input\s+(\w+)\s+(\w+)\s*=\s*([^;]+);(.*)$", line)
    if m:
        val = overrides.get(m.group(2), m.group(3).strip())
        line = f"const {m.group(1)} {m.group(2)} = {val};{m.group(4)}"
    line = re.sub(r"C'(\d+),(\d+),(\d+)'", r"RGBc(\1,\2,\3)", line)
    line = re.sub(r"(const\s+)?(\w+)\s*&\s*(\w+)\[\]", lambda m: f"{m.group(1) or ''}Arr<{m.group(2)}>& {m.group(3)}", line)
    m = re.match(r"^(\s*)(\w+)\s+((?:\w+\[\d*\]\s*,\s*)*\w+\[\d*\])\s*;\s*(//.*)?$", line)
    if m and m.group(2) not in ("return",):
        names = [n.strip() for n in m.group(3).split(",")]
        decl = []
        for n in names:
            mm = re.match(r"(\w+)\[(\d*)\]", n)
            decl.append(f"{mm.group(1)}({mm.group(2)})" if mm.group(2) else mm.group(1))
        line = f"{m.group(1)}Arr<{m.group(2)}> {', '.join(decl)}; {m.group(4) or ''}"
    out.append(line)
open(sys.argv[2], "w").write('#include "mql5_rt.h"\n' + "\n".join(out))
