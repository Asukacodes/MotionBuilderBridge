import pyfbsdk as fb
print([m for m in dir(fb) if 'Exec' in m or 'Eval' in m or 'Run' in m or 'Script' in m])

# Try FBSystem Execute
sys = fb.FBSystem()
for attr in dir(sys):
    if 'Exec' in attr or 'Eval' in attr or 'Run' in attr:
        print("SYS:", attr)

# Try FBApplication Execute
for attr in dir(fb.FBApplication()):
    if 'Exec' in attr or 'Eval' in attr or 'Run' in attr:
        print("APP:", attr)

# Check if there's a global Execute
for attr in dir(fb):
    if 'Exec' in attr or 'Eval' in attr or 'Run' in attr:
        print("FB:", attr)
