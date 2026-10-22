#!/usr/bin/env python
"""Export failed production runs as eval-case stubs into evals/inbox/. See evals/README.md.

    cd <repo> && backend/.venv/bin/python evals/export.py --since 7d
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
os.chdir(BACKEND)  # settings read backend/.env like the server
sys.path.insert(0, str(BACKEND))

from app.evals.export import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
