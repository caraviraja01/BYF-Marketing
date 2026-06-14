"""Initialise the database and create one demo cycle so the dashboard isn't empty.

Run:  python -m app.seed
"""
from __future__ import annotations

from .db import init_db
from .orchestrator import Orchestrator


def main() -> None:
    init_db()
    orch = Orchestrator()
    run_id = orch.run_cycle(topic="ELSS vs PPF: which tax-saver fits you?")
    print(f"Seeded demo cycle #{run_id}. Start the app with:  uvicorn app.main:app --reload")


if __name__ == "__main__":
    main()
