"""
MotionBuilderBridge loader.

Load inside MotionBuilder:
    exec(open('D:/LAFAN/MotionBuilderBridge/py/mb_bridge_plugin.py').read())

By default this starts the bridge immediately. Set MB_BRIDGE_AUTO_START=0 before
loading if you only want the functions imported.
"""

import os
import sys

_BRIDGE_ROOT = os.path.dirname(os.path.abspath(globals().get("__file__", r"D:/LAFAN/MotionBuilderBridge/py/mb_bridge_plugin.py")))
if _BRIDGE_ROOT not in sys.path:
    sys.path.insert(0, _BRIDGE_ROOT)

from mb_bridge_server import MBServer, get_bridge, start_bridge, stop_bridge

__plugin_name__ = "MotionBuilderBridge"
__plugin_version__ = "0.2.0"

print("[MBBridge] plugin v%s loaded" % __plugin_version__)

if os.environ.get("MB_BRIDGE_AUTO_START", "1") not in ("0", "false", "False", "no"):
    start_bridge()
else:
    print("[MBBridge] auto-start disabled; call start_bridge() when ready")
