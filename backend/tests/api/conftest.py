"""Conftest for tests/api — adds tests/api to sys.path so _helpers is importable."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
