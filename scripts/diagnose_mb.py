"""
diagnose_mb.py — Run this in Motion Builder Python Shell to check execution model.
"""
import sys
print("Python version:", sys.version)

# Check available modules
for m in ["socket", "threading", "select", "json", "struct", "base64"]:
    try:
        __import__(m)
        print(f"  {m}: OK")
    except ImportError:
        print(f"  {m}: MISSING")

print()

# Check pyfbsdk Evaluate method
try:
    import pyfbsdk as fb
    app = fb.FBApplication()
    print("FBApplication:", app)
    print("Has Evaluate:", hasattr(app, 'Evaluate'))

    # Try a simple Evaluate
    result = app.Evaluate('1 + 1')
    print("Evaluate('1+1'):", result)
    print("Evaluate type:", type(result))
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback; traceback.print_exc()
