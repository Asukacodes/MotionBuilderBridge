import pyfbsdk as fb

# FBEvaluateManager is the key — it's the equivalent of UE's IPythonScriptPlugin Exec
mgr = fb.FBEvaluateManager()
print("FBEvaluateManager methods:")
for m in dir(mgr):
    if not m.startswith('_'):
        print(" ", m)

# Check FBEvaluateInfo
info = fb.FBEvaluateInfo()
print()
print("FBEvaluateInfo methods:")
for m in dir(info):
    if not m.startswith('_'):
        print(" ", m)
