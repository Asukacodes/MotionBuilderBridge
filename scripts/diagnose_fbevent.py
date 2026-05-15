import pyfbsdk as fb
sys = fb.FBSystem()
src = sys.OnUIIdle
print("FBEventSource methods:")
for m in dir(src):
    if not m.startswith('_'):
        print(" ", m)
