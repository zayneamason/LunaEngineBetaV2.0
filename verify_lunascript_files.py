#!/usr/bin/env python3
"""Run this script from the project root to verify LunaScript files."""
import os
base = os.path.dirname(os.path.abspath(__file__))
expected = {
    "Docs/LunaScript/HANDOFF_LUNASCRIPT_COGNITIVE_SIGNATURE.md": 700,
    "Docs/LunaScript/lunascript_calibration_results.txt": 150,
    "Docs/LunaScript/README.md": 10,
    "src/luna/lunascript/__init__.py": 10,
    "src/luna/lunascript/lunascript_measurement_REFERENCE.py": 700,
    "config/lunascript.yaml": 30,
}
for rel, min_lines in expected.items():
    path = os.path.join(base, rel)
    if os.path.exists(path):
        with open(path) as f:
            lines = f.read().count('\n')
        status = "OK" if lines >= min_lines else f"SHORT ({lines} lines, need {min_lines}+)"
        print(f"  {status:12s} {rel} ({lines} lines)")
    else:
        print(f"  MISSING      {rel}")
