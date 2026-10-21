"""Isolated launcher. Usage: python -I engine/flood_cli.py status"""
from pathlib import Path
import sys

if not sys.flags.isolated:
    raise SystemExit("Use python -I engine/flood_cli.py; downloaded raster inputs are untrusted")

# Add only trusted checkout, never download directories or caller's working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.flood.run import main

if __name__ == "__main__":
    raise SystemExit(main())
