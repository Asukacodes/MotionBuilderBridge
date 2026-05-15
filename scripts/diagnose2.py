"""
diagnose2.py — Paste into Motion Builder Python Shell.
Checks how to execute Python code in MB.
"""
import pyfbsdk as fb

print("=== FBApplication methods ===")
app = fb.FBApplication()
methods = [m for m in dir(app) if not m.startswith('_')]
for m in sorted(methods):
    print(" ", m)

print()
print("=== FBSystem methods ===")
sys = fb.FBSystem()
methods = [m for m in dir(sys) if not m.startswith('_')]
for m in sorted(methods):
    print(" ", m)
