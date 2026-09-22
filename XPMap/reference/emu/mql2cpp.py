import re, sys
src = open(sys.argv[1]).read()
out = []
for line in src.split("\n"):
    if re.match(r"\s*#property", line): continue
    if re.match(r"\s*input group", line): continue
    line = re.sub(r"^input\s+", "const ", line)
    line = re.sub(r"C'(\d+),(\d+),(\d+)'", r"RGBc(\1,\2,\3)", line)
    # array params: const T &name[]  ->  const Arr<T>& name
    line = re.sub(r"(const\s+)?(\w+)\s*&\s*(\w+)\[\]", lambda m: f"{m.group(1) or ''}Arr<{m.group(2)}>& {m.group(3)}", line)
    # declarations of dynamic arrays: T a[], b[];  (only when the line is a declaration)
    m = re.match(r"^(\s*)(\w+)\s+((?:\w+\[\d*\]\s*,\s*)*\w+\[\d*\])\s*;\s*(//.*)?$", line)
    if m and m.group(2) not in ("return",):
        names = [n.strip() for n in m.group(3).split(",")]
        decl = []
        for n in names:
            mm = re.match(r"(\w+)\[(\d*)\]", n)
            decl.append(f"{mm.group(1)}({mm.group(2)})" if mm.group(2) else mm.group(1))
        line = f"{m.group(1)}Arr<{m.group(2)}> {', '.join(decl)}; {m.group(4) or ''}"
    out.append(line)
open(sys.argv[2], "w").write('#include "mql5_stubs.h"\n' + "\n".join(out))
