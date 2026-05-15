"""
diagnose.py — Run this in Motion Builder Python Shell to check available modules.
"""
import sys

print("Python version:", sys.version)
print("Executable:", sys.executable)
print()

# Check key modules
modules = [
    "socket", "threading", "select", "json", "struct",
    "base64", "traceback", "io", "os", "time",
]

available = []
unavailable = []
for m in modules:
    try:
        __import__(m)
        available.append(m)
    except ImportError:
        unavailable.append(m)

print("Available:", available)
print("NOT available:", unavailable)
print()

# Check pyfbsdk
try:
    import pyfbsdk as fb
    print("pyfbsdk: OK")
    print("FBScene:", fb.FBScene)
    print("FBPlayerControl:", fb.FBPlayerControl)
except ImportError as e:
    print(f"pyfbsdk FAILED: {e}")
