"""
Start MotionBuilderBridge from inside MotionBuilder's Python environment.

Usage in MotionBuilder Python Shell:
    exec(open(r"D:/LAFAN/MotionBuilderBridge/scripts/start_bridge.py").read())
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(globals().get("__file__", r"D:/LAFAN/MotionBuilderBridge/scripts/start_bridge.py")))
ROOT = os.path.abspath(os.path.join(_HERE, ".."))
PY_DIR = os.path.join(ROOT, "py")

if PY_DIR not in sys.path:
    sys.path.insert(0, PY_DIR)

from mb_bridge_server import start_bridge

start_bridge()
