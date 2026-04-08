"""Kompatibler Worker-Einstiegspunkt."""

from dflowp_processruntime.engine.engine_worker import main, run_worker

__all__ = ["main", "run_worker"]


if __name__ == "__main__":
    main()
