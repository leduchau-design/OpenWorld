"""Dependency-free checks for repository layout."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
required = [
    "README.md", "LICENSE", "SECURITY.md", "CONTRIBUTING.md", "AGENTS.md",
    "docs/ARCHITECTURE.md", "docs/WORKSTREAMS.md",
    "research/RESEARCH-STATUS.md",
    "src/openworld_superkernel/memory_contracts.py",
]
missing = [name for name in required if not (root / name).is_file()]
if missing:
    print("FAIL: missing required files:", ", ".join(missing))
    sys.exit(1)
print("PASS: required project structure is present")
