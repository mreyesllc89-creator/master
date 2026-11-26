"""REPORT.md = the hand-written text (REPORT_src.md) with the generated tables put in.

usage: python assemble_report.py [calibration_dir]

A line `<<Section title>>` in REPORT_src.md is replaced by the body of the section with that
`## ` title in REPORT_tables.md (written by report.py); `<<Settings per timeframe>>` brings
that section's `### ` parts with it.
A line `<<include path>>` is replaced by that file (path relative to the calibration folder).
"""
import os
import re
import sys


def sections(md):
    out, title, buf = {}, None, []
    for line in md.split("\n"):
        m = re.match(r"^## (.+)$", line)
        if m:
            if title is not None:
                out[title] = "\n".join(buf).strip("\n")
            title, buf = m.group(1).strip(), []
        elif title is not None:
            buf.append(line)
    if title is not None:
        out[title] = "\n".join(buf).strip("\n")
    return out


def run(root):
    src = open(os.path.join(root, "REPORT_src.md"), encoding="utf-8").read()
    sec = sections(open(os.path.join(root, "REPORT_tables.md"), encoding="utf-8").read())
    missing = []

    def put(m):
        name = m.group(1).strip()
        if name not in sec:
            missing.append(name)
            return m.group(0)
        return sec[name]

    def include(m):
        return open(os.path.join(root, m.group(1).strip()), encoding="utf-8").read().strip("\n")
    src = re.sub(r"^<<include (.+?)>>$", include, src, flags=re.M)
    out = re.sub(r"^<<(.+?)>>$", put, src, flags=re.M)
    if missing:
        raise SystemExit(f"no generated section for: {missing}; have: {list(sec)}")
    open(os.path.join(root, "REPORT.md"), "w", encoding="utf-8").write(out)
    print(f"REPORT.md written ({len(out.splitlines())} lines)")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
