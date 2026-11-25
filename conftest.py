"""pytest configuration: put the repo root on sys.path so ``import gui``,
``import machine`` and ``import dxfclean`` resolve when pytest runs from
anywhere in the tree."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
