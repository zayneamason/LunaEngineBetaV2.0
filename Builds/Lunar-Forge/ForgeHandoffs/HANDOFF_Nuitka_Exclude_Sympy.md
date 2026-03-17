# HANDOFF — SymPy in Nuitka Builds (DO NOT EXCLUDE)

**Date:** 2026-03-15
**Status:** Investigated — no action needed
**Verdict:** Keep sympy in builds. It powers two of Luna's skills.

---

## Investigation

SymPy adds ~10-15 minutes to Nuitka compilation (~600 modules compiled to C). Initially suspected to be transitive bloat from onnxruntime, but it's actually a **direct dependency** of two Luna skills:

### MathSkill (`src/luna/skills/math/skill.py`)
- Symbolic math: solve, integrate, differentiate, factor, simplify, expand
- Uses `sympy.solve()`, `sympy.integrate()`, `sympy.diff()`, `sympy.factor()`, `sympy.simplify()`, `sympy.expand()`
- Uses `sympy.parsing.sympy_parser.parse_expr` for natural language → expression parsing
- Uses `sympy.latex()` for formatted output

### LogicSkill (`src/luna/skills/logic/skill.py`)
- Propositional logic: truth tables, satisfiability, simplification
- Uses `sympy.logic.boolalg` (And, Or, Not, Xor)
- Uses `sympy.satisfiable()`, `sympy.simplify_logic()`

### Registry (`src/luna/skills/registry.py`)
- Lines 41-45: MathSkill import with graceful fallback — `"MathSkill not available (missing sympy?)"`
- Lines 58-60: LogicSkill same pattern
- Both skills degrade gracefully if sympy is missing (fallthrough to LLM), but the user loses exact computation

## Conclusion

Excluding sympy saves ~10 min build time but **disables two skills**. The compile cost is justified. Do NOT add sympy to `exclude_packages`.

## Future Optimization (if build time becomes critical)

Instead of excluding sympy entirely, Nuitka supports compiling only the submodules actually imported. A targeted include could cut the 600-module compile down to ~50 modules:

```yaml
nuitka:
  exclude_packages:
    - sympy             # exclude the full package
  extra_include_packages:
    - sympy.core        # but include only what Luna uses
    - sympy.parsing
    - sympy.solvers
    - sympy.integrals
    - sympy.simplify
    - sympy.polys
    - sympy.logic
    - sympy.printing.latex
```

This is untested — sympy has deep internal cross-imports that may cause runtime failures if submodules are missing. Would need careful testing.
