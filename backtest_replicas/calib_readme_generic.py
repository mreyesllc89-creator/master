"""Markdown of a calibration section: head text + tables (out/calib_rule_<s>.json) + closing text.
Usage: python3 -I calib_readme_generic.py <strategy> <decimals> <head.md> <shows.md> > section.md
In head.md the token {N} is replaced by the number of backtests."""
import json
import subprocess
import sys

s, dec, head, shows = sys.argv[1], sys.argv[2], open(sys.argv[3]).read().strip(), open(sys.argv[4]).read().strip()
unit = sys.argv[5] if len(sys.argv) > 5 else '%'
t = subprocess.run([sys.executable, '-I', 'calib_tables.py', s, dec, unit], capture_output=True, text=True, check=True).stdout.strip()
R = json.load(open(f'out/calib_rule_{s}.json'))
n = sum(r['settings'] for r in R.values())
print(head.replace('{N}', f'{n:,}') + '\n\n' + t + '\n\n' + shows + '\n')
