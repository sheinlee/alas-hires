"""Start an Alas instance with the high-resolution patch.

Usage (cwd = AzurLaneAutoScript, Alas's own python):
    toolkit\\python.exe <this file> [config name, default alas]

Same as alas.py's __main__ (AzurLaneAutoScript(name).loop()) after alas_hires.install().
"""
import os
import sys

sys.path.insert(0, os.getcwd())
sys.path.insert(1, os.path.dirname(os.path.abspath(__file__)))

import alas_hires  # noqa: E402

alas_hires.install()

from alas import AzurLaneAutoScript  # noqa: E402

AzurLaneAutoScript(sys.argv[1] if len(sys.argv) > 1 else 'alas').loop()
