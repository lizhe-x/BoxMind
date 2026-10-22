#!/usr/bin/env python
"""Run the BoxMind golden sets against the live model layer. See evals/README.md.

    cd <repo> && backend/.venv/bin/python evals/run.py routing extraction --model sonnet
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
os.chdir(BACKEND)  # settings read backend/.env; the claude provider keeps its work dir under backend/media
sys.path.insert(0, str(BACKEND))

from app.evals.harness import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
