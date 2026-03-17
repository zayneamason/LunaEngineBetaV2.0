"""Create a blank seed luna_engine.db with schema only."""

import sqlite3
import sys
from pathlib import Path

# Resolve paths
FORGE_ROOT = Path(__file__).parent.parent
ENGINE_ROOT = Path(
    sys.argv[2] if len(sys.argv) > 2
    else FORGE_ROOT.parent / "_LunaEngine_BetaProject_V2.0_Root"
)
SCHEMA = ENGINE_ROOT / "src" / "luna" / "substrate" / "schema.sql"
OUTPUT = Path(sys.argv[1]) if len(sys.argv) > 1 else FORGE_ROOT / "seed" / "luna_engine_seed.db"


def create_seed(schema_path: Path = SCHEMA, output_path: Path = OUTPUT) -> Path:
    """Create a seed database from schema.sql."""
    if not schema_path.exists():
        print(f"ERROR: schema.sql not found at {schema_path}", file=sys.stderr)
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    conn = sqlite3.connect(str(output_path))
    conn.executescript(schema_path.read_text())
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()

    size = output_path.stat().st_size
    print(f"Seed database created: {output_path} ({size:,} bytes)")
    return output_path


if __name__ == "__main__":
    create_seed()
