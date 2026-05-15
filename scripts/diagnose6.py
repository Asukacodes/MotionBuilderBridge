import pyfbsdk as fb
import sys
import builtins

# Check if exec is available and what namespace it runs in
print("exec available:", hasattr(builtins, 'exec'))
print("eval available:", hasattr(builtins, 'eval'))

# Try exec with pyfbsdk in scope
try:
    exec('import pyfbsdk as fb; print(fb.FBScene().Name)', {'fb': fb})
    print("exec with fb scope: OK")
except Exception as e:
    print("exec failed:", e)

# Check sys.modules for pyfbsdk
print("pyfbsdk in sys.modules:", 'pyfbsdk' in sys.modules)
